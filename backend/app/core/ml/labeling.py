import pandas as pd
from app.core.ml.config import StockMLConfig


def add_future_return_labels(df: pd.DataFrame, config: StockMLConfig) -> pd.DataFrame:
    """Label rows based on forward return over horizon."""
    data = df.copy()
    future_close = data["close"].shift(-config.horizon)
    future_return = (future_close / data["close"]) - 1.0

    data["label"] = None
    data.loc[future_return >= config.return_threshold, "label"] = 1
    data.loc[future_return <= -config.return_threshold, "label"] = 0

    data = data.dropna(subset=["label"])
    data["label"] = data["label"].astype(int)
    return data
