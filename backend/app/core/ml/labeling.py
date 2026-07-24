import pandas as pd
from app.core.ml.config import StockMLConfig


def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """Label rows based on forward return over horizon.

    Binary directional label — excludes neutral zone:
      1 = UP   (return >= +threshold)
      0 = DOWN (return <= -threshold)
    Neutral rows are dropped so the model learns clear direction.
    With horizon=20 and threshold=3%, the neutral zone is much smaller
    than at horizon=5/1.5%, giving cleaner signal without large data loss.
    """
    data = df.copy()
    future_close = data["close"].shift(-config.horizon)
    future_return = (future_close / data["close"]) - 1.0

    data["_future_return"] = future_return
    data = data[
        (data["_future_return"] >= config.return_threshold) |
        (data["_future_return"] <= -config.return_threshold)
    ].copy()
    data["label"] = (data["_future_return"] >= config.return_threshold).astype(int)
    data = data.drop(columns=["_future_return"])
    return data
