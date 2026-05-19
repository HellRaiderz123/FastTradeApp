from datetime import datetime, timezone
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.market.scheduler import scheduler as market_scheduler
from app.db.session import SessionLocal
from app.db.system_control_repo import get_or_create_system_control

router = APIRouter(prefix="/system", tags=["System Control"])

_scheduler_runs_lock = threading.Lock()
_scheduler_runs: dict[str, dict[str, Any]] = {}

_JOB_LABELS = {
    "candle_15m_job": "15m Candle Update",
    "daily_vix_job": "Daily VIX Update",
    "vix_initial_run": "Initial VIX Backfill",
    "daily_candles_job": "Daily Candle Update",
    "daily_candles_initial_run": "Initial Daily Candle Backfill",
    "auto_exit_job": "Auto Exit Monitor",
    "ml_training_job": "ML Training",
    "candle_5m_job": "5m Candle Update",
    "candle_1h_job": "1h Candle Update",
    "candle_5m_initial_run": "Initial 5m Candle Backfill",
    "candle_1h_initial_run": "Initial 1h Candle Backfill",
    "expiry_exit_job": "Expiry Exit Monitor",
    "twitter_sentiment_job": "Twitter Sentiment Update",
    "strategy_decay_job": "Strategy Decay Check",
    "strategy_discovery_job": "Strategy Discovery",
    "neon_sync_job": "Neon Delta Sync",
    "zerodha_auto_login_job": "Zerodha Auto Login",
    "watchlist_ai_analysis_job": "Watchlist AI Analysis",
    "nifty100_reconciliation_job": "Nifty100 Reconciliation",
    "holdings_reconciliation_job": "Holdings Reconciliation",
    "ai_outcome_evaluator": "AI Outcome Evaluation",
    "auto_trader_job": "Auto Trader Scan",
    "condition_scanner_job": "Condition Scanner",
}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return str(value)


def _safe_result(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def _trigger_summary(trigger: Any) -> str:
    text = str(trigger or "")
    return " ".join(text.split())


def _job_category(job_id: str) -> str:
    if any(token in job_id for token in ("ai", "reconciliation", "sentiment", "ml")):
        return "Intelligence"
    if any(token in job_id for token in ("candle", "vix", "expiry", "auto_exit")):
        return "Market Data"
    if any(token in job_id for token in ("strategy", "scanner", "auto_trader")):
        return "Trading"
    if any(token in job_id for token in ("sync", "login")):
        return "Operations"
    return "System"


def _manual_run_allowed(job_id: str) -> bool:
    return not job_id.endswith("_initial_run")


def _serialize_job(job: Any) -> dict[str, Any]:
    manual_state = _scheduler_runs.get(job.id, {})
    return {
        "id": job.id,
        "label": _JOB_LABELS.get(job.id, job.name or job.id.replace("_", " ").title()),
        "name": job.name,
        "category": _job_category(job.id),
        "trigger": _trigger_summary(job.trigger),
        "next_run_time": _iso(job.next_run_time),
        "pending": bool(getattr(job, "pending", False)),
        "max_instances": getattr(job, "max_instances", None),
        "coalesce": getattr(job, "coalesce", None),
        "manual_run_allowed": _manual_run_allowed(job.id),
        "manual_run": {
            "status": manual_state.get("status", "idle"),
            "started_at": manual_state.get("started_at"),
            "finished_at": manual_state.get("finished_at"),
            "last_error": manual_state.get("last_error"),
            "last_result": manual_state.get("last_result"),
        },
    }


def _run_job_now(job_id: str) -> None:
    job = market_scheduler.get_job(job_id)
    if not job:
        with _scheduler_runs_lock:
            _scheduler_runs[job_id] = {
                "status": "failed",
                "started_at": _iso(datetime.now(timezone.utc)),
                "finished_at": _iso(datetime.now(timezone.utc)),
                "last_error": "Job no longer exists in scheduler",
                "last_result": None,
            }
        return

    started_at = _iso(datetime.now(timezone.utc))
    with _scheduler_runs_lock:
        _scheduler_runs[job_id] = {
            "status": "running",
            "started_at": started_at,
            "finished_at": None,
            "last_error": None,
            "last_result": None,
        }

    try:
        result = job.func(*(job.args or ()), **(job.kwargs or {}))
        with _scheduler_runs_lock:
            _scheduler_runs[job_id] = {
                "status": "completed",
                "started_at": started_at,
                "finished_at": _iso(datetime.now(timezone.utc)),
                "last_error": None,
                "last_result": _safe_result(result),
            }
    except Exception as exc:
        with _scheduler_runs_lock:
            _scheduler_runs[job_id] = {
                "status": "failed",
                "started_at": started_at,
                "finished_at": _iso(datetime.now(timezone.utc)),
                "last_error": str(exc),
                "last_result": None,
            }


def _sorted_scheduler_jobs() -> list[dict[str, Any]]:
    jobs = [_serialize_job(job) for job in market_scheduler.get_jobs()]
    return sorted(
        jobs,
        key=lambda item: (
            item.get("next_run_time") is None,
            item.get("next_run_time") or "",
            item.get("label") or item.get("id") or "",
        ),
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/enable")
def enable_trading(db: Session = Depends(get_db)):
    sc = get_or_create_system_control(db)
    sc.trading_enabled = True
    db.commit()

    return {"trading_enabled": True}

@router.post("/disable")
def disable_trading(db: Session = Depends(get_db)):
    sc = get_or_create_system_control(db)
    sc.trading_enabled = False
    db.commit()

    return {"trading_enabled": False}

@router.get("/status")
def system_status(db: Session = Depends(get_db)):
    sc = get_or_create_system_control(db)
    return {
        "trading_enabled": sc.trading_enabled
    }


@router.get("/scheduler/jobs")
def list_scheduler_jobs() -> dict[str, Any]:
    return {
        "scheduler_running": market_scheduler.running,
        "timezone": str(getattr(market_scheduler, "timezone", "Asia/Kolkata")),
        "job_count": len(market_scheduler.get_jobs()),
        "jobs": _sorted_scheduler_jobs(),
    }


@router.post("/scheduler/jobs/{job_id}/run-now")
def run_scheduler_job_now(job_id: str) -> dict[str, Any]:
    job = market_scheduler.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Scheduler job '{job_id}' not found")
    if not _manual_run_allowed(job_id):
        raise HTTPException(status_code=400, detail="This startup-only job cannot be triggered manually")

    with _scheduler_runs_lock:
        current = _scheduler_runs.get(job_id, {})
        if current.get("status") == "running":
            raise HTTPException(status_code=409, detail="Job is already running manually")

    thread = threading.Thread(target=_run_job_now, args=(job_id,), daemon=True)
    thread.start()

    return {
        "ok": True,
        "job_id": job_id,
        "status": "queued",
        "message": f"Manual execution queued for {job_id}",
    }
