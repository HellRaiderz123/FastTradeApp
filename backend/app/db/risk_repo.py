from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models_risk import RiskLimitConfig, default_iv_limits


def get_or_create_risk_limits(db: Session) -> RiskLimitConfig:
    """Fetch the singleton risk limits row, creating it with defaults if missing."""
    record = db.query(RiskLimitConfig).first()

    if record is None:
        record = RiskLimitConfig(
            max_portfolio_loss_pct=3.0,
            max_trades_per_day=3,
            iv_regime_limits=default_iv_limits(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    # Ensure iv_regime_limits is always a dict (guard against string from migration)
    if isinstance(record.iv_regime_limits, str):
        import json
        try:
            record.iv_regime_limits = json.loads(record.iv_regime_limits)
            flag_modified(record, "iv_regime_limits")
            db.commit()
        except Exception:
            record.iv_regime_limits = default_iv_limits()
    if not record.iv_regime_limits:
        record.iv_regime_limits = default_iv_limits()
        db.commit()
        db.refresh(record)

    return record


def update_risk_limits(
    db: Session,
    *,
    max_portfolio_loss_pct: float,
    max_trades_per_day: int,
    iv_regime_limits: dict | None = None,
) -> RiskLimitConfig:
    """Persist updated risk limits and return the saved record."""
    record = get_or_create_risk_limits(db)

    record.max_portfolio_loss_pct = max_portfolio_loss_pct
    record.max_trades_per_day = max_trades_per_day
    record.iv_regime_limits = iv_regime_limits or default_iv_limits()

    # Flag the JSON column as modified so SQLAlchemy knows to persist changes
    flag_modified(record, "iv_regime_limits")

    db.add(record)
    db.commit()
    db.refresh(record)
    return record
