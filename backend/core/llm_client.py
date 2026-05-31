import asyncio
import json
import time

import httpx

from backend.core.call_logger import log_api_call
from backend.core.llm_config import get_llm_config

MAX_RETRIES = 3
RETRYABLE_STATUS = {500, 502, 503, 504}
TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)


async def llm_call(system_prompt: str, user_prompt: str) -> str:
    """Call the configured LLM and return the response text, with retry and logging."""
    config = get_llm_config()
    endpoint = f"{config['endpoint']}/chat/completions"
    last_error = None

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
                        "model": config["model"],
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.3,
                    },
                )
                status = resp.status_code
                elapsed = int((time.time() - t0) * 1000)

                if status in RETRYABLE_STATUS:
                    resp.read()
                    raise httpx.HTTPStatusError(
                        f"Server error {status}",
                        request=resp.request,
                        response=resp,
                    )

                if status == 429:
                    resp.read()
                    raise httpx.HTTPStatusError(
                        "Rate limited",
                        request=resp.request,
                        response=resp,
                    )

                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]

                log_api_call(
                    call_type="llm",
                    endpoint=endpoint,
                    model=config["model"],
                    latency_ms=elapsed,
                    status_code=status,
                    retry_count=attempt,
                )
                return content

        except (httpx.TimeoutException, httpx.ConnectError,
                httpx.RemoteProtocolError, httpx.ReadError,
                httpx.HTTPStatusError) as e:
            last_error = e
            elapsed = int((time.time() - t0) * 1000)
            status_code = None
            if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                status_code = e.response.status_code

            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                await asyncio.sleep(wait)
                continue

            log_api_call(
                call_type="llm",
                endpoint=endpoint,
                model=config["model"],
                latency_ms=elapsed,
                status_code=status_code,
                error_message=str(e),
                retry_count=attempt,
            )
            raise

    raise last_error  # type: ignore[misc]


async def llm_call_json(system_prompt: str, user_prompt: str) -> dict:
    """Call the LLM and parse the response as JSON."""
    text = await llm_call(system_prompt, user_prompt)
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

    return json.loads(text)
