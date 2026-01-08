from sqlalchemy import Column, Integer, Float, JSON, DateTime

from app.db.session import Base
from app.core.utils.time import now_ist


def default_iv_limits() -> dict:
    """Default IV-regime limits used when no overrides are stored."""
    return {
        "LOW": {
            "min_atm_dist_pct": 0.5,
            "max_risk_pct_capital": 4.0,
        },
        "NORMAL": {
            "min_atm_dist_pct": 0.6,
            "max_risk_pct_capital": 2.0,
        },
        "HIGH": {
            "min_atm_dist_pct": 0.8,
            "max_risk_pct_capital": 5.0,
        },
    }


class RiskLimitConfig(Base):
    __tablename__ = "risk_limits"

    id = Column(Integer, primary_key=True, index=True)
    max_portfolio_loss_pct = Column(Float, default=3.0)
    max_trades_per_day = Column(Integer, default=3)
    iv_regime_limits = Column(JSON, default=default_iv_limits)
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
