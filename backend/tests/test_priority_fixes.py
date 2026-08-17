"""
test_priority_fixes.py
----------------------
Verifies the 4 priority fixes applied to FastTradeApp backend:
  1. AUTH_ENABLED defaults to true; no hardcoded fallback password
  2. get_risk_percentage_from_settings() reads per_trade_risk_pct, not max_portfolio_loss_pct
  3. ExecutionIntent.execution_mode column exists; intent_repo passes it through
  4. sync_zerodha_trades has no early return (dead code removed)

Run:
    cd backend
    python -m pytest tests/test_priority_fixes.py -v
"""

import os
import inspect
import sys
from pathlib import Path

# Ensure backend/app is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Fix 1 — Auth defaults
# ---------------------------------------------------------------------------

def test_auth_enabled_defaults_to_true():
    """AUTH_ENABLED env var must default to 'true', not 'false'."""
    src = Path(__file__).parent.parent / "app" / "core" / "auth.py"
    text = src.read_text()
    assert '"AUTH_ENABLED", "true"' in text, (
        "auth.py: AUTH_ENABLED default must be 'true', found 'false'"
    )


def test_no_hardcoded_admin_password_fallback():
    """_expected_password() must NOT fall back to 'admin123'."""
    src = Path(__file__).parent.parent / "app" / "core" / "auth.py"
    text = src.read_text()
    assert "admin123" not in text, (
        "auth.py: hardcoded 'admin123' fallback password still present"
    )


def test_missing_auth_password_raises_not_returns_default():
    """When AUTH_PASSWORD is unset, _expected_password must raise, not return a default."""
    original = os.environ.pop("AUTH_PASSWORD", None)
    try:
        if "app.core.auth" in sys.modules:
            del sys.modules["app.core.auth"]
        from fastapi import HTTPException
        from app.core.auth import _expected_password
        try:
            _expected_password()
            assert False, "_expected_password() should raise when AUTH_PASSWORD is unset"
        except HTTPException as e:
            assert e.status_code == 500
    finally:
        if original is not None:
            os.environ["AUTH_PASSWORD"] = original
        if "app.core.auth" in sys.modules:
            del sys.modules["app.core.auth"]


# ---------------------------------------------------------------------------
# Fix 2 — Risk % calculation uses per_trade_risk_pct, not max_portfolio_loss_pct
# ---------------------------------------------------------------------------

def test_get_risk_percentage_reads_per_trade_field():
    """get_risk_percentage_from_settings must read per_trade_risk_pct, not max_portfolio_loss_pct."""
    src = Path(__file__).parent.parent / "app" / "core" / "risk" / "tp_sl_calculator.py"
    text = src.read_text()
    assert "limits.per_trade_risk_pct" in text, (
        "tp_sl_calculator.py: must read limits.per_trade_risk_pct"
    )
    assert "limits.max_portfolio_loss_pct" not in text, (
        "tp_sl_calculator.py: must NOT read max_portfolio_loss_pct as per-trade risk"
    )


def test_risk_env_var_capped_at_10_percent():
    """RISK_PER_TRADE env values > 10 must be rejected and fall back to BALANCED (2%)."""
    os.environ["RISK_PER_TRADE"] = "12"
    for mod in list(sys.modules):
        if "tp_sl_calculator" in mod:
            del sys.modules[mod]
    import unittest.mock as mock
    with mock.patch("app.db.session.SessionLocal", side_effect=Exception("no db")):
        from app.core.risk.tp_sl_calculator import get_risk_percentage_from_settings, RISK_PROFILES
        result = get_risk_percentage_from_settings(db=None)
    assert result == RISK_PROFILES["BALANCED"], (
        f"RISK_PER_TRADE=12 should be rejected, got {result}"
    )
    del os.environ["RISK_PER_TRADE"]


def test_risk_env_var_valid_value_accepted():
    """RISK_PER_TRADE=2 (valid) must be accepted when DB is unavailable."""
    os.environ["RISK_PER_TRADE"] = "2"
    for mod in list(sys.modules):
        if "tp_sl_calculator" in mod:
            del sys.modules[mod]
    import unittest.mock as mock
    with mock.patch("app.db.session.SessionLocal", side_effect=Exception("no db")):
        from app.core.risk.tp_sl_calculator import get_risk_percentage_from_settings
        result = get_risk_percentage_from_settings(db=None)
    assert result == 2.0, f"Expected 2.0, got {result}"
    del os.environ["RISK_PER_TRADE"]


def test_models_risk_has_per_trade_risk_pct_column():
    """RiskLimitConfig model must have a per_trade_risk_pct column."""
    from app.db.models_risk import RiskLimitConfig
    assert hasattr(RiskLimitConfig, "per_trade_risk_pct"), (
        "RiskLimitConfig missing per_trade_risk_pct column"
    )


def test_per_trade_risk_pct_is_separate_from_portfolio_loss_pct():
    """per_trade_risk_pct and max_portfolio_loss_pct must be distinct columns."""
    from app.db.models_risk import RiskLimitConfig
    cols = {c.key for c in RiskLimitConfig.__table__.columns}
    assert "per_trade_risk_pct" in cols
    assert "max_portfolio_loss_pct" in cols


# ---------------------------------------------------------------------------
# Fix 3 — execution_mode column on ExecutionIntent
# ---------------------------------------------------------------------------

def test_execution_intent_has_execution_mode_column():
    """ExecutionIntent must have an execution_mode column."""
    from app.db.models_intent import ExecutionIntent
    assert hasattr(ExecutionIntent, "execution_mode"), (
        "ExecutionIntent missing execution_mode column"
    )


def test_intent_repo_accepts_execution_mode_param():
    """create_execution_intent must accept an execution_mode keyword argument."""
    from app.db.intent_repo import create_execution_intent
    sig = inspect.signature(create_execution_intent)
    assert "execution_mode" in sig.parameters, (
        "intent_repo.create_execution_intent missing execution_mode parameter"
    )


def test_intent_repo_passes_execution_mode_to_model():
    """create_execution_intent must pass execution_mode to ExecutionIntent constructor."""
    src = Path(__file__).parent.parent / "app" / "db" / "intent_repo.py"
    text = src.read_text()
    assert "execution_mode=execution_mode" in text, (
        "intent_repo.py: execution_mode not passed to ExecutionIntent"
    )


# ---------------------------------------------------------------------------
# Fix 4 — Zerodha sync dead code removed
# ---------------------------------------------------------------------------

def test_sync_zerodha_no_early_return():
    """sync_zerodha_trades must not have an early return before the kite client call."""
    src = Path(__file__).parent.parent / "app" / "api" / "routes" / "journal.py"
    text = src.read_text()
    assert "def sync_zerodha_trades" in text

    func_start = text.index("def sync_zerodha_trades")
    kite_call_pos = text.index("kite = get_kite_client()", func_start)
    func_body_before_kite = text[func_start:kite_call_pos]

    for line in func_body_before_kite.splitlines():
        stripped = line.strip()
        assert not (stripped.startswith("return") and "success" in stripped), (
            f"sync_zerodha_trades has early return before kite client: {line!r}"
        )


def test_sync_zerodha_has_holdings_logic():
    """sync_zerodha_trades must contain holdings sync logic."""
    src = Path(__file__).parent.parent / "app" / "api" / "routes" / "journal.py"
    text = src.read_text()
    assert "ZERODHA_HOLDING" in text
    assert "kite.holdings()" in text


def test_sync_zerodha_returns_full_response():
    """sync_zerodha_trades must return holdings_synced and paired_trades counts."""
    src = Path(__file__).parent.parent / "app" / "api" / "routes" / "journal.py"
    text = src.read_text()
    assert "holdings_synced" in text
    assert "paired_trades" in text


# ---------------------------------------------------------------------------
# Fix 1 (continued) — main.py router auth coverage
# ---------------------------------------------------------------------------

def _get_router_line(router_attr: str) -> str:
    src = Path(__file__).parent.parent / "app" / "main.py"
    for line in src.read_text().splitlines():
        if f"{router_attr}" in line and "include_router" in line:
            return line
    return ""


def test_main_journal_router_has_auth():
    line = _get_router_line("journal.router")
    assert line, "journal.router include_router line not found"
    assert "require_authenticated_user" in line, f"journal router missing auth: {line!r}"


def test_main_ai_chat_router_has_auth():
    line = _get_router_line("ai_chat.router")
    assert line, "ai_chat.router include_router line not found"
    assert "require_authenticated_user" in line, f"ai_chat router missing auth: {line!r}"


def test_main_watchlists_router_has_auth():
    line = _get_router_line("watchlists.router")
    assert line, "watchlists.router include_router line not found"
    assert "require_authenticated_user" in line, f"watchlists router missing auth: {line!r}"


def test_main_ml_router_has_auth():
    line = _get_router_line("ml.router")
    assert line, "ml.router include_router line not found"
    assert "require_authenticated_user" in line, f"ml router missing auth: {line!r}"


def test_main_finance_router_has_auth():
    line = _get_router_line("finance_router")
    assert line, "finance_router include_router line not found"
    assert "require_authenticated_user" in line, f"finance router missing auth: {line!r}"


def test_main_alerts_router_has_auth():
    line = _get_router_line("alerts.router")
    assert line, "alerts.router include_router line not found"
    assert "require_authenticated_user" in line, f"alerts router missing auth: {line!r}"
