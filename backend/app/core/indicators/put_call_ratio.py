"""
Put/Call Ratio Analysis
Track Put/Call ratio for market sentiment analysis
"""

import logging
from typing import Dict, Optional, List, Tuple
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PutCallRatioAnalyzer:
    """Analyze Put/Call ratios for market sentiment"""
    
    def __init__(self, db: Session = None):
        self.db = db
    
    def calculate_pcr(
        self,
        put_oi: float,
        call_oi: float,
    ) -> Optional[float]:
        """
        Calculate Put/Call Ratio
        PCR = Total Put OI / Total Call OI
        
        Args:
            put_oi: Total open interest in puts
            call_oi: Total open interest in calls
        
        Returns:
            Put/Call ratio (typically 0.5 to 2.0)
        """
        try:
            if call_oi == 0:
                return None
            
            pcr = put_oi / call_oi
            return round(pcr, 4)
        
        except Exception as e:
            logger.warning(f"Error calculating PCR: {e}")
            return None
    
    def calculate_pcr_from_chain(
        self,
        option_chain: Dict,
    ) -> Dict[str, float]:
        """
        Calculate PCR from option chain
        
        Args:
            option_chain: {
                "data": [
                    {"strike": 26000, "call_oi": 10000, "put_oi": 8000},
                    ...
                ]
            }
        
        Returns:
            {
                "total_put_oi": 500000,
                "total_call_oi": 600000,
                "pcr": 0.833,
                "by_strike": {26000: 0.8, 26100: 0.85, ...}
            }
        """
        try:
            data = option_chain.get("data", [])
            
            total_put_oi = 0
            total_call_oi = 0
            by_strike = {}
            
            for item in data:
                strike = item.get("strike")
                call_oi = item.get("call_oi", 0)
                put_oi = item.get("put_oi", 0)
                
                if not strike:
                    continue
                
                total_call_oi += call_oi
                total_put_oi += put_oi
                
                if call_oi > 0:
                    by_strike[strike] = self.calculate_pcr(put_oi, call_oi) or 0.0
            
            pcr = self.calculate_pcr(total_put_oi, total_call_oi)
            
            return {
                "total_put_oi": total_put_oi,
                "total_call_oi": total_call_oi,
                "pcr": pcr or 0.0,
                "by_strike": by_strike,
            }
        
        except Exception as e:
            logger.error(f"Error calculating PCR from chain: {e}")
            return {
                "total_put_oi": 0,
                "total_call_oi": 0,
                "pcr": 0.0,
                "by_strike": {},
            }
    
    def get_pcr_interpretation(self, pcr: Optional[float]) -> str:
        """
        Interpret Put/Call ratio
        
        PCR Ranges:
        < 0.50: Extremely bullish (calls dominate)
        0.50-0.75: Bullish
        0.75-1.25: Neutral/Normal
        1.25-2.0: Bearish
        > 2.0: Extremely bearish (puts dominate)
        """
        if pcr is None:
            return "Unknown"
        
        if pcr < 0.50:
            return "Extremely Bullish (Calls >> Puts)"
        elif pcr < 0.75:
            return "Bullish (Calls > Puts)"
        elif pcr < 1.25:
            return "Neutral/Normal"
        elif pcr < 2.0:
            return "Bearish (Puts > Calls)"
        else:
            return "Extremely Bearish (Puts >> Calls)"
    
    def calculate_pcr_change(
        self,
        current_pcr: float,
        previous_pcr: float,
    ) -> Dict[str, float]:
        """
        Calculate PCR change from previous value
        """
        try:
            if previous_pcr == 0:
                pcr_change_pct = 0
            else:
                pcr_change_pct = ((current_pcr - previous_pcr) / previous_pcr) * 100
            
            return {
                "current": current_pcr,
                "previous": previous_pcr,
                "change": current_pcr - previous_pcr,
                "change_pct": round(pcr_change_pct, 2),
            }
        
        except Exception as e:
            logger.warning(f"Error calculating PCR change: {e}")
            return {}
    
    def get_pcr_levels(self) -> Dict[str, float]:
        """
        Get typical PCR levels for Indian market
        """
        return {
            "extremely_bullish": 0.40,
            "very_bullish": 0.50,
            "bullish": 0.70,
            "neutral_low": 0.90,
            "neutral_high": 1.10,
            "bearish": 1.30,
            "very_bearish": 1.60,
            "extremely_bearish": 2.0,
        }


class OptionChainAnalysis:
    """Comprehensive option chain analysis"""
    
    def __init__(self, db: Session = None):
        self.db = db
        self.pcr_analyzer = PutCallRatioAnalyzer(db)
    
    def analyze_chain(
        self,
        option_chain: Dict,
        spot: float,
    ) -> Dict:
        """
        Comprehensive analysis of option chain
        """
        try:
            data = option_chain.get("data", [])
            
            # Calculate total OI
            total_oi = sum(
                item.get("call_oi", 0) + item.get("put_oi", 0)
                for item in data
            )
            
            # Find max OI strikes
            max_call_oi = 0
            max_put_oi = 0
            max_call_strike = None
            max_put_strike = None
            
            for item in data:
                call_oi = item.get("call_oi", 0)
                put_oi = item.get("put_oi", 0)
                strike = item.get("strike")
                
                if call_oi > max_call_oi:
                    max_call_oi = call_oi
                    max_call_strike = strike
                
                if put_oi > max_put_oi:
                    max_put_oi = put_oi
                    max_put_strike = strike
            
            # Calculate PCR
            pcr_data = self.pcr_analyzer.calculate_pcr_from_chain(option_chain)
            
            # Identify support/resistance (max OI levels)
            support = max_put_strike  # Puts are protection below
            resistance = max_call_strike  # Calls are upside above
            
            return {
                "total_oi": total_oi,
                "pcr": pcr_data["pcr"],
                "pcr_interpretation": self.pcr_analyzer.get_pcr_interpretation(pcr_data["pcr"]),
                "put_oi": pcr_data["total_put_oi"],
                "call_oi": pcr_data["total_call_oi"],
                "max_call_strike": max_call_strike,
                "max_put_strike": max_put_strike,
                "support_level": max_put_strike,  # High put OI = support
                "resistance_level": max_call_strike,  # High call OI = resistance
                "spot_price": spot,
                "distance_to_support": spot - max_put_strike if max_put_strike else 0,
                "distance_to_resistance": max_call_strike - spot if max_call_strike else 0,
            }
        
        except Exception as e:
            logger.error(f"Error analyzing chain: {e}")
            return {}
    
    def get_sentiment_score(
        self,
        pcr: float,
        spot: float,
        support: float,
        resistance: float,
    ) -> Dict[str, float]:
        """
        Calculate sentiment score (-100 to +100)
        -100: Extremely bearish
        0: Neutral
        +100: Extremely bullish
        """
        try:
            # PCR component (-40 to +40)
            pcr_score = 0
            if pcr < 0.50:
                pcr_score = 40
            elif pcr < 0.75:
                pcr_score = 20
            elif pcr < 1.25:
                pcr_score = 0
            elif pcr < 2.0:
                pcr_score = -20
            else:
                pcr_score = -40
            
            # Position component (-30 to +30)
            if support and resistance:
                midpoint = (support + resistance) / 2
                position_in_range = (spot - support) / (resistance - support)
                
                if position_in_range > 0.6:
                    position_score = 30
                elif position_in_range > 0.4:
                    position_score = 10
                else:
                    position_score = -20
            else:
                position_score = 0
            
            # Support/Resistance component (-30 to +30)
            if support and spot < support * 1.02:
                # Near support
                bounce_score = -30
            elif resistance and spot > resistance * 0.98:
                # Near resistance
                bounce_score = 30
            else:
                bounce_score = 0
            
            total_score = pcr_score + position_score + bounce_score
            
            return {
                "pcr_score": pcr_score,
                "position_score": position_score,
                "bounce_score": bounce_score,
                "total_score": total_score,
                "sentiment": "Bearish" if total_score < -30 else "Neutral" if total_score < 30 else "Bullish",
            }
        
        except Exception as e:
            logger.warning(f"Error calculating sentiment score: {e}")
            return {}
