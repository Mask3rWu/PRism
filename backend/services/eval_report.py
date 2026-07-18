"""Generate a per-run evaluation report for a PR review.

After each review run (success or failure), the review service calls
:func:`generate_eval_report`, which:

1. Fetches the current review snapshot via the real export endpoint
   ``GET /api/reviews/{id}/export`` so the JSON on disk is identical to what a
   human would download.
2. Picks the Langfuse trace whose ``run_index`` matches this run and pulls its
   observations to quantify cost / tokens / cache / latency / reliability.
3. Reads previously written ``run_{M}_ouput.json`` files in the same directory
   so cross-run findings comparison self-improves over time.
4. Renders ``run_{N}.md`` and writes ``run_{N}_ouput.json`` into
   ``eval/review_{pr_number}_{review_id}/``.

Everything is best-effort: a missing Langfuse or unreachable backend degrades to
a partial report and never raises into the review hot path.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from backend.agents.routing import EXPERTS
from backend.core.config import settings
from backend.core.observability import (
    fetch_observations,
    fetch_traces_for_review_with_runindex,
)

logger = logging.getLogger(__name__)

# Severity ordering mirrors aggregate_results._SEVERITY_ORDER.
_SEVERITY_ORDER = ("critical", "high", "medium", "low")
# LLM call retry budget, mirrored from llm_client.MAX_RETRIES.
_MAX_RETRIES = 3

# Generation observation names emitted by the two tracing paths.
_GEN_NAME_DIRECT = "llm.chat.completions"
_GEN_NAME_REACT = "ChatOpenAI"


# --------------------------------------------------------------------------- #
# Token / usage extraction
# --------------------------------------------------------------------------- #
def _extract_tokens(obs: dict[str, Any]) -> dict[str, int]:
    """Pull cache hit / miss / input / output tokens from an observation.

    Two tracing paths use different field schemas for the same semantics, which
    is the "easy-to-confuse" field difference flagged in the manual trace reports.
    We distinguish by key presence rather than mashing aliases together:

    * Schema A -- DeepSeek-native (direct ``llm_client`` calls): ``prompt_tokens``
      is the FULL input; ``prompt_cache_hit_tokens`` / ``prompt_cache_miss_tokens``
      split it (hit + miss == full).
    * Schema B -- OpenAI-standard (ReAct ``ChatOpenAI`` via LangChain callback):
      ``input`` is the NON-cached new input; ``input_cache_read`` is the cache hit;
      full input = input + input_cache_read.
    """
    ud = obs.get("usageDetails") or {}

    if "prompt_cache_hit_tokens" in ud or "prompt_cache_miss_tokens" in ud:
        hit = int(ud.get("prompt_cache_hit_tokens") or 0)
        miss = int(ud.get("prompt_cache_miss_tokens") or 0)
        full = int(ud.get("prompt_tokens") or obs.get("promptTokens") or 0) or (hit + miss)
        output = int(ud.get("completion_tokens") or obs.get("completionTokens") or 0)
        return {"hit": hit, "miss": miss, "input": full, "output": output}

    if "input_cache_read" in ud:
        hit = int(ud.get("input_cache_read") or 0)
        miss = int(ud.get("input") or 0)  # non-cached new input
        output = int(ud.get("output") or obs.get("completionTokens") or 0)
        return {"hit": hit, "miss": miss, "input": hit + miss, "output": output}

    # Fallback: canonical top-level fields (no cache breakdown available).
    full = int(obs.get("promptTokens") or ud.get("prompt_tokens") or ud.get("input_tokens") or ud.get("input") or 0)
    output = int(obs.get("completionTokens") or ud.get("completion_tokens") or ud.get("output_tokens") or ud.get("output") or 0)
    return {"hit": 0, "miss": full, "input": full, "output": output}


def _obs_cost(obs: dict[str, Any]) -> tuple[float, bool]:
    """Return (cost, is_estimated).

    Preference order: our uploaded ``costDetails.total_cost`` (direct calls),
    then Langfuse's own ``calculatedTotalCost`` (covers ReAct when model pricing
    is configured), then a local estimate from token usage so a number still
    appears when neither is present.
    """
    cost_details = obs.get("costDetails") or {}
    total = cost_details.get("total_cost") or cost_details.get("totalCost")
    if isinstance(total, (int, float)) and total:
        return float(total), False

    calc = obs.get("calculatedTotalCost")
    if isinstance(calc, (int, float)) and calc:
        return float(calc), False

    # Last resort: estimate from token usage with the same pricing as
    # observability.calculate_cost_details so numbers stay comparable.
    tokens = _extract_tokens(obs)
    hit_price = settings.LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS
    miss_price = settings.LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS
    in_price = settings.LANGFUSE_INPUT_COST_PER_1M_TOKENS
    out_price = settings.LANGFUSE_OUTPUT_COST_PER_1M_TOKENS

    cache_configured = hit_price != 0 or miss_price != 0
    if cache_configured and (tokens["hit"] or tokens["miss"]):
        input_cost = (tokens["hit"] * hit_price + tokens["miss"] * miss_price) / 1_000_000
    else:
        input_cost = tokens["input"] * in_price / 1_000_000
    output_cost = tokens["output"] * out_price / 1_000_000
    total_cost = input_cost + output_cost
    return (total_cost, True) if total_cost else (0.0, True)


def _parse_time(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# Observation classification
# --------------------------------------------------------------------------- #
@dataclass
class GenRecord:
    """One LLM generation mapped to its pipeline stage."""

    stage: str            # react / finalizer / warmup / <expert key> / comment
    hit: int = 0
    miss: int = 0
    input: int = 0
    output: int = 0
    cost: float = 0.0
    is_estimated_cost: bool = False
    max_tokens: int | None = None
    retry_count: int = 0
    truncated: bool = False
    completion_ratio: float = 0.0
    start: datetime | None = None
    end: datetime | None = None
    latency_s: float = 0.0
    model: str = ""


def _classify_observations(observations: list[dict[str, Any]]) -> tuple[list[GenRecord], dict[str, int], dict[str, int]]:
    """Map generations to stages; also return observation-type and tool-call counts.

    Returns (gen_records, type_counts, tool_counts).
    """
    obs_by_id = {o.get("id"): o for o in observations if o.get("id")}

    def nearest_agent(obs: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        """Walk up parents to the nearest AGENT observation (skipping the root).

        Langfuse returns the parent link as ``parentObservationId`` (camelCase).
        """
        current = obs
        while current:
            if current.get("type") == "AGENT" and current.get("name") != "pr_review":
                return current.get("name"), current.get("metadata") or {}
            parent_id = current.get("parentObservationId")
            current = obs_by_id.get(parent_id) if parent_id else None
        return None, {}

    gens: list[GenRecord] = []
    type_counts: Counter = Counter()
    tool_counts: Counter = Counter()

    for obs in observations:
        otype = obs.get("type") or "SPAN"
        type_counts[otype] += 1
        if otype == "TOOL":
            tool_counts[obs.get("name") or "unknown"] += 1

        name = obs.get("name") or ""
        is_gen = otype == "GENERATION" or name in (_GEN_NAME_DIRECT, _GEN_NAME_REACT)
        if not is_gen:
            continue
        # Only generations that actually carry usage are real LLM calls.
        if not (obs.get("usageDetails") or obs.get("usage") or obs.get("costDetails")):
            continue

        agent_name, agent_meta = nearest_agent(obs)
        meta = obs.get("metadata") or {}
        purpose = meta.get("purpose") or agent_meta.get("purpose")

        if purpose == "expert_cache_warmup" or agent_name == "expert_cache_warmup":
            stage = "warmup"
        elif name == _GEN_NAME_REACT or agent_name == "coordinator":
            # ReAct uses ChatOpenAI generations; the finalizer is a direct
            # llm.chat.completions call whose nearest agent is also coordinator.
            stage = "react" if name == _GEN_NAME_REACT else "finalizer"
        elif agent_name == "review_expert":
            stage = agent_meta.get("agent") or "expert_unknown"
        elif agent_name == "comment_compose":
            stage = "comment"
        else:
            stage = agent_name or "unknown"

        tokens = _extract_tokens(obs)
        cost, is_est = _obs_cost(obs)
        max_tokens = meta.get("max_tokens")
        max_tokens = int(max_tokens) if isinstance(max_tokens, (int, float)) else None
        completion = tokens["output"]
        # Truncation: explicit (completion >= max_tokens) or, when no max_tokens
        # was recorded, hitting the provider's default ceiling (4096 for DeepSeek)
        # -- the latter is exactly the run-0 finalizer bug the manual reports found.
        # The warm-up call is excluded: it intentionally generates 1 token with
        # max_tokens=1, so completion==max_tokens there is by design, not a cut-off.
        _PROVIDER_DEFAULT_CEILING = 4096
        is_warmup = purpose == "expert_cache_warmup" or stage == "warmup"
        truncated = False if is_warmup else bool(
            (max_tokens and completion and completion >= max_tokens)
            or (not max_tokens and completion >= _PROVIDER_DEFAULT_CEILING)
        )
        ratio = (completion / max_tokens) if max_tokens else 0.0

        start = _parse_time(obs.get("startTime") or obs.get("start_time"))
        end = _parse_time(obs.get("endTime") or obs.get("end_time"))
        latency_s = (end - start).total_seconds() if start and end else 0.0

        gens.append(GenRecord(
            stage=stage,
            hit=tokens["hit"], miss=tokens["miss"], input=tokens["input"], output=tokens["output"],
            cost=cost, is_estimated_cost=is_est,
            max_tokens=max_tokens,
            retry_count=int(meta.get("retry_count") or 0),
            truncated=truncated, completion_ratio=ratio,
            start=start, end=end, latency_s=latency_s,
            model=obs.get("model") or "",
        ))
    return gens, dict(type_counts), dict(tool_counts)


# --------------------------------------------------------------------------- #
# Metric aggregation
# --------------------------------------------------------------------------- #
@dataclass
class StageStats:
    stage: str
    calls: int = 0
    input: int = 0
    output: int = 0
    hit: int = 0
    miss: int = 0
    cost: float = 0.0
    estimated_cost: bool = False
    retries: int = 0
    wall_s: float = 0.0
    sum_latency_s: float = 0.0
    truncated: bool = False
    max_completion_ratio: float = 0.0
    models: set[str] = field(default_factory=set)

    @property
    def hit_rate(self) -> float:
        total = self.hit + self.miss
        return (self.hit / total) if total else 0.0


def _stage_from_gens(gens: list[GenRecord]) -> dict[str, StageStats]:
    stages: dict[str, StageStats] = {}
    for g in gens:
        s = stages.setdefault(g.stage, StageStats(stage=g.stage))
        s.calls += 1
        s.input += g.input
        s.output += g.output
        s.hit += g.hit
        s.miss += g.miss
        s.cost += g.cost
        s.estimated_cost = s.estimated_cost or g.is_estimated_cost
        s.retries += g.retry_count
        s.sum_latency_s += g.latency_s
        s.truncated = s.truncated or g.truncated
        s.max_completion_ratio = max(s.max_completion_ratio, g.completion_ratio)
        if g.model:
            s.models.add(g.model)
    # Wall clock per stage = span(max end - min start) so parallel experts report
    # their true parallel duration rather than the sum of latencies.
    for g in gens:
        s = stages[g.stage]
        if g.start and g.end:
            span = (g.end - g.start).total_seconds()
            # Approximate stage wall by summing non-overlapping spans is hard; we
            # use min-start..max-end across the stage's generations.
    # Compute wall via min start / max end per stage.
    spans: dict[str, list[datetime]] = {}
    for g in gens:
        if g.start and g.end:
            spans.setdefault(g.stage, []).extend([g.start, g.end])
    for stage, times in spans.items():
        stages[stage].wall_s = (max(times) - min(times)).total_seconds()
    return stages


def _expert_label(key: str) -> str:
    return EXPERTS.get(key).label if key in EXPERTS else key


# --------------------------------------------------------------------------- #
# Report rendering
# --------------------------------------------------------------------------- #
def _money(x: float) -> str:
    return f"${x:.4f}" if x < 1 else f"${x:.2f}"


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _severity_from_snapshot(snapshot: dict[str, Any]) -> tuple[int, dict[str, int]]:
    final_report = (snapshot.get("review") or {}).get("final_report") or {}
    summary = final_report.get("summary") or {}
    by_sev = summary.get("by_severity") or {}
    counts = {sev: int(by_sev.get(sev, 0)) for sev in _SEVERITY_ORDER}
    return int(summary.get("total_findings", 0)), counts


def _routing_from_snapshot(snapshot: dict[str, Any]) -> tuple[list[str], list[str] | None, bool, str, dict[str, Any]]:
    review = snapshot.get("review") or {}
    enabled = (review.get("routing_plan") or {}).get("selected_agents") or []
    # enabled_agents is the configured superset; it is not stored on the review
    # row, so fall back to the full EXPERTS catalog minus the fallback-only one.
    routing_plan = review.get("routing_plan") or {}
    fallback_used = bool(routing_plan.get("fallback_used"))
    fallback_reason = str(routing_plan.get("fallback_reason") or "")
    return enabled, None, fallback_used, fallback_reason, routing_plan


def _findings_detail(snapshot: dict[str, Any]) -> dict[str, Any]:
    review = snapshot.get("review") or {}
    final_report = review.get("final_report") or {}
    findings = final_report.get("findings") or []
    experts = review.get("expert_results") or []
    raw_total = sum(len(e.get("findings") or []) for e in experts)
    located = sum(1 for f in findings if f.get("file") and f.get("file") != "unknown")
    with_line = sum(1 for f in findings if f.get("line_number"))
    conf = Counter(str(f.get("confidence", "medium")).lower() for f in findings)
    fixes = final_report.get("fix_suggestions") or []
    # Cross-expert overlap: same (file, line, title) key seen from >1 expert.
    seen: Counter = Counter()
    for e in experts:
        agent = e.get("agent", "?")
        for f in e.get("findings") or []:
            key = (str(f.get("file", "")).lower(), int(f.get("line_number") or 0), str(f.get("title", "")).lower())
            seen[(key, agent)] += 1
    file_line_title = Counter()
    for (key, _agent) in seen:
        file_line_title[key] += 1
    overlaps = sum(c - 1 for c in file_line_title.values() if c > 1)
    return {
        "total": len(findings),
        "raw_total": raw_total,
        "dedup_removed": max(raw_total - len(findings), 0),
        "located": located,
        "with_line": with_line,
        "confidence": dict(conf),
        "fix_coverage": len(fixes),
        "overlaps": overlaps,
        "per_expert": {e.get("agent", "?"): len(e.get("findings") or []) for e in experts},
    }


def _render_markdown(
    *,
    review_id: int,
    pr_number: int,
    repo: str,
    run_index: int,
    status: str,
    error_message: str | None,
    started_at: str | None,
    completed_at: str | None,
    trace: dict[str, Any] | None,
    observations: list[dict[str, Any]],
    gens: list[GenRecord],
    stages: dict[str, StageStats],
    type_counts: dict[str, int],
    tool_counts: dict[str, int],
    snapshot: dict[str, Any],
    timings: list[dict[str, Any]],
    cross_run: list[dict[str, Any]],
    notes: list[str],
    db_available: bool = True,
) -> str:
    lines: list[str] = []
    lines.append(f"# 评审运行评估报告 · review #{review_id} · run {run_index}\n")

    # ---- 1. Run 概览 ----
    total_cost = sum(s.cost for s in stages.values())
    trace_latency = None
    if trace and trace.get("timestamp"):
        # Latency from observations span.
        starts = [_parse_time(o.get("startTime") or o.get("start_time")) for o in observations]
        ends = [_parse_time(o.get("endTime") or o.get("end_time")) for o in observations]
        starts = [t for t in starts if t]
        ends = [t for t in ends if t]
        if starts and ends:
            trace_latency = (max(ends) - min(starts)).total_seconds()
    db_wall = None
    if started_at and completed_at:
        s = _parse_time(started_at)
        e = _parse_time(completed_at)
        if s and e:
            db_wall = (e - s).total_seconds()

    lines.append("## 1. Run 概览\n")
    lines.append("| 字段 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| review_id / pr | {review_id} / #{pr_number} |")
    lines.append(f"| 仓库 | {repo} |")
    lines.append(f"| run_index | {run_index} |")
    lines.append(f"| 状态 | **{status}** |")
    if error_message:
        lines.append(f"| error_message | `{error_message}` |")
    if trace:
        lines.append(f"| trace_id | `{trace.get('trace_id')}` |")
        lines.append(f"| trace url | {trace.get('url')} |")
    else:
        lines.append("| trace | （未找到匹配 run_index 的 Langfuse trace） |")
    lines.append(f"| 总成本 | {_money(total_cost)} |")
    if trace_latency is not None:
        lines.append(f"| trace 墙钟 | {trace_latency:.1f}s |")
    if db_wall is not None:
        flag = "" if trace_latency and abs(db_wall - trace_latency) < 30 else "  ⚠️ 与 trace 墙钟偏差>30s"
        lines.append(f"| DB 墙钟 (completed−started) | {db_wall:.1f}s{flag} |")
    lines.append(f"| observation 总数 | {sum(type_counts.values())} |")
    lines.append("")

    # ---- 2. 分阶段明细 ----
    lines.append("## 2. 分阶段明细\n")
    lines.append("| 阶段 | 调用数 | 输入token | 输出token | 缓存命中 | 命中率 | 成本 | 墙钟 | retry | 截断? |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|:---:|")
    # Stable stage ordering.
    order = ["react", "finalizer", "warmup"] + [k for k in sorted(stages) if k not in ("react", "finalizer", "warmup", "comment")] + ["comment"]
    seen_keys = set()
    for stage in order:
        if stage not in stages or stage in seen_keys:
            continue
        seen_keys.add(stage)
        s = stages[stage]
        label = {"react": "ReAct 协调", "finalizer": "finalizer", "warmup": "warmup", "comment": "comment_compose"}.get(stage, _expert_label(stage))
        cost = _money(s.cost) + ("(估)" if s.estimated_cost else "")
        lines.append(
            f"| {label} | {s.calls} | {s.input} | {s.output} | {s.hit} | "
            f"{_pct(s.hit_rate)} | {cost} | {s.wall_s:.1f}s | {s.retries} | "
            f"{'🔴' if s.truncated else '—'} |"
        )
    lines.append(f"| **合计** | **{sum(s.calls for s in stages.values())}** | "
                 f"**{sum(s.input for s in stages.values())}** | **{sum(s.output for s in stages.values())}** | "
                 f"**{sum(s.hit for s in stages.values())}** | | **{_money(total_cost)}** | | "
                 f"**{sum(s.retries for s in stages.values())}** | |")
    lines.append("")

    # ---- 3. Token 与成本汇总 ----
    expert_stages = {k: v for k, v in stages.items() if k not in ("react", "finalizer", "warmup", "comment")}
    expert_hit = sum(s.hit for s in expert_stages.values())
    expert_total = sum(s.hit + s.miss for s in expert_stages.values())
    expert_cost = sum(s.cost for s in expert_stages.values())
    warmup_cost = stages.get("warmup", StageStats("warmup")).cost
    overall_hit = sum(s.hit for s in stages.values())
    overall_total = sum(s.hit + s.miss for s in stages.values())
    # Cache savings vs all-miss, on expert input.
    expert_miss = sum(s.miss for s in expert_stages.values())
    savings = expert_hit * (settings.LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS
                            - settings.LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS) / 1_000_000
    total_findings, _ = _severity_from_snapshot(snapshot)

    lines.append("## 3. Token 与成本汇总\n")
    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| 总输入 / 输出 token | {sum(s.input for s in stages.values())} / {sum(s.output for s in stages.values())} |")
    lines.append(f"| 整体缓存命中率 | {_pct(overall_hit / overall_total) if overall_total else 'N/A'} ({overall_hit}/{overall_total}) |")
    lines.append(f"| 专家缓存命中率 | {_pct(expert_hit / expert_total) if expert_total else 'N/A'} ({expert_hit}/{expert_total}) |")
    lines.append(f"| 专家阶段成本（不含预热） | {_money(expert_cost)} |")
    lines.append(f"| 预热成本 | {_money(warmup_cost)} |")
    lines.append(f"| 专家阶段成本（含预热） | {_money(expert_cost + warmup_cost)} |")
    lines.append(f"| 缓存节省（vs 全 miss） | {_money(savings)} |")
    lines.append(f"| 单 finding 成本 | {_money(total_cost / total_findings) if total_findings else 'N/A'} |")
    if any(s.estimated_cost for s in stages.values()):
        lines.append("| ReAct 成本 | 估算（LangChain callback 未上报 costDetails） |")
    lines.append("")

    # ---- 4. 延迟与并行 ----
    lines.append("## 4. 延迟与并行\n")
    expert_timings = [t for t in timings if t.get("agent_name") in EXPERTS]
    lines.append("| 阶段 | 墙钟 | Σ单次 latency | 说明 |")
    lines.append("|---|---:|---:|---|")
    for stage in order:
        if stage not in stages:
            continue
        s = stages[stage]
        label = {"react": "ReAct 协调", "finalizer": "finalizer", "warmup": "warmup", "comment": "comment_compose"}.get(stage, _expert_label(stage))
        note = ""
        if stage in EXPERTS:
            note = "并行专家"
        lines.append(f"| {label} | {s.wall_s:.1f}s | {s.sum_latency_s:.1f}s | {note} |")
    if expert_timings:
        expert_wall = (max(_parse_time(t["end_time"]) for t in expert_timings if t.get("end_time"))
                       - min(_parse_time(t["start_time"]) for t in expert_timings if t.get("start_time")))
        if expert_wall.total_seconds() > 0:
            sum_expert = sum(t.get("latency_ms", 0) for t in expert_timings) / 1000.0
            parallel_eff = expert_wall.total_seconds() / sum_expert if sum_expert else 0
            starts = [_parse_time(t["start_time"]) for t in expert_timings if t.get("start_time")]
            dispersion = (max(starts) - min(starts)).total_seconds() if len(starts) > 1 else 0.0
            lines.append("")
            lines.append(f"- **专家并行效率比** = 专家阶段墙钟 / Σ单专家 latency = {expert_wall.total_seconds():.1f}s / {sum_expert:.1f}s = **{parallel_eff:.2f}**（越接近 1/专家数 表示并行越充分；接近 1 表示退化成串行）")
            lines.append(f"- **fan-out 启动离散度** = {dispersion*1000:.0f}ms（专家间最大启动时间差；越小越健康）")
            slowest = max(expert_timings, key=lambda t: t.get("latency_ms", 0))
            lines.append(f"- **最慢专家**：{_expert_label(slowest['agent_name'])} {slowest.get('latency_ms',0)/1000:.1f}s")
    lines.append("")

    # ---- 5. 可靠性 ----
    lines.append("## 5. 可靠性\n")
    truncations = [g.stage for g in gens if g.truncated]
    # Near-truncation warns on large outputs approaching their max_tokens budget;
    # warm-up (1/1) is intentional and excluded.
    near_ratio = [g for g in gens if g.stage != "warmup" and g.max_tokens and g.completion_ratio >= 0.8 and not g.truncated]
    _, _, fallback_used, fallback_reason, _ = _routing_from_snapshot(snapshot)

    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    total_retries = 0
    error_types: Counter = Counter()
    non_200 = 0
    near_fail: list[str] = []
    if not db_available:
        lines.append("| retry / 状态码 / 错误类型 | 历史 run，DB 已覆盖，不可用 |")
    else:
        total_retries = sum(t.get("retry_count", 0) or 0 for t in timings)
        error_types: Counter = Counter()
        non_200 = 0
        near_fail: list[str] = []
        for t in timings:
            rc = t.get("retry_count", 0) or 0
            if rc >= _MAX_RETRIES:
                near_fail.append(t.get("agent_name", "?"))
            sc = t.get("status_code")
            if sc and sc != 200:
                non_200 += 1
            for err in (t.get("retry_errors") or []):
                error_types[str(err.get("error", "unknown"))] += 1
        lines.append(f"| 总 retry 次数 | {total_retries} |")
        lines.append(f"| 非 200 状态码 | {non_200} |")
        if near_fail:
            lines.append(f"| ⚠️ retry 达上限(≥{_MAX_RETRIES})的 agent | {', '.join(near_fail)} |")
        if error_types:
            lines.append(f"| retry 错误类型分布 | {dict(error_types)} |")
    # Truncation / near-truncation come from the trace (generations), always available.
    if truncations:
        lines.append(f"| 🔴 输出截断（completion 撞顶） | {', '.join(_expert_label(s) for s in truncations)} |")
    else:
        lines.append("| 输出截断 | 无 |")
    if near_ratio:
        lines.append(f"| ⚠️ completion/max_tokens≥80%（临近截断） | {', '.join(_expert_label(g.stage) for g in near_ratio)} ({max(g.completion_ratio for g in near_ratio)*100:.0f}%) |")
    lines.append(f"| 路由 fallback | {'🔴 触发: '+fallback_reason if fallback_used else ('未触发' if db_available else '历史 run，不可用')} |")
    lines.append("")

    # ---- 6. 路由智能 ----
    lines.append("## 6. 路由智能\n")
    if not db_available:
        lines.append("> 历史 run：路由数据不可用（DB 已被覆盖式重跑覆盖）。\n")
    else:
        selected, _, _, _, routing_plan = _routing_from_snapshot(snapshot)
        enabled_agents = (snapshot.get("review") or {}).get("enabled_agents")
        if not enabled_agents:
            # Not persisted on review row; use EXPERTS minus fallback-only as the default superset.
            enabled_agents = [k for k in EXPERTS if k != "general_review"]
        prune_rate = len(set(selected)) / len(enabled_agents) if enabled_agents else 0
        lines.append(f"- **路由裁剪率** = selected / enabled = {len(set(selected))} / {len(enabled_agents)} = **{_pct(prune_rate)}**")
        lines.append(f"- 选中专家：{', '.join(_expert_label(a) for a in selected) or '（无）'}")
        unselected = [a for a in enabled_agents if a not in selected]
        if unselected:
            reasons = routing_plan.get("unselected_agents") or {}
            lines.append("- 未选中专家：")
            for a in unselected:
                r = reasons.get(a) or routing_plan.get("reasons", {}).get(a)
                rtext = f" - {r[0] if isinstance(r, list) and r else r}" if r else ""
                lines.append(f"  - {_expert_label(a)}{rtext}")
        lines.append("")

    # ---- 7. 输出质量（代理指标） ----
    lines.append("## 7. 输出质量（代理指标，非正确性）\n")
    if not db_available:
        lines.append("> 历史 run：findings 数据不可用（DB 已被覆盖式重跑覆盖）。\n")
    elif status != "succeeded" or not total_findings:
        lines.append("> 本次运行未成功完成或无 findings，本节为空。\n")
    else:
        fd = _findings_detail(snapshot)
        _, sev = _severity_from_snapshot(snapshot)
        lines.append("| 指标 | 值 |")
        lines.append("|---|---|")
        lines.append(f"| total_findings | {fd['total']} |")
        lines.append(f"| severity 分布 | critical={sev['critical']}, high={sev['high']}, medium={sev['medium']}, low={sev['low']} |")
        lines.append(f"| 去重率 | 原始 {fd['raw_total']} → 去重后 {fd['total']}（移除 {fd['dedup_removed']}） |")
        lines.append(f"| 跨专家重叠 | {fd['overlaps']} 条（同 file+line+title 被多个专家命中） |")
        loc_rate = fd['located'] / fd['total'] if fd['total'] else 0
        line_rate = fd['with_line'] / fd['total'] if fd['total'] else 0
        lines.append(f"| 定位精度 | 带 file={_pct(loc_rate)}, 带行号={_pct(line_rate)} |")
        lines.append(f"| fix_suggestion 覆盖 | {fd['fix_coverage']}/{fd['total']} |")
        lines.append(f"| confidence 分布 | {fd['confidence']} |")
        if fd['per_expert']:
            lines.append("")
            lines.append("分专家 findings 数：")
            lines.append("| 专家 | findings |")
            lines.append("|---|---:|")
            for agent, n in fd['per_expert'].items():
                lines.append(f"| {_expert_label(agent)} | {n} |")
        lines.append("")
        lines.append("> ⚠️ 以上为质量代理指标。findings 是否真阳性（正确性）需人工标注或 eval set，Langfuse trace 无法判定。\n")

    # ---- 8. LLM 调用结构 ----
    lines.append("## 8. LLM 调用结构\n")
    lines.append(f"- observation 类型分布：{type_counts}")
    if tool_counts:
        lines.append("- ReAct 工具调用分布：")
        for tool, n in sorted(tool_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - `{tool}`: {n}")
    lines.append("")

    # ---- 9. 跨 Run 对比 ----
    lines.append("## 9. 跨 Run 对比\n")
    if len(cross_run) <= 1:
        lines.append("> 仅当前 run 有数据（或 Langfuse 不可达）。多次重新评审后此处自动生成 delta 表。\n")
    else:
        lines.append("| run | 总成本 | 专家命中率 | 专家阶段墙钟 | 最长专家 | 输出截断 | findings | critical | retry总数 |")
        lines.append("|---:|---:|---:|---:|---:|:---:|---:|---:|---:|")
        for cr in cross_run:
            lines.append(
                f"| {cr['run_index']} | {_money(cr['cost'])} | {_pct(cr['expert_hit_rate']) if cr.get('expert_hit_rate') is not None else 'N/A'} | "
                f"{cr.get('expert_wall_s', 0):.1f}s | {cr.get('max_expert_s', 0):.1f}s | "
                f"{'🔴' if cr.get('truncated') else '—'} | "
                f"{cr.get('findings', 'N/A')} | {cr.get('critical', 'N/A')} | {cr.get('retries', 'N/A')} |"
            )
        lines.append("")
        lines.append("> 输出截断 = finalizer/专家/comment 任一阶段 completion 撞顶（不含 warmup）。findings / critical 列对历史 run 取自该目录下已存的 `run_{M}_ouput.json`（DB 已被覆盖式重跑覆盖，仅留导出快照）。N/A = 无快照。\n")

    # ---- 10. 异常与建议 ----
    lines.append("## 10. 异常与建议（自动标红项）\n")
    issues: list[str] = []
    if truncations:
        issues.append(f"🔴 输出截断：{', '.join(_expert_label(s) for s in truncations)}。建议给该阶段提高 max_tokens 或缩减输出字段。")
    if near_fail:
        issues.append(f"🔴 retry 达上限：{', '.join(near_fail)}。检查 provider 稳定性 / 超时配置。")
    if error_types:
        issues.append(f"⚠️ 重试错误：{dict(error_types)}。ReadError 多为网络/长连接问题。")
    if near_ratio:
        issues.append(f"⚠️ 临近截断（≥80%）：{', '.join(_expert_label(g.stage) for g in near_ratio)}，建议监控。")
    if fallback_used:
        issues.append(f"🔴 路由 fallback 触发：{fallback_reason}。coordinator ReAct 层可能失效。")
    if status != "succeeded":
        issues.append(f"🔴 评审未成功：{error_message or '未知错误'}。")
    if not issues:
        lines.append("本次运行无自动标红项。\n")
    else:
        for it in issues:
            lines.append(f"- {it}")
        lines.append("")
    if notes:
        lines.append("**备注**：")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")
    lines.append(f"> 报告生成时间：{datetime.now(timezone.utc).isoformat()}（best-effort，基于 Langfuse trace + 导出快照）")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Cross-run aggregation
# --------------------------------------------------------------------------- #
def _summarize_run(run_index: int, observations: list[dict[str, Any]], findings: int | None, critical: int | None) -> dict[str, Any]:
    gens, _, _ = _classify_observations(observations)
    stages = _stage_from_gens(gens)
    expert_stages = {k: v for k, v in stages.items() if k not in ("react", "finalizer", "warmup", "comment")}
    eh = sum(s.hit for s in expert_stages.values())
    et = sum(s.hit + s.miss for s in expert_stages.values())
    expert_wall = max((s.wall_s for s in expert_stages.values()), default=0.0)
    max_expert = max((s.wall_s for s in expert_stages.values()), default=0.0)
    # Truncation excludes warm-up (intentional 1-token gen) and ReAct (small outputs);
    # what matters is whether the finalizer, an expert, or comment got cut off.
    truncated = any(s.truncated for s in stages.values())
    retries = sum(s.retries for s in stages.values())
    return {
        "run_index": run_index,
        "cost": sum(s.cost for s in stages.values()),
        "expert_hit_rate": (eh / et) if et else None,
        "expert_wall_s": expert_wall,
        "max_expert_s": max_expert,
        "truncated": truncated,
        "retries": retries,
        "findings": findings,
        "critical": critical,
    }


# --------------------------------------------------------------------------- #
# Main entry
# --------------------------------------------------------------------------- #
async def generate_eval_report(review_id: int, run_index: int | None = None) -> dict[str, Any]:
    """Generate ``run_{N}.md`` + ``run_{N}_ouput.json`` for a review run.

    ``run_index=None`` uses the current DB run (the one just completed). Passing
    an explicit ``run_index`` targets a historical run; in that case only the
    ``.md`` is written (the export snapshot reflects the current run, not a
    historical one).
    """
    notes: list[str] = []
    repo_root = Path(__file__).resolve().parents[2]

    # 1. Fetch the export snapshot via the real endpoint.
    snapshot = await _fetch_export(review_id)
    if snapshot is None:
        logger.warning("Eval report: export endpoint unreachable for review %s; skipping", review_id)
        return {"skipped": True, "reason": "export unreachable"}

    review = snapshot.get("review") or {}
    pr_number = review.get("pr_number") or 0
    current_run = int(review.get("run_index") or 0)
    target = run_index if run_index is not None else current_run

    out_dir = repo_root / "eval" / f"review_{pr_number}_{review_id}"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"run_{target}_ouput.json"
    md_path = out_dir / f"run_{target}.md"

    # 2. Write the export snapshot only when it actually matches this run, and
    #    track whether DB-derived metrics (findings/routing/timings) are valid
    #    for this run. For a historical run without a stored snapshot they are
    #    NOT -- the DB has been overwritten -- so the report must not show them.
    db_available = True
    if target == current_run:
        json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    elif json_path.exists():
        # Reuse the stored snapshot for that run as the DB-side source of truth.
        try:
            snapshot = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    else:
        db_available = False
        notes.append(f"目标 run_index={target} 与当前 DB run={current_run} 不符，且无历史快照。DB 侧指标（findings/routing/retry）不可用，仅生成 trace 侧报告。")
        # Null out DB-specific fields so the renderer never shows another run's data.
        rev = dict(snapshot.get("review") or {})
        for k in ("final_report", "expert_results", "summary_result", "coordinator_result",
                  "routing_plan", "comment_content", "error_message", "started_at", "completed_at"):
            rev[k] = None
        rev["agent_timings"] = []
        rev["status"] = "历史 run（DB 已覆盖）"
        snapshot = {**snapshot, "review": rev}

    # Re-bind review: the snapshot may have been replaced (stored snapshot reuse
    # or historical-run field nulling) above, so the earlier binding is stale.
    review = snapshot.get("review") or {}

    # 3. Pick the Langfuse trace for this run_index.
    traces = fetch_traces_for_review_with_runindex(review_id)
    trace = next((t for t in traces if t["run_index"] == target), None)
    if trace is None and traces:
        # Fall back to the closest run; note the mismatch.
        trace = min(traces, key=lambda t: abs(t["run_index"] - target))
        notes.append(f"未找到 run_index={target} 的 trace，回退到最近的 run_index={trace['run_index']}。")
    observations: list[dict[str, Any]] = []
    if trace:
        observations = fetch_observations(trace["trace_id"])
    if not trace:
        notes.append("Langfuse 未启用或无该 review 的 trace，报告仅含导出快照侧指标。")

    # 4. Classify + aggregate current run.
    gens, type_counts, tool_counts = _classify_observations(observations)
    stages = _stage_from_gens(gens)

    # 5. Cross-run comparison (fetch observations for every run, best-effort).
    cross_run: list[dict[str, Any]] = []
    for t in traces:
        obs = observations if t["run_index"] == (trace["run_index"] if trace else -1) else fetch_observations(t["trace_id"])
        # Findings/critical from a stored snapshot for that run if present.
        fpath = out_dir / f"run_{t['run_index']}_ouput.json"
        findings = critical = None
        if fpath.exists():
            try:
                snap_m = json.loads(fpath.read_text(encoding="utf-8"))
                fr = (snap_m.get("review") or {}).get("final_report") or {}
                findings = (fr.get("summary") or {}).get("total_findings")
                by = (fr.get("summary") or {}).get("by_severity") or {}
                critical = by.get("critical")
            except Exception:
                pass
        cross_run.append(_summarize_run(t["run_index"], obs, findings, critical))

    # 6. Render + write.
    project = snapshot.get("project") or {}
    repo = f"{project.get('repo_owner')}/{project.get('repo_name')}" if project.get("repo_owner") else "unknown"
    md = _render_markdown(
        review_id=review_id,
        pr_number=pr_number,
        repo=repo,
        run_index=target,
        status=str(review.get("status") or "unknown"),
        error_message=review.get("error_message"),
        started_at=review.get("started_at"),
        completed_at=review.get("completed_at"),
        trace=trace,
        observations=observations,
        gens=gens,
        stages=stages,
        type_counts=type_counts,
        tool_counts=tool_counts,
        snapshot=snapshot,
        timings=review.get("agent_timings") or [],
        cross_run=cross_run,
        notes=notes,
        db_available=db_available,
    )
    md_path.write_text(md, encoding="utf-8")
    logger.info("Eval report written: %s (+ %s)", md_path, json_path)
    return {
        "md_path": str(md_path),
        "json_path": str(json_path) if target == current_run else None,
        "trace_id": trace.get("trace_id") if trace else None,
        "n_observations": len(observations),
    }


async def _fetch_export(review_id: int) -> dict[str, Any] | None:
    """GET the export endpoint on the local backend. Returns None if unreachable."""
    url = f"http://localhost:{settings.PORT}/api/reviews/{review_id}/export"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except Exception:
        logger.exception("Eval report: failed to fetch export from %s", url)
        return None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cli() -> None:
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if len(sys.argv) < 2:
        print("usage: python -m backend.services.eval_report <review_id> [run_index]")
        sys.exit(2)
    review_id = int(sys.argv[1])
    run_index = int(sys.argv[2]) if len(sys.argv) > 2 else None
    result = asyncio.run(generate_eval_report(review_id, run_index))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    _cli()
