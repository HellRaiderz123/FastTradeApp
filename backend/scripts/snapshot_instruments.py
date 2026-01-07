"""Save a dated Zerodha instruments snapshot.

Why this exists
- Options backtests need instrument_token resolution for a given option tradingsymbol.
- Zerodha's *current* instruments dump often does NOT include expired contracts.
- Saving daily snapshots allows older backtests to resolve tokens reliably.

Usage (PowerShell)
- python backend/scripts/snapshot_instruments.py
- python backend/scripts/snapshot_instruments.py --date 2026-01-07

Env
- FASTTRADE_INSTRUMENTS_SNAPSHOT_DIR (optional): override snapshot directory
"""

from __future__ import annotations

import argparse
from datetime import date

from app.core.broker.zerodha.instruments import save_instruments_snapshot


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", dest="asof", type=str, default=None)
    parser.add_argument("--exchange", dest="exchange", type=str, default="NFO")
    args = parser.parse_args()

    asof_date = date.fromisoformat(args.asof) if args.asof else None
    path = save_instruments_snapshot(asof=asof_date, exchange=args.exchange)
    print(str(path))


if __name__ == "__main__":
    main()
