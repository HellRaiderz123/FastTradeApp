"""
Strategy Marketplace — pre-built templates for one-click deploy
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.db.models import StrategyConfig
from app.core.utils.time import now_ist

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


TEMPLATES = [
    {
        "id": "iron_condor_nifty",
        "name": "Iron Condor — NIFTY",
        "category": "Neutral",
        "description": "Sell OTM call spread + OTM put spread. Profits when NIFTY stays range-bound. Best in high IV environments.",
        "underlying": "NIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "Medium",
        "ideal_market": "Sideways / High IV",
        "max_profit": "Net premium received",
        "max_loss": "Spread width − premium",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Conservative",
            "lots": 1,
            "capital": 100000,
            "min_confidence": 70,
            "preferred_strategy": "IRON_CONDOR",
            "use_ml": False,
        },
        "tags": ["neutral", "premium-selling", "high-iv"],
    },
    {
        "id": "bull_put_banknifty",
        "name": "Bull Put Spread — BANKNIFTY",
        "category": "Bullish",
        "description": "Sell ATM put, buy lower-strike put. Profits when BANKNIFTY stays above short strike. Limited risk.",
        "underlying": "BANKNIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "Low",
        "ideal_market": "Mildly Bullish",
        "max_profit": "Net premium received",
        "max_loss": "Spread width − premium",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Conservative",
            "lots": 1,
            "capital": 100000,
            "min_confidence": 72,
            "preferred_strategy": "BULL_PUT",
            "use_ml": False,
        },
        "tags": ["bullish", "premium-selling", "defined-risk"],
    },
    {
        "id": "bear_call_nifty",
        "name": "Bear Call Spread — NIFTY",
        "category": "Bearish",
        "description": "Sell ATM call, buy higher-strike call. Profits when NIFTY stays below short strike.",
        "underlying": "NIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "Low",
        "ideal_market": "Mildly Bearish",
        "max_profit": "Net premium received",
        "max_loss": "Spread width − premium",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Conservative",
            "lots": 1,
            "capital": 100000,
            "min_confidence": 72,
            "preferred_strategy": "BEAR_CALL",
            "use_ml": False,
        },
        "tags": ["bearish", "premium-selling", "defined-risk"],
    },
    {
        "id": "short_straddle_nifty",
        "name": "Short Straddle — NIFTY",
        "category": "Neutral",
        "description": "Sell ATM call + ATM put. Maximum premium collection. High risk — requires active management.",
        "underlying": "NIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "High",
        "ideal_market": "Very Low Volatility Expected",
        "max_profit": "Total premium received",
        "max_loss": "Unlimited (both sides)",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Aggressive",
            "lots": 1,
            "capital": 150000,
            "min_confidence": 80,
            "preferred_strategy": "SHORT_STRADDLE",
            "use_ml": True,
        },
        "tags": ["neutral", "high-premium", "high-risk"],
    },
    {
        "id": "butterfly_spread_nifty",
        "name": "Butterfly Spread — NIFTY",
        "category": "Neutral",
        "description": "Buy 1 ITM call, sell 2 ATM calls, buy 1 OTM call. Low cost, profits at ATM at expiry.",
        "underlying": "NIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "Low",
        "ideal_market": "Pinning at ATM",
        "max_profit": "Strike width − net debit",
        "max_loss": "Net debit paid",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Conservative",
            "lots": 1,
            "capital": 80000,
            "min_confidence": 75,
            "preferred_strategy": "BUTTERFLY_SPREAD",
            "use_ml": False,
        },
        "tags": ["neutral", "low-cost", "expiry-play"],
    },
    {
        "id": "bull_call_finnifty",
        "name": "Bull Call Spread — FINNIFTY",
        "category": "Bullish",
        "description": "Buy ATM call, sell OTM call. Defined risk bullish play on FINNIFTY.",
        "underlying": "FINNIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "Low",
        "ideal_market": "Bullish Trend",
        "max_profit": "Spread width − net debit",
        "max_loss": "Net debit paid",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Moderate",
            "lots": 1,
            "capital": 80000,
            "min_confidence": 70,
            "preferred_strategy": "BULL_CALL",
            "use_ml": False,
        },
        "tags": ["bullish", "debit-spread", "defined-risk"],
    },
    {
        "id": "short_strangle_banknifty",
        "name": "Short Strangle — BANKNIFTY",
        "category": "Neutral",
        "description": "Sell OTM call + OTM put. Wider breakevens than straddle, lower premium but more room.",
        "underlying": "BANKNIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "High",
        "ideal_market": "Range-bound with moderate IV",
        "max_profit": "Total premium received",
        "max_loss": "Unlimited (both sides)",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Moderate",
            "lots": 1,
            "capital": 150000,
            "min_confidence": 75,
            "preferred_strategy": "SHORT_STRANGLE",
            "use_ml": False,
        },
        "tags": ["neutral", "premium-selling", "high-risk"],
    },
    {
        "id": "ml_adaptive_nifty",
        "name": "ML Adaptive — NIFTY",
        "category": "Adaptive",
        "description": "Uses ML model to pick the best strategy (Bull Put / Bear Call / Iron Condor) based on current market regime.",
        "underlying": "NIFTY",
        "strategy_type": "option_spread_15m",
        "risk_level": "Medium",
        "ideal_market": "Any — ML decides",
        "max_profit": "Varies by selected strategy",
        "max_loss": "Varies by selected strategy",
        "parameters": {
            "interval": "15minute",
            "risk_mode": "Conservative",
            "lots": 1,
            "capital": 100000,
            "min_confidence": 78,
            "use_ml": True,
        },
        "tags": ["adaptive", "ml-powered", "auto-select"],
    },
]


@router.get("/templates")
def list_templates(category: Optional[str] = None, risk_level: Optional[str] = None):
    """List all strategy templates with optional filters"""
    templates = TEMPLATES
    if category:
        templates = [t for t in templates if t["category"].lower() == category.lower()]
    if risk_level:
        templates = [t for t in templates if t["risk_level"].lower() == risk_level.lower()]
    return {"templates": templates, "count": len(templates)}


class DeployRequest(BaseModel):
    template_id: str
    name: Optional[str] = None
    lots: Optional[int] = None
    capital: Optional[float] = None


@router.post("/deploy")
def deploy_template(request: DeployRequest, db: Session = Depends(get_db)):
    """Deploy a template as a new StrategyConfig (disabled by default)"""
    template = next((t for t in TEMPLATES if t["id"] == request.template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    params = {**template["parameters"]}
    if request.lots is not None:
        params["lots"] = request.lots
    if request.capital is not None:
        params["capital"] = request.capital

    name = request.name or f"{template['name']} {now_ist().strftime('%Y%m%d_%H%M%S')}"

    # Ensure unique name
    counter = 1
    base_name = name
    while db.query(StrategyConfig).filter(StrategyConfig.name == name).first():
        name = f"{base_name} ({counter})"
        counter += 1

    config = StrategyConfig(
        name=name,
        description=template["description"],
        strategy_type=template["strategy_type"],
        underlying=template["underlying"],
        parameters=params,
        enabled=False,
        created_by="marketplace",
    )
    db.add(config)
    db.commit()
    db.refresh(config)

    return {
        "message": f"Strategy '{name}' created from template. Enable it from the Strategies page.",
        "strategy_id": config.id,
        "name": config.name,
    }
