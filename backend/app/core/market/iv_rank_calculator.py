"""
iv_rank_calculator.py
--------------------
Calculate IV Rank from historic VIX data stored in database.
IV Rank = (Current VIX - 52w Low) / (52w High - 52w Low) * 100
"""

import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.models import VixHistoric

logger = logging.getLogger(__name__)


def get_52week_vix_range(db: Session) -> Tuple[Optional[float], Optional[float]]:
    """
    Get 52-week high and low VIX values from database.
    
    Returns:
        (52w_high, 52w_low) or (None, None) if insufficient data
    """
    try:
        # Get data from last 52 weeks
        fifty_two_weeks_ago = datetime.now().date() - timedelta(days=365)
        
        vix_data = (
            db.query(VixHistoric)
            .filter(VixHistoric.trade_date >= fifty_two_weeks_ago)
            .all()
        )
        
        if not vix_data:
            logger.warning("No historic VIX data found for 52-week range")
            return None, None
        
        vix_values = [v.india_vix for v in vix_data if v.india_vix is not None]
        
        if not vix_values:
            logger.warning("No valid VIX values in 52-week range")
            return None, None
        
        high_52w = max(vix_values)
        low_52w = min(vix_values)
        
        logger.info(f"52-week VIX range: {low_52w:.2f} - {high_52w:.2f}")
        return high_52w, low_52w
        
    except Exception as e:
        logger.error(f"Error calculating 52-week range: {e}")
        return None, None


def calculate_iv_rank(
    current_vix: float,
    high_52w: Optional[float],
    low_52w: Optional[float]
) -> Optional[float]:
    """
    Calculate IV Rank percentile.
    
    IV Rank = (Current VIX - 52w Low) / (52w High - 52w Low) * 100
    
    Args:
        current_vix: Current India VIX value
        high_52w: 52-week high VIX
        low_52w: 52-week low VIX
        
    Returns:
        IV Rank (0-100) or None if calculation not possible
    """
    try:
        # Validation
        if high_52w is None or low_52w is None:
            logger.warning("Cannot calculate IV Rank: Missing 52-week range")
            return None
        
        if high_52w == low_52w:
            logger.warning("52-week high equals low (no volatility change)")
            return 50.0  # Neutral
        
        if high_52w < low_52w:
            logger.error(f"Invalid range: {high_52w} < {low_52w}")
            return None
        
        # Calculate
        iv_rank = ((current_vix - low_52w) / (high_52w - low_52w)) * 100
        
        # Clamp to 0-100
        iv_rank = max(0, min(100, iv_rank))
        
        logger.debug(f"IV Rank: {iv_rank:.2f}% (VIX={current_vix}, Range={low_52w:.2f}-{high_52w:.2f})")
        return iv_rank
        
    except Exception as e:
        logger.error(f"Error calculating IV Rank: {e}")
        return None


def update_daily_iv_rank(db: Session, india_vix: float, trade_date=None) -> Optional[float]:
    """
    Update IV Rank for today and store in database.
    
    Args:
        db: Database session
        india_vix: Current India VIX value
        trade_date: Date to update (default: today)
        
    Returns:
        Calculated IV Rank or None if failed
    """
    try:
        if trade_date is None:
            trade_date = datetime.now().date()
        
        # Get 52-week range
        high_52w, low_52w = get_52week_vix_range(db)
        
        # Calculate IV Rank
        iv_rank = calculate_iv_rank(india_vix, high_52w, low_52w)
        
        # Store/update in database
        existing = (
            db.query(VixHistoric)
            .filter(VixHistoric.trade_date == trade_date)
            .first()
        )
        
        if existing:
            existing.india_vix = india_vix
            existing.vix_52w_high = high_52w
            existing.vix_52w_low = low_52w
            existing.iv_rank = iv_rank
            existing.updated_at = datetime.now()
            logger.info(f"Updated VIX record for {trade_date}: VIX={india_vix}, IV_Rank={iv_rank}")
        else:
            new_record = VixHistoric(
                trade_date=trade_date,
                india_vix=india_vix,
                vix_52w_high=high_52w,
                vix_52w_low=low_52w,
                iv_rank=iv_rank,
                source="zerodha"
            )
            db.add(new_record)
            logger.info(f"Created VIX record for {trade_date}: VIX={india_vix}, IV_Rank={iv_rank}")
        
        db.commit()
        return iv_rank
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating IV Rank: {e}")
        return None


def get_latest_iv_rank(db: Session) -> Optional[float]:
    """
    Get the latest calculated IV Rank from database.
    
    Returns:
        Latest IV Rank or None if not available
    """
    try:
        latest = (
            db.query(VixHistoric)
            .filter(VixHistoric.iv_rank.isnot(None))
            .order_by(VixHistoric.trade_date.desc())
            .first()
        )
        
        if latest and latest.iv_rank is not None:
            logger.debug(f"Latest IV Rank: {latest.iv_rank:.2f}% (from {latest.trade_date})")
            return latest.iv_rank
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching latest IV Rank: {e}")
        return None


def get_vix_historic_stats(db: Session) -> dict:
    """
    Get statistics about stored VIX data.
    
    Returns:
        Dict with counts and ranges
    """
    try:
        count = db.query(VixHistoric).count()
        
        if count == 0:
            return {
                "total_records": 0,
                "latest_date": None,
                "earliest_date": None,
                "current_vix": None,
                "current_iv_rank": None,
                "52w_high": None,
                "52w_low": None,
            }
        
        latest = (
            db.query(VixHistoric)
            .order_by(VixHistoric.trade_date.desc())
            .first()
        )
        
        earliest = (
            db.query(VixHistoric)
            .order_by(VixHistoric.trade_date.asc())
            .first()
        )
        
        # Get 52-week stats
        high_52w, low_52w = get_52week_vix_range(db)
        
        return {
            "total_records": count,
            "latest_date": str(latest.trade_date) if latest else None,
            "earliest_date": str(earliest.trade_date) if earliest else None,
            "current_vix": latest.india_vix if latest else None,
            "current_iv_rank": latest.iv_rank if latest else None,
            "52w_high": high_52w,
            "52w_low": low_52w,
        }
        
    except Exception as e:
        logger.error(f"Error getting VIX stats: {e}")
        return {}
