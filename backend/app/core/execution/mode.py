"""
Execution mode — broker-agnostic.

Modes:
  LIVE          — real orders via the active broker
  DRY_RUN       — builds and logs orders but does not send them
  PAPER_TRADING — simulates fills using live LTP, no broker involved
  BACKTEST      — historical simulation

The active broker (ZERODHA / INDMONEY / …) is determined separately
by ACTIVE_BROKER env var via app.core.broker.registry.get_active_broker().

Legacy mode strings like ZERODHA_LIVE / ZERODHA_DRY_RUN are accepted
as aliases so existing .env files and DB records keep working.
"""

import os

VALID_MODES = {"LIVE", "DRY_RUN", "PAPER_TRADING", "BACKTEST"}

# Legacy aliases — kept for backward compatibility with existing .env / DB values
_ALIASES = {
    # Old Zerodha-prefixed names
    "ZERODHA_LIVE":     "LIVE",
    "ZERODHA_DRY_RUN":  "DRY_RUN",
    "ZERODHA_PAPER":    "DRY_RUN",
    "ZERODHA":          "DRY_RUN",
    # Old INDMoney-prefixed names (in case anyone set these)
    "INDMONEY_LIVE":    "LIVE",
    "INDMONEY_DRY_RUN": "DRY_RUN",
    # Short aliases
    "PAPER":            "PAPER_TRADING",
    "PAPERTRADE":       "PAPER_TRADING",
    "PAPER_TRADE":      "PAPER_TRADING",
    "DRY":              "DRY_RUN",
    "LIVE_TRADING":     "LIVE",
}


def normalize_execution_mode(mode: str | None) -> str:
    m = (mode or "").strip().upper()
    # Resolve alias first
    resolved = _ALIASES.get(m, m)
    if resolved in VALID_MODES:
        return resolved
    # Unknown → safe default
    return "DRY_RUN"


def get_execution_mode() -> str:
    return normalize_execution_mode(os.getenv("EXECUTION_MODE"))


def is_live_mode(mode: str | None = None) -> bool:
    return normalize_execution_mode(mode) == "LIVE"


def is_paper_mode(mode: str | None = None) -> bool:
    return normalize_execution_mode(mode) in {"PAPER_TRADING", "BACKTEST"}


def is_dry_run(mode: str | None = None) -> bool:
    return normalize_execution_mode(mode) == "DRY_RUN"


# Legacy alias kept for callers that check is_zerodha_dry_run()
def is_zerodha_dry_run(mode: str | None = None) -> bool:
    return is_dry_run(mode)
