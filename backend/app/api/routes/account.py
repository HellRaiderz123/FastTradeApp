from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from app.db.session import SessionLocal
from app.db.models import DailyCapital
from app.core.broker.registry import get_active_broker, get_registry
from app.core.execution.mode import get_execution_mode, is_live_mode
import logging
import os

PAPER_CAPITAL = 20_000_000.0  # ₹2 Cr virtual capital for PAPER_TRADING / DRY_RUN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["Account"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_zerodha_profile() -> dict:
    """Fetch profile + margins from Zerodha Kite."""
    from app.core.broker.zerodha.client import get_kite_client
    kite = get_kite_client()
    profile = kite.profile()
    margins = kite.margins()
    equity = margins.get("equity", {})
    available = equity.get("available", {})
    live_balance = available.get("live_balance", 0)
    net_value = equity.get("net", 0)
    logger.info("📊 Zerodha account %s: Capital=₹%s", profile.get("user_id"), live_balance)
    return {
        "user_id": profile.get("user_id"),
        "email": profile.get("email"),
        "phone": profile.get("phone"),
        "broker": "ZERODHA",
        "capital": live_balance,
        "equity": net_value,
        "net_worth": net_value,
        "margins_available": live_balance,
        "live_balance": live_balance,
        "cash": available.get("cash", 0),
        "collateral": available.get("collateral", 0),
    }


def _parse_indmoney_funds(raw: dict) -> dict:
    """Extract balance fields from INDstocks /funds response.
    Tries multiple known key shapes across API versions.
    """
    def _f(obj, *keys):
        for k in keys:
            v = obj.get(k)
            if v is not None:
                try:
                    return float(v)
                except Exception:
                    pass
        return 0.0

    # Unwrap common envelope shapes: {data: {...}} or {data: [{...}]}
    data = raw.get("data", raw)
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        data = raw

    available = _f(data, "available_balance", "availableBalance", "available",
                   "net", "net_balance", "netBalance", "cash", "balance")
    used = _f(data, "used_margin", "usedMargin", "utilised", "used")
    total = _f(data, "total_balance", "totalBalance", "total", "gross") or (available + used)
    collateral = _f(data, "collateral", "collateralValue")

    return {
        "live_balance": available,
        "cash": available,
        "margins_available": available,
        "capital": available,
        "equity": total,
        "net_worth": total,
        "collateral": collateral,
        "used_margin": used,
        "raw_funds": raw,
    }


def _get_indmoney_profile() -> dict:
    """Fetch profile + funds from INDMoney."""
    from app.core.broker.indmoney.client import get_indmoney_client
    client = get_indmoney_client()
    user_id = os.getenv("INDMONEY_CLIENT_ID", "INDMONEY_USER")

    funds_data: dict = {}
    try:
        raw = client.get_funds()
        funds_data = _parse_indmoney_funds(raw)
        logger.info("📊 INDMoney account %s: available=₹%s", user_id, funds_data.get("live_balance"))
    except Exception as exc:
        logger.warning("INDMoney funds fetch failed: %s", exc)

    return {
        "user_id": user_id,
        "email": "",
        "phone": "",
        "broker": "INDMONEY",
        **funds_data,
    }


def _snapshot_daily_capital(live_balance: float, broker: str) -> None:
    """Persist today's capital snapshot to DB."""
    try:
        db = SessionLocal()
        today = date.today()
        existing = db.query(DailyCapital).filter(DailyCapital.trade_date == today).first()
        if not existing:
            db.add(DailyCapital(
                trade_date=today,
                opening_capital=live_balance,
                closing_capital=live_balance,
                daily_pnl=0.0,
                daily_return_pct=0.0,
                source=broker.lower(),
            ))
        else:
            existing.closing_capital = live_balance
            existing.daily_pnl = live_balance - existing.opening_capital
            if existing.opening_capital > 0:
                existing.daily_return_pct = (existing.daily_pnl / existing.opening_capital) * 100
            existing.updated_at = datetime.now()
        db.commit()
    except Exception as e:
        logger.warning("Could not update daily capital: %s", e)
    finally:
        db.close()


@router.get("/profile")
def get_account_profile():
    """
    Fetch account profile from the currently active broker.
    In PAPER_TRADING / DRY_RUN mode returns ₹2Cr virtual capital regardless of broker.
    """
    broker = get_active_broker()
    mode = get_execution_mode()

    # Paper / dry-run: return virtual ₹2Cr balance, skip broker API call
    if not is_live_mode(mode):
        return {
            "user_id": os.getenv("AUTH_USERNAME", "trader"),
            "email": "",
            "phone": "",
            "broker": broker,
            "execution_mode": mode,
            "capital": PAPER_CAPITAL,
            "live_balance": PAPER_CAPITAL,
            "cash": PAPER_CAPITAL,
            "equity": PAPER_CAPITAL,
            "net_worth": PAPER_CAPITAL,
            "margins_available": PAPER_CAPITAL,
            "collateral": 0.0,
            "note": f"{mode} mode — ₹2 Cr virtual capital",
        }

    try:
        if broker == "INDMONEY":
            data = _get_indmoney_profile()
        else:
            try:
                data = _get_zerodha_profile()
            except RuntimeError as e:
                if "API key or access token missing" in str(e):
                    logger.warning("Zerodha credentials not configured, returning demo profile")
                    return {
                        "user_id": "DEMO_USER",
                        "email": "demo@zerodha.com",
                        "phone": "+91-9876543210",
                        "broker": "ZERODHA",
                        "execution_mode": mode,
                        "capital": 500000.0,
                        "live_balance": 500000.0,
                        "cash": 500000.0,
                        "equity": 500000.0,
                        "net_worth": 500000.0,
                        "margins_available": 500000.0,
                    }
                raise

        data["execution_mode"] = mode
        if data.get("live_balance", 0):
            _snapshot_daily_capital(data["live_balance"], broker)
        return data

    except Exception as e:
        logger.error("Error fetching account profile from %s: %s", broker, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch account profile: {e}")


@router.get("/capital")
def get_available_capital():
    """
    Get available capital.
    PAPER_TRADING / DRY_RUN → ₹2 Cr virtual. LIVE → broker funds.
    """
    broker = get_active_broker()
    mode = get_execution_mode()

    if not is_live_mode(mode):
        return {"capital": PAPER_CAPITAL, "currency": "INR", "source": mode.lower(),
                "note": f"{mode} mode — ₹2 Cr virtual capital"}

    try:
        if broker == "INDMONEY":
            from app.core.broker.indmoney.client import get_indmoney_client
            client = get_indmoney_client()
            try:
                raw = client.get_funds()
                funds = _parse_indmoney_funds(raw)
                balance = funds["live_balance"]
            except Exception as exc:
                logger.warning("INDMoney funds fetch failed in /capital: %s", exc)
                balance = 0.0
            logger.info("💰 Available Capital (INDMoney): ₹%s", balance)
            return {"capital": balance, "currency": "INR", "source": "indmoney",
                    **(({"note": "funds API returned 0 — check INDMONEY_FUNDS_PATH in .env"}) if balance == 0 else {})}

        # Zerodha
        from app.core.broker.zerodha.client import get_kite_client
        try:
            kite = get_kite_client()
            margins = kite.margins()
            equity = margins.get("equity", {})
            available = equity.get("available", {})
            live_balance = available.get("live_balance", 0)
            logger.info("💰 Available Capital (Zerodha): ₹%s", live_balance)
            return {"capital": live_balance, "currency": "INR", "source": "zerodha"}
        except RuntimeError as e:
            if "API key or access token missing" in str(e):
                return {"capital": 100000.0, "currency": "INR", "source": "mock"}
            raise

    except Exception as e:
        logger.error("Error fetching capital from %s: %s", broker, e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch capital: {e}")


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

