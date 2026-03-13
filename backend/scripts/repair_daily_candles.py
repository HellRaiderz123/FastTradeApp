from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Tuple
from datetime import date

from dotenv import load_dotenv


def _bootstrap() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    load_dotenv(backend_dir / ".env", override=False)


_bootstrap()

from app.db.models_candles import CandleDaily  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.core.market.candles import fetch_daily_candles  # noqa: E402


def _pct_diff(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        return 1e9
    return abs(a - b) / ((a + b) / 2.0)


def _detect_spikes(
    db,
    symbols: List[str] | None,
    spike_ratio: float,
    neighbor_tolerance: float,
) -> List[Tuple[str, str, float, float, float]]:
    query = db.query(CandleDaily).order_by(CandleDaily.symbol.asc(), CandleDaily.date.asc())
    if symbols:
        query = query.filter(CandleDaily.symbol.in_([s.upper() for s in symbols]))
    rows = query.all()

    grouped = {}
    for row in rows:
        grouped.setdefault(row.symbol, []).append(row)

    spikes: List[Tuple[str, str, float, float, float]] = []
    for symbol, candles in grouped.items():
        if len(candles) < 3:
            continue
        for i in range(1, len(candles) - 1):
            prev_row = candles[i - 1]
            row = candles[i]
            next_row = candles[i + 1]

            prev_close = float(prev_row.close or 0)
            curr_close = float(row.close or 0)
            next_close = float(next_row.close or 0)
            if prev_close <= 0 or curr_close <= 0 or next_close <= 0:
                continue

            ratio_prev = max(curr_close / prev_close, prev_close / curr_close)
            ratio_next = max(curr_close / next_close, next_close / curr_close)
            neighbors_similar = _pct_diff(prev_close, next_close) <= neighbor_tolerance

            if ratio_prev >= spike_ratio and ratio_next >= spike_ratio and neighbors_similar:
                spikes.append((
                    symbol,
                    str(row.date),
                    prev_close,
                    curr_close,
                    next_close,
                ))

    return spikes


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect and repair corrupted daily candle spikes.")
    parser.add_argument("--symbols", nargs="*", default=None, help="Optional symbols to limit scan (e.g., LT ICICIBANK)")
    parser.add_argument("--spike-ratio", type=float, default=3.0, help="Min ratio vs prev and next close to classify a spike")
    parser.add_argument("--neighbor-tolerance", type=float, default=0.2, help="Max relative diff between prev and next closes")
    parser.add_argument("--mode", choices=["interpolate", "delete"], default="interpolate")
    parser.add_argument("--apply", action="store_true", help="Actually delete detected spikes")
    parser.add_argument("--refetch-days", type=int, default=30, help="If apply, attempt backfill this many days for affected symbols")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        spikes = _detect_spikes(
            db,
            symbols=args.symbols,
            spike_ratio=max(args.spike_ratio, 1.5),
            neighbor_tolerance=max(args.neighbor_tolerance, 0.0),
        )

        print(f"Detected spikes: {len(spikes)}")
        for symbol, dt, prev_close, curr_close, next_close in spikes:
            print(f"{symbol} {dt} prev={prev_close:.2f} curr={curr_close:.2f} next={next_close:.2f}")

        if not args.apply or not spikes:
            print("Dry-run only. Use --apply to delete spikes.")
            return 0

        affected = sorted({symbol for symbol, *_ in spikes})
        for symbol, dt, prev_close, curr_close, next_close in spikes:
            dt_obj = date.fromisoformat(dt)
            row = (
                db.query(CandleDaily)
                .filter(CandleDaily.symbol == symbol, CandleDaily.date == dt_obj)
                .first()
            )
            if not row:
                continue

            if args.mode == "delete":
                deleted = (
                    db.query(CandleDaily)
                    .filter(CandleDaily.symbol == symbol, CandleDaily.date == dt_obj)
                    .delete()
                )
                if deleted:
                    print(f"Deleted {symbol} {dt}")
                continue

            prev_row = (
                db.query(CandleDaily)
                .filter(CandleDaily.symbol == symbol, CandleDaily.date < dt_obj)
                .order_by(CandleDaily.date.desc())
                .first()
            )
            next_row = (
                db.query(CandleDaily)
                .filter(CandleDaily.symbol == symbol, CandleDaily.date > dt_obj)
                .order_by(CandleDaily.date.asc())
                .first()
            )

            if not prev_row or not next_row:
                print(f"Skip interpolation {symbol} {dt}: missing neighbor rows")
                continue

            prev_c = float(prev_row.close or prev_close)
            next_c = float(next_row.close or next_close)
            corrected_close = (prev_c + next_c) / 2.0
            corrected_open = prev_c
            corrected_high = max(prev_c, next_c, corrected_close)
            corrected_low = min(prev_c, next_c, corrected_close)
            prev_v = float(prev_row.volume or 0.0)
            next_v = float(next_row.volume or 0.0)
            corrected_volume = (prev_v + next_v) / 2.0 if (prev_v > 0 and next_v > 0) else max(prev_v, next_v, 1.0)

            row.open = corrected_open
            row.high = corrected_high
            row.low = corrected_low
            row.close = corrected_close
            row.volume = corrected_volume
            print(
                f"Interpolated {symbol} {dt}: {curr_close:.2f} -> {corrected_close:.2f} "
                f"(neighbors {prev_c:.2f}, {next_c:.2f})"
            )

        db.commit()

        if args.mode == "delete":
            for symbol in affected:
                try:
                    fetch_daily_candles(db, symbol, days=max(5, int(args.refetch_days)))
                    print(f"Refetch attempted: {symbol}")
                except Exception as exc:
                    db.rollback()
                    print(f"Refetch failed for {symbol}: {exc}")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())