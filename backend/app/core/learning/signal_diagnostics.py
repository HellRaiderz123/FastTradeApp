from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.models_signal_outcome import SignalOutcome


def _safe_str(value: Any, default: str = "UNKNOWN") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def record_entry_snapshot(
    db: Session,
    *,
    intent,
    engine_result: Dict[str, Any],
    commit: bool = True,
) -> Optional[SignalOutcome]:
    """Persist a signal snapshot for a newly executed intent."""
    if intent is None or not getattr(intent, "intent_id", None):
        return None

    existing = (
        db.query(SignalOutcome)
        .filter(SignalOutcome.intent_id == intent.intent_id)
        .first()
    )
    if existing:
        return existing

    sig = engine_result.get("signal") or {}
    ctx = engine_result.get("context") or {}

    outcome = SignalOutcome(
        intent_id=intent.intent_id,
        run_id=intent.run_id or 0,
        underlying=_safe_str(intent.underlying),
        strategy=_safe_str(intent.strategy),
        signal_strength=_safe_str(sig.get("signal") or sig.get("recommendation")),
        signal_bias=_safe_str(sig.get("bias")),
        confidence=float(sig.get("confidence") or 0),
        market_mode=_safe_str(ctx.get("market_mode")),
        iv_regime=_safe_str(ctx.get("iv_regime")),
        entry_credit=float(intent.entry_credit or 0) if intent.entry_credit is not None else None,
        entry_time=intent.created_at or now_ist(),
        signal_json=sig,
        context_json=ctx,
    )

    db.add(outcome)
    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            return None

    return outcome


def record_exit_outcome(
    db: Session,
    *,
    intent,
    commit: bool = True,
) -> Optional[SignalOutcome]:
    """Update an existing signal snapshot with final PnL/outcome."""
    if intent is None or not getattr(intent, "intent_id", None):
        return None

    outcome = (
        db.query(SignalOutcome)
        .filter(SignalOutcome.intent_id == intent.intent_id)
        .first()
    )
    if not outcome:
        return None

    pnl = float(intent.pnl or 0)
    entry_credit = float(outcome.entry_credit or intent.entry_credit or 0)
    pnl_pct = (pnl / entry_credit) * 100 if entry_credit else None

    if pnl > 0:
        outcome_label = "WIN"
    elif pnl < 0:
        outcome_label = "LOSS"
    else:
        outcome_label = "BREAKEVEN"

    outcome.exit_time = intent.closed_at or now_ist()
    outcome.pnl = pnl
    outcome.pnl_pct = pnl_pct
    outcome.exit_reason = _safe_str(getattr(intent, "exit_reason", None))
    outcome.outcome = outcome_label
    outcome.updated_at = now_ist()

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            return None

    return outcome


def _aggregate_rows(rows: Iterable[SignalOutcome]) -> Dict[str, Any]:
    total = 0
    win = 0
    loss = 0
    breakeven = 0
    gross_profit = 0.0
    gross_loss = 0.0
    pnl_sum = 0.0

    for row in rows:
        if row.pnl is None:
            continue
        total += 1
        pnl = float(row.pnl or 0)
        pnl_sum += pnl
        if pnl > 0:
            win += 1
            gross_profit += pnl
        elif pnl < 0:
            loss += 1
            gross_loss += abs(pnl)
        else:
            breakeven += 1

    win_rate = (win / total) * 100 if total else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss else None
    avg_pnl = (pnl_sum / total) if total else 0.0

    return {
        "trades": total,
        "wins": win,
        "losses": loss,
        "breakeven": breakeven,
        "win_rate_pct": round(win_rate, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor is not None else None,
        "avg_pnl": round(avg_pnl, 2),
        "net_pnl": round(pnl_sum, 2),
    }


def _group_by(rows: List[SignalOutcome], key_fn: Callable[[SignalOutcome], Tuple[str, ...]]) -> Dict[str, Any]:
    grouped: Dict[str, List[SignalOutcome]] = {}
    for row in rows:
        key_parts = key_fn(row)
        key = "|".join([_safe_str(p) for p in key_parts])
        grouped.setdefault(key, []).append(row)

    return {key: _aggregate_rows(items) for key, items in grouped.items()}


def compute_signal_diagnostics(
    db: Session,
    *,
    limit: int = 200,
    lookback_days: Optional[int] = 30,
    underlying: Optional[str] = None,
    strategy: Optional[str] = None,
) -> Dict[str, Any]:
    """Return rule-based diagnostics for recent closed trades."""
    query = db.query(SignalOutcome).filter(SignalOutcome.exit_time.isnot(None))

    # Safely convert to string if needed (handles FastAPI Query objects)
    if underlying:
        underlying_str = str(underlying).upper() if underlying else None
        if underlying_str:
            query = query.filter(SignalOutcome.underlying == underlying_str)
    if strategy:
        strategy_str = str(strategy).upper() if strategy else None
        if strategy_str:
            query = query.filter(SignalOutcome.strategy == strategy_str)
    if lookback_days:
        cutoff = now_ist() - timedelta(days=lookback_days)
        query = query.filter(SignalOutcome.exit_time >= cutoff)

    rows = (
        query.order_by(SignalOutcome.exit_time.desc())
        .limit(min(limit, 1000))
        .all()
    )

    summary = _aggregate_rows(rows)

    by_signal_bias = _group_by(rows, lambda r: (r.signal_bias or "UNKNOWN",))
    by_strategy = _group_by(rows, lambda r: (r.strategy or "UNKNOWN",))
    by_bias_strategy = _group_by(rows, lambda r: (r.signal_bias or "UNKNOWN", r.strategy or "UNKNOWN"))
    by_market_mode = _group_by(rows, lambda r: (r.market_mode or "UNKNOWN",))
    by_iv_regime = _group_by(rows, lambda r: (r.iv_regime or "UNKNOWN",))

    return {
        "summary": summary,
        "by_signal_bias": by_signal_bias,
        "by_strategy": by_strategy,
        "by_bias_strategy": by_bias_strategy,
        "by_market_mode": by_market_mode,
        "by_iv_regime": by_iv_regime,
        "count": len(rows),
        "lookback_days": lookback_days,
        "limit": limit,
    }
