"""Trade suggestions endpoints.

Goal: AlgoRoom-like experience - return ranked strategy tickets with reasons.
This endpoint is intentionally minimal: it reuses the existing option_spread_15m
engine and returns an ordered list of suggestions.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.strategies.option_spread_15m.engine import run_option_spread

router = APIRouter(prefix="/suggestions", tags=["Suggestions"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SuggestionsRequest(BaseModel):
    underlyings: List[str] = Field(default_factory=lambda: ["NIFTY"])
    capital: float = 100000
    lots: int = 1
    risk_mode: str = "Conservative"
    use_ml: bool = False
    min_confidence: float = 75


class SuggestionItem(BaseModel):
    underlying: str
    strategy: str
    approved: bool
    reason: str
    score: float
    spot: Optional[float] = None
    atm: Optional[int] = None
    ticket: Optional[Dict[str, Any]] = None
    risk_metrics: Optional[Dict[str, Any]] = None
    signal: Dict[str, Any]
    context: Dict[str, Any]


def _compute_score(result: Dict[str, Any]) -> float:
    """Higher score = better candidate."""
    import json as _json

    def _ensure_dict(v):
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except Exception:
                return {}
        return v if isinstance(v, dict) else {}

    approved = bool(result.get("approved"))
    if not approved:
        return 0.0

    sig = _ensure_dict(result.get("signal"))
    ctx = _ensure_dict(result.get("context"))
    risk = _ensure_dict(result.get("risk_metrics"))

    confidence = float(sig.get("confidence", 0.0))  # 0-100 in TA engine
    quality_score = float(ctx.get("quality_score", 0.0))  # 0-8
    readiness = float(ctx.get("trade_readiness_score", 0.0))  # 0-100
    risk_pct = float(risk.get("risk_pct_capital", 0.0))

    # weights tuned for simplicity
    score = (confidence * 1.0) + (quality_score * 8.0) + (readiness * 0.25) - (risk_pct * 6.0)
    return round(score, 2)


@router.post("", response_model=Dict[str, Any])
def get_suggestions(request: SuggestionsRequest, db: Session = Depends(get_db)):
    generated_at = datetime.utcnow().isoformat() + "Z"

    suggestions: List[Dict[str, Any]] = []

    for underlying in request.underlyings:
        try:
            payload = {
                "underlying": underlying,
                "interval": "15minute",
                "use_ml": request.use_ml,
                "min_confidence": request.min_confidence,
                "risk_mode": request.risk_mode,
                "lots": request.lots,
                "capital": request.capital,
            }

            result = run_option_spread(db=db, payload=payload)
            score = _compute_score(result)

            suggestions.append(
                {
                    "underlying": underlying,
                    "strategy": result.get("strategy") or "NO_TRADE",
                    "approved": bool(result.get("approved")),
                    "reason": str(result.get("reason") or ""),
                    "score": score,
                    "spot": result.get("spot"),
                    "atm": result.get("atm"),
                    "ticket": result.get("ticket"),
                    "risk_metrics": result.get("risk_metrics"),
                    "signal": result.get("signal") or {},
                    "context": result.get("context") or {},
                }
            )
        except Exception as e:
            # Don't let one underlying failure crash the whole request
            import logging
            logging.getLogger(__name__).warning(f"Suggestion generation failed for {underlying}: {e}")
            suggestions.append(
                {
                    "underlying": underlying,
                    "strategy": "NO_TRADE",
                    "approved": False,
                    "reason": f"Error: {str(e)}",
                    "score": 0.0,
                    "spot": None,
                    "atm": None,
                    "ticket": None,
                    "risk_metrics": None,
                    "signal": {},
                    "context": {},
                }
            )

    # Sort approved first, then by score
    suggestions.sort(key=lambda x: (x.get("approved") is True, float(x.get("score") or 0.0)), reverse=True)

    return {
        "generated_at": generated_at,
        "count": len(suggestions),
        "suggestions": suggestions,
    }
