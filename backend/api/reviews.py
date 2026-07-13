from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, joinedload

from backend.core.config import settings
from backend.core.database import SessionLocal, get_db
from backend.core.observability import find_traces_for_review
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
            review.pr_number,
            full_comment,
        )
        if ok:
            review.write_comment = True
            review.writeback_error = None
            db.commit()
            return {"status": "ok", "message": "Comment posted successfully"}
        else:
            review.writeback_error = "Failed to post comment to GitHub"
            db.commit()
            raise HTTPException(status_code=502, detail="Failed to post comment to GitHub")
    finally:
        db.close()


@router.get("/{review_id}/export")
def export_review(review_id: int, db: Session = Depends(get_db)):
    """Export a review snapshot as a downloadable JSON file.

    Includes the full review payload (summary, coordinator output, expert
    findings, final report, comment, timings) plus Langfuse trace references so
    the snapshot can be compared against a later re-run. Trace lookup failures
    degrade gracefully: the export still returns, with an empty trace list.
    """
    review = (
        db.query(Review)
        .options(joinedload(Review.agent_timings), joinedload(Review.project))
        .filter(Review.id == review_id)
        .first()
    )
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    project = review.project
    snapshot = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "review": {
            "id": review.id,
            "project_id": review.project_id,
            "pr_number": review.pr_number,
            "pr_title": review.pr_title,
            "status": review.status.value if hasattr(review.status, "value") else review.status,
            "run_index": review.run_index,
            "stage": review.stage,
            "error_message": review.error_message,
            "summary_result": review.summary_result,
            "coordinator_result": review.coordinator_result,
            "routing_plan": review.routing_plan,
            "expert_results": review.expert_results,
            "final_report": review.final_report,
            "comment_content": review.comment_content,
            "writeback_error": review.writeback_error,
            "started_at": review.started_at.isoformat() if review.started_at else None,
            "completed_at": review.completed_at.isoformat() if review.completed_at else None,
            "created_at": review.created_at.isoformat() if review.created_at else None,
            "agent_timings": [
                {
                    "agent_name": t.agent_name,
                    "start_time": t.start_time.isoformat() if t.start_time else None,
                    "end_time": t.end_time.isoformat() if t.end_time else None,
                    "model": t.model,
                    "latency_ms": t.latency_ms,
                    "status_code": t.status_code,
                    "retry_count": t.retry_count,
                    "retry_errors": t.retry_errors,
                }
                for t in (review.agent_timings or [])
            ],
        },
        "project": {
            "id": project.id if project else None,
            "repo_owner": project.repo_owner if project else None,
            "repo_name": project.repo_name if project else None,
            "description": project.description if project else None,
        },
        "langfuse": {
            "host": settings.LANGFUSE_HOST.rstrip("/") if settings.LANGFUSE_HOST else None,
            "environment": settings.LANGFUSE_ENVIRONMENT,
            "traces": find_traces_for_review(review.id),
        },
    }

    payload = json.dumps(snapshot, ensure_ascii=False, indent=2, default=str)
    filename = f"review_{review.id}_pr{review.pr_number}.json"
    return Response(
        content=payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
