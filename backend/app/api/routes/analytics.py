from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/pnl")
def get_pnl_analytics(
    days: int = Query(90, ge=7, le=365),
    strategy: Optional[str] = Query(None),
    underlying: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Returns full P&L analytics for the Strategy P&L Dashboard:
    - Per-strategy stats (win rate, profit factor, avg win/loss)
    - Equity curve (cumulative P&L over time)
    - Monthly P&L heatmap data
    - Drawdown series
    - Exit reason breakdown
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    q = db.query(ExecutionIntent).filter(
        ExecutionIntent.status == "CLOSED",
        ExecutionIntent.closed_at >= cutoff,
        ExecutionIntent.pnl.isnot(None),
    )
    if strategy:
        q = q.filter(ExecutionIntent.strategy == strategy)
    if underlying:
        q = q.filter(ExecutionIntent.underlying == underlying)

    trades = q.order_by(ExecutionIntent.closed_at.asc()).all()

    # ── Per-strategy stats ────────────────────────────────────────
    strategy_map: dict = defaultdict(lambda: {
        "trades": [], "wins": 0, "losses": 0,
        "gross_profit": 0.0, "gross_loss": 0.0,
    })

    for t in trades:
        pnl = t.pnl or 0.0
        s = strategy_map[t.strategy or "Unknown"]
        s["trades"].append(pnl)
        if pnl >= 0:
            s["wins"] += 1
            s["gross_profit"] += pnl
        else:
            s["losses"] += 1
            s["gross_loss"] += abs(pnl)

    strategy_stats = []
    for name, d in strategy_map.items():
        total = len(d["trades"])
        win_rate = round(d["wins"] / total * 100, 1) if total else 0
        avg_win = round(d["gross_profit"] / d["wins"], 2) if d["wins"] else 0
        avg_loss = round(d["gross_loss"] / d["losses"], 2) if d["losses"] else 0
        profit_factor = round(d["gross_profit"] / d["gross_loss"], 2) if d["gross_loss"] else None
        total_pnl = round(sum(d["trades"]), 2)
        strategy_stats.append({
            "strategy": name,
            "total_trades": total,
            "wins": d["wins"],
            "losses": d["losses"],
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "profit_factor": profit_factor,
            "total_pnl": total_pnl,
            "gross_profit": round(d["gross_profit"], 2),
            "gross_loss": round(d["gross_loss"], 2),
        })
    strategy_stats.sort(key=lambda x: x["total_pnl"], reverse=True)

    # ── Equity curve (cumulative P&L by date) ────────────────────
    equity_curve = []
    cumulative = 0.0
    for t in trades:
        cumulative += t.pnl or 0.0
        equity_curve.append({
            "date": t.closed_at.strftime("%Y-%m-%d") if t.closed_at else None,
            "pnl": round(t.pnl or 0.0, 2),
            "cumulative": round(cumulative, 2),
            "strategy": t.strategy,
            "underlying": t.underlying,
        })

    # ── Drawdown series ───────────────────────────────────────────
    peak = 0.0
    drawdown_series = []
    for point in equity_curve:
        c = point["cumulative"]
        if c > peak:
            peak = c
        dd = round(((c - peak) / peak * 100) if peak > 0 else 0.0, 2)
        drawdown_series.append({"date": point["date"], "drawdown": dd})

    max_drawdown = min((d["drawdown"] for d in drawdown_series), default=0.0)

    # ── Monthly heatmap ───────────────────────────────────────────
    monthly: dict = defaultdict(float)
    for t in trades:
        if t.closed_at:
            key = t.closed_at.strftime("%Y-%m")
            monthly[key] += t.pnl or 0.0

    monthly_heatmap = [
        {"month": k, "pnl": round(v, 2)}
        for k, v in sorted(monthly.items())
    ]

    # ── Exit reason breakdown ─────────────────────────────────────
    exit_reasons: dict = defaultdict(int)
    for t in trades:
        exit_reasons[t.exit_reason or "MANUAL"] += 1

    # ── Summary totals ────────────────────────────────────────────
    all_pnls = [t.pnl or 0.0 for t in trades]
    total_trades = len(all_pnls)
    total_wins = sum(1 for p in all_pnls if p >= 0)
    total_losses = total_trades - total_wins
    gross_profit = sum(p for p in all_pnls if p >= 0)
    gross_loss = sum(abs(p) for p in all_pnls if p < 0)

    # Distinct strategy/underlying lists for filter dropdowns
    all_strategies = sorted({t.strategy for t in db.query(ExecutionIntent.strategy)
                              .filter(ExecutionIntent.status == "CLOSED").distinct()
                              if t.strategy})
    all_underlyings = sorted({t.underlying for t in db.query(ExecutionIntent.underlying)
                               .filter(ExecutionIntent.status == "CLOSED").distinct()
                               if t.underlying})

    return {
        "summary": {
            "total_trades": total_trades,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "win_rate": round(total_wins / total_trades * 100, 1) if total_trades else 0,
            "total_pnl": round(sum(all_pnls), 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else None,
            "avg_win": round(gross_profit / total_wins, 2) if total_wins else 0,
            "avg_loss": round(gross_loss / total_losses, 2) if total_losses else 0,
            "max_drawdown": max_drawdown,
            "days": days,
        },
        "strategy_stats": strategy_stats,
        "equity_curve": equity_curve,
        "drawdown_series": drawdown_series,
        "monthly_heatmap": monthly_heatmap,
        "exit_reasons": dict(exit_reasons),
        "filters": {
            "strategies": all_strategies,
            "underlyings": all_underlyings,
        },
    }
