import json
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models import Project, Review, ReviewStatus
from backend.schemas.project import BatchDeleteRequest, PaginatedProjectsResponse, ProjectCreate, ProjectResponse, ProjectUpdate
from backend.schemas.pull_request import PaginatedPRResponse, PullRequestItem, ReviewStats
from backend.schemas.review import ReviewResponse
from backend.seed import SEED_PR_LISTS
from backend.services.github.client import fetch_pr_detail, fetch_pulls, search_pulls
from backend.services.review.service import _run_review_background

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    existing = db.query(Project).filter(
        Project.repo_owner == body.repo_owner,
        Project.repo_name == body.repo_name,
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Repository {body.repo_owner}/{body.repo_name} is already added as '{existing.name}'.",
        )

    project = Project(
        name=body.name,
        repo_owner=body.repo_owner,
        repo_name=body.repo_name,
        description=body.description,
        permission=body.permission,
        tags=json.dumps(body.tags),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=PaginatedProjectsResponse)
def list_projects(
    search: str = Query(default=""),
    tag: list[str] = Query(default=[]),
    favorite: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Project)

    if search:
        query = query.filter(Project.name.ilike(f"%{search}%"))

    if favorite:
        query = query.filter(Project.is_favorite == True)

    query = query.order_by(Project.is_favorite.desc(), Project.updated_at.desc())

    projects = query.all()

    if tag:
        projects = [p for p in projects if any(t in json.loads(p.tags or "[]") for t in tag)]

    total = len(projects)
    start = (page - 1) * per_page
    items = projects[start : start + per_page]

    return PaginatedProjectsResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    project.last_synced_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.name is not None:
        project.name = body.name
    if body.description is not None:
        project.description = body.description
    if body.tags is not None:
        project.tags = json.dumps(body.tags)
    if body.is_favorite is not None:
        project.is_favorite = body.is_favorite

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return None


@router.post("/batch-delete", status_code=204)
def batch_delete_projects(body: BatchDeleteRequest, db: Session = Depends(get_db)):
    if not body.ids:
        raise HTTPException(status_code=400, detail="No project IDs provided")

    db.query(Project).filter(Project.id.in_(body.ids)).delete(synchronize_session=False)
    db.commit()
    return None


def _pr_to_item(pr: dict, review_status_map: dict[int, str], review_id_map: dict[int, int] | None = None) -> PullRequestItem:
    labels_raw = pr.get("labels") or []
    pr_number = pr["number"]
    return PullRequestItem(
        pr_number=pr_number,
        title=pr["title"],
        author=pr["user"]["login"] if pr.get("user") else "unknown",
        created_at=pr["created_at"],
        updated_at=pr.get("updated_at"),
        head_branch=pr["head"]["ref"],
        base_branch=pr["base"]["ref"],
        review_status=review_status_map.get(pr_number, "none"),
        review_id=review_id_map.get(pr_number) if review_id_map else None,
        state=pr.get("state", "open"),
        labels=[{"name": lb["name"], "color": lb["color"]} for lb in labels_raw if lb.get("name")],
        is_draft=pr.get("draft", False),
        merged_at=pr.get("merged_at"),
    )


def _filter_by_pr_status(items: list[PullRequestItem], pr_status: list[str]) -> list[PullRequestItem]:
    if not pr_status:
        return items
    return [it for it in items if it.review_status in pr_status]


def _compute_review_stats(project: Project, db: Session) -> ReviewStats:
    """Compute review stats purely from local DB — counts distinct PRs by their latest review status."""

    subq = (
        db.query(Review.pr_number, func.max(Review.created_at).label("max_created"))
        .filter(Review.project_id == project.id)
        .group_by(Review.pr_number)
        .subquery()
    )
    latest_reviews = (
        db.query(Review)
        .join(
            subq,
            and_(
                Review.pr_number == subq.c.pr_number,
                Review.created_at == subq.c.max_created,
            ),
        )
        .filter(Review.project_id == project.id)
        .all()
    )

    succeeded = sum(1 for r in latest_reviews if r.status == ReviewStatus.succeeded)
    failed = sum(1 for r in latest_reviews if r.status == ReviewStatus.failed)
    in_progress = sum(1 for r in latest_reviews if r.status in (ReviewStatus.queued, ReviewStatus.running))

    return ReviewStats(
        total=succeeded + failed + in_progress,
        succeeded=succeeded,
        failed=failed,
        in_progress=in_progress,
    )


@router.get("/{project_id}/pulls", response_model=PaginatedPRResponse)
async def list_pull_requests(
    project_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    state: str = Query("open"),
    search: str = Query(""),
    author: str = Query(""),
    labels: list[str] = Query([]),
    pr_status: list[str] = Query([]),
    sort: str = Query("created"),
    direction: str = Query("desc"),
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.is_seeded:
        all_prs = SEED_PR_LISTS.get(project.id, [])
        # Server-side filtering for seed data
        filtered = [pr for pr in all_prs if pr.get("state", "open") == state]
        if search:
            filtered = [pr for pr in filtered if search.lower() in pr["title"].lower()]
        if author:
            filtered = [pr for pr in filtered if (pr.get("user") or {}).get("login", "").lower() == author.lower()]
        if labels:
            filtered = [
                pr for pr in filtered
                if any(lb["name"] in labels for lb in (pr.get("labels") or []))
            ]
        total = len(filtered)
        start = (page - 1) * per_page
        prs = filtered[start : start + per_page]
    else:
        has_text_filter = bool(search or author or labels)
        if has_text_filter:
            result = await search_pulls(
                project.repo_owner, project.repo_name,
                page=page, per_page=per_page,
                state=state, search=search, author=author,
                labels=labels if labels else None,
                sort=sort, direction=direction,
            )
            if result is None:
                raise HTTPException(status_code=502, detail="Failed to search pull requests from GitHub")
            total = result["total_count"]
            prs = result["items"]
        else:
            github_prs = await fetch_pulls(
                project.repo_owner, project.repo_name,
                page=page, per_page=per_page,
                state=state, sort=sort, direction=direction,
            )
            if github_prs is None:
                raise HTTPException(status_code=502, detail="Failed to fetch pull requests from GitHub")
            total = (page - 1) * per_page + len(github_prs)
            if len(github_prs) >= per_page:
                total = page * per_page + 1  # indicate more pages exist
            prs = github_prs

    pr_numbers = [pr["number"] for pr in prs]
    reviews = db.query(Review).filter(
        Review.project_id == project_id,
        Review.pr_number.in_(pr_numbers),
    ).all()
    review_status_map: dict[int, str] = {r.pr_number: r.status.value for r in reviews}
    review_id_map: dict[int, int] = {r.pr_number: r.id for r in reviews}

    items = [_pr_to_item(pr, review_status_map, review_id_map) for pr in prs]
    items = _filter_by_pr_status(items, pr_status)

    # Compute review stats (total across all PRs, not just current page/filter)
    stats = _compute_review_stats(project, db)

    return PaginatedPRResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        review_stats=stats,
    )


@router.get("/{project_id}/review-stats", response_model=ReviewStats)
async def get_review_stats(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _compute_review_stats(project, db)


@router.post("/{project_id}/pulls/{pr_number}/review", response_model=ReviewResponse, status_code=202)
async def trigger_review(
    project_id: int,
    pr_number: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    existing = db.query(Review).filter(
        Review.project_id == project_id,
        Review.pr_number == pr_number,
        Review.status.in_([ReviewStatus.queued, ReviewStatus.running]),
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A review is already in progress for this PR")

    pr_detail = await fetch_pr_detail(
        project.repo_owner, project.repo_name,
        pr_number,
    )
    if pr_detail is None:
        raise HTTPException(status_code=502, detail="Failed to fetch PR details from GitHub")

    review = Review(
        project_id=project_id,
        pr_number=pr_number,
        pr_title=pr_detail["title"],
        status=ReviewStatus.queued,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    background_tasks.add_task(_run_review_background, review.id)

    return review
