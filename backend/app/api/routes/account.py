from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from app.core.broker.zerodha.client import get_kite_client
from app.db.session import SessionLocal
from app.db.models import DailyCapital
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["Account"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/profile")
def get_account_profile():
    """
    Fetch account profile including available capital from Zerodha.
    
    Returns:
        {
            "user_id": str,
            "email": str,
            "phone": str,
            "capital": float,
            "equity": float,
            "net_worth": float,
            "margins_available": float
        }
    """
    try:
        kite = get_kite_client()
        
        # Get account profile
        profile = kite.profile()
        
        # Get account margins/balance info
        margins = kite.margins()
        
        # Extract equity details from margins
        equity = margins.get("equity", {})
        available = equity.get("available", {})
        utilised = equity.get("utilised", {})
        
        # Capital is JUST live_balance (don't add intraday_payin - it's the same money!)
        live_balance = available.get("live_balance", 0)
        
        # Get net equity value
        net_value = equity.get("net", 0)
        
        logger.info(f"📊 Account {profile.get('user_id')}: Capital = ₹{live_balance}, Net = ₹{net_value}")
        
        # Store daily capital snapshot
        try:
            db = SessionLocal()
            today = date.today()
            existing = db.query(DailyCapital).filter(DailyCapital.trade_date == today).first()
            
            if not existing:
                daily_capital = DailyCapital(
                    trade_date=today,
                    opening_capital=live_balance,
                    closing_capital=live_balance,
                    daily_pnl=0.0,
                    daily_return_pct=0.0,
                    source="zerodha"
                )
                db.add(daily_capital)
            else:
                # Update closing capital
                existing.closing_capital = live_balance
                existing.daily_pnl = live_balance - existing.opening_capital
                if existing.opening_capital > 0:
                    existing.daily_return_pct = (existing.daily_pnl / existing.opening_capital) * 100
                existing.updated_at = datetime.now()
            
            db.commit()
        except Exception as e:
            logger.warning(f"Could not update daily capital: {e}")
        finally:
            db.close()
        
        return {
            "user_id": profile.get("user_id"),
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "capital": live_balance,  # Real available capital
            "equity": net_value,  # Net equity value
            "net_worth": net_value,  # Same as equity for now
            "margins_available": live_balance,  # Available margin
            "live_balance": live_balance,
            "cash": available.get("cash", 0),
            "collateral": available.get("collateral", 0),
        }
    
    except RuntimeError as e:
        if "API key or access token missing" in str(e):
            logger.warning("Zerodha credentials not configured, using mock data for development")
            # Return mock data for development
            return {
                "user_id": "DEMO_USER",
                "email": "demo@zerodha.com",
                "phone": "+91-9876543210",
                "capital": 500000.0,  # Demo capital
                "live_balance": 500000.0,
                "intraday_payin": 0.0,
                "adhoc_margin": 0.0,
                "cash": 500000.0,
            }
        else:
            logger.error(f"Error fetching account profile: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch account profile: {str(e)}"
            )
    
    except Exception as e:
        logger.error(f"Error fetching account profile: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch account profile: {str(e)}"
        )


@router.get("/capital")
def get_available_capital():
    """
    Get available capital from Zerodha account.
    
    Returns:
        {
            "capital": float,
            "currency": str,
            "source": str
        }
    """
    try:
        kite = get_kite_client()
        margins = kite.margins()
        
        # Extract capital from equity data - just use live_balance
        equity = margins.get("equity", {})
        available = equity.get("available", {})
        live_balance = available.get("live_balance", 0)
        
        logger.info(f"💰 Available Capital: ₹{live_balance}")
        
        return {
            "capital": live_balance,
            "currency": "INR",
            "source": "zerodha",
        }
    
    except RuntimeError as e:
        if "API key or access token missing" in str(e):
            logger.warning("Zerodha credentials not configured, using mock data for development")
            # Return mock data for development
            return {
                "capital": 100000.0,
                "currency": "INR",
                "source": "mock",
            }
        else:
            logger.error(f"Error fetching capital: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch capital: {str(e)}"
            )
    
    except Exception as e:
        logger.error(f"Error fetching capital: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch capital: {str(e)}"
        )


@router.get("/daily-capital")
def get_daily_capital_history(days: int = 30, db: Session = Depends(get_db)):
    """
    Get daily capital history for portfolio growth chart.
    
    Query params:
        days: Number of days to retrieve (default: 30)
    
    Returns:
        [
            {
                "date": "2026-01-06",
                "opening_capital": 500000,
                "closing_capital": 502500,
                "daily_pnl": 2500,
                "daily_return_pct": 0.5
            },
            ...
        ]
    """
    try:
        start_date = date.today() - timedelta(days=days)
        
        records = (
            db.query(DailyCapital)
            .filter(DailyCapital.trade_date >= start_date)
            .order_by(DailyCapital.trade_date.asc())
            .all()
        )
        
        logger.info(f"📈 Retrieved {len(records)} days of capital history")
        
        return [
            {
                "date": str(record.trade_date),
                "opening_capital": record.opening_capital,
                "closing_capital": record.closing_capital,
                "daily_pnl": record.daily_pnl,
                "daily_return_pct": record.daily_return_pct or 0.0,
            }
            for record in records
        ]
    
    except Exception as e:
        logger.error(f"Error fetching daily capital history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch capital history: {str(e)}"
        )


@router.post("/daily-capital")
def record_daily_capital(
    capital: float,
    date_str: str = None,
    db: Session = Depends(get_db)
):
    """
    Record daily capital snapshot.
    
    Body:
        {
            "capital": 502500,
            "date": "2026-01-06"  # optional, defaults to today
        }
    
    Returns:
        {
            "success": true,
            "message": "Capital recorded for 2026-01-06"
        }
    """
    try:
        target_date = date.fromisoformat(date_str) if date_str else date.today()
        
        existing = db.query(DailyCapital).filter(DailyCapital.trade_date == target_date).first()
        
        if existing:
            # Update closing capital
            existing.closing_capital = capital
            existing.daily_pnl = capital - existing.opening_capital
            if existing.opening_capital > 0:
                existing.daily_return_pct = (existing.daily_pnl / existing.opening_capital) * 100
            existing.updated_at = datetime.now()
        else:
            # Create new record (opening and closing same for first snapshot)
            existing = DailyCapital(
                trade_date=target_date,
                opening_capital=capital,
                closing_capital=capital,
                daily_pnl=0.0,
                daily_return_pct=0.0,
                source="manual"
            )
            db.add(existing)
        
        db.commit()
        logger.info(f"✅ Capital recorded: {target_date} = ₹{capital}")
        
        return {
            "success": True,
            "message": f"Capital recorded for {target_date}"
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error recording capital: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record capital: {str(e)}"
        )

