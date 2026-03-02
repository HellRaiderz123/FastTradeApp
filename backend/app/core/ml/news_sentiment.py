"""
Feature #18 — News Sentiment Scoring in Signal Context
Scores recent news headlines for a symbol and blends
a sentiment multiplier into the ML signal confidence.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simple keyword-based sentiment scorer (no external LLM dependency)
# ---------------------------------------------------------------------------

# Positive / negative word lists tuned for Indian equity markets
_POSITIVE_WORDS = {
    "upgrade", "outperform", "beat", "bullish", "growth", "profit",
    "surge", "gain", "rally", "record", "high", "positive", "buy",
    "strong", "expand", "dividend", "breakout", "recovery", "up",
    "boost", "exceed", "impressive", "uptrend", "rebound", "optimistic",
    "stellar", "accelerat", "overweight", "target raised", "order win",
    "contract", "expansion", "upside", "momentum", "acquire", "deal",
}

_NEGATIVE_WORDS = {
    "downgrade", "underperform", "miss", "bearish", "loss", "drop",
    "fall", "decline", "weak", "negative", "sell", "cut", "reduce",
    "slump", "crash", "fraud", "probe", "investigation", "warning",
    "bankrupt", "default", "debt", "fine", "penalty", "risk",
    "shutdown", "layoff", "recall", "overvalued", "downtrend",
    "underweight", "target cut", "delay", "concern", "slowdown",
}

_NEUTRAL_OVERRIDE = {"stock split", "ex-date", "bonus", "rights issue"}


def _score_headline(headline: str) -> float:
    """
    Score a headline in [-1.0, +1.0].
    Simple bag-of-words approach; robust with zero external dependencies.
    """
    text = headline.lower()

    # Check neutral overrides
    for phrase in _NEUTRAL_OVERRIDE:
        if phrase in text:
            return 0.0

    pos_count = sum(1 for w in _POSITIVE_WORDS if w in text)
    neg_count = sum(1 for w in _NEGATIVE_WORDS if w in text)

    total = pos_count + neg_count
    if total == 0:
        return 0.0

    raw = (pos_count - neg_count) / total  # range [-1, 1]
    return round(raw, 3)


def score_headlines(headlines: List[str]) -> List[Dict[str, Any]]:
    """Score a list of headlines and return per-headline + aggregate."""
    scored = []
    for h in headlines:
        s = _score_headline(h)
        scored.append({"headline": h, "score": s})
    return scored


def aggregate_sentiment(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate scored headlines into a single sentiment object."""
    if not scored:
        return {"composite_score": 0.0, "label": "NEUTRAL", "headline_count": 0}

    scores = [s["score"] for s in scored]
    composite = sum(scores) / len(scores)

    if composite > 0.2:
        label = "POSITIVE"
    elif composite < -0.2:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"

    return {
        "composite_score": round(composite, 3),
        "label": label,
        "headline_count": len(scored),
        "positive_count": sum(1 for s in scores if s > 0),
        "negative_count": sum(1 for s in scores if s < 0),
        "neutral_count": sum(1 for s in scores if s == 0),
    }


# ---------------------------------------------------------------------------
# Integration with ML signal
# ---------------------------------------------------------------------------


def adjust_signal_with_sentiment(
    signal_result: Dict[str, Any],
    sentiment: Dict[str, Any],
    *,
    weight: float = 0.15,
) -> Dict[str, Any]:
    """
    Blend news sentiment into ML signal confidence.
    • If sentiment confirms signal direction → boost confidence
    • If sentiment contradicts → reduce confidence
    • Adds 'sentiment_adjustment' to the result dict.
    """
    result = dict(signal_result)
    composite = sentiment.get("composite_score", 0.0)
    bias = result.get("bias", "NEUTRAL")

    # Direction alignment
    if bias == "BULLISH" and composite > 0:
        adjustment = abs(composite) * weight * 100
    elif bias == "BEARISH" and composite < 0:
        adjustment = abs(composite) * weight * 100
    elif bias == "BULLISH" and composite < 0:
        adjustment = -abs(composite) * weight * 100
    elif bias == "BEARISH" and composite > 0:
        adjustment = -abs(composite) * weight * 100
    else:
        adjustment = 0

    old_conf = result.get("confidence", 50)
    new_conf = max(0, min(100, int(old_conf + adjustment)))

    result["confidence"] = new_conf
    result["sentiment_adjustment"] = round(adjustment, 1)
    result["news_sentiment"] = {
        "composite_score": composite,
        "label": sentiment.get("label", "NEUTRAL"),
        "headline_count": sentiment.get("headline_count", 0),
    }

    return result


# ---------------------------------------------------------------------------
# Fetch headlines from existing RSS service (if available)
# ---------------------------------------------------------------------------


def fetch_symbol_news(symbol: str, limit: int = 20) -> List[str]:
    """
    Attempt to get recent headlines for a symbol from existing services.
    Falls back to empty list if RSS service is unavailable.
    """
    headlines: List[str] = []

    try:
        from app.services.rss_feed_service import RSSFeedService
        rss = RSSFeedService()
        # Try to get stock-specific news
        feeds = rss.get_feeds() if hasattr(rss, "get_feeds") else []
        for feed in feeds[:limit]:
            title = feed.get("title", "")
            if symbol.upper() in title.upper() or symbol.lower() in title.lower():
                headlines.append(title)
    except Exception:
        pass

    # Return what we have, might be empty
    return headlines[:limit]


def get_signal_with_news(
    db: Session,
    symbol: str,
    config=None,
    *,
    model_type: str = "single",
) -> Dict[str, Any]:
    """
    Full pipeline: get ML signal → fetch news → blend sentiment.
    """
    from app.core.ml.config import StockMLConfig
    if config is None:
        config = StockMLConfig()

    # Get base signal
    if model_type == "ensemble":
        from app.core.ml.ensemble import predict_ensemble
        signal_result = predict_ensemble(db, symbol, config)
    else:
        from app.core.ml.stock_model import predict_stock_signal
        signal_result = predict_stock_signal(db, symbol, config)

    # Fetch and score news
    headlines = fetch_symbol_news(symbol)
    scored = score_headlines(headlines)
    sentiment = aggregate_sentiment(scored)

    # Blend
    adjusted = adjust_signal_with_sentiment(signal_result, sentiment)
    adjusted["scored_headlines"] = scored[:10]

    return adjusted
