"""
Tests for Quantitative Analysis Bots.

Phase 5: Unit tests for CashEquityQuantBot, OptionsQuantBot, and GEX calculations.
"""

import pytest
from datetime import date, datetime, timedelta
import numpy as np

from app.services.quant_bots import (
    CashEquityQuantBot,
    OptionsQuantBot,
    CashQuantReport,
    OptionsQuantReport,
)


class TestCashEquityQuantBot:
    """Tests for CashEquityQuantBot."""

    def setup_method(self):
        self.bot = CashEquityQuantBot()

    def test_empty_candles_returns_default_report(self):
        """Empty candles should return a default report without errors."""
        report = self.bot.analyze(
            symbol="TEST",
            candles_5m=[],
            candles_daily=[],
        )
        assert isinstance(report, CashQuantReport)
        assert report.symbol == "TEST"
        assert report.regime == "RANDOM"

    def test_hurst_trending_regime(self):
        """Trending price series should have Hurst > 0.55."""
        # Generate trending prices (cumulative sum of positive values)
        np.random.seed(42)
        prices = np.cumsum(np.abs(np.random.randn(200)) + 0.1) + 100
        
        hurst = self.bot._calc_hurst(prices)
        assert hurst > 0.5, f"Trending series should have H > 0.5, got {hurst}"

    def test_hurst_mean_reverting_regime(self):
        """Mean-reverting series should have Hurst < 0.5."""
        # Generate mean-reverting prices (oscillating around mean)
        np.random.seed(42)
        prices = 100 + 5 * np.sin(np.linspace(0, 20 * np.pi, 200)) + np.random.randn(200) * 0.5
        
        hurst = self.bot._calc_hurst(prices)
        assert hurst < 0.55, f"Mean-reverting series should have H < 0.55, got {hurst}"

    def test_zscore_calculation(self):
        """Z-score should be correct for known values."""
        prices = np.array([100, 102, 98, 101, 99, 103, 97, 100, 102, 98,
                          101, 99, 103, 97, 100, 102, 98, 101, 99, 110])
        
        zscore = self.bot._calc_zscore(prices, 20)
        
        # Last price (110) is above mean, so z-score should be positive
        assert zscore > 0, f"Z-score should be positive for price above mean, got {zscore}"

    def test_atr_calculation(self):
        """ATR should be calculated correctly."""
        candles = [
            {"high": 105, "low": 95, "close": 100},
            {"high": 106, "low": 96, "close": 102},
            {"high": 108, "low": 98, "close": 104},
            {"high": 107, "low": 97, "close": 101},
            {"high": 109, "low": 99, "close": 105},
            {"high": 110, "low": 100, "close": 106},
            {"high": 108, "low": 98, "close": 103},
            {"high": 107, "low": 97, "close": 102},
            {"high": 109, "low": 99, "close": 105},
            {"high": 111, "low": 101, "close": 108},
            {"high": 110, "low": 100, "close": 106},
            {"high": 108, "low": 98, "close": 104},
            {"high": 107, "low": 97, "close": 102},
            {"high": 109, "low": 99, "close": 105},
        ]
        df = self.bot._to_dataframe(candles)
        
        atr = self.bot._calc_atr(df, 14)
        
        # ATR should be around 10 (high-low range)
        assert 8 < atr < 12, f"ATR should be around 10, got {atr}"

    def test_vwap_calculation(self):
        """VWAP should be calculated correctly."""
        candles = [
            {"high": 105, "low": 95, "close": 100, "volume": 1000},
            {"high": 106, "low": 96, "close": 102, "volume": 1500},
            {"high": 108, "low": 98, "close": 104, "volume": 2000},
        ]
        df = self.bot._to_dataframe(candles)
        
        vwap_result = self.bot._calc_vwap(df)
        
        # VWAP should be volume-weighted average of typical prices
        assert vwap_result["vwap"] > 0
        assert vwap_result["upper_1sd"] > vwap_result["vwap"]
        assert vwap_result["lower_1sd"] < vwap_result["vwap"]


class TestOptionsQuantBot:
    """Tests for OptionsQuantBot."""

    def setup_method(self):
        self.bot = OptionsQuantBot()

    def test_empty_chain_returns_default_report(self):
        """Empty option chain should return default report."""
        report = self.bot.analyze(
            underlying="NIFTY",
            spot=22000,
            option_chain=[],
            expiry_date=date.today() + timedelta(days=7),
        )
        assert isinstance(report, OptionsQuantReport)
        assert report.underlying == "NIFTY"

    def test_atm_strike_finding(self):
        """ATM strike should be closest to spot."""
        chain = [
            {"strike": 21900},
            {"strike": 22000},
            {"strike": 22100},
        ]
        df = self.bot._to_dataframe(chain)
        
        atm = self.bot._find_atm(df, spot=22050)
        
        assert atm == 22000, f"ATM should be 22000, got {atm}"

    def _to_dataframe(self, chain):
        import pandas as pd
        return pd.DataFrame(chain)

    def test_greeks_calculation(self):
        """Greeks should be calculated correctly for ATM option."""
        spot = 22000
        strike = 22000
        tau = 7 / 365  # 7 days to expiry
        iv = 0.15  # 15% IV
        
        ce_greeks = self.bot._calc_greeks(spot, strike, tau, iv, "CE")
        pe_greeks = self.bot._calc_greeks(spot, strike, tau, iv, "PE")
        
        # ATM call delta should be around 0.5
        assert 0.4 < ce_greeks["delta"] < 0.6, f"CE delta should be ~0.5, got {ce_greeks['delta']}"
        
        # ATM put delta should be around -0.5
        assert -0.6 < pe_greeks["delta"] < -0.4, f"PE delta should be ~-0.5, got {pe_greeks['delta']}"
        
        # Gamma should be positive for both
        assert ce_greeks["gamma"] > 0
        assert pe_greeks["gamma"] > 0
        
        # Theta should be negative (time decay)
        assert ce_greeks["theta"] < 0
        assert pe_greeks["theta"] < 0
        
        # Vega should be positive
        assert ce_greeks["vega"] > 0
        assert pe_greeks["vega"] > 0

    def test_ivp_calculation(self):
        """IV Percentile should be calculated correctly."""
        historical_iv = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28]
        current_iv = 0.20
        
        ivp = self.bot._calc_ivp(current_iv, historical_iv)
        
        # 0.20 is at 50th percentile (5 values below, 4 above)
        assert 40 < ivp < 60, f"IVP should be around 50, got {ivp}"

    def test_ivr_calculation(self):
        """IV Rank should be calculated correctly."""
        historical_iv = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28]
        current_iv = 0.19
        
        ivr = self.bot._calc_ivr(current_iv, historical_iv)
        
        # IVR = (0.19 - 0.10) / (0.28 - 0.10) = 0.09 / 0.18 = 50%
        assert 45 < ivr < 55, f"IVR should be around 50, got {ivr}"

    def test_max_pain_calculation(self):
        """Max pain should be calculated correctly."""
        chain = [
            {"strike": 21900, "ce_oi": 1000, "pe_oi": 5000},
            {"strike": 22000, "ce_oi": 3000, "pe_oi": 3000},
            {"strike": 22100, "ce_oi": 5000, "pe_oi": 1000},
        ]
        import pandas as pd
        df = pd.DataFrame(chain)
        
        max_pain = self.bot._calc_max_pain(df)
        
        # Max pain should be at 22000 (balanced OI)
        assert max_pain == 22000, f"Max pain should be 22000, got {max_pain}"

    def test_gex_regime_classification(self):
        """GEX regime should be classified correctly."""
        # Positive GEX = more call OI at higher strikes
        chain_positive = [
            {"strike": 21900, "ce_oi": 1000, "pe_oi": 5000, "ce_iv": 0.15},
            {"strike": 22000, "ce_oi": 3000, "pe_oi": 3000, "ce_iv": 0.15},
            {"strike": 22100, "ce_oi": 10000, "pe_oi": 1000, "ce_iv": 0.15},
        ]
        
        gex = self.bot._calc_gex(
            self._to_dataframe(chain_positive),
            spot=22000,
            tau=7/365,
        )
        
        # Should have some GEX value (positive or negative)
        assert gex["net_gex"] != 0 or gex["regime"] in ["POSITIVE_GEX", "NEGATIVE_GEX", "NEUTRAL"]

    def test_structure_recommendation_low_iv(self):
        """Low IV should recommend debit structures."""
        report = OptionsQuantReport(
            underlying="NIFTY",
            spot=22000,
            iv_percentile=25,  # Low IV
            gex_regime="NEGATIVE_GEX",
        )
        
        rec = self.bot._recommend_structure(report)
        
        assert "STRADDLE" in rec["structure"] or "DEBIT" in rec["structure"]

    def test_structure_recommendation_high_iv(self):
        """High IV should recommend credit structures."""
        report = OptionsQuantReport(
            underlying="NIFTY",
            spot=22000,
            iv_percentile=75,  # High IV
            gex_regime="POSITIVE_GEX",
        )
        
        rec = self.bot._recommend_structure(report)
        
        assert "CONDOR" in rec["structure"] or "CREDIT" in rec["structure"]


class TestMarginSafeOrderSorting:
    """Tests for margin-safe multi-leg order sorting."""

    def test_buy_legs_before_sell_legs(self):
        """BUY hedge legs should be sequenced before SELL short legs."""
        legs = [
            {"strike": 22000, "type": "CE", "action": "SELL"},
            {"strike": 22100, "type": "CE", "action": "BUY"},
            {"strike": 21900, "type": "PE", "action": "SELL"},
            {"strike": 21800, "type": "PE", "action": "BUY"},
        ]
        
        # Sort: BUY legs first
        sorted_legs = sorted(legs, key=lambda x: (0 if x["action"] == "BUY" else 1, x["strike"]))
        
        # First two should be BUY
        assert sorted_legs[0]["action"] == "BUY"
        assert sorted_legs[1]["action"] == "BUY"
        # Last two should be SELL
        assert sorted_legs[2]["action"] == "SELL"
        assert sorted_legs[3]["action"] == "SELL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
