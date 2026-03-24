"""
Zerodha Auto-Login Service
Automates the browser OAuth flow using Playwright:
  1. Opens Zerodha login page headlessly
  2. Fills in user_id + password + TOTP (if configured)
  3. Captures the request_token from the redirect URL
  4. Exchanges it for an access_token and saves to DB + .env

Requirements (add to requirements.txt):
    playwright>=1.40.0

First-time setup (run once inside container):
    playwright install chromium --with-deps

Env vars needed in .env:
    ZERODHA_USER_ID       — your Zerodha client ID (e.g. AB1234)
    ZERODHA_PASSWORD      — your Zerodha login password
    ZERODHA_TOTP_SECRET   — your TOTP secret key (from Zerodha 2FA setup)
                            Get this when enabling 2FA: it shows a secret key
                            you can use with pyotp instead of Google Authenticator
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

import pyotp

logger = logging.getLogger(__name__)

KITE_LOGIN_URL = "https://kite.zerodha.com/connect/login?v=3&api_key={api_key}"
KITE_LOGIN_PAGE = "https://kite.zerodha.com"


def _get_totp() -> Optional[str]:
    secret = os.getenv("ZERODHA_TOTP_SECRET", "").strip()
    if not secret:
        return None
    try:
        return pyotp.TOTP(secret).now()
    except Exception as e:
        logger.error(f"❌ TOTP generation failed: {e}")
        return None


def _save_token_to_env(access_token: str):
    """Update ZERODHA_ACCESS_TOKEN in backend/.env so it survives restarts."""
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
        if "ZERODHA_ACCESS_TOKEN=" in text:
            text = re.sub(
                r"^ZERODHA_ACCESS_TOKEN=.*$",
                f"ZERODHA_ACCESS_TOKEN={access_token}",
                text,
                flags=re.MULTILINE,
            )
        else:
            text += f"\nZERODHA_ACCESS_TOKEN={access_token}\n"
        env_path.write_text(text, encoding="utf-8")
        logger.info("✅ ZERODHA_ACCESS_TOKEN updated in .env")
    except Exception as e:
        logger.warning(f"⚠️  Could not update .env: {e}")


def run_auto_login(db) -> Optional[str]:
    """
    Run the full Zerodha auto-login flow.
    Returns the new access_token on success, None on failure.
    """
    api_key = os.getenv("ZERODHA_API_KEY", "").strip()
    user_id = os.getenv("ZERODHA_USER_ID", "").strip()
    password = os.getenv("ZERODHA_PASSWORD", "").strip()

    if not all([api_key, user_id, password]):
        logger.error(
            "❌ Auto-login requires ZERODHA_API_KEY, ZERODHA_USER_ID, ZERODHA_PASSWORD in .env"
        )
        return None

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error("❌ Playwright not installed. Run: pip install playwright && playwright install chromium --with-deps")
        return None

    request_token = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            login_url = KITE_LOGIN_URL.format(api_key=api_key)
            logger.info(f"🌐 Opening Zerodha login: {login_url}")
            page.goto(login_url, timeout=30000)

            # Fill user ID
            page.wait_for_selector('input[type="text"]', timeout=15000)
            page.fill('input[type="text"]', user_id)

            # Fill password
            page.fill('input[type="password"]', password)

            # Click login
            page.click('button[type="submit"]')

            # Handle TOTP / PIN screen
            try:
                page.wait_for_selector('input[type="number"], input[label="External TOTP"]', timeout=10000)
                totp = _get_totp()
                if totp:
                    logger.info("🔐 Entering TOTP...")
                    page.fill('input[type="number"]', totp)
                    page.click('button[type="submit"]')
                else:
                    logger.warning("⚠️  TOTP screen appeared but ZERODHA_TOTP_SECRET not set")
                    browser.close()
                    return None
            except PWTimeout:
                # No TOTP screen — that's fine, continue
                pass

            # Wait for redirect to our redirect_url containing request_token
            try:
                page.wait_for_url(
                    re.compile(r"request_token="),
                    timeout=20000,
                )
                final_url = page.url
                match = re.search(r"request_token=([^&]+)", final_url)
                if match:
                    request_token = match.group(1)
                    logger.info(f"✅ Got request_token: {request_token[:8]}...")
            except PWTimeout:
                logger.error(f"❌ Timed out waiting for redirect. Current URL: {page.url}")

            browser.close()

    except Exception as e:
        logger.error(f"❌ Auto-login browser error: {e}", exc_info=True)
        return None

    if not request_token:
        return None

    # Exchange request_token → access_token
    try:
        from app.core.broker.zerodha.oauth import exchange_request_token_for_access_token
        from app.core.broker.zerodha import client as kite_client_module

        access_token = exchange_request_token_for_access_token(db, request_token)
        if access_token:
            # Update os.environ so current process uses new token immediately
            os.environ["ZERODHA_ACCESS_TOKEN"] = access_token
            # Persist to .env for next restart
            _save_token_to_env(access_token)
            # Reset cached kite client so it picks up new token
            kite_client_module._kite = None
            logger.info("✅ Zerodha auto-login complete — new access token active")
            return access_token
        else:
            logger.error("❌ Token exchange failed")
            return None
    except Exception as e:
        logger.error(f"❌ Token exchange error: {e}", exc_info=True)
        return None
