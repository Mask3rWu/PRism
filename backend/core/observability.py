"""Langfuse tracing helpers with privacy-safe defaults.

Tracing is disabled until both Langfuse API keys are configured. Source code,
prompts, and model responses are only sent when LANGFUSE_TRACE_CONTENT=true.
"""

from contextlib import contextmanager
from functools import lru_cache
import logging
import sys
from typing import Any, Iterator
from urllib.parse import urlparse

from backend.core.config import settings

logger = logging.getLogger(__name__)


def langfuse_enabled() -> bool:
    return bool(settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY)


def langchain_callbacks() -> list[Any]:
    """Return ReAct tracing callbacks only when full content tracing is enabled."""
    if not langfuse_enabled() or not settings.LANGFUSE_TRACE_CONTENT:
        return []

    # CallbackHandler reuses the initialized client and records each LangChain
    # model and tool run as a child observation.
    if get_langfuse_client() is None:
        return []
    try:
        from langfuse.langchain import CallbackHandler

        return [CallbackHandler(public_key=settings.LANGFUSE_PUBLIC_KEY)]
    except Exception:
        # ReAct tracing must not change review availability, but a missing
        # integration dependency must be visible to operators.
        logger.exception("Failed to initialize Langfuse LangChain callback")
        return []


@lru_cache(maxsize=1)
def get_langfuse_client() -> Any | None:
    """Create the client lazily so disabled tracing has no runtime impact."""
    if not langfuse_enabled():
        return None

    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST,
            environment=settings.LANGFUSE_ENVIRONMENT,
            release=settings.LANGFUSE_RELEASE or None,
        )
    except Exception:
        # Observability must never interrupt a code review.
        return None


def reset_langfuse_client() -> None:
    """Clear the cached client. Intended for tests and controlled restarts."""
    get_langfuse_client.cache_clear()


def shutdown_langfuse() -> None:
    if get_langfuse_client.cache_info().currsize == 0:
        return
    client = get_langfuse_client()
    if client is None:
        return
    try:
        client.flush()
        client.shutdown()
    except Exception:
        pass
    finally:
        reset_langfuse_client()


def _content(value: Any) -> Any:
    if settings.LANGFUSE_TRACE_CONTENT:
        return value
    return _summary(value)


def _summary(value: Any) -> Any:
    if isinstance(value, str):
        return {"redacted": True, "type": "text", "chars": len(value)}
    if isinstance(value, dict):
        return {
            "redacted": True,
            "type": "object",
            "keys": sorted(str(key) for key in value)[:30],
            "items": len(value),
        }
    if isinstance(value, (list, tuple)):
        return {"redacted": True, "type": "list", "items": len(value)}
    return value


def _endpoint_host(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    return parsed.netloc or endpoint.split("/")[0]


def review_metadata(
    review_id: int,
    project_id: int,
    repo_owner: str,
    repo_name: str,
    pr_number: int,
    enabled_agents: list[str],
) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "project_id": project_id,
        "repository": f"{repo_owner}/{repo_name}",
        "pr_number": pr_number,
        "enabled_agents": enabled_agents,
    }


@contextmanager
def _start_observation(**kwargs: Any) -> Iterator[Any | None]:
    client = get_langfuse_client()
    if client is None:
        yield None
        return

    try:
        manager = client.start_as_current_observation(**kwargs)
        observation = manager.__enter__()
    except Exception:
        yield None
        return

    try:
        yield observation
    except BaseException:
        try:
            manager.__exit__(*sys.exc_info())
        except Exception:
            pass
        raise
    else:
        try:
            manager.__exit__(None, None, None)
        except Exception:
            pass


@contextmanager
def observe_review(metadata: dict[str, Any]) -> Iterator[Any | None]:
    with _start_observation(
        name="pr_review",
        as_type="agent",
        metadata=metadata,
        input=_content({"review": metadata}),
    ) as observation:
        yield observation


@contextmanager
def observe_graph_node(node_name: str, state: dict[str, Any]) -> Iterator[Any | None]:
    metadata = {
        "review_id": state.get("review_id"),
        "agent": state.get("active_expert", node_name),
        "selected_agents": state.get("selected_agents", []),
    }
    node_input = {
        "review_id": state.get("review_id"),
        "agent": state.get("active_expert", node_name),
        "project_description": state.get("project_description", ""),
        "pr_diff": state.get("pr_diff", ""),
    }

    with _start_observation(
        name=node_name,
        as_type="agent",
        metadata=metadata,
        input=_content(node_input),
    ) as observation:
        yield observation


@contextmanager
def observe_llm_generation(
    model: str,
    endpoint: str,
    system_prompt: str,
    user_prompt: str,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any | None]:
    observation_metadata = {
        "provider_host": _endpoint_host(endpoint),
        **(metadata or {}),
    }
    with _start_observation(
        name="llm.chat.completions",
        as_type="generation",
        model=model,
        model_parameters={"temperature": 0.3},
        metadata=observation_metadata,
        input=_content({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        }),
    ) as generation:
        yield generation


def update_observation(
    observation: Any | None,
    *,
    output: Any | None = None,
    metadata: dict[str, Any] | None = None,
    level: str | None = None,
    status_message: str | None = None,
    usage_details: dict[str, int] | None = None,
    cost_details: dict[str, float] | None = None,
) -> None:
    if observation is None:
        return
    try:
        kwargs: dict[str, Any] = {}
        if output is not None:
            kwargs["output"] = _content(output)
        if metadata:
            kwargs["metadata"] = metadata
        if level:
            kwargs["level"] = level
        if status_message:
            kwargs["status_message"] = status_message[:500]
        if usage_details:
            kwargs["usage_details"] = usage_details
        if cost_details:
            kwargs["cost_details"] = cost_details
        observation.update(**kwargs)
    except Exception:
        pass


def calculate_cost_details(usage: dict[str, int] | None) -> dict[str, float] | None:
    if not usage:
        return None
    input_tokens = usage.get("prompt_tokens", usage.get("input", 0))
    output_tokens = usage.get("completion_tokens", usage.get("output", 0))
    cache_hit_tokens = usage.get("prompt_cache_hit_tokens")
    cache_miss_tokens = usage.get("prompt_cache_miss_tokens")
    cache_pricing_configured = (
        settings.LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS != 0
        or settings.LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS != 0
    )

    if cache_pricing_configured and (cache_hit_tokens is not None or cache_miss_tokens is not None):
        cache_hit_tokens = cache_hit_tokens or 0
        cache_miss_tokens = cache_miss_tokens if cache_miss_tokens is not None else max(
            input_tokens - cache_hit_tokens, 0
        )
        input_cost = (
            cache_hit_tokens * settings.LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS
            + cache_miss_tokens * settings.LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS
        ) / 1_000_000
    else:
        input_cost = input_tokens * settings.LANGFUSE_INPUT_COST_PER_1M_TOKENS / 1_000_000
    output_cost = output_tokens * settings.LANGFUSE_OUTPUT_COST_PER_1M_TOKENS / 1_000_000
    total_cost = input_cost + output_cost
    if total_cost == 0:
        return None
    return {"total_cost": total_cost}
