"""
Backfill daily candle data from Zerodha into candles_daily.

Usage:
  python refresh_daily_candles.py
  python refresh_daily_candles.py --symbols RELIANCE SBIN
  python refresh_daily_candles.py --days 600
"""

import argparse
from app.db.session import SessionLocal
from app.db.models_candles import CandleDaily
from app.core.market.candles import fetch_daily_candles

DEFAULT_SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "BHARTIARTL",
    "KOTAKBANK",
    "ITC",
    "HINDUNILVR",
]


def main():
    parser = argparse.ArgumentParser(description="Refresh daily candles from Zerodha")
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS, help="Symbols to fetch")
    parser.add_argument("--days", type=int, default=500, help="Days of history to fetch")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("=" * 70)
        print("🔄 REFRESHING DAILY CANDLE DATA")
        print("=" * 70)
        print(f"Symbols: {', '.join(args.symbols)}")
        print(f"Days: {args.days}")
        print()

        for symbol in args.symbols:
            current_count = db.query(CandleDaily).filter(CandleDaily.symbol == symbol).count()
            print(f"{symbol}: current candles = {current_count}")

            try:
                fetch_daily_candles(db, symbol, days=args.days)
            except Exception as exc:
                print(f"❌ {symbol}: fetch failed: {exc}")
                continue

            new_count = db.query(CandleDaily).filter(CandleDaily.symbol == symbol).count()
            added = new_count - current_count
            print(f"✅ {symbol}: added {added} candles (total {new_count})")
            print()

        print("=" * 70)
        print("✅ Daily candles refresh complete")
        print("=" * 70)
    finally:
        db.close()


if __name__ == "__main__":
    main()
