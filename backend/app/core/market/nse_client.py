"""
nse_client.py — Shared NSE HTTP session manager.

NSE requires:
  1. Visit nseindia.com homepage first to get session cookies (bm_sv, nsit, nseappid, etc.)
  2. Pass those cookies on every subsequent API call
  3. Refresh the session every ~5 minutes (Akamai bot protection expires it)

All NSE callers (fii_dii, nse_news_service, indian_market_data_service, vix) should
use get_nse_session() / nse_get() instead of managing their own cookies.

Provides both sync (requests) and async (httpx) interfaces.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urljoin

import requests as _req

logger = logging.getLogger(__name__)

NSE_HOME = "https://www.nseindia.com/"
SESSION_TTL_SECONDS = 270  # refresh every 4.5 minutes

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nseindia.com/",
}

# ── Sync session (requests) ──────────────────────────────────────────────────

class _NSESyncSession:
    """Thread-safe singleton sync session for NSE."""

    def __init__(self) -> None:
        self._session: Optional[_req.Session] = None
        self._refreshed_at: float = 0.0
        self._lock = threading.Lock()

    def _needs_refresh(self) -> bool:
        return time.monotonic() - self._refreshed_at > SESSION_TTL_SECONDS

    def _do_refresh(self) -> None:
        try:
            if self._session is None:
                self._session = _req.Session()
                self._session.headers.update(NSE_HEADERS)
            r = self._session.get(NSE_HOME, timeout=10)
            # Accept 200 or 403 — even a 403 may set cookies that unlock API calls
            self._refreshed_at = time.monotonic()
            if r.status_code == 200:
                logger.info("nse_client: sync session refreshed (cookies: %s)", list(self._session.cookies.keys()))
            else:
                logger.debug("nse_client: homepage returned %s (cookies may still be set)", r.status_code)
        except Exception as e:
            logger.warning("nse_client: sync session refresh failed: %s", e)

    def get(self, url: str, **kwargs) -> _req.Response:
        """GET with automatic session refresh. Retries once on 401/403."""
        with self._lock:
            if self._needs_refresh() or self._session is None:
                self._do_refresh()

        assert self._session is not None
        kwargs.setdefault("timeout", 20)
        r = self._session.get(url, **kwargs)

        if r.status_code in (401, 403):
            # Cookie expired mid-session — refresh and retry once
            logger.info("nse_client: got %s, refreshing session and retrying %s", r.status_code, url)
            with self._lock:
                self._do_refresh()
            r = self._session.get(url, **kwargs)

        return r

    def get_with_referer(self, url: str, referer: str, **kwargs) -> _req.Response:
        """GET with a specific Referer header (needed for some NSE endpoints)."""
        headers = kwargs.pop("headers", {})
        headers["Referer"] = referer
        return self.get(url, headers=headers, **kwargs)


_sync_session = _NSESyncSession()


def nse_get(url: str, referer: Optional[str] = None, **kwargs) -> _req.Response:
    """
    Shared sync NSE GET. Handles session cookies automatically.

    Usage:
        from app.core.market.nse_client import nse_get
        r = nse_get("https://www.nseindia.com/api/fiidiiTradeReact")
    """
    if referer:
        return _sync_session.get_with_referer(url, referer, **kwargs)
    return _sync_session.get(url, **kwargs)


def nse_get_json(url: str, referer: Optional[str] = None, **kwargs) -> Any:
    """GET and parse JSON. Returns None on error."""
    try:
        r = nse_get(url, referer=referer, **kwargs)
        if r.status_code == 200:
            return r.json()
        logger.warning("nse_client: %s returned %s", url, r.status_code)
    except Exception as e:
        logger.warning("nse_client: nse_get_json failed for %s: %s", url, e)
    return None


# ── Async session (httpx) ────────────────────────────────────────────────────

try:
    import httpx as _httpx

    class _NSEAsyncSession:
        """Async NSE session for use in FastAPI async endpoints."""

        def __init__(self) -> None:
            self._client: Optional[_httpx.AsyncClient] = None
            self._refreshed_at: float = 0.0
            self._lock: Optional[Any] = None  # asyncio.Lock — created lazily

        def _needs_refresh(self) -> bool:
            return time.monotonic() - self._refreshed_at > SESSION_TTL_SECONDS

        async def _get_lock(self):
            import asyncio
            if self._lock is None:
                self._lock = asyncio.Lock()
            return self._lock

        async def _ensure_client(self) -> _httpx.AsyncClient:
            if self._client is None or self._client.is_closed:
                self._client = _httpx.AsyncClient(
                    headers=NSE_HEADERS,
                    timeout=_httpx.Timeout(20.0),
                    follow_redirects=True,
                )
                self._refreshed_at = 0.0
            return self._client

        async def _do_refresh(self) -> None:
            try:
                client = await self._ensure_client()
                r = await client.get(NSE_HOME)
                if r.status_code == 200:
                    self._refreshed_at = time.monotonic()
                    logger.info("nse_client: async session refreshed")
                else:
                    logger.warning("nse_client: async homepage returned %s", r.status_code)
            except Exception as e:
                logger.warning("nse_client: async session refresh failed: %s", e)

        async def get(self, url: str, **kwargs) -> _httpx.Response:
            lock = await self._get_lock()
            async with lock:
                if self._needs_refresh():
                    await self._do_refresh()
            client = await self._ensure_client()
            kwargs.setdefault("timeout", 20.0)
            r = await client.get(url, **kwargs)
            if r.status_code in (401, 403):
                async with lock:
                    await self._do_refresh()
                r = await client.get(url, **kwargs)
            return r

        async def close(self) -> None:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None

    _async_session = _NSEAsyncSession()

    async def nse_async_get(url: str, **kwargs) -> _httpx.Response:
        """Shared async NSE GET."""
        return await _async_session.get(url, **kwargs)

    async def nse_async_get_json(url: str, **kwargs) -> Any:
        """Async GET and parse JSON. Returns None on error."""
        try:
            r = await nse_async_get(url, **kwargs)
            if r.status_code == 200:
                return r.json()
            logger.warning("nse_client: async %s returned %s", url, r.status_code)
        except Exception as e:
            logger.warning("nse_client: nse_async_get_json failed for %s: %s", url, e)
        return None

except ImportError:
    logger.warning("nse_client: httpx not available, async NSE calls disabled")
