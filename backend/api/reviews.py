from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.core.config import settings
from backend.core.database import SessionLocal, get_db
from backend.models import Review
from backend.schemas.review import ReviewDetailResponse, ReviewStatusResponse
from backend.services.github.client import writeback_comment

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/{review_id}/status", response_model=ReviewStatusResponse)
def get_review_status(review_id: int, db: Session = Depends(get_db)):
    review = (
        db.query(Review)
        .options(joinedload(Review.agent_timings))
        .filter(Review.id == review_id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.get("/{review_id}", response_model=ReviewDetailResponse)
def get_review_detail(review_id: int, db: Session = Depends(get_db)):
    review = (
        db.query(Review)
        .options(joinedload(Review.agent_timings))
        .filter(Review.id == review_id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.post("/{review_id}/retry-writeback")
async def retry_writeback(review_id: int):
    db = SessionLocal()
    try:
        review = (
            db.query(Review)
            .options(joinedload(Review.project))
            .filter(Review.id == review_id)
            .first()
        )
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found")

        if not review.comment_content:
            raise HTTPException(status_code=400, detail="No comment content to write back")

        project = review.project
        review_link = f"{settings.FRONTEND_URL}/reviews/{review_id}"
        full_comment = review.comment_content.replace("https://github.com", review_link)

        ok = await writeback_comment(
            project.repo_owner, project.repo_name,
            review.pr_number, project.encrypted_pat,
            full_comment,
        )
        if ok:
            review.writeback_error = None
            db.commit()
            return {"status": "ok", "message": "Comment posted successfully"}
        else:
            review.writeback_error = "Failed to post comment to GitHub"
            db.commit()
            raise HTTPException(status_code=502, detail="Failed to post comment to GitHub")
    finally:
        db.close()
