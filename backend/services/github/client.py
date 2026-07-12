import asyncio
import base64
import time

import httpx

from backend.core.call_logger import log_api_call
from backend.core.database import SessionLocal
from backend.core.security import decrypt_token
from backend.models import AppSettings

GH_TIMEOUT = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
GH_RETRIES = 2
RETRYABLE_STATUS = {500, 502, 503, 504}


def _get_decrypted_pat() -> str:
    """Read the global PAT from app_settings, decrypt and return it."""
    db = SessionLocal()
    try:
        s = db.query(AppSettings).filter(AppSettings.id == 1).first()
        if s is None or not s.encrypted_pat:
            return ""
        return decrypt_token(s.encrypted_pat)
    finally:
        db.close()


def _gh_headers(accept: str = "application/vnd.github.v3+json") -> dict:
    """Build headers for a GitHub API request. Includes Authorization only if a PAT is configured."""
    headers = {"Accept": accept}
    pat = _get_decrypted_pat()
    if pat:
        headers["Authorization"] = f"Bearer {pat}"
    return headers


async def validate_pat_global(pat: str) -> tuple[bool, str | None]:
    """Validate a GitHub PAT by calling the /user endpoint and checking scopes."""
    url = "https://api.github.com/user"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers)
        except httpx.RequestError:
            return False, "Failed to connect to GitHub API"

    if response.status_code == 200:
        scopes = response.headers.get("X-OAuth-Scopes", "")
        scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
        if not scopes:
            return False, "PAT has no scopes. Generate a new token with repo scope."
        if "repo" not in scope_list:
            return False, f"PAT is missing the 'repo' scope. Current scopes: {', '.join(scope_list)}. Please generate a new token with repo access."
        return True, None
    if response.status_code in (401, 403):
        scopes = response.headers.get("X-OAuth-Scopes", "")
        if scopes:
            return False, f"PAT is valid but lacks permissions for this action. Current scopes: {scopes}"
        return False, "Invalid PAT or insufficient permissions"
    return False, f"GitHub API error: {response.status_code}"


async def validate_pat(owner: str, repo: str, pat: str) -> tuple[bool, str | None]:
    """Validate a GitHub PAT by fetching the target repository. Returns (is_valid, error_message)."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers)
        except httpx.RequestError:
            return False, "Failed to connect to GitHub API"

    if response.status_code == 200:
        scopes = response.headers.get("X-OAuth-Scopes", "")
        scope_list = [s.strip() for s in scopes.split(",") if s.strip()]
        if not scopes:
            return False, "PAT has no scopes. Generate a new token with repo scope."
        if "repo" not in scope_list:
            return False, f"PAT is missing the 'repo' scope. Current scopes: {', '.join(scope_list)}"
        return True, None
    if response.status_code == 404:
        return False, f"Repository {owner}/{repo} not found"
    if response.status_code in (401, 403):
        scopes = response.headers.get("X-OAuth-Scopes", "")
        if scopes:
            return False, f"PAT is valid but lacks permissions for this repository. Current scopes: {scopes}"
        return False, "Invalid PAT or insufficient permissions"
    return False, f"GitHub API error: {response.status_code}"


async def fetch_pulls(
    owner: str, repo: str,
    page: int = 1, per_page: int = 30,
    state: str = "open",
    sort: str = "created",
    direction: str = "desc",
) -> list[dict] | None:
    """Fetch pull requests from a GitHub repository. Works without PAT for public repos."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    params: dict[str, str | int] = {
        "state": state, "page": page, "per_page": per_page,
        "sort": sort, "direction": direction,
    }
    headers = _gh_headers()

    for attempt in range(GH_RETRIES + 1):
        t0 = time.time()
        async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                elapsed = int((time.time() - t0) * 1000)
                if response.status_code == 200:
                    log_api_call("github", url, latency_ms=elapsed,
                                 status_code=200, retry_count=attempt)
                    return response.json()
                if response.status_code in RETRYABLE_STATUS and attempt < GH_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log_api_call("github", url, latency_ms=elapsed,
                             status_code=response.status_code,
                             error_message=f"HTTP {response.status_code}",
                             retry_count=attempt)
            except httpx.RequestError as e:
                elapsed = int((time.time() - t0) * 1000)
                if attempt < GH_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log_api_call("github", url, latency_ms=elapsed,
                             error_message=str(e), retry_count=attempt)
    return None


async def search_pulls(
    owner: str, repo: str,
    page: int = 1, per_page: int = 30,
    state: str = "open",
    search: str = "",
    author: str = "",
    labels: list[str] | None = None,
    sort: str = "created",
    direction: str = "desc",
) -> dict | None:
    """Search pull requests using the GitHub Search API. Requires PAT (Search API auth mandatory)."""
    pat = _get_decrypted_pat()
    if not pat:
        return None

    qualifiers = [f"type:pr", f"repo:{owner}/{repo}", f"state:{state}"]
    if author:
        qualifiers.append(f"author:{author}")
    if labels:
        for label in labels:
            qualifiers.append(f'label:"{label}"')
    if search:
        qualifiers.append(f"{search} in:title")

    q = "+".join(qualifiers)

    sort_map = {"created": "created", "updated": "updated"}
    search_sort = sort_map.get(sort, "created")

    url = "https://api.github.com/search/issues"
    params: dict[str, str | int] = {
        "q": q, "sort": search_sort, "order": direction,
        "page": page, "per_page": per_page,
    }
    headers = _gh_headers()

    for attempt in range(GH_RETRIES + 1):
        t0 = time.time()
        async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                elapsed = int((time.time() - t0) * 1000)
                if response.status_code != 200:
                    if response.status_code in RETRYABLE_STATUS and attempt < GH_RETRIES:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    log_api_call("github", url, latency_ms=elapsed,
                                 status_code=response.status_code,
                                 error_message=f"HTTP {response.status_code}",
                                 retry_count=attempt)
                    return None
                data = response.json()
                log_api_call("github", url, latency_ms=elapsed,
                             status_code=200, retry_count=attempt)
                break
            except httpx.RequestError as e:
                elapsed = int((time.time() - t0) * 1000)
                if attempt < GH_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log_api_call("github", url, latency_ms=elapsed,
                             error_message=str(e), retry_count=attempt)
                return None

    items = data.get("items", [])
    if not items:
        return {"total_count": data.get("total_count", 0), "items": []}

    async def _fetch_branch(pr_number: int) -> tuple[int, str, str]:
        detail = await fetch_pr_detail(owner, repo, pr_number)
        if detail and detail.get("head") and detail.get("base"):
            return (pr_number, detail["head"]["ref"], detail["base"]["ref"])
        return (pr_number, "unknown", "unknown")

    branch_tasks = [_fetch_branch(item["number"]) for item in items]
    branch_results = await asyncio.gather(*branch_tasks)
    branch_map: dict[int, tuple[str, str]] = {
        num: (head, base) for num, head, base in branch_results
    }

    prs = []
    for item in items:
        pr_num = item["number"]
        head_ref, base_ref = branch_map.get(pr_num, ("unknown", "unknown"))
        is_merged = item.get("pull_request", {}).get("merged_at") if isinstance(item.get("pull_request"), dict) else None
        prs.append({
            "number": pr_num,
            "title": item["title"],
            "user": item.get("user", {"login": "unknown"}),
            "created_at": item["created_at"],
            "updated_at": item.get("updated_at"),
            "head": {"ref": head_ref},
            "base": {"ref": base_ref},
            "labels": item.get("labels", []),
            "state": item["state"],
            "draft": item.get("draft", False),
            "merged_at": is_merged,
        })

    return {"total_count": data["total_count"], "items": prs}


async def fetch_pr_detail(owner: str, repo: str, pr_number: int) -> dict | None:
    """Fetch a single PR's details (JSON) from GitHub. Works without PAT for public repos."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = _gh_headers()

    t0 = time.time()
    async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers)
            elapsed = int((time.time() - t0) * 1000)
            if response.status_code == 200:
                log_api_call("github", url, latency_ms=elapsed, status_code=200)
                return response.json()
            log_api_call("github", url, latency_ms=elapsed,
                         status_code=response.status_code,
                         error_message=f"HTTP {response.status_code}")
        except httpx.RequestError as e:
            elapsed = int((time.time() - t0) * 1000)
            log_api_call("github", url, latency_ms=elapsed, error_message=str(e))
    return None


async def fetch_pr_diff(owner: str, repo: str, pr_number: int) -> str | None:
    """Fetch a single PR's raw diff from GitHub. Works without PAT for public repos."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = _gh_headers("application/vnd.github.v3.diff")

    for attempt in range(GH_RETRIES + 1):
        t0 = time.time()
        async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
            try:
                response = await client.get(url, headers=headers)
                elapsed = int((time.time() - t0) * 1000)
                if response.status_code == 200:
                    log_api_call("github", url, latency_ms=elapsed,
                                 status_code=200, retry_count=attempt)
                    return response.text
                if response.status_code in RETRYABLE_STATUS and attempt < GH_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log_api_call("github", url, latency_ms=elapsed,
                             status_code=response.status_code,
                             error_message=f"HTTP {response.status_code}",
                             retry_count=attempt)
            except httpx.RequestError as e:
                elapsed = int((time.time() - t0) * 1000)
                if attempt < GH_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log_api_call("github", url, latency_ms=elapsed,
                             error_message=str(e), retry_count=attempt)
    return None


async def fetch_repository_file(owner: str, repo: str, path: str, ref: str) -> str | None:
    """Read one text file at a fixed Git ref. Used only by review-scoped tools."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = _gh_headers()
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
            response = await client.get(url, headers=headers, params={"ref": ref})
        elapsed = int((time.time() - t0) * 1000)
        if response.status_code != 200:
            log_api_call("github", url, latency_ms=elapsed, status_code=response.status_code,
                         error_message=f"HTTP {response.status_code}")
            return None
        data = response.json()
        if not isinstance(data, dict) or data.get("type") != "file":
            log_api_call("github", url, latency_ms=elapsed, status_code=200,
                         error_message="Path is not a file")
            return None
        encoded = data.get("content", "")
        if not isinstance(encoded, str):
            return None
        content = base64.b64decode(encoded.replace("\n", ""), validate=False)
        text = content.decode("utf-8", errors="replace")
        log_api_call("github", url, latency_ms=elapsed, status_code=200)
        return text
    except (httpx.RequestError, ValueError) as exc:
        elapsed = int((time.time() - t0) * 1000)
        log_api_call("github", url, latency_ms=elapsed, error_message=str(exc))
        return None


async def search_repository_code(
    owner: str,
    repo: str,
    query: str,
    *,
    path_glob: str = "",
    max_results: int = 10,
) -> list[dict] | None:
    """Search code in one repository and return paths only, never arbitrary URLs."""
    if not _get_decrypted_pat():
        return None
    sanitized = " ".join(query.split())
    if not sanitized or len(sanitized) > 200:
        return []
    qualifiers = [sanitized, f"repo:{owner}/{repo}"]
    if path_glob:
        qualifiers.append(f"path:{path_glob}")
    url = "https://api.github.com/search/code"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
            response = await client.get(
                url,
                headers=_gh_headers("application/vnd.github+json"),
                params={"q": " ".join(qualifiers), "per_page": max(1, min(max_results, 20))},
            )
        elapsed = int((time.time() - t0) * 1000)
        if response.status_code != 200:
            log_api_call("github", url, latency_ms=elapsed, status_code=response.status_code,
                         error_message=f"HTTP {response.status_code}")
            return None
        data = response.json()
        items = data.get("items", []) if isinstance(data, dict) else []
        results = [
            {"path": str(item.get("path", "")), "sha": str(item.get("sha", ""))}
            for item in items
            if isinstance(item, dict) and item.get("path")
        ]
        log_api_call("github", url, latency_ms=elapsed, status_code=200)
        return results
    except httpx.RequestError as exc:
        elapsed = int((time.time() - t0) * 1000)
        log_api_call("github", url, latency_ms=elapsed, error_message=str(exc))
        return None


async def writeback_comment(owner: str, repo: str, pr_number: int, body: str) -> bool:
    """Post a review comment to a GitHub PR. Requires PAT (write operation)."""
    pat = _get_decrypted_pat()
    if not pat:
        return False
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = _gh_headers()

    for attempt in range(GH_RETRIES + 1):
        t0 = time.time()
        async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
            try:
                response = await client.post(url, headers=headers, json={"body": body})
                elapsed = int((time.time() - t0) * 1000)
                if response.status_code == 201:
                    log_api_call("github", url, latency_ms=elapsed,
                                 status_code=201, retry_count=attempt)
                    return True
                # Only retry on server errors for POST (not client errors)
                if response.status_code in RETRYABLE_STATUS and attempt < GH_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log_api_call("github", url, latency_ms=elapsed,
                             status_code=response.status_code,
                             error_message=f"HTTP {response.status_code}",
                             retry_count=attempt)
            except httpx.RequestError as e:
                elapsed = int((time.time() - t0) * 1000)
                if attempt < GH_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue
                log_api_call("github", url, latency_ms=elapsed,
                             error_message=str(e), retry_count=attempt)
    return False


async def get_repo(owner: str, repo: str) -> dict | None:
    """Fetch repository info from GitHub. Works without PAT for public repos."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = _gh_headers()

    t0 = time.time()
    async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers)
            elapsed = int((time.time() - t0) * 1000)
            if response.status_code == 200:
                log_api_call("github", url, latency_ms=elapsed, status_code=200)
                return response.json()
            log_api_call("github", url, latency_ms=elapsed,
                         status_code=response.status_code,
                         error_message=f"HTTP {response.status_code}")
        except httpx.RequestError as e:
            elapsed = int((time.time() - t0) * 1000)
            log_api_call("github", url, latency_ms=elapsed, error_message=str(e))
    return None


async def list_user_repos(per_page: int = 100) -> list[dict] | None:
    """Fetch the authenticated user's repositories. Requires PAT (user identity)."""
    pat = _get_decrypted_pat()
    if not pat:
        return None
    url = "https://api.github.com/user/repos"
    params = {"type": "owner", "sort": "updated", "per_page": per_page}
    headers = _gh_headers()

    t0 = time.time()
    async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            elapsed = int((time.time() - t0) * 1000)
            if response.status_code == 200:
                log_api_call("github", url, latency_ms=elapsed, status_code=200)
                return response.json()
            log_api_call("github", url, latency_ms=elapsed,
                         status_code=response.status_code,
                         error_message=f"HTTP {response.status_code}")
        except httpx.RequestError as e:
            elapsed = int((time.time() - t0) * 1000)
            log_api_call("github", url, latency_ms=elapsed, error_message=str(e))
    return None


async def validate_public_repo(owner: str, repo: str) -> tuple[bool, str | None]:
    """Check that a repository exists and is public. Works without PAT for public repos.

    Note: without PAT, private repos return 404 (indistinguishable from nonexistent repos).
    """
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = _gh_headers()

    async with httpx.AsyncClient(timeout=GH_TIMEOUT) as client:
        try:
            response = await client.get(url, headers=headers)
        except httpx.RequestError:
            return False, "Failed to connect to GitHub API"

    if response.status_code == 200:
        data = response.json()
        if data.get("private", True):
            return False, "This is a private repository. Use 'Add Personal Repo' instead."
        return True, None
    if response.status_code == 404:
        return False, f"Repository {owner}/{repo} not found"
    return False, f"GitHub API error: {response.status_code}"
