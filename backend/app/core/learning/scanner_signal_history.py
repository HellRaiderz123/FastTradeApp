from __future__ import annotations

from datetime import date as dt_date
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.utils.time import now_ist
from app.db.models_scanner_signal import ScannerSignalHistory


def _today_ist() -> dt_date:
    return now_ist().date()


def record_scanner_signal(
    db: Session,
    *,
    strategy_id: Optional[int],
    strategy_name: str,
    symbol: str,
    direction: str,
    timeframe: Optional[str],
    universe: Optional[str],
    signal_payload: Dict[str, Any],
    auto_execute: bool = False,
    execution_mode: Optional[str] = None,
    signal_date: Optional[dt_date] = None,
    commit: bool = True,
) -> Optional[ScannerSignalHistory]:
    """Insert or update the current day's scanner signal snapshot."""
    current_date = signal_date or _today_ist()
    now = now_ist()

    existing = (
        db.query(ScannerSignalHistory)
        .filter(
            ScannerSignalHistory.strategy_id == strategy_id,
            ScannerSignalHistory.symbol == symbol,
            ScannerSignalHistory.direction == direction,
            ScannerSignalHistory.signal_date == current_date,
        )
        .order_by(ScannerSignalHistory.id.desc())
        .first()
    )

    if existing:
        existing.last_seen_at = now
        existing.trigger_count = int(existing.trigger_count or 0) + 1
        existing.strategy_name = strategy_name or existing.strategy_name
        existing.timeframe = timeframe or existing.timeframe
        existing.universe = universe or existing.universe
        existing.auto_execute = bool(existing.auto_execute or auto_execute)
        existing.execution_mode = execution_mode or existing.execution_mode
        existing.ltp = signal_payload.get("ltp")
        existing.change_percent = signal_payload.get("change_percent")
        existing.indicators_json = signal_payload.get("indicators")
        existing.signal_payload = signal_payload
        row = existing
    else:
        row = ScannerSignalHistory(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            symbol=symbol,
            direction=direction,
            timeframe=timeframe,
            universe=universe,
            status="SIGNAL_GENERATED",
            signal_date=current_date,
            first_seen_at=now,
            last_seen_at=now,
            auto_execute=auto_execute,
            execution_mode=execution_mode,
            ltp=signal_payload.get("ltp"),
            change_percent=signal_payload.get("change_percent"),
            indicators_json=signal_payload.get("indicators"),
            signal_payload=signal_payload,
        )
        db.add(row)

    if commit:
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            return None

    return row


def mark_signal_execution(
    db: Session,
    *,
    history_id: Optional[int],
    strategy_id: Optional[int],
    strategy_name: str,
    symbol: str,
    direction: str,
    status: str,
    execution_payload: Dict[str, Any],
    quantity: Optional[int] = None,
    execution_mode: Optional[str] = None,
    order_id: Optional[str] = None,
    commit: bool = True,
) -> Optional[ScannerSignalHistory]:
    """Update an existing signal row with execution status/details."""
    row = None
    if history_id:
        row = db.query(ScannerSignalHistory).filter(ScannerSignalHistory.id == history_id).first()

    if row is None:
        row = (
            db.query(ScannerSignalHistory)
            .filter(
                ScannerSignalHistory.strategy_id == strategy_id,
                ScannerSignalHistory.symbol == symbol,
                ScannerSignalHistory.direction == direction,
                ScannerSignalHistory.signal_date == _today_ist(),
            )
            .order_by(ScannerSignalHistory.id.desc())
            .first()
        )

    if row is None:
        row = record_scanner_signal(
            db,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            symbol=symbol,
            direction=direction,
            timeframe=None,
            universe=None,
            signal_payload={"symbol": symbol},
            auto_execute=False,
            execution_mode=execution_mode,
            commit=False,
        )
        if row is None:
            return None

    now = now_ist()
    row.status = status
    row.executed_at = now if status in {"FILLED_PAPER", "PLACED_LIVE", "EXECUTED", "DRY_RUN"} else row.executed_at
    row.last_seen_at = now
    row.quantity = quantity or row.quantity
    row.execution_mode = execution_mode or row.execution_mode
    row.order_id = order_id or row.order_id
    row.execution_payload = execution_payload

    if commit:
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            return None

    return row