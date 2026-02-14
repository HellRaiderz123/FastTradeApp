"""
Train stock ML model for the terminal.

Usage:
  python train_stock_ml.py --symbols RELIANCE TCS INFY --timeframe daily
"""

import argparse
from app.db.session import SessionLocal
from app.core.ml.config import StockMLConfig
from app.core.ml.stock_model import train_stock_model


def main():
    parser = argparse.ArgumentParser(description="Train stock ML model")
    parser.add_argument("--symbols", nargs="*", required=True, help="Symbols to include")
    parser.add_argument("--timeframe", default="daily", help="daily or 15minute")
    args = parser.parse_args()

    config = StockMLConfig(timeframe=args.timeframe)

    db = SessionLocal()
    try:
        metadata = train_stock_model(db, [s.upper() for s in args.symbols], config)
        print("✅ ML model trained")
        print(metadata)
    finally:
        db.close()


if __name__ == "__main__":
    main()
