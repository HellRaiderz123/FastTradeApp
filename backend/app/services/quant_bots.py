"""
Quantitative Analysis Bots — Cash Equities & F&O Options.

Phase 3: Institutional-grade quant calculators using numpy, pandas, scipy.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Risk-free rate (India 91-day T-bill ~6.8%)
RISK_FREE_RATE = 0.068


@dataclass
class CashQuantReport:
    """Quantitative report for cash equities."""
    symbol: str
    timestamp: datetime = field(default_factory=datetime.now)
    # ORB
    orb_high: float = 0.0
    orb_low: float = 0.0
    orb_breakout: str = "NONE"  # BULLISH, BEARISH, NONE
    # RVOL
    rvol: float = 1.0
    rvol_signal: str = "NORMAL"  # HIGH, LOW, NORMAL
    # VWAP
    vwap: float = 0.0
    vwap_upper_1sd: float = 0.0
    vwap_lower_1sd: float = 0.0
    vwap_upper_2sd: float = 0.0
    vwap_lower_2sd: float = 0.0
    price_vs_vwap: str = "AT_VWAP"  # ABOVE, BELOW, AT_VWAP
    # Relative Strength
    rs_vs_nifty_5d: float = 0.0
    rs_vs_sector_5d: float = 0.0
    rs_intraday: float = 0.0
    # Regime
    hurst_exponent: float = 0.5
    regime: str = "RANDOM"  # TRENDING, MEAN_REVERTING, RANDOM
    zscore_20: float = 0.0
    bb_width_percentile: float = 50.0
    # ATR & Position Sizing
    atr_14: float = 0.0
    suggested_stop_loss: float = 0.0
    position_size_lots: int = 1
    # Delivery
    delivery_pct: float = 0.0
    institutional_accumulation: bool = False


@dataclass 
class OptionsQuantReport:
    """Quantitative report for F&O options."""
    underlying: str
    spot: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    # Greeks (ATM)
    atm_strike: float = 0.0
    atm_ce_delta: float = 0.0
    atm_ce_gamma: float = 0.0
    atm_ce_theta: float = 0.0
    atm_ce_vega: float = 0.0
    atm_pe_delta: float = 0.0
    atm_pe_gamma: float = 0.0
    atm_pe_theta: float = 0.0
    atm_pe_vega: float = 0.0
    # IV
    atm_iv: float = 0.0
    iv_percentile: float = 50.0
    iv_rank: float = 50.0
    # OI Microstructure
    pcr_oi: float = 1.0
    pcr_change_oi: float = 1.0
    max_pain: float = 0.0
    call_wall: float = 0.0
    put_wall: float = 0.0
    # GEX
    net_gex: float = 0.0
    gex_regime: str = "NEUTRAL"  # POSITIVE_GEX, NEGATIVE_GEX, NEUTRAL
    # Recommendation
    recommended_structure: str = "NONE"
    structure_rationale: str = ""


class CashEquityQuantBot:
    """
    Quantitative calculator for cash equities.
    
    Computes: ORB, RVOL, VWAP bands, RS, Hurst, Z-score, ATR position sizing.
    """

    def __init__(self):
        self._nifty_returns: Optional[pd.Series] = None

    def analyze(
        self,
        symbol: str,
        candles_5m: List[Dict],
        candles_daily: List[Dict],
        nifty_candles: Optional[List[Dict]] = None,
        sector_candles: Optional[List[Dict]] = None,
        delivery_pct: float = 0.0,
        account_risk_pct: float = 1.0,
        account_capital: float = 100000.0,
    ) -> CashQuantReport:
        """
        Generate comprehensive quant report for a cash equity.
        
        Args:
            symbol: Stock symbol
            candles_5m: Intraday 5-minute candles (today)
            candles_daily: Daily candles (at least 60 days)
            nifty_candles: Nifty 50 daily candles for RS calculation
            sector_candles: Sector index daily candles
            delivery_pct: Delivery percentage from NSE
            account_risk_pct: Max risk per trade as % of capital
            account_capital: Trading capital
        """
        report = CashQuantReport(symbol=symbol)
        
        try:
            df_5m = self._to_dataframe(candles_5m)
            df_daily = self._to_dataframe(candles_daily)
            
            if df_5m.empty and df_daily.empty:
                return report
            
            # ORB (Opening Range Breakout)
            if not df_5m.empty:
                orb = self._calc_orb(df_5m)
                report.orb_high = orb["high"]
                report.orb_low = orb["low"]
                report.orb_breakout = orb["breakout"]
            
            # RVOL (Relative Volume)
            if not df_5m.empty:
                rvol = self._calc_rvol(df_5m, df_daily)
                report.rvol = rvol["rvol"]
                report.rvol_signal = rvol["signal"]
            
            # VWAP with bands
            if not df_5m.empty:
                vwap = self._calc_vwap(df_5m)
                report.vwap = vwap["vwap"]
                report.vwap_upper_1sd = vwap["upper_1sd"]
                report.vwap_lower_1sd = vwap["lower_1sd"]
                report.vwap_upper_2sd = vwap["upper_2sd"]
                report.vwap_lower_2sd = vwap["lower_2sd"]
                report.price_vs_vwap = vwap["position"]
            
            # Relative Strength
            if not df_daily.empty:
                rs = self._calc_relative_strength(
                    df_daily, 
                    self._to_dataframe(nifty_candles) if nifty_candles else None,
                    self._to_dataframe(sector_candles) if sector_candles else None,
                )
                report.rs_vs_nifty_5d = rs["vs_nifty"]
                report.rs_vs_sector_5d = rs["vs_sector"]
            
            # Hurst Exponent & Regime
            if len(df_daily) >= 100:
                hurst = self._calc_hurst(df_daily["close"].values)
                report.hurst_exponent = hurst
                if hurst > 0.55:
                    report.regime = "TRENDING"
                elif hurst < 0.45:
                    report.regime = "MEAN_REVERTING"
                else:
                    report.regime = "RANDOM"
            
            # Z-Score & BB Width
            if len(df_daily) >= 20:
                report.zscore_20 = self._calc_zscore(df_daily["close"].values, 20)
                report.bb_width_percentile = self._calc_bb_width_percentile(df_daily)
            
            # ATR & Position Sizing
            if len(df_daily) >= 14:
                atr = self._calc_atr(df_daily, 14)
                report.atr_14 = atr
                current_price = df_daily["close"].iloc[-1]
                report.suggested_stop_loss = round(current_price - 1.5 * atr, 2)
                
                # Position size based on ATR
                risk_per_share = 1.5 * atr
                risk_amount = account_capital * (account_risk_pct / 100)
                if risk_per_share > 0:
                    report.position_size_lots = max(1, int(risk_amount / risk_per_share))
            
            # Delivery
            report.delivery_pct = delivery_pct
            report.institutional_accumulation = delivery_pct > 60.0 and report.rvol > 1.5
            
        except Exception as e:
            logger.warning("CashEquityQuantBot.analyze failed for %s: %s", symbol, e)
        
        return report

    def _to_dataframe(self, candles: Optional[List[Dict]]) -> pd.DataFrame:
        """Convert candle list to DataFrame."""
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame(candles)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df

    def _calc_orb(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate Opening Range Breakout (9:15-9:30 IST)."""
        result = {"high": 0.0, "low": 0.0, "breakout": "NONE"}
        
        if "ts" in df.columns:
            df["timestamp"] = pd.to_datetime(df["ts"])
        elif "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        else:
            return result
        
        # Filter first 15 minutes (3 x 5-min candles)
        orb_candles = df.head(3)
        if len(orb_candles) < 3:
            return result
        
        orb_high = orb_candles["high"].max()
        orb_low = orb_candles["low"].min()
        current_price = df["close"].iloc[-1]
        
        result["high"] = round(orb_high, 2)
        result["low"] = round(orb_low, 2)
        
        if current_price > orb_high:
            result["breakout"] = "BULLISH"
        elif current_price < orb_low:
            result["breakout"] = "BEARISH"
        
        return result

    def _calc_rvol(self, df_5m: pd.DataFrame, df_daily: pd.DataFrame) -> Dict[str, Any]:
        """Calculate Relative Volume (current vs 20-day avg for same time)."""
        result = {"rvol": 1.0, "signal": "NORMAL"}
        
        if df_5m.empty or len(df_daily) < 20:
            return result
        
        current_volume = df_5m["volume"].sum()
        avg_volume = df_daily["volume"].tail(20).mean()
        
        if avg_volume > 0:
            rvol = current_volume / avg_volume
            result["rvol"] = round(rvol, 2)
            
            if rvol > 2.0:
                result["signal"] = "HIGH"
            elif rvol < 0.5:
                result["signal"] = "LOW"
        
        return result

    def _calc_vwap(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate VWAP with standard deviation bands."""
        result = {
            "vwap": 0.0,
            "upper_1sd": 0.0,
            "lower_1sd": 0.0,
            "upper_2sd": 0.0,
            "lower_2sd": 0.0,
            "position": "AT_VWAP",
        }
        
        if df.empty:
            return result
        
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        cumulative_tp_vol = (typical_price * df["volume"]).cumsum()
        cumulative_vol = df["volume"].cumsum()
        
        vwap = cumulative_tp_vol / cumulative_vol
        vwap_value = vwap.iloc[-1]
        
        # Standard deviation
        squared_diff = ((typical_price - vwap) ** 2 * df["volume"]).cumsum()
        variance = squared_diff / cumulative_vol
        std = np.sqrt(variance.iloc[-1])
        
        current_price = df["close"].iloc[-1]
        
        result["vwap"] = round(vwap_value, 2)
        result["upper_1sd"] = round(vwap_value + std, 2)
        result["lower_1sd"] = round(vwap_value - std, 2)
        result["upper_2sd"] = round(vwap_value + 2 * std, 2)
        result["lower_2sd"] = round(vwap_value - 2 * std, 2)
        
        if current_price > vwap_value + 0.5 * std:
            result["position"] = "ABOVE"
        elif current_price < vwap_value - 0.5 * std:
            result["position"] = "BELOW"
        
        return result

    def _calc_relative_strength(
        self,
        stock_df: pd.DataFrame,
        nifty_df: Optional[pd.DataFrame],
        sector_df: Optional[pd.DataFrame],
    ) -> Dict[str, float]:
        """Calculate relative strength vs Nifty and sector."""
        result = {"vs_nifty": 0.0, "vs_sector": 0.0}
        
        if len(stock_df) < 5:
            return result
        
        stock_return = (stock_df["close"].iloc[-1] / stock_df["close"].iloc[-5] - 1) * 100
        
        if nifty_df is not None and len(nifty_df) >= 5:
            nifty_return = (nifty_df["close"].iloc[-1] / nifty_df["close"].iloc[-5] - 1) * 100
            result["vs_nifty"] = round(stock_return - nifty_return, 2)
        
        if sector_df is not None and len(sector_df) >= 5:
            sector_return = (sector_df["close"].iloc[-1] / sector_df["close"].iloc[-5] - 1) * 100
            result["vs_sector"] = round(stock_return - sector_return, 2)
        
        return result

    def _calc_hurst(self, prices: np.ndarray, max_lag: int = 100) -> float:
        """Calculate Hurst exponent using R/S analysis."""
        if len(prices) < max_lag:
            return 0.5
        
        lags = range(2, min(max_lag, len(prices) // 2))
        rs_values = []
        
        for lag in lags:
            rs = self._rs_for_lag(prices, lag)
            if rs > 0:
                rs_values.append((np.log(lag), np.log(rs)))
        
        if len(rs_values) < 10:
            return 0.5
        
        x = np.array([v[0] for v in rs_values])
        y = np.array([v[1] for v in rs_values])
        
        slope, _, _, _, _ = stats.linregress(x, y)
        return round(max(0, min(1, slope)), 3)

    def _rs_for_lag(self, prices: np.ndarray, lag: int) -> float:
        """Calculate R/S statistic for a given lag."""
        returns = np.diff(np.log(prices))
        n = len(returns)
        
        if n < lag:
            return 0.0
        
        rs_list = []
        for start in range(0, n - lag + 1, lag):
            segment = returns[start:start + lag]
            mean_adj = segment - segment.mean()
            cumsum = np.cumsum(mean_adj)
            r = cumsum.max() - cumsum.min()
            s = segment.std()
            if s > 0:
                rs_list.append(r / s)
        
        return np.mean(rs_list) if rs_list else 0.0

    def _calc_zscore(self, prices: np.ndarray, period: int) -> float:
        """Calculate Z-score of current price vs period mean."""
        if len(prices) < period:
            return 0.0
        
        recent = prices[-period:]
        mean = recent.mean()
        std = recent.std()
        
        if std == 0:
            return 0.0
        
        return round((prices[-1] - mean) / std, 2)

    def _calc_bb_width_percentile(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculate Bollinger Band width percentile (volatility contraction)."""
        if len(df) < period * 2:
            return 50.0
        
        closes = df["close"].values
        widths = []
        
        for i in range(period, len(closes)):
            window = closes[i - period:i]
            mean = window.mean()
            std = window.std()
            if mean > 0:
                width = (2 * 2 * std) / mean * 100
                widths.append(width)
        
        if not widths:
            return 50.0
        
        current_width = widths[-1]
        percentile = stats.percentileofscore(widths, current_width)
        return round(percentile, 1)

    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(df) < period:
            return 0.0
        
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        
        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:] - close[:-1])
            )
        )
        
        atr = np.mean(tr[-period:])
        return round(atr, 2)


class OptionsQuantBot:
    """
    Quantitative calculator for F&O options.
    
    Computes: Greeks, IVP/IVR, PCR, Max Pain, GEX, structure recommendations.
    """

    def analyze(
        self,
        underlying: str,
        spot: float,
        option_chain: List[Dict],
        expiry_date: date,
        historical_iv: Optional[List[float]] = None,
    ) -> OptionsQuantReport:
        """
        Generate comprehensive quant report for options.
        
        Args:
            underlying: Underlying symbol (NIFTY, BANKNIFTY, stock)
            spot: Current spot price
            option_chain: List of option chain rows with OI, IV, LTP
            expiry_date: Expiry date for Greeks calculation
            historical_iv: 252-day historical IV values for IVP/IVR
        """
        report = OptionsQuantReport(underlying=underlying, spot=spot)
        
        try:
            if not option_chain:
                return report
            
            df = pd.DataFrame(option_chain)
            
            # Find ATM strike
            atm_strike = self._find_atm(df, spot)
            report.atm_strike = atm_strike
            
            # Calculate Greeks for ATM
            days_to_expiry = max(1, (expiry_date - date.today()).days)
            tau = days_to_expiry / 365.0
            
            atm_row = df[df["strike"] == atm_strike]
            if not atm_row.empty:
                atm_iv = float(atm_row.iloc[0].get("ce_iv", 0.2) or 0.2)
                report.atm_iv = atm_iv
                
                # CE Greeks
                ce_greeks = self._calc_greeks(spot, atm_strike, tau, atm_iv, "CE")
                report.atm_ce_delta = ce_greeks["delta"]
                report.atm_ce_gamma = ce_greeks["gamma"]
                report.atm_ce_theta = ce_greeks["theta"]
                report.atm_ce_vega = ce_greeks["vega"]
                
                # PE Greeks
                pe_greeks = self._calc_greeks(spot, atm_strike, tau, atm_iv, "PE")
                report.atm_pe_delta = pe_greeks["delta"]
                report.atm_pe_gamma = pe_greeks["gamma"]
                report.atm_pe_theta = pe_greeks["theta"]
                report.atm_pe_vega = pe_greeks["vega"]
            
            # IV Percentile & Rank
            if historical_iv and len(historical_iv) >= 252:
                report.iv_percentile = self._calc_ivp(report.atm_iv, historical_iv)
                report.iv_rank = self._calc_ivr(report.atm_iv, historical_iv)
            
            # OI Microstructure
            oi_metrics = self._calc_oi_metrics(df)
            report.pcr_oi = oi_metrics["pcr_oi"]
            report.pcr_change_oi = oi_metrics["pcr_change_oi"]
            report.max_pain = oi_metrics["max_pain"]
            report.call_wall = oi_metrics["call_wall"]
            report.put_wall = oi_metrics["put_wall"]
            
            # GEX (Gamma Exposure)
            gex = self._calc_gex(df, spot, tau)
            report.net_gex = gex["net_gex"]
            report.gex_regime = gex["regime"]
            
            # Structure Recommendation
            rec = self._recommend_structure(report)
            report.recommended_structure = rec["structure"]
            report.structure_rationale = rec["rationale"]
            
        except Exception as e:
            logger.warning("OptionsQuantBot.analyze failed for %s: %s", underlying, e)
        
        return report

    def _find_atm(self, df: pd.DataFrame, spot: float) -> float:
        """Find ATM strike closest to spot."""
        if df.empty or "strike" not in df.columns:
            return 0.0
        strikes = df["strike"].unique()
        return float(min(strikes, key=lambda s: abs(s - spot)))

    def _calc_greeks(
        self,
        spot: float,
        strike: float,
        tau: float,
        iv: float,
        option_type: str,
    ) -> Dict[str, float]:
        """Calculate Black-Scholes Greeks."""
        result = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        
        if tau <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
            return result
        
        try:
            sqrt_tau = math.sqrt(tau)
            d1 = (math.log(spot / strike) + (RISK_FREE_RATE + 0.5 * iv ** 2) * tau) / (iv * sqrt_tau)
            d2 = d1 - iv * sqrt_tau
            
            nd1 = stats.norm.cdf(d1)
            nd2 = stats.norm.cdf(d2)
            pdf_d1 = stats.norm.pdf(d1)
            
            if option_type == "CE":
                delta = nd1
                theta = (
                    -spot * pdf_d1 * iv / (2 * sqrt_tau)
                    - RISK_FREE_RATE * strike * math.exp(-RISK_FREE_RATE * tau) * nd2
                ) / 365
            else:
                delta = nd1 - 1
                theta = (
                    -spot * pdf_d1 * iv / (2 * sqrt_tau)
                    + RISK_FREE_RATE * strike * math.exp(-RISK_FREE_RATE * tau) * (1 - nd2)
                ) / 365
            
            gamma = pdf_d1 / (spot * iv * sqrt_tau)
            vega = spot * pdf_d1 * sqrt_tau / 100
            
            result["delta"] = round(delta, 4)
            result["gamma"] = round(gamma, 6)
            result["theta"] = round(theta, 4)
            result["vega"] = round(vega, 4)
            
        except Exception as e:
            logger.debug("Greeks calculation error: %s", e)
        
        return result

    def _calc_ivp(self, current_iv: float, historical_iv: List[float]) -> float:
        """Calculate IV Percentile (% of days IV was lower)."""
        if not historical_iv:
            return 50.0
        return round(stats.percentileofscore(historical_iv, current_iv), 1)

    def _calc_ivr(self, current_iv: float, historical_iv: List[float]) -> float:
        """Calculate IV Rank ((current - min) / (max - min))."""
        if not historical_iv:
            return 50.0
        iv_min = min(historical_iv)
        iv_max = max(historical_iv)
        if iv_max == iv_min:
            return 50.0
        return round((current_iv - iv_min) / (iv_max - iv_min) * 100, 1)

    def _calc_oi_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate OI-based metrics: PCR, Max Pain, Walls."""
        result = {
            "pcr_oi": 1.0,
            "pcr_change_oi": 1.0,
            "max_pain": 0.0,
            "call_wall": 0.0,
            "put_wall": 0.0,
        }
        
        if df.empty:
            return result
        
        # PCR by OI
        total_ce_oi = df["ce_oi"].sum() if "ce_oi" in df.columns else 0
        total_pe_oi = df["pe_oi"].sum() if "pe_oi" in df.columns else 0
        if total_ce_oi > 0:
            result["pcr_oi"] = round(total_pe_oi / total_ce_oi, 3)
        
        # PCR by Change in OI
        total_ce_chg = df["ce_change_oi"].sum() if "ce_change_oi" in df.columns else 0
        total_pe_chg = df["pe_change_oi"].sum() if "pe_change_oi" in df.columns else 0
        if total_ce_chg > 0:
            result["pcr_change_oi"] = round(total_pe_chg / total_ce_chg, 3)
        
        # Call Wall (highest CE OI)
        if "ce_oi" in df.columns:
            max_ce_idx = df["ce_oi"].idxmax()
            result["call_wall"] = float(df.loc[max_ce_idx, "strike"])
        
        # Put Wall (highest PE OI)
        if "pe_oi" in df.columns:
            max_pe_idx = df["pe_oi"].idxmax()
            result["put_wall"] = float(df.loc[max_pe_idx, "strike"])
        
        # Max Pain
        result["max_pain"] = self._calc_max_pain(df)
        
        return result

    def _calc_max_pain(self, df: pd.DataFrame) -> float:
        """Calculate max pain strike."""
        if df.empty or "strike" not in df.columns:
            return 0.0
        
        strikes = df["strike"].unique()
        min_pain = float("inf")
        max_pain_strike = 0.0
        
        for target in strikes:
            pain = 0.0
            for _, row in df.iterrows():
                strike = row["strike"]
                ce_oi = row.get("ce_oi", 0) or 0
                pe_oi = row.get("pe_oi", 0) or 0
                
                if target > strike:
                    pain += (target - strike) * ce_oi
                if target < strike:
                    pain += (strike - target) * pe_oi
            
            if pain < min_pain:
                min_pain = pain
                max_pain_strike = target
        
        return float(max_pain_strike)

    def _calc_gex(self, df: pd.DataFrame, spot: float, tau: float) -> Dict[str, Any]:
        """
        Calculate Net Dealer Gamma Exposure (GEX).
        
        GEX = (CE_OI * CE_Gamma - PE_OI * PE_Gamma) * Spot^2 * 0.01
        
        Positive GEX = Mean-reverting (dealers hedge by selling rallies, buying dips)
        Negative GEX = Trending (dealers amplify moves)
        """
        result = {"net_gex": 0.0, "regime": "NEUTRAL"}
        
        if df.empty or tau <= 0:
            return result
        
        net_gex = 0.0
        
        for _, row in df.iterrows():
            strike = row.get("strike", 0)
            ce_oi = row.get("ce_oi", 0) or 0
            pe_oi = row.get("pe_oi", 0) or 0
            iv = row.get("ce_iv", 0.2) or 0.2
            
            if strike <= 0 or iv <= 0:
                continue
            
            # Calculate gamma for this strike
            ce_greeks = self._calc_greeks(spot, strike, tau, iv, "CE")
            pe_greeks = self._calc_greeks(spot, strike, tau, iv, "PE")
            
            ce_gamma = ce_greeks["gamma"]
            pe_gamma = pe_greeks["gamma"]
            
            # GEX contribution
            strike_gex = (ce_oi * ce_gamma - pe_oi * pe_gamma) * (spot ** 2) * 0.01
            net_gex += strike_gex
        
        result["net_gex"] = round(net_gex / 1e9, 2)  # In billions
        
        # Classify regime
        if net_gex > 1e9:
            result["regime"] = "POSITIVE_GEX"
        elif net_gex < -1e9:
            result["regime"] = "NEGATIVE_GEX"
        
        return result

    def _recommend_structure(self, report: OptionsQuantReport) -> Dict[str, str]:
        """
        Recommend option structure based on IV and GEX regime.
        
        Low IV + Breakout/Negative GEX -> Debit structures
        High IV + Positive GEX -> Credit structures
        """
        ivp = report.iv_percentile
        gex = report.gex_regime
        
        # Low IV environment (IVP < 35)
        if ivp < 35:
            if gex == "NEGATIVE_GEX":
                return {
                    "structure": "LONG_STRADDLE",
                    "rationale": f"Low IV ({ivp:.0f}%) + Negative GEX = Breakout expected. Buy ATM straddle.",
                }
            else:
                return {
                    "structure": "DEBIT_SPREAD",
                    "rationale": f"Low IV ({ivp:.0f}%) = Cheap options. Use directional debit spread.",
                }
        
        # High IV environment (IVP > 65)
        if ivp > 65:
            if gex == "POSITIVE_GEX":
                return {
                    "structure": "IRON_CONDOR",
                    "rationale": f"High IV ({ivp:.0f}%) + Positive GEX = Range-bound. Sell iron condor.",
                }
            else:
                return {
                    "structure": "CREDIT_SPREAD",
                    "rationale": f"High IV ({ivp:.0f}%) = Expensive options. Sell credit spread with hedge.",
                }
        
        # Neutral IV
        return {
            "structure": "WAIT",
            "rationale": f"IV ({ivp:.0f}%) in neutral zone. Wait for better setup.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Factory functions
# ─────────────────────────────────────────────────────────────────────────────

_cash_bot: Optional[CashEquityQuantBot] = None
_options_bot: Optional[OptionsQuantBot] = None


def get_cash_quant_bot() -> CashEquityQuantBot:
    """Get singleton CashEquityQuantBot."""
    global _cash_bot
    if _cash_bot is None:
        _cash_bot = CashEquityQuantBot()
    return _cash_bot


def get_options_quant_bot() -> OptionsQuantBot:
    """Get singleton OptionsQuantBot."""
    global _options_bot
    if _options_bot is None:
        _options_bot = OptionsQuantBot()
    return _options_bot
