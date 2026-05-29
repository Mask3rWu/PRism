from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from backend.core.database import get_db
from backend.models import Review
from backend.schemas.review import ReviewDetailResponse, ReviewStatusResponse

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
