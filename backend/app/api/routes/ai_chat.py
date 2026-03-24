from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from datetime import datetime, timedelta
from collections import defaultdict
import os, re

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

router = APIRouter(prefix="/ai-chat", tags=["AI Chat"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    message: str


def _parse_days(text: str) -> int:
    if "today" in text: return 1
    if "week" in text: return 7
    if "month" in text: return 30
    if "year" in text: return 365
    m = re.search(r"(\d+)\s*day", text)
    if m: return int(m.group(1))
    return 30


def _fmt(val):
    if val is None: return "N/A"
    return f"₹{val:,.2f}"


def _handle(msg: str, db: Session) -> dict:
    t = msg.lower()
    days = _parse_days(t)
    cutoff = datetime.utcnow() - timedelta(days=days)

    base = db.query(ExecutionIntent).filter(
        ExecutionIntent.status == "CLOSED",
        ExecutionIntent.pnl.isnot(None),
        ExecutionIntent.closed_at >= cutoff,
    )

    # ── losing trades ─────────────────────────────────────────────
    if any(w in t for w in ["losing", "loss", "losses", "red"]):
        trades = base.filter(ExecutionIntent.pnl < 0).order_by(ExecutionIntent.closed_at.desc()).limit(20).all()
        if not trades:
            return {"answer": f"No losing trades in the last {days} day(s)."}
        rows = [{"date": tr.closed_at.strftime("%d %b %Y"), "strategy": tr.strategy,
                 "underlying": tr.underlying, "pnl": _fmt(tr.pnl)} for tr in trades]
        total = sum(tr.pnl for tr in trades)
        return {"answer": f"Found {len(trades)} losing trade(s) in the last {days} day(s). Total loss: {_fmt(total)}.", "table": rows}

    # ── winning trades ────────────────────────────────────────────
    if any(w in t for w in ["winning", "win", "profit", "green"]):
        trades = base.filter(ExecutionIntent.pnl > 0).order_by(ExecutionIntent.closed_at.desc()).limit(20).all()
        if not trades:
            return {"answer": f"No winning trades in the last {days} day(s)."}
        rows = [{"date": tr.closed_at.strftime("%d %b %Y"), "strategy": tr.strategy,
                 "underlying": tr.underlying, "pnl": _fmt(tr.pnl)} for tr in trades]
        total = sum(tr.pnl for tr in trades)
        return {"answer": f"Found {len(trades)} winning trade(s) in the last {days} day(s). Total profit: {_fmt(total)}.", "table": rows}

    # ── best strategy ─────────────────────────────────────────────
    if any(w in t for w in ["best strategy", "top strategy", "best performing"]):
        trades = base.all()
        if not trades:
            return {"answer": "No closed trades found."}
        sm = defaultdict(float)
        for tr in trades:
            sm[tr.strategy or "Unknown"] += tr.pnl or 0
        ranked = sorted(sm.items(), key=lambda x: x[1], reverse=True)
        rows = [{"strategy": s, "total_pnl": _fmt(p)} for s, p in ranked]
        return {"answer": f"Best strategy: {ranked[0][0]} with {_fmt(ranked[0][1])} in {days} day(s).", "table": rows}

    # ── summary / pnl ─────────────────────────────────────────────
    if any(w in t for w in ["summary", "pnl", "p&l", "performance", "how am i", "how did"]):
        trades = base.all()
        if not trades:
            return {"answer": f"No closed trades in the last {days} day(s)."}
        pnls = [tr.pnl or 0 for tr in trades]
        wins = sum(1 for p in pnls if p > 0)
        total = sum(pnls)
        wr = round(wins / len(pnls) * 100, 1)
        return {"answer": f"Last {days} day(s): {len(trades)} trades, {wins} wins ({wr}% win rate), total P&L: {_fmt(total)}."}

    # ── recent trades ─────────────────────────────────────────────
    if any(w in t for w in ["recent", "last", "latest", "trades"]):
        trades = db.query(ExecutionIntent).filter(
            ExecutionIntent.closed_at >= cutoff
        ).order_by(ExecutionIntent.closed_at.desc()).limit(10).all()
        if not trades:
            return {"answer": f"No trades in the last {days} day(s)."}
        rows = [{"date": tr.closed_at.strftime("%d %b %Y") if tr.closed_at else "-",
                 "strategy": tr.strategy, "underlying": tr.underlying,
                 "status": tr.status, "pnl": _fmt(tr.pnl)} for tr in trades]
        return {"answer": f"Last {len(trades)} trade(s) in {days} day(s):", "table": rows}

    # ── open positions ────────────────────────────────────────────
    if any(w in t for w in ["open", "active", "running", "live position"]):
        trades = db.query(ExecutionIntent).filter(
            ExecutionIntent.status.in_(["CONFIRMED", "OPEN"])
        ).order_by(ExecutionIntent.created_at.desc()).all()
        if not trades:
            return {"answer": "No open positions right now."}
        rows = [{"strategy": tr.strategy, "underlying": tr.underlying,
                 "unrealized_pnl": _fmt(tr.unrealized_pnl)} for tr in trades]
        return {"answer": f"{len(trades)} open position(s):", "table": rows}

    # ── fallback ──────────────────────────────────────────────────
    return {
        "answer": "I can answer questions like:\n• Show me losing trades this month\n• Best strategy this week\n• My P&L summary\n• Recent trades\n• Open positions"
    }


@router.post("/query")
def chat_query(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        result = _handle(req.message, db)
        return {"ok": True, **result}
    except Exception as e:
        return {"ok": False, "answer": f"Error: {str(e)}"}
