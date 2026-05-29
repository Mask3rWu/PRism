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
