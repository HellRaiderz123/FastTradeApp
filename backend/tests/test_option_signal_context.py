import pytest

from app.core.indicators.put_call_ratio import OptionChainAnalysis
from app.core.signals.signals import _apply_option_context_to_signal


def test_option_chain_sentiment_is_bullish_near_support():
    analysis = OptionChainAnalysis()

    sentiment = analysis.get_sentiment_score(
        pcr=0.7,
        spot=19795,
        support=19780,
        resistance=20100,
    )

    assert sentiment["total_score"] > 0
    assert sentiment["sentiment"] == "Bullish"


def test_apply_option_context_downgrades_conflicting_bullish_signal():
    sig = {
        "signal": "BULLISH",
        "bias": "BULLISH",
        "confidence": 78,
        "reason": "TA bullish",
        "indicators": {},
        "quality_checks": {},
        "quality_score": 3,
    }
    analytics = {
        "pcr": 1.45,
        "support_level": 19650,
        "resistance_level": 19820,
        "spot_price": 19810,
        "sentiment": "Bearish",
        "total_score": -45,
    }

    updated = _apply_option_context_to_signal(sig, analytics)

    assert updated["confidence"] < 78
    assert updated["quality_checks"]["oi_bias_confirm"] is False
    assert "OI/PCR conflict" in updated["reason"]
