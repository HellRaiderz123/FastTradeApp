"""
Shared LLM client — reads NVIDIA / Groq / OpenAI config from environment.

All LLM I/O runs in a dedicated thread pool (_llm_executor) so it NEVER
blocks the FastAPI async event loop or other sync request threads.

Usage:
  - Sync callers: call_llm(prompt) — runs in thread pool, safe from any context
  - Async callers: await call_llm_async(prompt) — awaits thread pool result

Config (set in .env):
  LLM_PROVIDER  = custom | groq | openai
  LLM_API_KEY   = nvapi-... / gsk_... / sk-...
  LLM_BASE_URL  = https://integrate.api.nvidia.com/v1
  LLM_MODEL     = deepseek-ai/deepseek-v4-pro
"""

import asyncio
import os
import json
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# --- Dedicated thread pool for LLM calls (isolated from main app threads) ---
_LLM_POOL_SIZE = int(os.getenv("LLM_THREAD_POOL_SIZE", "3"))
_llm_executor = ThreadPoolExecutor(max_workers=_LLM_POOL_SIZE, thread_name_prefix="llm")

_LLM_BASE = {
    "groq":   "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
}

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
LLM_API_KEY  = (
    os.getenv("LLM_API_KEY")
    or os.getenv("GROQ_API_KEY")
    or os.getenv("OPENAI_API_KEY")
    or ""
)
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or _LLM_BASE.get(LLM_PROVIDER, _LLM_BASE["groq"])
LLM_MODEL    = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
LLM_MODEL_FALLBACKS = [
    model.strip()
    for model in (os.getenv("LLM_MODEL_FALLBACKS", "") or "").split(",")
    if model.strip()
]
LLM_MIN_INTERVAL_SEC = max(float(os.getenv("LLM_MIN_INTERVAL_SEC", "1.5") or 1.5), 0.0)
LLM_MAX_RETRIES = max(int(os.getenv("LLM_MAX_RETRIES", "3") or 3), 0)
LLM_RETRY_BASE_DELAY_SEC = max(float(os.getenv("LLM_RETRY_BASE_DELAY_SEC", "2.0") or 2.0), 0.1)

# --- Circuit breaker ---
_CIRCUIT_FAILURE_THRESHOLD = 3
_CIRCUIT_RECOVERY_SEC = 60.0
_circuit_failures = 0
_circuit_open_until = 0.0
_circuit_lock = threading.Lock()

# --- Rate limiter ---
_rate_limit_lock = threading.Lock()
_llm_next_request_at = 0.0


def _circuit_is_open() -> bool:
    if _circuit_failures < _CIRCUIT_FAILURE_THRESHOLD:
        return False
    return time.monotonic() < _circuit_open_until


def _circuit_record_success() -> None:
    global _circuit_failures
    with _circuit_lock:
        _circuit_failures = 0


def _circuit_record_failure() -> None:
    global _circuit_failures, _circuit_open_until
    with _circuit_lock:
        _circuit_failures += 1
        if _circuit_failures >= _CIRCUIT_FAILURE_THRESHOLD:
            _circuit_open_until = time.monotonic() + _CIRCUIT_RECOVERY_SEC
            logger.warning(
                "LLM circuit breaker OPEN — %d consecutive failures, pausing for %.0fs",
                _circuit_failures, _CIRCUIT_RECOVERY_SEC,
            )


def is_available() -> bool:
    """Return True if an LLM API key is configured and circuit is closed."""
    return bool(LLM_API_KEY) and not _circuit_is_open()


def get_model_candidates(preferred_model: str | None = None) -> list[str]:
    candidates: list[str] = []
    for model in [preferred_model, LLM_MODEL, *LLM_MODEL_FALLBACKS]:
        clean = str(model or "").strip()
        if clean and clean not in candidates:
            candidates.append(clean)
    return candidates or [LLM_MODEL]


def _wait_for_rate_limit() -> None:
    global _llm_next_request_at

    if LLM_MIN_INTERVAL_SEC <= 0:
        return

    with _rate_limit_lock:
        now = time.monotonic()
        wait_for = _llm_next_request_at - now
        _llm_next_request_at = max(now, _llm_next_request_at) + LLM_MIN_INTERVAL_SEC

    if wait_for > 0:
        time.sleep(wait_for)


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = (response.headers.get("Retry-After") or "").strip()
    if retry_after:
        try:
            return max(float(retry_after), LLM_RETRY_BASE_DELAY_SEC)
        except ValueError:
            pass
    return LLM_RETRY_BASE_DELAY_SEC * (2 ** max(0, attempt - 1))


def _do_chat_completion(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float = 30.0,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    preferred_model: str | None = None,
) -> tuple[Optional[dict], Optional[str], Optional[str]]:
    """Internal: runs the actual HTTP call. Always executed inside _llm_executor."""
    if not LLM_API_KEY:
        return None, None, "LLM_API_KEY not configured"

    if _circuit_is_open():
        return None, None, "LLM circuit breaker is open (recent failures)"

    last_error: str | None = None
    http_timeout = httpx.Timeout(connect=5.0, read=min(timeout, 20.0), write=10.0, pool=5.0)

    with httpx.Client(timeout=http_timeout) as client:
        for model_name in get_model_candidates(preferred_model):
            payload: dict[str, Any] = {
                "model": model_name,
                "messages": messages,
            }
            if max_tokens is not None:
                payload["max_tokens"] = max_tokens
            if temperature is not None:
                payload["temperature"] = temperature
            if tools is not None:
                payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice

            for attempt in range(1, LLM_MAX_RETRIES + 2):
                try:
                    _wait_for_rate_limit()
                    resp = client.post(
                        f"{LLM_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {LLM_API_KEY}",
                            "Content-Type":  "application/json",
                        },
                        json=payload,
                    )
                    resp.raise_for_status()
                    _circuit_record_success()
                    return resp.json(), model_name, None
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        last_error = f"429 Too Many Requests for model {model_name}"
                        if attempt <= LLM_MAX_RETRIES:
                            delay = _retry_delay_seconds(e.response, attempt)
                            logger.warning(
                                "LLM rate-limited for model %s; retrying in %.1fs (attempt %d/%d)",
                                model_name, delay, attempt, LLM_MAX_RETRIES,
                            )
                            time.sleep(delay)
                            continue
                        break
                    last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    logger.warning("LLM HTTP error on model %s %s: %s", model_name, e.response.status_code, e.response.text[:200])
                    break
                except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                    last_error = f"Timeout on model {model_name}: {e}"
                    logger.warning("LLM timeout on model %s: %s", model_name, e)
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.warning("LLM call failed on model %s: %s", model_name, e)
                    break

    _circuit_record_failure()
    return None, None, last_error


def request_chat_completion(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float = 30.0,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    preferred_model: str | None = None,
) -> tuple[Optional[dict], Optional[str], Optional[str]]:
    """Make a chat completion request. Runs in dedicated LLM thread pool."""
    future = _llm_executor.submit(
        _do_chat_completion,
        messages,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
        tools=tools,
        tool_choice=tool_choice,
        preferred_model=preferred_model,
    )
    return future.result(timeout=timeout + 10)


async def request_chat_completion_async(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float = 30.0,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    preferred_model: str | None = None,
) -> tuple[Optional[dict], Optional[str], Optional[str]]:
    """Async version — awaits LLM thread pool without blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _llm_executor,
        partial(
            _do_chat_completion,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            tools=tools,
            tool_choice=tool_choice,
            preferred_model=preferred_model,
        ),
    )


def call_llm(
    prompt: str,
    system_prompt: str = (
        "You are a financial market expert specialising in Indian equity markets (NSE/BSE). "
        "Always reply with valid JSON when asked."
    ),
    max_tokens: int = 300,
    temperature: float = 0.1,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Synchronous LLM call. Runs in dedicated thread pool — never blocks main thread.
    Returns response text or None on failure.
    """
    if not LLM_API_KEY:
        logger.debug("LLM_API_KEY not configured — skipping LLM call")
        return None

    if _circuit_is_open():
        logger.debug("LLM circuit breaker open — skipping call")
        return None

    response_json, model_used, error = request_chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    if not response_json:
        if error:
            logger.warning("LLM request failed across models %s: %s", get_model_candidates(), error)
        return None

    try:
        content = response_json["choices"][0]["message"].get("content")
        if content is None:
            logger.warning("LLM returned null content for model %s", model_used)
            return None
        return content.strip()
    except Exception as exc:
        logger.warning("LLM response parse failed for model %s: %s", model_used, exc)
        return None


async def call_llm_async(
    prompt: str,
    system_prompt: str = (
        "You are a financial market expert specialising in Indian equity markets (NSE/BSE). "
        "Always reply with valid JSON when asked."
    ),
    max_tokens: int = 300,
    temperature: float = 0.1,
    timeout: float = 30.0,
) -> Optional[str]:
    """
    Async LLM call — awaits dedicated thread pool, never blocks event loop.
    Use this from async route handlers.
    """
    if not LLM_API_KEY or _circuit_is_open():
        return None

    response_json, model_used, error = await request_chat_completion_async(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    if not response_json:
        if error:
            logger.warning("LLM request failed across models %s: %s", get_model_candidates(), error)
        return None

    try:
        content = response_json["choices"][0]["message"].get("content")
        if content is None:
            logger.warning("LLM returned null content for model %s", model_used)
            return None
        return content.strip()
    except Exception as exc:
        logger.warning("LLM response parse failed for model %s: %s", model_used, exc)
        return None


def extract_json(text: str) -> Optional[dict]:
    """Extract the first JSON object from an LLM response string."""
    if not text:
        return None
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
