from typing import List, Tuple
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models_candles import Candle15m, CandleDaily
from app.core.ml.config import StockMLConfig
from app.core.ml.feature_builder import build_features_from_df, FEATURE_COLUMNS
from app.core.ml.labeling import add_future_return_labels


def _load_candles_df(db: Session, symbol: str, timeframe: str, max_candles: int) -> pd.DataFrame:
    symbol = symbol.upper().strip()

    if timeframe == "daily":
        rows = (
            db.query(CandleDaily)
            .filter(CandleDaily.symbol == symbol)
            .order_by(CandleDaily.date.asc())
            .limit(max_candles)
            .all()
        )
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([{
            "timestamp": r.date,
            "open": r.open, "high": r.high,
            "low": r.low,  "close": r.close, "volume": r.volume,
        } for r in rows])

    rows = (
        db.query(Candle15m)
        .filter(Candle15m.symbol == symbol)
        .order_by(Candle15m.timestamp.asc())
        .limit(max_candles)
        .all()
    )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "timestamp": r.timestamp,
        "open": r.open, "high": r.high,
        "low": r.low,  "close": r.close, "volume": r.volume,
    } for r in rows])


def build_stock_ml_dataset(
    db: Session,
    symbols: List[str],
    config: StockMLConfig,
) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Build features + labels dataset.

    Key correctness guarantees:
    - timestamp is carried through so splits are date-anchored, not row-anchored
    - label overlap is eliminated inside add_future_return_labels (stride sampling)
    - symbol column is kept so _per_symbol_split can do per-symbol date cuts
    """
    frames: List[pd.DataFrame] = []

    for symbol in symbols:
        raw = _load_candles_df(db, symbol, config.timeframe, config.max_candles)
        if raw.empty:
            continue

        features = build_features_from_df(raw, config)
        if features.empty:
            continue

        labeled = add_future_return_labels(features, config)
        if labeled.empty:
            continue

        labeled["symbol"] = symbol
        frames.append(labeled)

    if not frames:
        return pd.DataFrame(), pd.Series(dtype=int)

    dataset = pd.concat(frames, ignore_index=True)

    x = dataset[FEATURE_COLUMNS + ["symbol", "timestamp"]] if "timestamp" in dataset.columns \
        else dataset[FEATURE_COLUMNS + ["symbol"]]
    y = dataset["label"]

    return x, y
