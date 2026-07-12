"""Coordinator node: ReAct research, semantic routing, and evidence packaging."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any

from backend.agents.routing import DEFAULT_ENABLED_AGENTS, EXPERTS
from backend.agents.states import ReviewState
from backend.agents.tools.change_inventory import (
    build_change_inventory,
    compact_inventory,
    has_docs_changes,
    is_docs_only,
)
from backend.agents.tools.context import ReviewContextTools
from backend.core.database import SessionLocal
from backend.core.llm_config import get_llm_config
from backend.core.llm_client import llm_call_json
from backend.core.observability import langchain_callbacks
from backend.models import AgentTiming, Review, ReviewStatus
from backend.schemas.coordinator import (
    CommonContext,
    CoordinatorResult,
    CoordinatorRoutingPlan,
    Evidence,
    ExpertContext,
    PrSummary,
)

REACT_RECURSION_LIMIT = 20
REACT_TIMEOUT_SECONDS = 120
COORDINATOR_FINALIZER_MAX_TOKENS = 4096
FINALIZER_MAX_TOOL_RESULTS = 8
FINALIZER_MAX_TOOL_RESULT_CHARS = 4_000
FINALIZER_MAX_TOOL_CONTEXT_CHARS = 24_000
FINALIZER_MAX_PROJECT_CONTEXT_CHARS = 4_000
_CORE_FALLBACK_AGENTS = ("issue_detection", "test_suggestions", "risk_analysis")
_FALLBACK_ONLY_AGENTS = {"general_review"}


def _fallback_agents(enabled_agents: list[str], inventory: dict) -> list[str]:
    if is_docs_only(inventory) and "docs_review" in enabled_agents:
        return ["docs_review"]
    if "general_review" in enabled_agents:
        return ["general_review"]
    selected = [agent for agent in _CORE_FALLBACK_AGENTS if agent in enabled_agents]
    return selected or enabled_agents[:1]


def build_fallback_coordinator_result(
    project_description: str,
    inventory: dict,
    enabled_agents: list[str],
    reason: str,
) -> CoordinatorResult:
    """Produce an evidence-labelled safe fallback when tool-capable routing is unavailable."""
    files = [str(item.get("path", "")) for item in inventory["files"] if item.get("path")]
    selected = _fallback_agents(enabled_agents, inventory) if files else []
    evidence = [
        Evidence(
            source_type="pr_diff",
            path=path,
            ref="pr_diff",
            fact="该文件包含在本次 PR 的变更中。",
        )
        for path in files[:100]
    ]
    contexts = {
        agent: ExpertContext(
            relevant_changes=["Coordinator 未能完成工具调研；请基于已提供的 PR diff 独立审查。"],
            relevant_files=files,
            evidence=evidence,
            unresolved_context=[reason],
        )
        for agent in selected
    }
    return CoordinatorResult(
        pr_summary=PrSummary(
            overview=f"该 PR 涉及 {len(files)} 个文件的变更；详细语义摘要在 Coordinator 回退时不可用。",
            scope=files[:20],
            key_changes=[f"变更统计：新增 {inventory['total_additions']} 行，删除 {inventory['total_deletions']} 行。"],
        ),
        common_context=CommonContext(
            change_intent="Coordinator 未能完成工具调研，以下内容仅来自 PR diff 的确定性文件清单。",
            affected_components=files[:50],
            changed_files=files,
            known_unknowns=[reason],
            evidence=evidence,
        ),
        routing_plan=CoordinatorRoutingPlan(
            selected_agents=selected,
            reasons={agent: ["Coordinator 回退策略：确保变更不会被静默跳过。"] for agent in selected},
            fallback_used=True,
            fallback_reason=reason,
        ),
        expert_contexts=contexts,
    )


def _extract_message_text(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])
    if not messages:
        raise ValueError("Coordinator returned no messages")
    content = getattr(messages[-1], "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content)


def _parse_result(text: str) -> CoordinatorResult:
    payload = text.strip()
    if payload.startswith("<think>"):
        end = payload.find("</think>")
        if end != -1:
            payload = payload[end + len("</think>"):].strip()
    if payload.startswith("```"):
        lines = payload.splitlines()
        payload = "\n".join(lines[1:-1] if lines and lines[-1].startswith("```") else lines[1:])
    return CoordinatorResult.model_validate(json.loads(payload))


def _normalise_result(
    result: CoordinatorResult,
    enabled_agents: list[str],
    inventory: dict,
    project_description: str,
    pr_diff: str,
) -> CoordinatorResult:
    allowed = set(enabled_agents)
    normal_routable = allowed - _FALLBACK_ONLY_AGENTS
    selected = list(dict.fromkeys(
        agent for agent in result.routing_plan.selected_agents if agent in normal_routable and agent in EXPERTS
    ))
    files = [str(item.get("path", "")) for item in inventory.get("files", []) if item.get("path")]

    if has_docs_changes(inventory) and "docs_review" in allowed and "docs_review" not in selected:
        selected.append("docs_review")
        result.routing_plan.reasons.setdefault(
            "docs_review", ["检测到文档变更，需核对其与代码、API 或配置的一致性。"]
        )

    if files and not selected:
        fallback = build_fallback_coordinator_result(
            project_description, inventory, enabled_agents, "Coordinator 未选择任何可用专家，已启用安全回退。"
        )
        return fallback

    result.routing_plan.selected_agents = selected
    result.routing_plan.reasons = {
        agent: reasons
        for agent, reasons in result.routing_plan.reasons.items()
        if agent in selected
    }
    result.routing_plan.unselected_agents = {
        agent: reasons
        for agent, reasons in result.routing_plan.unselected_agents.items()
        if agent in normal_routable and agent in EXPERTS and agent not in selected
    }
    result.common_context.changed_files = files

    # Every dispatched expert receives at least a factual changed-file baseline.
    generic_evidence = [
        Evidence(source_type="pr_diff", path=path, ref="pr_diff", fact="该文件包含在本次 PR 的变更中。")
        for path in files[:100]
    ]
    if not result.common_context.evidence:
        result.common_context.evidence = generic_evidence
    result.expert_contexts = {
        agent: context
        for agent, context in result.expert_contexts.items()
        if agent in selected
    }
    for agent in selected:
        if agent not in result.expert_contexts:
            result.expert_contexts[agent] = ExpertContext(
                relevant_files=files,
                evidence=generic_evidence,
                unresolved_context=["Coordinator 未返回该专家的定制证据包。"],
            )

    assigned_files = {
        path
        for context in result.expert_contexts.values()
        for path in context.relevant_files
    }
    missing_files = [path for path in files if path not in assigned_files]
    if missing_files and selected:
        coverage_agent = "issue_detection" if "issue_detection" in selected else selected[0]
        coverage_context = result.expert_contexts[coverage_agent]
        coverage_context.relevant_files = list(dict.fromkeys(coverage_context.relevant_files + missing_files))
        coverage_context.evidence.extend(
            evidence for evidence in generic_evidence if evidence.path in missing_files
        )
        coverage_context.unresolved_context.append(
            "以下文件由覆盖保障加入；Coordinator 未能建立更细的定制上下文。"
        )
    return result


def _coordinator_prompt() -> str:
    return """You are the PRism research coordinator. Use only the read-only tools to collect
facts needed to understand the PR and prepare later specialist review.

Collect evidence about changed behavior, relevant files, callers, configuration, and tests when
needed. When documentation changes, collect the code, API, commands, or configuration that the
documentation describes so a specialist can check consistency. Do not determine whether a defect, vulnerability, or risk exists. Do not propose fixes or
severity. Do not produce the final PR summary, routing plan, or JSON: a separate finalizer uses
the tool results for those tasks.

Do not repeat tool results in your final response. Once you have enough evidence, finish with a
short plain-text completion message."""


def _build_finalizer_tool_results(messages: list[Any]) -> list[dict[str, str]]:
    """Pass bounded tool evidence, never model messages or reasoning, to the finalizer."""
    results: list[dict[str, str]] = []
    remaining = FINALIZER_MAX_TOOL_CONTEXT_CHARS
    for message in messages:
        if type(message).__name__ != "ToolMessage" or remaining <= 0:
            continue
        content = str(getattr(message, "content", ""))
        content = content[:min(FINALIZER_MAX_TOOL_RESULT_CHARS, remaining)]
        results.append({"tool": str(getattr(message, "name", "context_tool")), "result": content})
        remaining -= len(content)
        if len(results) >= FINALIZER_MAX_TOOL_RESULTS:
            break
    return results


def _build_finalizer_prompt(
    project_description: str,
    inventory: dict,
    enabled_agents: list[str],
    tool_results: list[dict[str, str]],
) -> str:
    expert_catalog = [
        {"key": definition.key, "label": definition.label, "focus": definition.focus}
        for key, definition in EXPERTS.items()
        if key in enabled_agents and key not in _FALLBACK_ONLY_AGENTS
    ]
    return f"""You are the final structured-output stage of a PR review coordinator.
Use only the supplied deterministic inventory and tool results as factual evidence. Do not decide whether defects, vulnerabilities, or risks exist; specialists do that later.
All JSON values must be Simplified Chinese except JSON keys, paths, symbols, and technical identifiers.

Return JSON only in this exact shape:
{{
  "pr_summary": {{"overview": "...", "scope": ["..."], "key_changes": ["..."]}},
  "common_context": {{"change_intent": "...", "affected_components": ["..."], "behavior_before_after": ["..."], "changed_files": ["..."], "known_unknowns": ["..."], "evidence": [{{"source_type": "pr_diff|repository_file|pr_metadata|project_description", "path": "...", "ref": "...", "start_line": 0, "end_line": 0, "excerpt": "...", "fact": "..."}}]}},
  "routing_plan": {{"selected_agents": ["..."], "reasons": {{"agent": ["..."]}}, "unselected_agents": {{"agent": ["..."]}}}},
  "expert_contexts": {{"agent": {{"relevant_changes": ["..."], "relevant_files": ["..."], "related_symbols": ["..."], "related_tests": ["..."], "evidence": [], "unresolved_context": ["..."]}}}}
}}

Select agents only from the enabled expert catalog. Select Documentation Review whenever changed documentation needs consistency checks. `general_review` is reserved for deterministic fallback and must not be selected here.
Expert catalog: {json.dumps(expert_catalog, ensure_ascii=False)}
Enabled routable agents: {json.dumps([agent for agent in enabled_agents if agent not in _FALLBACK_ONLY_AGENTS], ensure_ascii=False)}
Project context: {project_description[:FINALIZER_MAX_PROJECT_CONTEXT_CHARS]}
Initial inventory: {json.dumps(compact_inventory(inventory), ensure_ascii=False)}
Tool results: {json.dumps(tool_results, ensure_ascii=False)}"""


async def _run_react_coordinator(
    tools: ReviewContextTools,
    project_description: str,
    inventory: dict,
    enabled_agents: list[str],
) -> CoordinatorResult:
    """Create the nested LangGraph ReAct agent only when this node actually runs."""
    try:
        from langchain_openai import ChatOpenAI
        from langgraph.prebuilt import create_react_agent
    except ImportError as exc:
        raise RuntimeError("Coordinator requires langchain-openai and LangGraph ReAct dependencies") from exc

    config = get_llm_config()
    model = ChatOpenAI(
        model=config["model"],
        api_key=config["api_key"],
        base_url=config["endpoint"],
        temperature=0.2,
    )
    agent = create_react_agent(model, tools.as_langchain_tools(), prompt=_coordinator_prompt())
    initial_input = {
        "project_description": project_description,
        "enabled_agents": enabled_agents,
        "change_inventory": compact_inventory(inventory),
        "instruction": "请收集足够的可追溯事实后完成协调结果。",
    }
    react_config: dict[str, Any] = {"recursion_limit": REACT_RECURSION_LIMIT}
    callbacks = langchain_callbacks()
    if callbacks:
        react_config["callbacks"] = callbacks
    response = await asyncio.wait_for(
        agent.ainvoke(
            {"messages": [{"role": "user", "content": json.dumps(initial_input, ensure_ascii=False)}]},
            react_config,
        ),
        timeout=REACT_TIMEOUT_SECONDS,
    )
    if not tools.tool_summary:
        raise ValueError("Coordinator completed without using any context tool")

    tool_results = _build_finalizer_tool_results(response.get("messages", []))
    finalizer_prompt = _build_finalizer_prompt(
        project_description, inventory, enabled_agents, tool_results
    )
    final_data, _ = await llm_call_json(
        "You produce only a valid JSON object matching the requested coordinator schema.",
        finalizer_prompt,
        response_format={"type": "json_object"},
        max_tokens=COORDINATOR_FINALIZER_MAX_TOKENS,
    )
    return CoordinatorResult.model_validate(final_data)


async def coordinator_node(state: ReviewState) -> dict:
    """Run the Coordinator subgraph and persist its public, structured output."""
    review_id = state.get("review_id", 0)
    project_description = state.get("project_description", "")
    pr_diff = state.get("pr_diff", "")
    enabled_agents = state.get("enabled_agents") or list(DEFAULT_ENABLED_AGENTS)
    inventory = build_change_inventory(pr_diff)
    db = SessionLocal()
    timing: AgentTiming | None = None
    started = time.monotonic()
    try:
        review = db.query(Review).filter(Review.id == review_id).first()
        if review is None:
            return {"summary_result": None, "selected_agents": []}

        review.stage = "coordinating_review"
        timing = AgentTiming(review_id=review_id, agent_name="coordinator", start_time=datetime.now(timezone.utc))
        db.add(timing)
        db.commit()

        project = review.project
        tools = ReviewContextTools(
            owner=project.repo_owner,
            repo=project.repo_name,
            pr_number=review.pr_number,
            project_description=project_description,
            pr_diff=pr_diff,
        )
        fallback_reason = ""
        try:
            result = await _run_react_coordinator(tools, project_description, inventory, enabled_agents)
            result = _normalise_result(
                result, enabled_agents, inventory, project_description, pr_diff
            )
        except Exception as exc:
            fallback_reason = f"Coordinator ReAct 不可用：{type(exc).__name__}"
            result = build_fallback_coordinator_result(project_description, inventory, enabled_agents, fallback_reason)

        data = result.model_dump(mode="json")
        review.summary_result = data["pr_summary"]
        review.routing_plan = data["routing_plan"]
        review.coordinator_result = data
        review.stage = "coordinated"
        timing.model = get_llm_config().get("model") if not fallback_reason else None
        timing.latency_ms = int((time.monotonic() - started) * 1000)
        timing.retry_errors = [{"error": fallback_reason}] if fallback_reason else None
        timing.end_time = datetime.now(timezone.utc)
        db.commit()
        return {
            "summary_result": data["pr_summary"],
            "coordinator_result": data,
            "common_context": data["common_context"],
            "routing_plan": data["routing_plan"],
            "selected_agents": data["routing_plan"]["selected_agents"],
            "expert_contexts": data["expert_contexts"],
        }
    except Exception:
        db.rollback()
        review = db.query(Review).filter(Review.id == review_id).first()
        if review:
            review.status = ReviewStatus.failed
            review.stage = "coordinating_review"
            review.error_message = "Coordinator persistence failed"
            review.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()
