"""
Shared LLM client — reads NVIDIA / Groq / OpenAI config from environment.

Used by:
  - twitter_service.py  (LLM sentiment analysis)
  - rss_feed_service.py (news impact scoring)
  - condition_scanner.py (strategy explainer)

Config (set in .env):
  LLM_PROVIDER  = custom | groq | openai
  LLM_API_KEY   = nvapi-... / gsk_... / sk-...
  LLM_BASE_URL  = https://integrate.api.nvidia.com/v1
  LLM_MODEL     = mistralai/mistral-small-4-119b-2603
"""

import os
import json
import logging
import re
import threading
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

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

_llm_request_lock = threading.Lock()
_llm_next_request_at = 0.0


def is_available() -> bool:
    """Return True if an LLM API key is configured."""
    return bool(LLM_API_KEY)


def get_model_candidates(preferred_model: str | None = None) -> list[str]:
    candidates: list[str] = []
    for model in [preferred_model, LLM_MODEL, *LLM_MODEL_FALLBACKS]:
        clean = str(model or "").strip()
        if clean and clean not in candidates:
            candidates.append(clean)
    return candidates or [LLM_MODEL]


def _maybe_wait_for_rate_limit() -> None:
    global _llm_next_request_at

    if LLM_MIN_INTERVAL_SEC <= 0:
        return

    now = time.monotonic()
    wait_for = _llm_next_request_at - now
    if wait_for > 0:
        time.sleep(wait_for)
    _llm_next_request_at = time.monotonic() + LLM_MIN_INTERVAL_SEC


def _retry_delay_seconds(response: httpx.Response, attempt: int) -> float:
    retry_after = (response.headers.get("Retry-After") or "").strip()
    if retry_after:
        try:
            return max(float(retry_after), LLM_RETRY_BASE_DELAY_SEC)
        except ValueError:
            pass
    return LLM_RETRY_BASE_DELAY_SEC * (2 ** max(0, attempt - 1))


def request_chat_completion(
    messages: list[dict[str, Any]],
    *,
    max_tokens: int | None = None,
    temperature: float | None = None,
    timeout: float = 15.0,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any | None = None,
    preferred_model: str | None = None,
) -> tuple[Optional[dict], Optional[str], Optional[str]]:
    """Make an OpenAI-compatible chat completion request with model fallback support."""
    if not LLM_API_KEY:
        return None, None, "LLM_API_KEY not configured"

    last_error: str | None = None

    with httpx.Client(timeout=timeout) as client:
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
                    with _llm_request_lock:
                        _maybe_wait_for_rate_limit()
                        resp = client.post(
                            f"{LLM_BASE_URL}/chat/completions",
                            headers={
                                "Authorization": f"Bearer {LLM_API_KEY}",
                                "Content-Type":  "application/json",
                            },
                            json=payload,
                        )

                    resp.raise_for_status()
                    return resp.json(), model_name, None
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        last_error = f"429 Too Many Requests for model {model_name}"
                        if attempt <= LLM_MAX_RETRIES:
                            delay = _retry_delay_seconds(e.response, attempt)
                            logger.warning(
                                "LLM rate-limited for model %s; retrying in %.1fs (attempt %d/%d)",
                                model_name,
                                delay,
                                attempt,
                                LLM_MAX_RETRIES,
                            )
                            time.sleep(delay)
                            continue

                        logger.warning(
                            "LLM model %s exhausted retries after rate limiting; trying fallback model if configured",
                            model_name,
                        )
                        break

                    last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                    logger.warning("LLM HTTP error on model %s %s: %s", model_name, e.response.status_code, e.response.text[:200])
                    break
                except Exception as e:
                    last_error = str(e)
                    logger.warning("LLM call failed on model %s: %s", model_name, e)
                    break

    return None, None, last_error


def call_llm(
    prompt: str,
    system_prompt: str = (
        "You are a financial market expert specialising in Indian equity markets (NSE/BSE). "
        "Always reply with valid JSON when asked."
    ),
    max_tokens: int = 300,
    temperature: float = 0.1,
    timeout: float = 15.0,
) -> Optional[str]:
    """
    Synchronous LLM call. Returns response text or None on failure.

    Uses the provider configured via LLM_PROVIDER / LLM_BASE_URL env vars
    (defaults to NVIDIA NIM which is already configured in this project).
    """
    if not LLM_API_KEY:
        logger.debug("LLM_API_KEY not configured — skipping LLM call")
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
        return response_json["choices"][0]["message"]["content"].strip()
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
