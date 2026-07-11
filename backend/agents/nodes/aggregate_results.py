from collections import Counter
from datetime import datetime, timezone

from backend.agents.states import ReviewState
from backend.core.database import SessionLocal
from backend.models import AgentTiming, Review, ReviewStatus

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _normalize_line_number(value: object) -> int:
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return 0


def _normalize_finding(finding: dict, agent: str) -> dict:
    severity = str(finding.get("severity", "medium")).lower()
    if severity not in _SEVERITY_ORDER:
        severity = "medium"
    return {
        "id": "",
        "agent": agent,
        "severity": severity,
        "category": str(finding.get("category", "code_quality")),
        "title": str(finding.get("title") or finding.get("description") or finding.get("reason") or "Review finding"),
        "reason": str(finding.get("reason") or finding.get("description") or ""),
        "file": str(finding.get("file", "unknown")),
        "line_number": _normalize_line_number(finding.get("line_number", finding.get("line", 0))),
        "evidence": str(finding.get("evidence") or finding.get("code_segment") or ""),
        "fix_suggestion": str(finding.get("fix_suggestion") or finding.get("suggestion") or ""),
        "verification": str(finding.get("verification") or "Run the relevant regression tests."),
        "confidence": str(finding.get("confidence", "medium")),
    }


def build_final_report(routing_plan: dict, expert_results: list[dict]) -> dict:
    """Normalize and de-duplicate results from independently executed experts."""
    findings: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for expert_result in expert_results:
        agent = str(expert_result.get("agent", "unknown"))
        for raw_finding in expert_result.get("findings", []):
            if not isinstance(raw_finding, dict):
                continue
            finding = _normalize_finding(raw_finding, agent)
            key = (finding["file"].lower(), int(finding["line_number"]), finding["title"].lower())
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding)

    findings.sort(key=lambda finding: (_SEVERITY_ORDER[finding["severity"]], finding["file"], finding["line_number"]))
    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"finding-{index}"

    severity_counts = Counter(finding["severity"] for finding in findings)
    return {
        "routing_plan": routing_plan,
        "experts": expert_results,
        "summary": {"total_findings": len(findings), "by_severity": {severity: severity_counts.get(severity, 0) for severity in _SEVERITY_ORDER}},
        "findings": findings,
        "fix_suggestions": [
            {"finding_id": finding["id"], "file": finding["file"], "line_number": finding["line_number"], "suggestion": finding["fix_suggestion"], "verification": finding["verification"]}
            for finding in findings
            if finding["fix_suggestion"]
        ],
    }


async def aggregate_results_node(state: ReviewState) -> dict:
    review_id = state.get("review_id", 0)
    report = build_final_report(state.get("routing_plan") or {}, state.get("expert_results") or [])
    db = SessionLocal()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return {"final_report": report}

        review.stage = "aggregating_results"
        db.commit()
        timing = AgentTiming(review_id=review_id, agent_name="aggregate_results", start_time=datetime.now(timezone.utc))
        db.add(timing)
        db.commit()

        review.routing_plan = state.get("routing_plan") or {}
        review.expert_results = state.get("expert_results") or []
        review.final_report = report
        review.stage = "results_aggregated"
        timing.end_time = datetime.now(timezone.utc)
        db.commit()
        return {"final_report": report}
    except Exception as exc:
        db.rollback()
        review = db.query(Review).filter(Review.id == review_id).first()
        if review:
            review.status = ReviewStatus.failed
            review.stage = "aggregating_results"
            review.error_message = f"Result aggregation failed: {exc}"
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
