from dataclasses import dataclass
import os
from pathlib import Path


def _bool_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ["1", "true", "yes", "y"]


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return float(value)


def _path_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return Path(value)


@dataclass
class StockMLConfig:
    enabled: bool = _bool_env("STOCK_ML_ENABLED", "false")
    timeframe: str = os.getenv("STOCK_ML_TIMEFRAME", "daily").strip().lower()

    model_dir: Path = _path_env(
        "STOCK_ML_MODEL_DIR",
        Path(__file__).resolve().parents[3] / "data" / "ml_models",
    )
    model_name: str = os.getenv("STOCK_ML_MODEL_NAME", "stock_daily_model.joblib").strip()

    max_candles: int = _int_env("STOCK_ML_MAX_CANDLES", 1200)
    min_rows: int = _int_env("STOCK_ML_MIN_ROWS", 300)

    horizon: int = _int_env("STOCK_ML_HORIZON", 5)
    return_threshold: float = _float_env("STOCK_ML_RETURN_THRESHOLD", 0.01)

    min_confidence: int = _int_env("STOCK_ML_MIN_CONFIDENCE", 60)
    bullish_prob_threshold: float = _float_env("STOCK_ML_BULLISH_PROB", 0.55)
    bearish_prob_threshold: float = _float_env("STOCK_ML_BEARISH_PROB", 0.45)

    rsi_period: int = _int_env("STOCK_ML_RSI_PERIOD", 14)
    adx_period: int = _int_env("STOCK_ML_ADX_PERIOD", 14)
    ema_fast: int = _int_env("STOCK_ML_EMA_FAST", 20)
    ema_slow: int = _int_env("STOCK_ML_EMA_SLOW", 50)
    ema_long: int = _int_env("STOCK_ML_EMA_LONG", 200)
    vol_window: int = _int_env("STOCK_ML_VOL_WINDOW", 20)
    ret_short_window: int = _int_env("STOCK_ML_RET_SHORT", 5)
    ret_long_window: int = _int_env("STOCK_ML_RET_LONG", 20)

    @property
    def model_path(self) -> Path:
        return self.model_dir / self.model_name
