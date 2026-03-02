"""
Models for tracking trade costs and charges.
Includes brokerage, STT, exchange charges, GST, etc.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from app.db.session import Base
from app.core.utils.time import now_ist


class TradeCost(Base):
    """Store detailed cost breakdown for each trade"""
    __tablename__ = "trade_costs"

    id = Column(Integer, primary_key=True)
    
    # Reference to execution intent or order
    intent_id = Column(String, index=True, nullable=True)
    order_id = Column(String, index=True, nullable=True)
    
    # Trade details
    symbol = Column(String, index=True)
    trade_type = Column(String)  # BUY, SELL
    segment = Column(String)  # EQUITY, FNO (Futures & Options)
    quantity = Column(Integer)
    price = Column(Float)
    trade_value = Column(Float)  # quantity * price
    
    # Cost components (all in INR)
    brokerage = Column(Float, default=0.0)
    stt_ctt = Column(Float, default=0.0)  # Securities Transaction Tax / Commodities Transaction Tax
    exchange_txn_charge = Column(Float, default=0.0)
    gst = Column(Float, default=0.0)  # 18% on (brokerage + exchange charges)
    sebi_charges = Column(Float, default=0.0)
    stamp_duty = Column(Float, default=0.0)
    
    # Total costs
    total_cost = Column(Float, default=0.0)
    net_value = Column(Float, default=0.0)  # trade_value ± total_cost
    
    # Breakdown for UI display
    cost_breakdown = Column(JSON, nullable=True)  # Detailed breakdown
    
    # Metadata
    trade_date = Column(DateTime(timezone=True), default=now_ist)
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)


class BrokerageConfig(Base):
    """Store brokerage configuration and rates"""
    __tablename__ = "brokerage_config"

    id = Column(Integer, primary_key=True)
    
    # Broker details
    broker_name = Column(String, default="Zerodha")
    plan_name = Column(String, default="Default")  # e.g., "Zerodha Free Plan", "Pro Plan"
    
    # Brokerage rates
    # Equity Delivery
    equity_delivery_brokerage_pct = Column(Float, default=0.0)  # 0% for Zerodha
    equity_delivery_brokerage_flat = Column(Float, default=0.0)
    
    # Equity Intraday
    equity_intraday_brokerage_pct = Column(Float, default=0.03)  # 0.03% or ₹20 per trade
    equity_intraday_brokerage_cap = Column(Float, default=20.0)
    
    # F&O (Futures & Options)
    fno_brokerage_flat = Column(Float, default=20.0)  # ₹20 per order
    
    # Statutory charges (%)
    stt_equity_delivery = Column(Float, default=0.1)  # 0.1% on sell side
    stt_equity_intraday = Column(Float, default=0.025)  # 0.025% on sell side
    stt_fno_options = Column(Float, default=0.0625)  # 0.0625% on sell side (premium)
    stt_fno_futures = Column(Float, default=0.0125)  # 0.0125% on sell side
    
    # Exchange transaction charges (%)
    nse_equity_charge = Column(Float, default=0.00297)  # NSE: 0.00297%
    nse_fno_charge = Column(Float, default=0.00173)  # NSE F&O: 0.00173%
    
    # Other charges
    gst_pct = Column(Float, default=18.0)  # 18% GST on brokerage + exchange charges
    sebi_charges_per_crore = Column(Float, default=10.0)  # ₹10 per crore
    stamp_duty_pct = Column(Float, default=0.003)  # 0.003% on buy side (max ₹300 per trade)
    stamp_duty_cap = Column(Float, default=300.0)
    
    # Metadata
    is_active = Column(Integer, default=1)  # 1 = active, 0 = inactive
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
