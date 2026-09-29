import logging
import pandas as pd
import numpy as np
from app.core.ml.config import StockMLConfig

logger = logging.getLogger(__name__)

def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """
    Label rows based on forward return over horizon.
    Simple fixed threshold — no adaptive correction that can silently override config.
    BUY=1 if forward return > return_threshold, else 0.
    """
    data = df.copy()

    future_close = data["close"].shift(-config.horizon)
    data["_future_return"] = (future_close / data["close"]) - 1.0
    data = data.dropna(subset=["_future_return"]).copy()

    # Fixed threshold label — clean, no look-ahead, no adaptive override
    data["label"] = (data["_future_return"] > config.return_threshold).astype(int)

    buy_rate = data["label"].mean()
    logger.info(
        f"Label stats: buy_rate={buy_rate:.3f}, threshold={config.return_threshold}, "
        f"horizon={config.horizon}, rows={len(data)}"
    )

    # Warn if label distribution is degenerate — but do NOT silently fix it
    # (fixing it with global percentiles causes look-ahead leakage)
    if buy_rate > 0.55:
        logger.warning(
            f"High BUY rate {buy_rate:.1%} — return_threshold={config.return_threshold} may be too low. "
            f"Consider raising STOCK_ML_RETURN_THRESHOLD."
        )
    elif buy_rate < 0.20:
        logger.warning(
            f"Low BUY rate {buy_rate:.1%} — return_threshold={config.return_threshold} may be too high. "
            f"Consider lowering STOCK_ML_RETURN_THRESHOLD."
        )

    data = data.drop(columns=["_future_return"])
    return data