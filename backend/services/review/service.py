import asyncio
import logging
from datetime import datetime, timezone

from backend.agents.review_graph import review_graph
from backend.agents.routing import DEFAULT_ENABLED_AGENTS
from backend.agents.states import ReviewState
from backend.core.config import settings
from backend.core.database import SessionLocal
from backend.core.observability import flush_langfuse, observe_review, review_metadata, update_observation
from backend.models import AppSettings, Review, ReviewStatus
from backend.services.github.client import fetch_pr_diff, writeback_comment

logger = logging.getLogger(__name__)

_review_semaphore = asyncio.Semaphore(3)


async def _generate_eval_report_safe(review_id: int, run_index: int) -> None:
    """Generate the per-run eval report after a review finishes.

    Best-effort by construction: it flushes Langfuse, then calls the report
    generator, and swallows every error so the review hot path is never
    affected. The flush runs in a worker thread because the Langfuse SDK's
    ``flush()`` is blocking.
    """
    try:
        await asyncio.to_thread(flush_langfuse)
        from backend.services.eval_report import generate_eval_report
        await generate_eval_report(review_id, run_index)
    except Exception:
        logger.exception("Eval report generation failed for review %s", review_id)


async def _run_review_background(
    review_id: int,
    enabled_agents: list[str] | None = None,
    write_comment: bool = True,
    run_index: int = 0,
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
            metadata = review_metadata(
                review_id=review.id,
                project_id=project.id,
                repo_owner=project.repo_owner,
                repo_name=project.repo_name,
                pr_number=review.pr_number,
                enabled_agents=enabled_agents if enabled_agents is not None else DEFAULT_ENABLED_AGENTS,
                run_index=run_index,
            )
            with observe_review(metadata) as observation:
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
                    update_observation(
                        observation,
                        output={"status": "failed"},
                        metadata={**metadata, "status": "failed"},
                        level="ERROR",
                        status_message=review.error_message,
                    )
                    await _generate_eval_report_safe(review_id, run_index)
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
                    update_observation(
                        observation,
                        output={"status": "failed"},
                        metadata={**metadata, "status": "failed"},
                        level="ERROR",
                        status_message=str(e),
                    )
                    await _generate_eval_report_safe(review_id, run_index)
                    return

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

                db.refresh(review)
                review.status = ReviewStatus.succeeded
                review.completed_at = datetime.now(timezone.utc)
                db.commit()

                update_observation(
                    observation,
                    output={
                        "status": "succeeded",
                        "findings": (review.final_report or {}).get("summary", {}).get("total_findings", 0),
                        "writeback_succeeded": not bool(review.writeback_error),
                    },
                    metadata={
                        **metadata,
                        "status": "succeeded",
                        "findings": (review.final_report or {}).get("summary", {}).get("total_findings", 0),
                        "writeback_succeeded": not bool(review.writeback_error),
                    },
                )
                await _generate_eval_report_safe(review_id, run_index)
    finally:
        db.close()
