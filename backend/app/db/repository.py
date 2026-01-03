from sqlalchemy.orm import Session
from app.db.models import StrategyRun


def save_strategy_run(
    db: Session,
    *,
    strategy: str,
    underlying: str,
    approved: bool,
    reason: str,
    risk_metrics: dict | None,
    ticket: dict | None,
    signal: dict,
    context: dict,
):
    run = StrategyRun(
        strategy=strategy,
        underlying=underlying,
        approved=approved,
        reason=reason,
        risk_pct=(risk_metrics or {}).get("risk_pct_capital"),
        max_loss=(risk_metrics or {}).get("max_loss"),
        ticket=ticket,
        signal=signal,
        context=context,
    )

    db.add(run)
    db.commit()
    db.refresh(run)

    return run
