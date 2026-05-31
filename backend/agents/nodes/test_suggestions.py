import json
from datetime import datetime, timezone

from backend.agents.states import ReviewState
from backend.core.database import SessionLocal
from backend.core.llm_client import llm_call_json
from backend.models import AgentTiming, Review, ReviewStatus


def _load_prompt(project_description: str, pr_summary: str, pr_diff: str) -> tuple[str, str]:
    import os

    prompt_path = os.path.join(os.path.dirname(__file__), "..", "prompts", "test_suggestions.md")
    with open(prompt_path) as f:
        template = f.read()

    system_prompt = "You are a code review assistant. Always respond with valid JSON only."
    user_prompt = (
        template.replace("{project_description}", project_description)
        .replace("{pr_summary}", pr_summary)
        .replace("{pr_diff}", pr_diff)
    )
    return system_prompt, user_prompt


async def test_suggestions_node(state: ReviewState) -> dict:
    review_id = state.get("review_id", 0)
    project_description = state["project_description"]
    pr_diff = state["pr_diff"]
    summary_result = state.get("summary_result") or {}

    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return {"test_result": None}

        review.stage = "suggesting_tests"
        db.commit()

        timing = AgentTiming(review_id=review_id, agent_name="test_suggestions", start_time=datetime.now(timezone.utc))
        db.add(timing)
        db.commit()

        pr_summary = json.dumps(summary_result, ensure_ascii=False)
        system_prompt, user_prompt = _load_prompt(project_description, pr_summary, pr_diff)
        result = await llm_call_json(system_prompt, user_prompt)

        db.refresh(review)
        review.test_result = result
        review.stage = "tests_suggested"
        db.commit()

        timing.end_time = datetime.now(timezone.utc)
        db.commit()

        return {"test_result": result}
    except Exception as e:
        db.rollback()
        review = db.query(Review).filter(Review.id == review_id).first()
        if review:
            review.status = ReviewStatus.failed
            review.stage = "suggesting_tests"
            review.error_message = f"Test suggestions agent failed: {e}"
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
