from sqlalchemy.orm import Session
from app.db.models import StrategyRun
from app.db.models_signal_outcome import SignalOutcome


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
    record_diagnostics: bool = True,
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

    # Record signal diagnostics for this strategy run (approved or rejected)
    if record_diagnostics:
        _record_strategy_run_diagnostics(
            db,
            run=run,
            signal=signal,
            context=context,
        )

    return run


def _record_strategy_run_diagnostics(
    db: Session,
    *,
    run: StrategyRun,
    signal: dict,
    context: dict,
) -> None:
    """
    Record signal diagnostics for a strategy run.
    Captures signal quality at decision time, even if trade is rejected.
    """
    try:
        import json as _json

        # Guard: JSON columns may come back as strings from DB (migration artifact)
        def _ensure_dict(v):
            if isinstance(v, str):
                try:
                    return _json.loads(v)
                except Exception:
                    return {}
            return v if isinstance(v, dict) else {}

        sig = _ensure_dict(signal)
        ctx = _ensure_dict(context)

        outcome = SignalOutcome(
            intent_id=f"strategy_run_{run.id}",
            run_id=run.id or 0,
            underlying=run.underlying or "UNKNOWN",
            strategy=run.strategy or "UNKNOWN",
            signal_strength=str(sig.get("signal") or sig.get("recommendation") or "UNKNOWN"),
            signal_bias=str(sig.get("bias") or "UNKNOWN"),
            confidence=float(sig.get("confidence") or 0),
            market_mode=str(ctx.get("market_mode") or "UNKNOWN"),
            iv_regime=str(ctx.get("iv_regime") or "UNKNOWN"),
            # Entry doesn't have exit info yet
            entry_time=run.created_at,
            exit_time=None,
            exit_reason=None,
            pnl=None,
        )

        # Check if outcome already exists
        existing = (
            db.query(SignalOutcome)
            .filter(SignalOutcome.intent_id == outcome.intent_id)
            .first()
        )
        if not existing:
            db.add(outcome)
            db.commit()
    except Exception as e:
        # Log but don't fail the entire operation
        import logging
        logger = logging.getLogger(__name__)
        logger.exception(f"Failed to record signal diagnostics for run {run.id}: {e}")
