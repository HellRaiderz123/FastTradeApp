import logging
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.broker.zerodha.client import get_kite_client

logger = logging.getLogger(__name__)

INDEX_TOKENS = {
    "NIFTY": 256265,
    "BANKNIFTY": 260105,
    "FINNIFTY": 257801,
    "NIFTY_IT": 259849,    # NIFTY IT index (NSE token)
    "NIFTYIT": 259849,     # Alias
    "NIFTYVIX": 264969,    # India VIX (Zerodha)
}



@lru_cache(maxsize=4)
def _load_live_instruments(exchange: str = "NFO") -> pd.DataFrame:
    """Load instruments from Zerodha API (live)."""
    try:
        kite = get_kite_client()
        instruments = kite.instruments(exchange)
        logger.info(f"✅ Loaded {len(instruments)} {exchange} instruments from Zerodha")
        return pd.DataFrame(instruments)
    except Exception as e:
        logger.warning(f"⚠️  Could not load instruments ({e}), using empty fallback")
        return pd.DataFrame(columns=[
            "instrument_token", "name", "strike", "instrument_type",
            "expiry", "segment", "tradingsymbol", "lot_size"
        ])


def _snapshot_dir() -> Path:
    # Allow override via env; otherwise default to backend/data/instruments_snapshots
    override = os.environ.get("FASTTRADE_INSTRUMENTS_SNAPSHOT_DIR")
    if override:
        return Path(override)
    # instruments.py is backend/app/core/broker/zerodha/instruments.py
    return Path(__file__).resolve().parents[4] / "data" / "instruments_snapshots"


def _snapshot_path(exchange: str, asof: date) -> Path:
    return _snapshot_dir() / f"{exchange.upper()}_{asof.isoformat()}.csv"


def save_instruments_snapshot(asof: Optional[date] = None, exchange: str = "NFO") -> Path:
    """Fetch live instruments and save to a dated snapshot CSV.

    This enables options backtests for older dates, because expired contracts are
    often absent from the *current* instruments dump.
    """
    asof = asof or date.today()
    snap_dir = _snapshot_dir()
    snap_dir.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(exchange, asof)

    df = _load_live_instruments(exchange)
    df.to_csv(path, index=False)
    logger.info(f"✅ Saved instruments snapshot: {path}")
    return path


def _find_best_snapshot(exchange: str, asof: date) -> Optional[Path]:
    snap_dir = _snapshot_dir()
    if not snap_dir.exists():
        return None

    prefix = f"{exchange.upper()}_"
    candidates = []
    for p in snap_dir.glob(f"{prefix}*.csv"):
        try:
            d = date.fromisoformat(p.stem.replace(prefix, ""))
        except Exception:
            continue
        if d <= asof:
            candidates.append((d, p))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


@lru_cache(maxsize=8)
def _load_snapshot_csv(path_str: str) -> pd.DataFrame:
    path = Path(path_str)
    df = pd.read_csv(path)
    logger.info(f"✅ Loaded instruments snapshot: {path} rows={len(df)}")
    return df


def load_instruments(exchange: str = "NFO", asof_date: Optional[date] = None) -> pd.DataFrame:
    """Load instruments.

    - If asof_date is provided, prefer the latest snapshot <= asof_date.
    - Otherwise, fall back to live Zerodha instruments (cached).

    Note: Without historical snapshots, you generally cannot resolve instrument_token
    for expired option contracts when backtesting old years.
    """
    if asof_date is not None:
        snap = _find_best_snapshot(exchange, asof_date)
        if snap is not None:
            return _load_snapshot_csv(str(snap))
        logger.warning(
            f"⚠️ No instruments snapshot found for {exchange} asof {asof_date}. Falling back to live instruments."
        )

    # Live instruments fetch is cached via lru_cache on _load_live_instruments
    return _load_live_instruments(exchange)

def get_index_token(index: str) -> int:
    return INDEX_TOKENS[index]


def get_equity_token(symbol: str, exchange: str = "NSE") -> int:
    symbol = symbol.upper().strip()
    instruments = load_instruments(exchange=exchange)
    if instruments.empty:
        raise KeyError(f"No instruments available for exchange {exchange}")

    if "tradingsymbol" not in instruments.columns or "instrument_token" not in instruments.columns:
        raise KeyError(f"Missing instrument columns for exchange {exchange}")

    row = instruments[instruments["tradingsymbol"] == symbol]
    if row.empty:
        raise KeyError(f"Instrument token not found for {symbol} on {exchange}")

    token = row.iloc[0].get("instrument_token")
    if pd.isna(token):
        raise KeyError(f"Invalid instrument_token for {symbol} on {exchange}")

    return int(token)
