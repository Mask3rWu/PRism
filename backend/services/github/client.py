import httpx

from backend.core.security import decrypt_token


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
        return True, None
    if response.status_code == 404:
        return False, f"Repository {owner}/{repo} not found"
    if response.status_code in (401, 403):
        return False, "Invalid PAT or insufficient permissions"
    return False, f"GitHub API error: {response.status_code}"


async def fetch_pulls(owner: str, repo: str, encrypted_pat: str, page: int = 1, per_page: int = 30) -> list[dict] | None:
    """Fetch open pull requests from a GitHub repository."""
    pat = decrypt_token(encrypted_pat)
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


async def fetch_pr_detail(owner: str, repo: str, pr_number: int, encrypted_pat: str) -> dict | None:
    """Fetch a single PR's details (JSON) from GitHub."""
    pat = decrypt_token(encrypted_pat)
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


async def fetch_pr_diff(owner: str, repo: str, pr_number: int, encrypted_pat: str) -> str | None:
    """Fetch a single PR's raw diff from GitHub."""
    pat = decrypt_token(encrypted_pat)
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


async def writeback_comment(owner: str, repo: str, pr_number: int, encrypted_pat: str, body: str) -> bool:
    """Post a review comment to a GitHub PR issue. Returns True on success."""
    pat = decrypt_token(encrypted_pat)
    url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    headers = {"Authorization": f"Bearer {pat}", "Accept": "application/vnd.github.v3+json"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json={"body": body})
            return response.status_code == 201
        except httpx.RequestError:
            return False


async def get_repo(owner: str, repo: str, encrypted_pat: str) -> dict | None:
    """Fetch repository info from GitHub using a stored encrypted PAT."""
    pat = decrypt_token(encrypted_pat)
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
