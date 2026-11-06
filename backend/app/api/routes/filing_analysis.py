"""
NSE Filing PDF Analysis API
GET /nse/filing-analysis          — paginated history (all or filtered)
GET /nse/filing-analysis/stats    — sentiment breakdown, top tags
GET /nse/filing-analysis/{id}     — single filing detail with full PDF text
POST /nse/filing-analysis/rerun/{id} — re-analyse a specific filing
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nse/filing-analysis", tags=["filing_analysis"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _row_to_dict(row) -> dict:
    return {
        "id": row.id,
        "symbol": row.symbol,
        "company": row.company,
        "headline": row.headline,
        "category": row.category,
        "impact": row.impact,
        "pdf_url": row.pdf_url,
        "published_at": row.published_at,
        "pdf_extracted": row.pdf_extracted,
        "sentiment": row.sentiment,
        "sentiment_score": row.sentiment_score,
        "summary": row.summary,
        "key_numbers": json.loads(row.key_numbers or "{}"),
        "signal_tags": [t for t in (row.signal_tags or "").split(",") if t],
        "passed_filter": row.passed_filter,
        "avg_volume": row.avg_volume,
        "filter_reason": row.filter_reason,
        "analysed_at": row.analysed_at.isoformat() if row.analysed_at else None,
    }


@router.get("")
def get_filing_analysis(
    symbol: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None, description="BULLISH|BEARISH|NEUTRAL"),
    impact: Optional[str] = Query(None, description="HIGH|MEDIUM"),
    passed_only: bool = Query(True, description="Only show filings that passed operator filter"),
    tag: Optional[str] = Query(None, description="Filter by signal tag e.g. BEAT, ORDER_WIN"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated filing analysis history."""
    from app.db.models_filing_analysis import NseFilingAnalysis

    q = db.query(NseFilingAnalysis)

    if passed_only:
        q = q.filter(NseFilingAnalysis.passed_filter == True)  # noqa: E712
    if symbol:
        q = q.filter(NseFilingAnalysis.symbol == symbol.upper())
    if sentiment:
        q = q.filter(NseFilingAnalysis.sentiment == sentiment.upper())
    if impact:
        q = q.filter(NseFilingAnalysis.impact == impact.upper())
    if tag:
        q = q.filter(NseFilingAnalysis.signal_tags.contains(tag.upper()))

    total = q.count()
    rows = q.order_by(NseFilingAnalysis.analysed_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "data": [_row_to_dict(r) for r in rows],
    }


@router.get("/stats")
def get_filing_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Sentiment breakdown, top signal tags, most active symbols."""
    from app.db.models_filing_analysis import NseFilingAnalysis
    from datetime import datetime, timedelta
    from sqlalchemy import func

    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(NseFilingAnalysis)
        .filter(
            NseFilingAnalysis.passed_filter == True,  # noqa: E712
            NseFilingAnalysis.analysed_at >= cutoff,
        )
        .all()
    )

    sentiment_counts = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    tag_counts: dict[str, int] = {}
    symbol_counts: dict[str, int] = {}

    for r in rows:
        sentiment_counts[r.sentiment] = sentiment_counts.get(r.sentiment, 0) + 1
        for t in (r.signal_tags or "").split(","):
            if t:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        symbol_counts[r.symbol] = symbol_counts.get(r.symbol, 0) + 1

    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "days": days,
        "total_analysed": len(rows),
        "sentiment_breakdown": sentiment_counts,
        "top_signal_tags": [{"tag": t, "count": c} for t, c in top_tags],
        "most_active_symbols": [{"symbol": s, "count": c} for s, c in top_symbols],
    }


@router.get("/{filing_id}")
def get_filing_detail(filing_id: int, db: Session = Depends(get_db)):
    """Single filing with full PDF text."""
    from app.db.models_filing_analysis import NseFilingAnalysis

    row = db.query(NseFilingAnalysis).filter(NseFilingAnalysis.id == filing_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Filing not found")

    d = _row_to_dict(row)
    d["pdf_text"] = row.pdf_text  # include full text only in detail view
    return d


@router.post("/rerun/{filing_id}")
def rerun_filing_analysis(filing_id: int, db: Session = Depends(get_db)):
    """Re-download and re-analyse a specific filing."""
    from app.db.models_filing_analysis import NseFilingAnalysis
    from app.services.filing_pdf_analyzer import analyze_filing

    row = db.query(NseFilingAnalysis).filter(NseFilingAnalysis.id == filing_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Filing not found")

    result = analyze_filing(
        symbol=row.symbol,
        company=row.company,
        headline=row.headline,
        category=row.category or "",
        impact=row.impact or "HIGH",
        pdf_url=row.pdf_url,
        published_at=row.published_at or "",
        dedup_key=row.dedup_key,
    )

    for k, v in result.items():
        if hasattr(row, k):
            setattr(row, k, v)
    db.commit()

    return {"status": "reanalysed", "filing_id": filing_id, "sentiment": result["sentiment"]}
