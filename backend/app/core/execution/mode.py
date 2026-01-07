import os


VALID_MODES = {"ZERODHA_LIVE", "ZERODHA_DRY_RUN", "PAPER_TRADING", "BACKTEST"}


def normalize_execution_mode(mode: str | None) -> str:
    m = (mode or "").strip().upper()
    # Backward-compatible aliases
    if m in {"PAPER", "PAPERTRADE", "PAPER_TRADE"}:
        return "PAPER_TRADING"
    if m in {"DRY_RUN", "ZERODHA_PAPER", "ZERODHA"}:
        return "ZERODHA_DRY_RUN"
    if m == "LIVE":
        return "ZERODHA_LIVE"
    if m == "":
        return "ZERODHA_DRY_RUN"
    if m not in VALID_MODES:
        # Default safely to dry-run
        return "ZERODHA_DRY_RUN"
    return m


def get_execution_mode() -> str:
    return normalize_execution_mode(os.getenv("EXECUTION_MODE"))


def is_live_mode(mode: str | None = None) -> bool:
    return normalize_execution_mode(mode) == "ZERODHA_LIVE"


def is_paper_mode(mode: str | None = None) -> bool:
    return normalize_execution_mode(mode) in {"PAPER_TRADING", "BACKTEST"}


def is_zerodha_dry_run(mode: str | None = None) -> bool:
    return normalize_execution_mode(mode) == "ZERODHA_DRY_RUN"
