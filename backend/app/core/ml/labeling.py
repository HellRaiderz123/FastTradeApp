import logging
import pandas as pd
import numpy as np
from app.core.ml.config import StockMLConfig

logger = logging.getLogger(__name__)

def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """
    Label rows based on forward return over horizon.
    Uses adaptive threshold to ensure reasonable class balance (30-50% positive).
    BUY=1 if forward return > threshold, else 0.
    """
    data = df.copy()

    future_close = data["close"].shift(-config.horizon)
    data["_future_return"] = (future_close / data["close"]) - 1.0
    data = data.dropna(subset=["_future_return"]).copy()

    if len(data) < 100:
        data["label"] = (data["_future_return"] > config.return_threshold).astype(int)
        data = data.drop(columns=["_future_return"])
        return data

    # Start with configured threshold
    threshold = config.return_threshold
    data["label"] = (data["_future_return"] > threshold).astype(int)
    buy_rate = data["label"].mean()

    # Adaptive adjustment if class balance is poor
    # Target: 30-50% positive class for balanced learning
    if buy_rate < 0.25 or buy_rate > 0.55:
        # Use percentile-based threshold for better balance
        target_rate = 0.40  # Target 40% positive
        threshold = float(data["_future_return"].quantile(1 - target_rate))
        # Ensure threshold is reasonable (not negative for BUY signals)
        threshold = max(threshold, 0.001)
        data["label"] = (data["_future_return"] > threshold).astype(int)
        buy_rate = data["label"].mean()
        logger.info(
            f"Label adaptive: adjusted threshold to {threshold:.4f} for buy_rate={buy_rate:.3f}"
        )

    logger.info(
        f"Label stats: buy_rate={buy_rate:.3f}, threshold={threshold:.4f}, "
        f"horizon={config.horizon}, rows={len(data)}"
    )

    data = data.drop(columns=["_future_return"])
    return data