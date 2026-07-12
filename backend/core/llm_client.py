import asyncio
import json
import time

import httpx

from backend.core.llm_config import get_llm_config
from backend.core.observability import (
    calculate_cost_details,
    observe_llm_generation,
    update_observation,
)

MAX_RETRIES = 3
MAX_JSON_RETRIES = 2
RETRYABLE_STATUS = {500, 502, 503, 504}
TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


async def llm_call(system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    """Call the configured LLM and return (content, meta).

    meta fields: model, endpoint, latency_ms, status_code, retry_count, retry_errors
    retry_errors is a list of {attempt, latency_ms, error} for each failed attempt.
    """
    config = get_llm_config()
    endpoint = f"{config['endpoint']}/chat/completions"
    model = config["model"]
    language = config.get("language", "zh")
    retry_errors: list[dict] = []

    if language == "zh":
        lang_instruction = (
            "Language: You MUST write all text content in Chinese (简体中文). "
            "All descriptions, summaries, scenarios, reasons, suggestions, overviews, "
            "and explanations must be in Chinese. Only JSON keys, code identifiers, "
            "and technical terms should remain in English."
        )
    else:
        lang_instruction = "Reply in English."
    if lang_instruction not in system_prompt:
        system_prompt = f"{system_prompt}\n{lang_instruction}"

    with observe_llm_generation(model, endpoint, system_prompt, user_prompt) as generation:
        for attempt in range(MAX_RETRIES + 1):
            t0 = time.time()
            try:
                async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                    resp = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {config['api_key']}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.3,
                        },
                    )
                    status = resp.status_code
                    elapsed = int((time.time() - t0) * 1000)

                    if status in RETRYABLE_STATUS or status == 429:
                        resp.read()
                        raise httpx.HTTPStatusError(
                            f"Server error {status}",
                            request=resp.request,
                            response=resp,
                        )

                    resp.raise_for_status()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    usage = _extract_usage(data.get("usage"))
                    meta = {
                        "model": model,
                        "endpoint": endpoint,
                        "latency_ms": elapsed,
                        "status_code": status,
                        "retry_count": attempt,
                        "retry_errors": retry_errors if retry_errors else None,
                        "usage": usage,
                    }
                    update_observation(
                        generation,
                        output=content,
                        metadata={
                            "status_code": status,
                            "retry_count": attempt,
                            "retry_errors": retry_errors,
                        },
                        usage_details=usage,
                        cost_details=calculate_cost_details(usage),
                    )
                    return content, meta

            except (httpx.TimeoutException, httpx.ConnectError,
                    httpx.RemoteProtocolError, httpx.ReadError,
                    httpx.HTTPStatusError) as e:
                elapsed = int((time.time() - t0) * 1000)
                err_entry = {
                    "attempt": attempt + 1,
                    "latency_ms": elapsed,
                    "error": _format_error(e),
                }
                retry_errors.append(err_entry)

                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)
                    continue

                update_observation(
                    generation,
                    metadata={"retry_count": attempt, "retry_errors": retry_errors},
                    level="ERROR",
                    status_message=_format_error(e),
                )
                raise


def _format_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code if e.response else "?"
        return f"HTTP {code}"
    if isinstance(e, httpx.TimeoutException):
        return "timeout"
    return type(e).__name__


def _extract_usage(usage: object) -> dict[str, int] | None:
    """Normalize usage fields returned by OpenAI-compatible providers."""
    if not isinstance(usage, dict):
        return None

    aliases = {
        "prompt_tokens": ("prompt_tokens", "input_tokens"),
        "completion_tokens": ("completion_tokens", "output_tokens"),
        "total_tokens": ("total_tokens",),
        # DeepSeek context-cache usage. Keep these provider-native names so
        # Langfuse can show cache-hit rates without losing the raw breakdown.
        "prompt_cache_hit_tokens": ("prompt_cache_hit_tokens",),
        "prompt_cache_miss_tokens": ("prompt_cache_miss_tokens",),
    }
    normalized: dict[str, int] = {}
    for target, names in aliases.items():
        for name in names:
            value = usage.get(name)
            if isinstance(value, (int, float)):
                normalized[target] = int(value)
                break

    if "total_tokens" not in normalized and normalized:
        normalized["total_tokens"] = (
            normalized.get("prompt_tokens", 0) + normalized.get("completion_tokens", 0)
        )
    return normalized or None


async def llm_call_json(system_prompt: str, user_prompt: str) -> tuple[dict, dict]:
    """Call the LLM and parse the response as JSON. Returns (parsed_json, meta).

    Retries the LLM call if JSON parsing fails (empty or malformed response).
    """
    last_text = ""
    last_meta: dict = {}

    for json_attempt in range(MAX_JSON_RETRIES + 1):
        text, meta = await llm_call(system_prompt, user_prompt)
        last_meta = meta
        text = text.strip()

        # Strip <think>...</think> tags (reasoning tokens from MiniMax / DeepSeek models)
        if text.startswith("<think>"):
            end_idx = text.find("</think>")
            if end_idx != -1:
                text = text[end_idx + len("</think>"):].strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            return json.loads(text), meta
        except json.JSONDecodeError:
            last_text = text
            if json_attempt < MAX_JSON_RETRIES:
                await asyncio.sleep(1)
                continue

    preview = last_text[:200] if last_text else "(empty)"
    raise ValueError(f"LLM returned unparseable response after {MAX_JSON_RETRIES + 1} attempts: {preview}")
