"""
backfill_candles.py
--------------------
Bulk-ingest historical candles for all deduped_stocks symbols into the
FastTrade PostgreSQL DB using the existing candles.py fetchers.

Zerodha max lookback:
  day      -> 2000 days
  15minute -> 200  days
  5minute  -> 100  days

Usage:
  python scripts/backfill_candles.py                  # all timeframes
  python scripts/backfill_candles.py --tf day         # daily only
  python scripts/backfill_candles.py --tf 5min 15min  # intraday only
  python scripts/backfill_candles.py --symbols RELIANCE INFY  # specific symbols
  python scripts/backfill_candles.py --resume         # skip symbols already in DB
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# ── bootstrap ────────────────────────────────────────────────────────────────
BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT    = BACKEND_DIR.parent

# Allow override via env var (used inside Docker)
_deduped_env = os.environ.get("DEDUPED_STOCKS_PATH")
if _deduped_env:
    DEDUPED_PATH = Path(_deduped_env)
else:
    DEDUPED_PATH = REPO_ROOT / "project_full_trading" / "docs" / "references" / "deduped_stocks.txt"
    # Docker: file is mounted at /tmp/deduped_stocks.txt
    if not DEDUPED_PATH.exists():
        DEDUPED_PATH = Path("/tmp/deduped_stocks.txt")

sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env", override=False)

from app.db.session import SessionLocal                          # noqa: E402
from app.core.market.candles import (                           # noqa: E402
    fetch_daily_candles,
    fetch_5m_candles,
    fetch_15m_candles,
)

# ── config ───────────────────────────────────────────────────────────────────
TIMEFRAMES = {
    "day":   (fetch_daily_candles, 2000),
    "15min": (fetch_15m_candles,   200),
    "5min":  (fetch_5m_candles,    100),
}

# Zerodha allows ~3 historical API calls/second; stay well under that
DELAY_BETWEEN_CALLS = 0.5   # seconds between each symbol+timeframe call
DELAY_BETWEEN_SYMBOLS = 1.0 # extra pause after all timeframes for one symbol


def load_symbols() -> list[str]:
    if not DEDUPED_PATH.exists():
        print(f"[ERROR] deduped_stocks.txt not found at {DEDUPED_PATH}")
        sys.exit(1)
    txt = DEDUPED_PATH.read_text(encoding="utf-8")
    symbols = re.findall(r'"([A-Z0-9\-&]+)"', txt)
    # deduplicate while preserving order
    seen: set[str] = set()
    unique = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def symbols_in_db(db, timeframe: str) -> set[str]:
    """Return set of symbols that already have at least one row for this timeframe."""
    from app.db.models_candles import Candle5m, Candle15m, CandleDaily
    model_map = {"day": CandleDaily, "15min": Candle15m, "5min": Candle5m}
    model = model_map.get(timeframe)
    if model is None:
        return set()
    try:
        rows = db.query(model.symbol).distinct().all()
        return {r[0] for r in rows}
    except Exception:
        return set()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill candles for all deduped stocks")
    parser.add_argument("--tf", nargs="+", choices=list(TIMEFRAMES), default=list(TIMEFRAMES),
                        help="Timeframes to backfill (default: all)")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Override symbol list (default: all from deduped_stocks.txt)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip symbols that already have data in DB for that timeframe")
    args = parser.parse_args()

    all_symbols = args.symbols if args.symbols else load_symbols()
    selected_tfs = args.tf

    print(f"Symbols  : {len(all_symbols)}")
    print(f"Timeframes: {selected_tfs}")
    print(f"Resume   : {args.resume}")
    print("=" * 60)

    db = SessionLocal()
    existing: dict[str, set[str]] = {}
    if args.resume:
        for tf in selected_tfs:
            existing[tf] = symbols_in_db(db, tf)
            print(f"  [{tf}] already in DB: {len(existing[tf])} symbols")

    total = len(all_symbols)
    failed: list[str] = []

    for idx, symbol in enumerate(all_symbols, 1):
        print(f"\n[{idx}/{total}] {symbol}")

        for tf in selected_tfs:
            if args.resume and symbol in existing.get(tf, set()):
                print(f"  {tf:6s} SKIP (already in DB)")
                continue

            fetcher, days = TIMEFRAMES[tf]
            try:
                fetcher(db, symbol, days=days)
                print(f"  {tf:6s} OK")
            except Exception as e:
                err = str(e)[:80]
                print(f"  {tf:6s} FAIL — {err}")
                failed.append(f"{symbol}/{tf}: {err}")

            time.sleep(DELAY_BETWEEN_CALLS)

        time.sleep(DELAY_BETWEEN_SYMBOLS)

    db.close()

    print("\n" + "=" * 60)
    print(f"Done. {total} symbols processed.")
    if failed:
        print(f"Failed ({len(failed)}):")
        for f in failed:
            print(f"  {f}")
    else:
        print("All symbols ingested successfully.")


if __name__ == "__main__":
    main()
