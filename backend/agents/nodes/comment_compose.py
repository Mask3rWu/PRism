import json
from datetime import datetime, timezone

from backend.agents.states import ReviewState
from backend.core.database import SessionLocal
from backend.core.llm_client import llm_call_json
from backend.models import AgentTiming, Review, ReviewStatus


def _load_prompt(
    project_description: str,
    pr_summary: str,
    review_report: str,
) -> tuple[str, str]:
    import os

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "comment_compose.md")
    with open(prompt_path, encoding="utf-8") as f:
        template = f.read()

    system_prompt = "You are a code review assistant. Always respond with valid JSON only."
    user_prompt = (
        template.replace("{project_description}", project_description)
        .replace("{pr_summary}", pr_summary)
        .replace("{review_report}", review_report)
    )
    return system_prompt, user_prompt


async def comment_compose_node(state: ReviewState) -> dict:
    review_id = state.get("review_id", 0)
    project_description = state["project_description"]
    pr_diff = state["pr_diff"]
    summary_result = state.get("summary_result") or {}
    final_report = state.get("final_report") or {}

    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return {"comment_result": None}

        review.stage = "composing_comment"
        db.commit()

        timing = AgentTiming(
            review_id=review_id,
            agent_name="comment_compose",
            start_time=datetime.now(timezone.utc),
        )
        db.add(timing)
        db.commit()

        pr_summary = json.dumps(summary_result, ensure_ascii=False)
        review_report = json.dumps(final_report, ensure_ascii=False)

        system_prompt, user_prompt = _load_prompt(
            project_description, pr_summary, review_report
        )
        result, meta = await llm_call_json(system_prompt, user_prompt)

        comment_content = result.get("comment", "") if isinstance(result, dict) else ""

        db.refresh(review)
        review.comment_content = comment_content
        review.stage = "comment_composed"
        db.commit()

        timing.model = meta["model"]
        timing.latency_ms = meta["latency_ms"]
        timing.status_code = meta["status_code"]
        timing.retry_count = meta["retry_count"]
        timing.retry_errors = meta.get("retry_errors")
        timing.end_time = datetime.now(timezone.utc)
        db.commit()

        return {"comment_result": result}
    except Exception as e:
        db.rollback()
        review = db.query(Review).filter(Review.id == review_id).first()
        if review:
            review.status = ReviewStatus.failed
            review.stage = "composing_comment"
            review.error_message = f"Comment compose agent failed: {e}"
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
