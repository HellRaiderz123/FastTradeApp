"""
Technical Indicators Engine
RSI, MACD, Bollinger Bands, ADX, Moving Averages, and more
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """Calculate technical indicators from price/volume data"""
    
    @staticmethod
    def calculate_sma(prices: List[float], period: int) -> Optional[float]:
        """Simple Moving Average"""
        try:
            if len(prices) < period:
                return None
            return sum(prices[-period:]) / period
        except Exception as e:
            logger.warning(f"Error calculating SMA: {e}")
            return None
    
    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> Optional[float]:
        """Exponential Moving Average"""
        try:
            if len(prices) < period:
                return None
            
            # Start with SMA for first value
            prices_array = np.array(prices)
            weights = np.exp(np.linspace(-1., 0., period))
            weights /= weights.sum()
            
            ema_values = []
            for i in range(period - 1, len(prices_array)):
                window = prices_array[i - period + 1:i + 1]
                ema = np.dot(window, weights)
                ema_values.append(ema)
            
            return float(ema_values[-1]) if ema_values else None
        except Exception as e:
            logger.warning(f"Error calculating EMA: {e}")
            return None
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Relative Strength Index
        
        RSI = 100 - (100 / (1 + RS))
        RS = Average Gain / Average Loss
        """
        try:
            if len(prices) < period + 1:
                return None
            
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])
            
            if avg_loss == 0:
                return 100.0
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return round(rsi, 2)
        except Exception as e:
            logger.warning(f"Error calculating RSI: {e}")
            return None
    
    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """
        Moving Average Convergence Divergence
        
        Returns:
            {
                "macd": MACD line,
                "signal": Signal line,
                "histogram": MACD - Signal
            }
        """
        try:
            if len(prices) < slow_period + signal_period:
                return None
            
            # Calculate EMAs
            fast_ema = TechnicalIndicators._calc_ema_series(prices, fast_period)
            slow_ema = TechnicalIndicators._calc_ema_series(prices, slow_period)
            
            if fast_ema is None or slow_ema is None:
                return None
            
            # MACD line
            macd_line = fast_ema[-1] - slow_ema[-1]
            
            # Calculate signal line (EMA of MACD)
            macd_series = [f - s for f, s in zip(fast_ema, slow_ema)]
            signal_line = TechnicalIndicators._calc_ema_series(macd_series, signal_period)
            
            if signal_line is None:
                return None
            
            signal = signal_line[-1]
            histogram = macd_line - signal
            
            return {
                "macd": round(macd_line, 2),
                "signal": round(signal, 2),
                "histogram": round(histogram, 2)
            }
        except Exception as e:
            logger.warning(f"Error calculating MACD: {e}")
            return None
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """
        Bollinger Bands
        
        Middle Band = SMA(period)
        Upper Band = Middle + (std_dev * standard deviation)
        Lower Band = Middle - (std_dev * standard deviation)
        """
        try:
            if len(prices) < period:
                return None
            
            recent_prices = prices[-period:]
            middle = sum(recent_prices) / period
            
            variance = sum((p - middle) ** 2 for p in recent_prices) / period
            std = variance ** 0.5
            
            upper = middle + (std_dev * std)
            lower = middle - (std_dev * std)
            
            # Calculate %B (position within bands)
            current_price = prices[-1]
            percent_b = (current_price - lower) / (upper - lower) if upper != lower else 0.5
            
            # Calculate bandwidth
            bandwidth = ((upper - lower) / middle) * 100 if middle != 0 else 0
            
            return {
                "upper": round(upper, 2),
                "middle": round(middle, 2),
                "lower": round(lower, 2),
                "percent_b": round(percent_b, 2),
                "bandwidth": round(bandwidth, 2)
            }
        except Exception as e:
            logger.warning(f"Error calculating Bollinger Bands: {e}")
            return None
    
    @staticmethod
    def calculate_adx(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> Optional[Dict[str, float]]:
        """
        Average Directional Index (ADX)
        Measures trend strength (0-100) using Wilder-style smoothing.

        Returns:
            {
                "adx": ADX value (0-100),
                "plus_di": +DI,
                "minus_di": -DI
            }
        """
        try:
            if len(highs) <= period or len(lows) <= period or len(closes) <= period:
                return None

            tr_list: List[float] = []
            plus_dm_list: List[float] = []
            minus_dm_list: List[float] = []

            for i in range(1, len(closes)):
                up_move = highs[i] - highs[i - 1]
                down_move = lows[i - 1] - lows[i]

                plus_dm_list.append(up_move if up_move > down_move and up_move > 0 else 0.0)
                minus_dm_list.append(down_move if down_move > up_move and down_move > 0 else 0.0)

                high_low = highs[i] - lows[i]
                high_close = abs(highs[i] - closes[i - 1])
                low_close = abs(lows[i] - closes[i - 1])
                tr_list.append(max(high_low, high_close, low_close))

            if len(tr_list) < period:
                return None

            tr_smooth = sum(tr_list[:period])
            plus_dm_smooth = sum(plus_dm_list[:period])
            minus_dm_smooth = sum(minus_dm_list[:period])

            dx_values: List[float] = []
            plus_di = 0.0
            minus_di = 0.0

            for idx in range(period, len(tr_list)):
                if idx > period:
                    tr_smooth = tr_smooth - (tr_smooth / period) + tr_list[idx]
                    plus_dm_smooth = plus_dm_smooth - (plus_dm_smooth / period) + plus_dm_list[idx]
                    minus_dm_smooth = minus_dm_smooth - (minus_dm_smooth / period) + minus_dm_list[idx]

                if tr_smooth <= 0:
                    plus_di = 0.0
                    minus_di = 0.0
                    dx = 0.0
                else:
                    plus_di = (plus_dm_smooth / tr_smooth) * 100
                    minus_di = (minus_dm_smooth / tr_smooth) * 100
                    di_sum = plus_di + minus_di
                    dx = (abs(plus_di - minus_di) / di_sum * 100) if di_sum > 0 else 0.0

                dx_values.append(dx)

            if not dx_values:
                return None

            if len(dx_values) >= period:
                adx = sum(dx_values[:period]) / period
                for dx in dx_values[period:]:
                    adx = ((adx * (period - 1)) + dx) / period
            else:
                adx = sum(dx_values) / len(dx_values)

            return {
                "adx": round(min(max(adx, 0), 100), 2),
                "plus_di": round(min(max(plus_di, 0), 100), 2),
                "minus_di": round(min(max(minus_di, 0), 100), 2),
            }
        except Exception as e:
            logger.warning(f"Error calculating ADX: {e}")
            return None
    
    @staticmethod
    def calculate_stochastic(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        k_period: int = 14,
        d_period: int = 3
    ) -> Optional[Dict[str, float]]:
        """
        Stochastic Oscillator (slow/full variant)

        fast %K = (Current Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %K = SMA(3) of fast %K
        %D = SMA(d_period) of %K
        """
        try:
            if len(closes) < k_period:
                return None

            fast_k_values: List[float] = []
            for end_idx in range(k_period, len(closes) + 1):
                highest_high = max(highs[end_idx - k_period:end_idx])
                lowest_low = min(lows[end_idx - k_period:end_idx])
                current_close = closes[end_idx - 1]

                if highest_high == lowest_low:
                    fast_k_values.append(50.0)
                else:
                    fast_k_values.append(((current_close - lowest_low) / (highest_high - lowest_low)) * 100)

            if not fast_k_values:
                return None

            slow_window = 3
            slow_k_values: List[float] = []
            for idx in range(len(fast_k_values)):
                window = fast_k_values[max(0, idx - slow_window + 1): idx + 1]
                slow_k_values.append(sum(window) / len(window))

            d_values: List[float] = []
            for idx in range(len(slow_k_values)):
                window = slow_k_values[max(0, idx - max(1, d_period) + 1): idx + 1]
                d_values.append(sum(window) / len(window))

            k = slow_k_values[-1]
            d = d_values[-1]

            return {
                "k": round(k, 2),
                "d": round(d, 2),
                "fast_k": round(fast_k_values[-1], 2),
            }
        except Exception as e:
            logger.warning(f"Error calculating Stochastic: {e}")
            return None
    
    @staticmethod
    def calculate_atr(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14
    ) -> Optional[float]:
        """Average True Range - measures volatility."""
        try:
            if len(highs) < period or len(lows) < period or len(closes) < period:
                return None

            tr_list = []
            for i in range(len(closes)):
                high_low = highs[i] - lows[i]
                if i == 0:
                    tr = high_low
                else:
                    high_close = abs(highs[i] - closes[i - 1])
                    low_close = abs(lows[i] - closes[i - 1])
                    tr = max(high_low, high_close, low_close)
                tr_list.append(tr)

            window = tr_list[-period:]
            atr = sum(window) / max(len(window), 1)
            return round(atr, 2)
        except Exception as e:
            logger.warning(f"Error calculating ATR: {e}")
            return None
    
    @staticmethod
    def calculate_volume_analysis(
        volumes: List[float],
        prices: List[float],
        period: int = 20
    ) -> Optional[Dict[str, Any]]:
        """
        Volume Analysis
        
        Returns:
            {
                "avg_volume": Average volume,
                "volume_ratio": Current volume vs average,
                "volume_trend": "increasing" or "decreasing",
                "unusual_activity": True if volume spike detected
            }
        """
        try:
            if len(volumes) < period:
                return None
            
            current_volume = volumes[-1]
            avg_volume = sum(volumes[-period:]) / period
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Detect trend
            recent_avg = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else current_volume
            older_avg = sum(volumes[-period:-5]) / (period - 5) if len(volumes) >= period else avg_volume
            volume_trend = "increasing" if recent_avg > older_avg else "decreasing"
            
            # Unusual activity if volume > 2x average
            unusual_activity = volume_ratio > 2.0
            
            # On-Balance Volume (OBV) - simplified
            obv = 0
            for i in range(1, len(prices)):
                if prices[i] > prices[i-1]:
                    obv += volumes[i]
                elif prices[i] < prices[i-1]:
                    obv -= volumes[i]
            
            return {
                "avg_volume": round(avg_volume, 0),
                "current_volume": round(current_volume, 0),
                "volume_ratio": round(volume_ratio, 2),
                "volume_trend": volume_trend,
                "unusual_activity": unusual_activity,
                "obv": round(obv, 0)
            }
        except Exception as e:
            logger.warning(f"Error calculating volume analysis: {e}")
            return None
    
    @staticmethod
    def _calc_ema_series(prices: List[float], period: int) -> Optional[List[float]]:
        """Calculate EMA series (all values, not just last)"""
        try:
            if len(prices) < period:
                return None
            
            multiplier = 2 / (period + 1)
            ema_values = []
            
            # Start with SMA
            sma = sum(prices[:period]) / period
            ema_values.append(sma)
            
            # Calculate EMA for remaining values
            for price in prices[period:]:
                ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
                ema_values.append(ema)
            
            return ema_values
        except Exception:
            return None
    
    @staticmethod
    def detect_swing_pattern(
        prices: List[float],
        volumes: List[float],
        highs: List[float],
        lows: List[float]
    ) -> Optional[Dict[str, Any]]:
        """
        Detect swing trading patterns
        
        Returns pattern type and strength
        """
        try:
            if len(prices) < 20:
                return None
            
            closes = prices
            
            # Calculate indicators
            rsi = TechnicalIndicators.calculate_rsi(closes, 14)
            macd = TechnicalIndicators.calculate_macd(closes)
            bb = TechnicalIndicators.calculate_bollinger_bands(closes)
            adx = TechnicalIndicators.calculate_adx(highs, lows, closes)
            
            if not all([rsi, macd, bb, adx]):
                return None
            
            # Detect patterns
            patterns = []
            strength = 0
            
            # Bullish patterns
            if rsi < 35 and macd["histogram"] > 0:
                patterns.append("OVERSOLD_REVERSAL")
                strength += 25
            
            if closes[-1] < bb["lower"] and macd["macd"] > macd["signal"]:
                patterns.append("BB_BOUNCE")
                strength += 20
            
            if adx["adx"] > 25 and adx["plus_di"] > adx["minus_di"]:
                patterns.append("STRONG_UPTREND")
                strength += 30
            
            # Bearish patterns
            if rsi > 65 and macd["histogram"] < 0:
                patterns.append("OVERBOUGHT_REVERSAL")
                strength += 25
            
            if closes[-1] > bb["upper"] and macd["macd"] < macd["signal"]:
                patterns.append("BB_REJECTION")
                strength += 20
            
            if adx["adx"] > 25 and adx["minus_di"] > adx["plus_di"]:
                patterns.append("STRONG_DOWNTREND")
                strength += 30
            
            # Volume confirmation
            vol_analysis = TechnicalIndicators.calculate_volume_analysis(volumes, closes)
            if vol_analysis and vol_analysis["unusual_activity"]:
                strength += 15
                patterns.append("VOLUME_SPIKE")
            
            # Determine overall signal
            signal = "NEUTRAL"
            if strength > 50:
                if any(p in patterns for p in ["OVERSOLD_REVERSAL", "BB_BOUNCE", "STRONG_UPTREND"]):
                    signal = "BULLISH"
                elif any(p in patterns for p in ["OVERBOUGHT_REVERSAL", "BB_REJECTION", "STRONG_DOWNTREND"]):
                    signal = "BEARISH"
            
            return {
                "patterns": patterns,
                "signal": signal,
                "strength": min(strength, 100),
                "rsi": rsi,
                "adx": adx["adx"],
                "volume_spike": vol_analysis["unusual_activity"] if vol_analysis else False
            }
        except Exception as e:
            logger.warning(f"Error detecting swing pattern: {e}")
            return None
