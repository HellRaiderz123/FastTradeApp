import pandas as pd
import numpy as np
from app.core.ml.config import StockMLConfig


def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """Label rows based on forward return over horizon.

    Uses adaptive threshold based on rolling volatility to account for
    different market regimes. This improves label quality significantly.
    
    Binary directional label:
      1 = UP   (return >= +threshold)
      0 = DOWN (return <= -threshold)
    Neutral rows are dropped so the model learns clear direction.
    """
    data = df.copy()
    future_close = data["close"].shift(-config.horizon)
    future_return = (future_close / data["close"]) - 1.0

    # Adaptive threshold: use rolling volatility to set dynamic threshold
    # This helps in both high-vol and low-vol regimes
    rolling_vol = data["close"].pct_change().rolling(20).std() * np.sqrt(config.horizon)
    adaptive_threshold = np.maximum(rolling_vol * 1.5, config.return_threshold)
    
    data["_future_return"] = future_return
    data["_threshold"] = adaptive_threshold
    
    # Filter: keep only rows with clear directional moves
    data = data[
        (data["_future_return"] >= data["_threshold"]) |
        (data["_future_return"] <= -data["_threshold"])
    ].copy()
    
    data["label"] = (data["_future_return"] >= data["_threshold"]).astype(int)
    data = data.drop(columns=["_future_return", "_threshold"])
    return data
