"""
AI Analysis API Routes
Multi-agent LLM analysis pipeline for Indian equity symbols (NSE/BSE).

Inspired by TradingAgents (github.com/TauricResearch/TradingAgents),
adapted to use FastTradeApp's own data sources and LLM infrastructure.

Endpoints:
  POST /ai-analysis/analyze          — start an analysis job
  GET  /ai-analysis/status/{job_id}  — poll job progress / result
  GET  /ai-analysis/health           — check LLM availability
  GET  /ai-analysis/jobs             — list recent jobs (for debugging)
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services.trading_agents import (
    cleanup_expired_jobs,
    evaluate_pending_outcomes,
    get_job,
    start_analysis,
)
from app.services.llm_service import LLM_MODEL, LLM_PROVIDER, is_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-analysis", tags=["AI Analysis"])

# Allowed exchange values
_ALLOWED_EXCHANGES = {"NSE", "BSE", "NFO", "MCX"}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    symbol: str = Field(
        min_length=1,
        max_length=30,
        examples=["RELIANCE", "NIFTY", "SBIN"],
        description="NSE/BSE symbol (e.g. RELIANCE, NIFTY, BANKNIFTY)",
    )
    exchange: str = Field(
        default="NSE",
        examples=["NSE", "BSE"],
        description="Exchange: NSE or BSE",
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        clean = v.strip().upper()
        if not re.match(r"^[A-Z0-9&\-\.]{1,30}$", clean):
            raise ValueError(
                "Symbol must be 1-30 uppercase alphanumeric characters "
                "(hyphens, dots, & allowed)."
            )
        return clean

    @field_validator("exchange")
    @classmethod
    def validate_exchange(cls, v: str) -> str:
        clean = v.strip().upper()
        if clean not in _ALLOWED_EXCHANGES:
            raise ValueError(f"Exchange must be one of: {', '.join(sorted(_ALLOWED_EXCHANGES))}")
        return clean


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
def ai_analysis_health() -> dict:
    """Check whether the AI analysis service is ready."""
    return {
        "ok": is_available(),
        "provider": LLM_PROVIDER,
        "model": LLM_MODEL,
        "message": (
            "AI analysis service is ready."
            if is_available()
            else "LLM_API_KEY is not configured — analysis will fail."
        ),
        "agents": [
            "TechnicalAnalyst",
            "NewsAnalyst",
            "SentimentAnalyst",
            "BullResearcher",
            "BearResearcher",
            "FundamentalsAnalyst",
            "TraderDecision",
        ],
        "pipeline_steps": 8,
        "estimated_duration_sec": "90-180",
    }


@router.post("/analyze", status_code=202)
def start_ai_analysis(req: AnalyzeRequest) -> dict:
    """
    Start a multi-agent analysis pipeline for a given symbol.

    The pipeline runs asynchronously (background thread).
    Returns a job_id — poll /ai-analysis/status/{job_id} for results.

    **Typical duration:** 90-180 seconds (7 sequential LLM calls).
    """
    if not is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "LLM service is not configured. "
                "Set LLM_API_KEY (or GROQ_API_KEY / OPENAI_API_KEY) in your .env file."
            ),
        )

    try:
        job_id = start_analysis(symbol=req.symbol, exchange=req.exchange)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "ok": True,
        "job_id": job_id,
        "symbol": req.symbol,
        "exchange": req.exchange,
        "status": "QUEUED",
        "message": "Analysis started. Poll /ai-analysis/status/{job_id} for progress.",
        "poll_url": f"/ai-analysis/status/{job_id}",
    }


@router.get("/status/{job_id}")
def get_analysis_status(job_id: str) -> dict:
    """
    Get the current status and (when complete) full result for a job.

    Status values:
      - QUEUED     — waiting to start
      - RUNNING    — pipeline is executing; `step` shows current agent
      - COMPLETED  — full result available in `result`
      - FAILED     — pipeline error; see `error` field
    """
    # Basic UUID format check to avoid log pollution
    if not re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        job_id,
        re.IGNORECASE,
    ):
        raise HTTPException(status_code=400, detail="Invalid job_id format.")

    job = get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found. It may have expired (jobs are kept for 60 minutes).",
        )

    # Build a clean response — omit None fields for clarity
    response: dict = {
        "job_id": job["job_id"],
        "symbol": job["symbol"],
        "exchange": job["exchange"],
        "status": job["status"],
        "steps_done": job["steps_done"],
        "created_at": job["created_at"],
    }
    if job.get("step"):
        response["current_step"] = job["step"]
    if job.get("completed_at"):
        response["completed_at"] = job["completed_at"]
    if job.get("error"):
        response["error"] = job["error"]
    if job.get("result"):
        response["result"] = job["result"]

    return response


@router.delete("/jobs/cleanup")
def purge_expired_jobs() -> dict:
    """
    Remove completed/failed jobs older than 60 minutes from memory.
    Safe to call at any time; intended for ops/admin use.
    """
    removed = cleanup_expired_jobs()
    return {"ok": True, "jobs_removed": removed}


@router.get("/history/{symbol}")
def get_symbol_history(
    symbol: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """
    Return the last N persisted AI decisions for a symbol.
    Includes outcome evaluation results when available.
    """
    import re
    if not re.match(r"^[A-Z0-9&\-\.]{1,30}$", symbol.strip().upper()):
        raise HTTPException(status_code=400, detail="Invalid symbol.")

    try:
        from app.db.session import SessionLocal
        from app.db.models_ai_decisions import AIDecision
        from sqlalchemy import desc

        db = SessionLocal()
        try:
            rows = (
                db.query(AIDecision)
                .filter(AIDecision.symbol == symbol.upper())
                .order_by(desc(AIDecision.analysed_at))
                .limit(limit)
                .all()
            )
            decisions = [
                {
                    "id": r.id,
                    "job_id": r.job_id,
                    "symbol": r.symbol,
                    "exchange": r.exchange,
                    "action": r.action,
                    "confidence": r.confidence,
                    "conviction": r.conviction,
                    "time_horizon": r.time_horizon,
                    "risk_level": r.risk_level,
                    "rationale": r.rationale,
                    "suggested_stop_loss_pct": r.suggested_stop_loss_pct,
                    "suggested_target_pct": r.suggested_target_pct,
                    "price_at_decision": r.price_at_decision,
                    "outcome_evaluated_at": r.outcome_evaluated_at.isoformat() if r.outcome_evaluated_at else None,
                    "price_at_evaluation": r.price_at_evaluation,
                    "actual_return_pct": r.actual_return_pct,
                    "outcome_correct": r.outcome_correct,
                    "reflection": r.reflection,
                    "analysed_at": r.analysed_at.isoformat() if r.analysed_at else None,
                }
                for r in rows
            ]
        finally:
            db.close()

        evaluated = [d for d in decisions if d["outcome_correct"] is not None]
        accuracy = (
            round(sum(d["outcome_correct"] for d in evaluated) / len(evaluated) * 100, 1)
            if evaluated else None
        )

        return {
            "symbol": symbol.upper(),
            "total": len(decisions),
            "accuracy_pct": accuracy,
            "decisions": decisions,
        }
    except Exception as e:
        logger.error("ai_analysis history error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to fetch decision history.")


@router.post("/evaluate-outcomes")
def trigger_outcome_evaluation(
    evaluation_days: int = Query(default=3, ge=1, le=30),
) -> dict:
    """
    Manually trigger outcome evaluation for past BUY/SELL decisions
    that are older than `evaluation_days` days and not yet evaluated.
    """
    updated = evaluate_pending_outcomes(evaluation_days=evaluation_days)
    return {"ok": True, "decisions_evaluated": updated}
