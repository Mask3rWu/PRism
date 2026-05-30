import httpx

from backend.core.database import SessionLocal
from backend.core.security import decrypt_token
from backend.models import AppSettings


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


async def validate_pat_global(pat: str) -> tuple[bool, str | None]:
    """Validate a GitHub PAT by calling the /user endpoint and checking scopes."""
    url = "https://api.github.com/user"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
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

    async with httpx.AsyncClient() as client:
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


async def fetch_pulls(owner: str, repo: str, page: int = 1, per_page: int = 30) -> list[dict] | None:
    """Fetch open pull requests from a GitHub repository using the global PAT."""
    pat = _get_decrypted_pat()
    if not pat:
        return None
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    params: dict[str, str | int] = {"state": "open", "page": page, "per_page": per_page}
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    return None


async def fetch_pr_detail(owner: str, repo: str, pr_number: int) -> dict | None:
    """Fetch a single PR's details (JSON) from GitHub using the global PAT."""
    pat = _get_decrypted_pat()
    if not pat:
        return None
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    return None


async def fetch_pr_diff(owner: str, repo: str, pr_number: int) -> str | None:
    """Fetch a single PR's raw diff from GitHub using the global PAT."""
    pat = _get_decrypted_pat()
    if not pat:
        return None
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3.diff"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.text
        except httpx.RequestError:
            pass
    return None


async def writeback_comment(owner: str, repo: str, pr_number: int, body: str) -> bool:
    """Post a review comment to a GitHub PR issue using the global PAT. Returns True on success."""
    pat = _get_decrypted_pat()
    if not pat:
        return False
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json={"body": body})
            return response.status_code == 201
        except httpx.RequestError:
            return False


async def get_repo(owner: str, repo: str) -> dict | None:
    """Fetch repository info from GitHub using the global PAT."""
    pat = _get_decrypted_pat()
    if not pat:
        return None
    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    return None


async def list_user_repos(per_page: int = 100) -> list[dict] | None:
    """Fetch the authenticated user's repositories from GitHub."""
    pat = _get_decrypted_pat()
    if not pat:
        return None
    url = "https://api.github.com/user/repos"
    params = {"type": "owner", "sort": "updated", "per_page": per_page}
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
        except httpx.RequestError:
            pass
    return None


async def validate_public_repo(owner: str, repo: str) -> tuple[bool, str | None]:
    """Check that a repository exists and is public. Returns (is_valid, error_message)."""
    pat = _get_decrypted_pat()
    if not pat:
        return False, "No PAT configured. Please set a PAT in Settings first."

    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
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
