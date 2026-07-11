import json
from datetime import datetime, timezone

from backend.agents.routing import EXPERTS
from backend.agents.states import ReviewState
from backend.core.database import SessionLocal
from backend.core.llm_client import llm_call_json
from backend.models import AgentTiming, Review, ReviewStatus


def _build_prompt(agent: str, project_description: str, summary: dict, pr_diff: str) -> tuple[str, str]:
    definition = EXPERTS[agent]
    system_prompt = "You are a code review specialist. Always respond with valid JSON only."
    user_prompt = f"""You are the {definition.label} specialist. Review the PR change below.

Focus: {definition.focus}.

Project context:
{project_description}

PR summary:
{json.dumps(summary, ensure_ascii=False)}

PR diff:
{pr_diff}

Return JSON only in this exact shape:
{{
  \"findings\": [
    {{
      \"severity\": \"critical|high|medium|low\",
      \"category\": \"short category\",
      \"title\": \"short finding title\",
      \"reason\": \"why this matters\",
      \"file\": \"changed file path or unknown\",
      \"line_number\": 0,
      \"evidence\": \"relevant changed code or reference\",
      \"fix_suggestion\": \"concrete repair steps\",
      \"verification\": \"how to verify the repair\",
      \"confidence\": \"high|medium|low\"
    }}
  ]
}}

Report only evidence-backed findings. Use Chinese for all finding content."""
    return system_prompt, user_prompt


async def expert_review_node(state: ReviewState) -> dict:
    agent = state.get("active_expert", "")
    if agent not in EXPERTS:
        return {"expert_results": []}

    review_id = state.get("review_id", 0)
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return {"expert_results": []}

        review.stage = f"reviewing_{agent}"
        db.commit()
        timing = AgentTiming(review_id=review_id, agent_name=agent, start_time=datetime.now(timezone.utc))
        db.add(timing)
        db.commit()

        system_prompt, user_prompt = _build_prompt(
            agent,
            state.get("project_description", ""),
            state.get("summary_result") or {},
            state.get("pr_diff", ""),
        )
        raw_result, meta = await llm_call_json(system_prompt, user_prompt)
        findings = raw_result.get("findings", []) if isinstance(raw_result, dict) else []
        findings = [finding for finding in findings if isinstance(finding, dict)]

        timing.model = meta["model"]
        timing.latency_ms = meta["latency_ms"]
        timing.status_code = meta["status_code"]
        timing.retry_count = meta["retry_count"]
        timing.retry_errors = meta.get("retry_errors")
        timing.end_time = datetime.now(timezone.utc)
        db.commit()

        plan = state.get("routing_plan") or {}
        definition = EXPERTS[agent]
        return {"expert_results": [{
            "agent": agent,
            "label": definition.label,
            "focus": definition.focus,
            "routing_reasons": (plan.get("reasons") or {}).get(agent, []),
            "findings": findings,
        }]}
    except Exception as exc:
        db.rollback()
        review = db.query(Review).filter(Review.id == review_id).first()
        if review:
            review.status = ReviewStatus.failed
            review.stage = f"reviewing_{agent}"
            review.error_message = f"{agent} failed: {exc}"
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
