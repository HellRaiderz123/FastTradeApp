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
from typing import Optional

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


def is_available() -> bool:
    """Return True if an LLM API key is configured."""
    return bool(LLM_API_KEY)


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

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {LLM_API_KEY}",
                    "Content-Type":  "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as e:
        logger.warning("LLM HTTP error %s: %s", e.response.status_code, e.response.text[:200])
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
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
