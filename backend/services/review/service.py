import asyncio
from datetime import datetime, timezone

from backend.agents.review_graph import review_graph
from backend.agents.routing import DEFAULT_ENABLED_AGENTS
from backend.agents.states import ReviewState
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.models import AppSettings, Review, ReviewStatus
from backend.services.github.client import fetch_pr_diff, writeback_comment

_review_semaphore = asyncio.Semaphore(3)


async def _run_review_background(
    review_id: int,
    enabled_agents: list[str] | None = None,
    write_comment: bool = True,
) -> None:
    """Background task: wait for concurrency slot, fetch PR diff, run review graph."""
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return

        async with _review_semaphore:
            db.refresh(review)
            review.status = ReviewStatus.running
            review.stage = "fetching_diff"
            review.started_at = datetime.now(timezone.utc)
            db.commit()

            project = review.project
            diff = await fetch_pr_diff(
                project.repo_owner, project.repo_name,
                review.pr_number,
            )

            db.refresh(review)
            if diff is None:
                review.status = ReviewStatus.failed
                review.error_message = "Failed to fetch PR diff from GitHub"
                review.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

            review.diff_content = diff
            review.stage = "diff_fetched"
            review.write_comment = write_comment
            db.commit()

            state: ReviewState = {
                "project_description": project.description or "",
                "pr_diff": diff,
                "review_id": review_id,
                "enabled_agents": enabled_agents if enabled_agents is not None else DEFAULT_ENABLED_AGENTS,
                "write_comment": write_comment,
            }
            try:
                await review_graph.ainvoke(state)
            except Exception as e:
                db.refresh(review)
                if review.status != ReviewStatus.failed:
                    review.status = ReviewStatus.failed
                    review.error_message = str(e)
                    review.completed_at = datetime.now(timezone.utc)
                    db.commit()
                return

            db.refresh(review)
            review.status = ReviewStatus.succeeded
            review.completed_at = datetime.now(timezone.utc)
            db.commit()

            # Increment free review count if using default LLM
            app_settings = db.query(AppSettings).filter(AppSettings.id == 1).first()
            if app_settings and not app_settings.encrypted_llm_api_key:
                app_settings.review_count += 1
                db.commit()

            if write_comment and review.comment_content:
                review_link = f"{settings.FRONTEND_URL}/reviews/{review_id}"
                full_comment = review.comment_content.replace(
                    "https://github.com", review_link
                )
                ok = await writeback_comment(
                    project.repo_owner, project.repo_name,
                    review.pr_number,
                    full_comment,
                )
                if not ok:
                    db.refresh(review)
                    review.writeback_error = "Failed to post comment to GitHub"
                    db.commit()
    finally:
        db.close()
