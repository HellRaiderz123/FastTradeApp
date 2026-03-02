"""
Trade Cost Calculator API
Calculates brokerage, STT, GST, and other charges for trades.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from app.db.session import SessionLocal
from app.db.models_trade_costs import TradeCost, BrokerageConfig

router = APIRouter(prefix="/trade-costs", tags=["Trade Costs"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TradeInput(BaseModel):
    symbol: str
    trade_type: str  # BUY or SELL
    segment: str  # EQUITY or FNO
    product_type: str  # DELIVERY, INTRADAY, OPTIONS, FUTURES
    quantity: int
    price: float
    intent_id: Optional[str] = None
    order_id: Optional[str] = None


class CostBreakdown(BaseModel):
    brokerage: float
    stt_ctt: float
    exchange_txn_charge: float
    gst: float
    sebi_charges: float
    stamp_duty: float
    total_cost: float
    net_value: float
    trade_value: float


def calculate_trade_costs(trade: TradeInput, config: BrokerageConfig) -> dict:
    """
    Calculate all costs for a trade based on Indian market rules.
    
    References:
    - Zerodha Brokerage Calculator: https://zerodha.com/brokerage-calculator
    - STT/GST: https://zerodha.com/z-connect/queries/stock-and-fo-queries/latest-stt-and-statutory-charges
    """
    trade_value = trade.quantity * trade.price
    
    # 1. Brokerage
    brokerage = 0.0
    if trade.segment == "EQUITY":
        if trade.product_type == "DELIVERY":
            # Zerodha: ₹0 for delivery
            brokerage = max(
                trade_value * (config.equity_delivery_brokerage_pct / 100),
                config.equity_delivery_brokerage_flat
            )
        elif trade.product_type == "INTRADAY":
            # 0.03% or ₹20, whichever is lower
            brokerage = min(
                trade_value * (config.equity_intraday_brokerage_pct / 100),
                config.equity_intraday_brokerage_cap
            )
    elif trade.segment == "FNO":
        # Flat ₹20 per order for F&O
        brokerage = config.fno_brokerage_flat
    
    # 2. STT/CTT (Securities/Commodities Transaction Tax)
    stt = 0.0
    if trade.trade_type == "SELL":  # STT only on sell side (mostly)
        if trade.segment == "EQUITY":
            if trade.product_type == "DELIVERY":
                stt = trade_value * (config.stt_equity_delivery / 100)
            elif trade.product_type == "INTRADAY":
                stt = trade_value * (config.stt_equity_intraday / 100)
        elif trade.segment == "FNO":
            if trade.product_type == "OPTIONS":
                # STT on option premium (sell side only)
                stt = trade_value * (config.stt_fno_options / 100)
            elif trade.product_type == "FUTURES":
                # STT on futures (0.0125% on sell side)
                stt = trade_value * (config.stt_fno_futures / 100)
    
    # 3. Exchange Transaction Charges
    exchange_charge = 0.0
    if trade.segment == "EQUITY":
        exchange_charge = trade_value * (config.nse_equity_charge / 100)
    elif trade.segment == "FNO":
        exchange_charge = trade_value * (config.nse_fno_charge / 100)
    
    # 4. GST (18% on brokerage + exchange charges)
    taxable_value = brokerage + exchange_charge
    gst = taxable_value * (config.gst_pct / 100)
    
    # 5. SEBI Charges (₹10 per crore of turnover)
    sebi_charges = (trade_value / 10000000) * config.sebi_charges_per_crore
    
    # 6. Stamp Duty (on buy side only, 0.003% capped at ₹300)
    stamp_duty = 0.0
    if trade.trade_type == "BUY":
        stamp_duty = min(
            trade_value * (config.stamp_duty_pct / 100),
            config.stamp_duty_cap
        )
    
    # Total costs
    total_cost = brokerage + stt + exchange_charge + gst + sebi_charges + stamp_duty
    
    # Net value (for BUY: value + costs, for SELL: value - costs)
    if trade.trade_type == "BUY":
        net_value = trade_value + total_cost
    else:
        net_value = trade_value - total_cost
    
    return {
        "trade_value": round(trade_value, 2),
        "brokerage": round(brokerage, 2),
        "stt_ctt": round(stt, 2),
        "exchange_txn_charge": round(exchange_charge, 2),
        "gst": round(gst, 2),
        "sebi_charges": round(sebi_charges, 2),
        "stamp_duty": round(stamp_duty, 2),
        "total_cost": round(total_cost, 2),
        "net_value": round(net_value, 2),
        "cost_pct": round((total_cost / trade_value * 100), 4) if trade_value > 0 else 0,
    }


@router.post("/calculate", response_model=CostBreakdown)
def calculate_costs(trade: TradeInput, db: Session = Depends(get_db)):
    """
    Calculate trade costs for a given trade.
    Returns detailed breakdown of all charges.
    """
    # Get active config (or use default Zerodha rates)
    config = db.query(BrokerageConfig).filter(BrokerageConfig.is_active == 1).first()
    
    if not config:
        # Create default Zerodha config
        config = BrokerageConfig(
            broker_name="Zerodha",
            plan_name="Default",
            is_active=1
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    
    # Calculate costs
    costs = calculate_trade_costs(trade, config)
    
    # Save to database
    trade_cost = TradeCost(
        intent_id=trade.intent_id,
        order_id=trade.order_id,
        symbol=trade.symbol,
        trade_type=trade.trade_type,
        segment=trade.segment,
        quantity=trade.quantity,
        price=trade.price,
        trade_value=costs["trade_value"],
        brokerage=costs["brokerage"],
        stt_ctt=costs["stt_ctt"],
        exchange_txn_charge=costs["exchange_txn_charge"],
        gst=costs["gst"],
        sebi_charges=costs["sebi_charges"],
        stamp_duty=costs["stamp_duty"],
        total_cost=costs["total_cost"],
        net_value=costs["net_value"],
        cost_breakdown=costs,
    )
    db.add(trade_cost)
    db.commit()
    
    return costs


@router.get("/history")
def get_cost_history(limit: int = 50, db: Session = Depends(get_db)):
    """Get historical trade costs"""
    costs = db.query(TradeCost)\
        .order_by(TradeCost.created_at.desc())\
        .limit(limit)\
        .all()
    
    return {
        "costs": costs,
        "total_records": db.query(TradeCost).count()
    }


@router.get("/summary")
def get_cost_summary(db: Session = Depends(get_db)):
    """Get aggregate cost summary"""
    from sqlalchemy import func
    
    summary = db.query(
        func.sum(TradeCost.total_cost).label("total_costs"),
        func.sum(TradeCost.brokerage).label("total_brokerage"),
        func.sum(TradeCost.stt_ctt).label("total_stt"),
        func.sum(TradeCost.gst).label("total_gst"),
        func.count(TradeCost.id).label("total_trades")
    ).first()
    
    return {
        "total_costs": round(summary.total_costs or 0, 2),
        "total_brokerage": round(summary.total_brokerage or 0, 2),
        "total_stt": round(summary.total_stt or 0, 2),
        "total_gst": round(summary.total_gst or 0, 2),
        "total_trades": summary.total_trades or 0,
        "avg_cost_per_trade": round((summary.total_costs or 0) / max(summary.total_trades or 1, 1), 2)
    }


@router.get("/config")
def get_brokerage_config(db: Session = Depends(get_db)):
    """Get current brokerage configuration"""
    config = db.query(BrokerageConfig).filter(BrokerageConfig.is_active == 1).first()
    
    if not config:
        return {"error": "No active brokerage config found"}
    
    return config


@router.post("/config")
def update_brokerage_config(config_data: dict, db: Session = Depends(get_db)):
    """Update brokerage configuration"""
    config = db.query(BrokerageConfig).filter(BrokerageConfig.is_active == 1).first()
    
    if not config:
        # Create new config
        config = BrokerageConfig(**config_data)
        db.add(config)
    else:
        # Update existing
        for key, value in config_data.items():
            if hasattr(config, key):
                setattr(config, key, value)
    
    db.commit()
    db.refresh(config)
    
    return config
