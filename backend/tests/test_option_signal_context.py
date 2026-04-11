from datetime import datetime

import pandas as pd
import pytest

from app.core.indicators.put_call_ratio import OptionChainAnalysis
from app.core.signals.signals import _apply_option_context_to_signal, _apply_weekly_option_entry_filter


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


def test_weekly_expiry_gate_blocks_late_expiry_day_option_buy():
    sig = {
        "signal": "BULLISH",
        "bias": "BULLISH",
        "confidence": 84,
        "reason": "Strong trend",
        "trade_readiness_score": 74,
        "indicators": {"adx": 31, "rsi": 61},
        "quality_checks": {"oi_bias_confirm": True},
        "quality_score": 5,
        "context": {},
    }

    updated = _apply_weekly_option_entry_filter(
        sig,
        "NIFTY",
        asof_dt=datetime(2026, 4, 14, 13, 5),
    )

    assert updated["recommendation"] == "NO_TRADE"
    assert updated["quality_checks"]["expiry_entry_ok"] is False
    assert "expiry-day theta risk" in updated["reason"]


def test_weekly_entry_gate_allows_buy_ce_for_strong_non_expiry_setup():
    sig = {
        "signal": "BULLISH",
        "bias": "BULLISH",
        "confidence": 83,
        "reason": "Strong trend",
        "trade_readiness_score": 76,
        "indicators": {"adx": 29, "rsi": 60},
        "quality_checks": {"oi_bias_confirm": True},
        "quality_score": 5,
        "context": {},
    }
    chain_df = pd.DataFrame(
        [
            {"strike": 19750, "instrument_type": "CE", "tradingsymbol": "NIFTY19750CE", "oi": 22000, "volume": 18000, "bid": 156, "ask": 158, "ltp": 157},
            {"strike": 19800, "instrument_type": "CE", "tradingsymbol": "NIFTY19800CE", "oi": 25000, "volume": 22000, "bid": 126, "ask": 128, "ltp": 127},
            {"strike": 19850, "instrument_type": "CE", "tradingsymbol": "NIFTY19850CE", "oi": 24000, "volume": 21000, "bid": 98, "ask": 100, "ltp": 99},
        ]
    )

    updated = _apply_weekly_option_entry_filter(
        sig,
        "NIFTY",
        asof_dt=datetime(2026, 4, 13, 10, 15),
        chain_df=chain_df,
        spot=19820,
    )

    assert updated["recommendation"] == "BUY_CE"
    assert updated["quality_checks"]["expiry_entry_ok"] is True
    assert updated["quality_checks"]["liquidity_ok"] is True
    assert updated["context"]["options_entry"]["entry_type"] == "OPTION_BUY"
    assert updated["context"]["options_entry"]["selected_contract"]["tradingsymbol"] in {
        "NIFTY19800CE",
        "NIFTY19850CE",
    }
    assert 0.25 <= updated["context"]["options_entry"]["selected_contract"]["approx_delta"] <= 0.7


def test_weekly_entry_gate_blocks_illiquid_contracts_even_if_ta_is_strong():
    sig = {
        "signal": "BULLISH",
        "bias": "BULLISH",
        "confidence": 86,
        "reason": "Strong trend",
        "trade_readiness_score": 79,
        "indicators": {"adx": 31, "rsi": 59},
        "quality_checks": {"oi_bias_confirm": True},
        "quality_score": 5,
        "context": {},
    }
    chain_df = pd.DataFrame(
        [
            {"strike": 19800, "instrument_type": "CE", "tradingsymbol": "NIFTY19800CE", "oi": 80, "volume": 6, "bid": 100, "ask": 108, "ltp": 104},
            {"strike": 19850, "instrument_type": "CE", "tradingsymbol": "NIFTY19850CE", "oi": 60, "volume": 4, "bid": 72, "ask": 79, "ltp": 75},
        ]
    )

    updated = _apply_weekly_option_entry_filter(
        sig,
        "NIFTY",
        asof_dt=datetime(2026, 4, 13, 10, 20),
        chain_df=chain_df,
        spot=19820,
    )

    assert updated["recommendation"] == "NO_TRADE"
    assert updated["quality_checks"]["liquidity_ok"] is False
    assert any("liquidity" in reason for reason in updated["context"]["options_entry"]["blocked_reasons"])


def test_weekly_entry_gate_blocks_high_iv_crush_risk_for_direct_buy():
    sig = {
        "signal": "BULLISH",
        "bias": "BULLISH",
        "confidence": 78,
        "reason": "Trend up",
        "trade_readiness_score": 73,
        "indicators": {"adx": 30, "rsi": 58},
        "quality_checks": {"oi_bias_confirm": True},
        "quality_score": 5,
        "iv_regime": "HIGH",
        "context": {"vix_rank": 88},
    }
    chain_df = pd.DataFrame(
        [
            {"strike": 19800, "instrument_type": "CE", "tradingsymbol": "NIFTY19800CE", "oi": 22000, "volume": 18000, "bid": 126, "ask": 128, "ltp": 127},
        ]
    )

    updated = _apply_weekly_option_entry_filter(
        sig,
        "NIFTY",
        asof_dt=datetime(2026, 4, 13, 10, 15),
        chain_df=chain_df,
        spot=19820,
    )

    assert updated["recommendation"] == "NO_TRADE"
    assert updated["quality_checks"]["iv_crush_safe"] is False
    assert any("IV" in reason for reason in updated["context"]["options_entry"]["blocked_reasons"])
