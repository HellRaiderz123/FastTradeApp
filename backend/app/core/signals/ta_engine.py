import logging
import pandas as pd
import numpy as np
from typing import Dict
from sqlalchemy.orm import Session
from app.db.models_candles import Candle15m

logger = logging.getLogger(__name__)

def ta_signal_15m(db: Session, symbol: str) -> Dict:
    symbol = symbol.upper().strip()
    candles = (
        db.query(Candle15m)
        .filter(Candle15m.symbol == symbol)
        .order_by(Candle15m.timestamp.desc())
        .limit(300)
        .all()
    )

    logger.info(
        "TA DEBUG | symbol=%s | candles_found=%d",
        symbol,
        len(candles),
    )

    if len(candles) < 100:
        return {
            "signal": "NO_TRADE",
            "confidence": 0,
            "reason": "Not enough candles",
        }

    df = pd.DataFrame(
        [{
            "close": c.close,
            "high": c.high,
            "low": c.low,
            "volume": c.volume,
        } for c in reversed(candles)]
    )

    df["ema_20"] = df["close"].ewm(span=20).mean()
    df["ema_50"] = df["close"].ewm(span=50).mean()
    df["ema_20_slope"] = df["ema_20"].diff()
    df["rsi"] = compute_rsi(df["close"])

    last = df.iloc[-1]

    if (
        last["ema_20"] > last["ema_50"]
        and last["ema_20_slope"] > 0
        and last["rsi"] > 50
    ):
        return {
            "signal": "BULLISH",
            "confidence": 70,
            "reason": "EMA trend up + RSI > 50",
        }

    if (
        last["ema_20"] < last["ema_50"]
        and last["ema_20_slope"] < 0
        and last["rsi"] < 50
    ):
        return {
            "signal": "BEARISH",
            "confidence": 70,
            "reason": "EMA trend down + RSI < 50",
        }

    return {
        "signal": "RANGE",
        "confidence": 45,
        "reason": "No directional edge",
    }



def compute_rsi(series: pd.Series, period: int = 14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))
