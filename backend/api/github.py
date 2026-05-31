import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models import AppSettings
from backend.services.github.client import list_user_repos, validate_public_repo

router = APIRouter(prefix="/api/github", tags=["github"])


def _check_pat(db: Session) -> str:
    """Ensure a PAT is configured, raise 400 if not."""
    s = db.query(AppSettings).filter(AppSettings.id == 1).first()
    if not s or not s.encrypted_pat:
        raise HTTPException(status_code=400, detail="No PAT configured. Please set a PAT in Settings first.")
    return s.encrypted_pat


@router.get("/repos")
async def get_user_repos(db: Session = Depends(get_db)):
    _check_pat(db)
    repos = await list_user_repos()
    if repos is None:
        raise HTTPException(status_code=502, detail="Failed to fetch repositories from GitHub")

    def _derive_permission(perms: dict) -> str:
        if perms.get("admin"):
            return "Owner"
        if perms.get("maintain"):
            return "Maintainer"
        if perms.get("push"):
            return "Collaborator"
        return "Viewer"

    return [
        {
            "full_name": r["full_name"],
            "owner": r["owner"]["login"],
            "name": r["name"],
            "private": r["private"],
            "description": r.get("description"),
            "html_url": r["html_url"],
            "permission": _derive_permission(r.get("permissions", {})),
        }
        for r in repos
    ]


@router.post("/validate-repo")
async def validate_repo(body: dict, db: Session = Depends(get_db)):
    url = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Parse owner/repo from URL — supports:
    #   https://github.com/owner/repo
    #   github.com/owner/repo
    #   owner/repo
    pattern = r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
    m = re.match(pattern, url)
    if not m and re.match(r"^[^/]+/[^/]+$", url):
        parts = url.split("/")
        owner, repo = parts[0], parts[1]
    elif m:
        owner, repo = m.group(1), m.group(2)
    else:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL. Expected format: https://github.com/owner/repo")

    is_valid, error = await validate_public_repo(owner, repo)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    return {"owner": owner, "repo_name": repo, "is_public": True}
