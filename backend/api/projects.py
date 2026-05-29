from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import encrypt_token
from backend.models import Project, Review, ReviewStatus
from backend.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from backend.schemas.pull_request import PullRequestItem
from backend.schemas.review import ReviewResponse
from backend.seed import SEED_PR_LISTS
from backend.services.github.client import fetch_pr_detail, fetch_pulls, validate_pat
from backend.services.review.service import _run_review_background

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    is_valid, error = await validate_pat(body.repo_owner, body.repo_name, body.pat)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)

    encrypted_pat = encrypt_token(body.pat)
    project = Project(
        name=body.name,
        repo_owner=body.repo_owner,
        repo_name=body.repo_name,
        encrypted_pat=encrypted_pat,
        description=body.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: int, body: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if body.pat is not None:
        is_valid, error = await validate_pat(project.repo_owner, project.repo_name, body.pat)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        project.encrypted_pat = encrypt_token(body.pat)

    if body.description is not None:
        project.description = body.description

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


@router.get("/{project_id}/pulls", response_model=list[PullRequestItem])
async def list_pull_requests(
    project_id: int,
    page: int = 1,
    per_page: int = 30,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.is_seeded:
        all_prs = SEED_PR_LISTS[project.id] if project.id in SEED_PR_LISTS else []
        start = (page - 1) * per_page
        prs = all_prs[start : start + per_page]
    else:
        github_prs = await fetch_pulls(
            project.repo_owner, project.repo_name, project.encrypted_pat,
            page=page, per_page=per_page,
        )
        if github_prs is None:
            raise HTTPException(status_code=502, detail="Failed to fetch pull requests from GitHub")
        prs = github_prs

    pr_numbers = [pr["number"] for pr in prs]
    reviews = db.query(Review).filter(
        Review.project_id == project_id,
        Review.pr_number.in_(pr_numbers),
    ).all()
    review_status_map: dict[int, str] = {r.pr_number: r.status.value for r in reviews}

    result = []
    for pr in prs:
        result.append(PullRequestItem(
            pr_number=pr["number"],
            title=pr["title"],
            author=pr["user"]["login"] if pr.get("user") else "unknown",
            created_at=pr["created_at"],
            head_branch=pr["head"]["ref"],
            base_branch=pr["base"]["ref"],
            review_status=review_status_map.get(pr["number"], "none"),
        ))

    return result


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
        pr_number, project.encrypted_pat,
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
