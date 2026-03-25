from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from collections import defaultdict
import os
import httpx

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

router = APIRouter(prefix="/ai-chat", tags=["AI Chat"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    message: str
    history: list = []  # [{role: "user"|"assistant", content: "..."}]


def _fmt(val):
    if val is None:
        return "N/A"
    return f"₹{val:,.2f}"


def _build_context(db: Session) -> str:
    lines = []

    # ── Open positions ────────────────────────────────────────────
    open_trades = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == "EXECUTED", ExecutionIntent.closed_at.is_(None))
        .order_by(ExecutionIntent.created_at.desc())
        .limit(50)
        .all()
    )
    if open_trades:
        total_unrealized = sum(t.unrealized_pnl or 0 for t in open_trades)
        lines.append(f"OPEN POSITIONS ({len(open_trades)}, total unrealized P&L: {_fmt(total_unrealized)}):")
        for t in open_trades:
            entry = _fmt(t.entry_credit)
            opened = t.created_at.strftime("%d %b %Y %H:%M") if t.created_at else "-"
            mode = ""
            if isinstance(t.execution_result, dict):
                mode = t.execution_result.get("mode", "")
            lines.append(
                f"  • {t.underlying} | {t.strategy} | Entry: {entry} | "
                f"Unrealized P&L: {_fmt(t.unrealized_pnl)} | Opened: {opened} | Mode: {mode}"
            )
    else:
        lines.append("OPEN POSITIONS: None currently")

    # ── Closed trades — last 90 days ──────────────────────────────
    cutoff = datetime.utcnow() - timedelta(days=90)
    closed = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.closed_at.isnot(None), ExecutionIntent.closed_at >= cutoff)
        .order_by(ExecutionIntent.closed_at.desc())
        .limit(100)
        .all()
    )
    if closed:
        total_pnl = sum(t.pnl or 0 for t in closed)
        wins = sum(1 for t in closed if (t.pnl or 0) > 0)
        losses = sum(1 for t in closed if (t.pnl or 0) < 0)
        win_rate = round(wins / len(closed) * 100, 1)
        avg_win = sum(t.pnl for t in closed if (t.pnl or 0) > 0) / max(wins, 1)
        avg_loss = sum(t.pnl for t in closed if (t.pnl or 0) < 0) / max(losses, 1)

        lines.append(
            f"\nCLOSED TRADES LAST 90 DAYS ({len(closed)} trades | "
            f"{wins}W/{losses}L | Win rate: {win_rate}% | "
            f"Total P&L: {_fmt(total_pnl)} | Avg win: {_fmt(avg_win)} | Avg loss: {_fmt(avg_loss)}):"
        )
        for t in closed:
            date = t.closed_at.strftime("%d %b %Y") if t.closed_at else "-"
            exit_r = t.exit_reason or "-"
            lines.append(
                f"  • {date} | {t.underlying} | {t.strategy} | "
                f"P&L: {_fmt(t.pnl)} | Exit: {exit_r}"
            )

        # ── Strategy breakdown ────────────────────────────────────
        by_strategy = defaultdict(lambda: {"pnl": 0, "trades": 0, "wins": 0})
        for t in closed:
            s = t.strategy or "Unknown"
            by_strategy[s]["pnl"] += t.pnl or 0
            by_strategy[s]["trades"] += 1
            if (t.pnl or 0) > 0:
                by_strategy[s]["wins"] += 1
        lines.append("\nSTRATEGY PERFORMANCE (last 90 days):")
        for s, v in sorted(by_strategy.items(), key=lambda x: x[1]["pnl"], reverse=True):
            wr = round(v["wins"] / v["trades"] * 100, 1)
            lines.append(f"  • {s}: {v['trades']} trades | Win rate: {wr}% | Total P&L: {_fmt(v['pnl'])}")

        # ── Underlying breakdown ──────────────────────────────────
        by_symbol = defaultdict(lambda: {"pnl": 0, "trades": 0})
        for t in closed:
            sym = t.underlying or "Unknown"
            by_symbol[sym]["pnl"] += t.pnl or 0
            by_symbol[sym]["trades"] += 1
        top_symbols = sorted(by_symbol.items(), key=lambda x: x[1]["pnl"], reverse=True)[:10]
        lines.append("\nTOP SYMBOLS BY P&L (last 90 days):")
        for sym, v in top_symbols:
            lines.append(f"  • {sym}: {v['trades']} trades | P&L: {_fmt(v['pnl'])}")
    else:
        lines.append("\nCLOSED TRADES: None in last 90 days")

    return "\n".join(lines)


SYSTEM_PROMPT = """You are an expert trading assistant for FastTrade, an algorithmic trading platform for Indian stock markets (NSE/BSE).

You have FULL access to the user's real trade data provided below. Use it to give specific, data-driven answers.

Your capabilities:
- Analyze open positions and suggest hold/exit decisions
- Calculate P&L, win rates, profit factors from the data
- Identify best/worst performing strategies and symbols
- Explain trading concepts (RSI, MACD, options greeks, spreads, etc.)
- Suggest risk management improvements based on actual trade history
- Identify patterns in winning vs losing trades
- Answer questions about Indian markets, NIFTY, BANKNIFTY, F&O
- Give actionable advice based on the user's specific trading style

Rules:
- Always answer based on the actual data provided — never say you don't have access
- Use ₹ for Indian rupees
- Be concise and direct — no fluff
- If data shows no trades, say so clearly
- For market/strategy questions without data, give expert advice

=== USER'S LIVE TRADE DATA ===
{context}
=============================="""


def _call_ollama(message: str, history: list, db: Session) -> str:
    context = _build_context(db)
    system = SYSTEM_PROMPT.format(context=context)

    messages = [{"role": "system", "content": system}]
    # Include conversation history for multi-turn chat
    for h in history[-10:]:  # last 10 turns to stay within context window
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        resp = httpx.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except httpx.ConnectError:
        return (
            "⚠️ Ollama is not running. Pull a model first:\n"
            "  docker exec fasttrade-ollama ollama pull llama3.2:3b"
        )
    except httpx.TimeoutException:
        return "⚠️ Ollama timed out — the model may still be loading. Try again in a moment."
    except Exception as e:
        return f"⚠️ LLM error: {e}"


@router.post("/query")
def chat_query(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        answer = _call_ollama(req.message, req.history, db)
        return {"ok": True, "answer": answer}
    except Exception as e:
        return {"ok": False, "answer": f"Error: {str(e)}"}
