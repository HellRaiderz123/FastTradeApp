from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from collections import defaultdict
import os
import httpx

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest
from app.db.models_scanner_signal import ScannerSignalHistory
from app.db.models_finance import (
    FinanceTransaction, Budget, SavingsGoal, BillReminder, RecurringTransaction
)
from app.db.models_trade_costs import TradeCost

router = APIRouter(prefix="/ai-chat", tags=["AI Chat"])

# ── LLM provider config ────────────────────────────────────────────────────
# Default: Groq (free, fast — get key at console.groq.com)
# Fallback: OpenAI-compatible endpoint (set LLM_BASE_URL + LLM_API_KEY)
# If no key is configured the AI screen shows a friendly setup message.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")   # groq | openai | custom
LLM_API_KEY  = os.getenv("LLM_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
LLM_MODEL    = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")  # fast Groq default
_LLM_BASE: dict[str, str] = {
    "groq":   "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
}
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or _LLM_BASE.get(LLM_PROVIDER, _LLM_BASE["groq"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    message: str
    history: list = []


def _fmt(val):
    if val is None:
        return "N/A"
    return f"₹{val:,.2f}"


def _build_context(db: Session) -> str:
    sections = []
    now = datetime.utcnow()

    # ── 1. OPEN POSITIONS ─────────────────────────────────────────
    open_pos = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.status == "EXECUTED", ExecutionIntent.closed_at.is_(None))
        .order_by(ExecutionIntent.created_at.desc()).limit(50).all()
    )
    if open_pos:
        total_unrealized = sum(t.unrealized_pnl or 0 for t in open_pos)
        lines = [f"OPEN POSITIONS ({len(open_pos)} | Total Unrealized P&L: {_fmt(total_unrealized)}):"]
        for t in open_pos:
            mode = (t.execution_result or {}).get("mode", "") if isinstance(t.execution_result, dict) else ""
            lines.append(
                f"  • {t.underlying} | Strategy: {t.strategy} | Entry: {_fmt(t.entry_credit)} "
                f"| Unrealized P&L: {_fmt(t.unrealized_pnl)} | Mode: {mode} "
                f"| Opened: {t.created_at.strftime('%d %b %Y %H:%M') if t.created_at else '-'}"
            )
        sections.append("\n".join(lines))
    else:
        sections.append("OPEN POSITIONS: None")

    # ── 2. CLOSED TRADES (last 90 days) ──────────────────────────
    cutoff90 = now - timedelta(days=90)
    closed = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.closed_at.isnot(None), ExecutionIntent.closed_at >= cutoff90)
        .order_by(ExecutionIntent.closed_at.desc()).limit(200).all()
    )
    if closed:
        total_pnl = sum(t.pnl or 0 for t in closed)
        wins = [t for t in closed if (t.pnl or 0) > 0]
        losses = [t for t in closed if (t.pnl or 0) < 0]
        win_rate = round(len(wins) / len(closed) * 100, 1)
        avg_win = sum(t.pnl for t in wins) / max(len(wins), 1)
        avg_loss = sum(t.pnl for t in losses) / max(len(losses), 1)
        profit_factor = abs(sum(t.pnl for t in wins) / sum(t.pnl for t in losses)) if losses else 0

        lines = [
            f"CLOSED TRADES LAST 90 DAYS ({len(closed)} trades | {len(wins)}W/{len(losses)}L "
            f"| Win Rate: {win_rate}% | Total P&L: {_fmt(total_pnl)} "
            f"| Avg Win: {_fmt(avg_win)} | Avg Loss: {_fmt(avg_loss)} | Profit Factor: {profit_factor:.2f}):"
        ]
        for t in closed:
            lines.append(
                f"  • {t.closed_at.strftime('%d %b %Y') if t.closed_at else '-'} "
                f"| {t.underlying} | {t.strategy} | P&L: {_fmt(t.pnl)} | Exit: {t.exit_reason or '-'}"
            )

        # Strategy breakdown
        by_strat = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0})
        for t in closed:
            s = t.strategy or "Unknown"
            by_strat[s]["pnl"] += t.pnl or 0
            by_strat[s]["trades"] += 1
            if (t.pnl or 0) > 0:
                by_strat[s]["wins"] += 1
        lines.append("\nSTRATEGY BREAKDOWN:")
        for s, v in sorted(by_strat.items(), key=lambda x: x[1]["pnl"], reverse=True):
            wr = round(v["wins"] / v["trades"] * 100, 1)
            lines.append(f"  • {s}: {v['trades']} trades | WR: {wr}% | P&L: {_fmt(v['pnl'])}")

        # Symbol breakdown
        by_sym = defaultdict(lambda: {"pnl": 0.0, "trades": 0})
        for t in closed:
            by_sym[t.underlying or "?"]["pnl"] += t.pnl or 0
            by_sym[t.underlying or "?"]["trades"] += 1
        top = sorted(by_sym.items(), key=lambda x: x[1]["pnl"], reverse=True)[:10]
        lines.append("\nTOP SYMBOLS BY P&L:")
        for sym, v in top:
            lines.append(f"  • {sym}: {v['trades']} trades | P&L: {_fmt(v['pnl'])}")

        sections.append("\n".join(lines))
    else:
        sections.append("CLOSED TRADES: None in last 90 days")

    # ── 3. CONDITION STRATEGIES (SCANNER) ────────────────────────
    try:
        strategies = db.query(ConditionStrategy).order_by(ConditionStrategy.created_at.desc()).limit(50).all()
        if strategies:
            lines = [f"CONDITION SCANNER STRATEGIES ({len(strategies)} total):"]
            for s in strategies:
                bt_info = ""
                if s.last_backtest_id:
                    bt = db.query(ConditionStrategyBacktest).filter(
                        ConditionStrategyBacktest.id == s.last_backtest_id
                    ).first()
                    if bt:
                        summary = (bt.result_dict or {}).get("summary", {})
                        bt_info = (
                            f" | Backtest: Return={summary.get('total_return_pct', 'N/A')}% "
                            f"Sharpe={summary.get('sharpe_ratio', 'N/A')} "
                            f"WR={summary.get('win_rate', 'N/A')}% "
                            f"Trades={summary.get('total_trades', 'N/A')}"
                        )
                lines.append(
                    f"  • [{s.id}] {s.name} | {s.direction} | {s.timeframe} | {s.universe} "
                    f"| Active: {s.is_active} | Last scan: {s.last_scan.strftime('%d %b %Y') if s.last_scan else 'Never'} "
                    f"| Signals: {s.last_signal_count}{bt_info}"
                )
            sections.append("\n".join(lines))
    except Exception:
        pass

    # ── 4. RECENT SCANNER SIGNALS ─────────────────────────────────
    try:
        cutoff7 = now - timedelta(days=7)
        signals = (
            db.query(ScannerSignalHistory)
            .filter(ScannerSignalHistory.first_seen_at >= cutoff7)
            .order_by(ScannerSignalHistory.first_seen_at.desc())
            .limit(30).all()
        )
        if signals:
            lines = [f"RECENT SCANNER SIGNALS (last 7 days, {len(signals)} signals):"]
            for sig in signals:
                lines.append(
                    f"  • {sig.symbol} | {sig.strategy_name} | {sig.direction} "
                    f"| Status: {sig.status} | LTP: {_fmt(sig.ltp)} "
                    f"| {sig.first_seen_at.strftime('%d %b %H:%M') if sig.first_seen_at else '-'}"
                )
            sections.append("\n".join(lines))
    except Exception:
        pass

    # ── 5. TRADE COSTS ────────────────────────────────────────────
    try:
        cutoff30 = now - timedelta(days=30)
        costs = (
            db.query(TradeCost)
            .filter(TradeCost.trade_date >= cutoff30)
            .order_by(TradeCost.trade_date.desc())
            .limit(50).all()
        )
        if costs:
            total_cost = sum(c.total_cost or 0 for c in costs)
            lines = [f"TRADE COSTS LAST 30 DAYS ({len(costs)} trades | Total charges: {_fmt(total_cost)}):"]
            by_seg = defaultdict(float)
            for c in costs:
                by_seg[c.segment or "UNKNOWN"] += c.total_cost or 0
            for seg, amt in by_seg.items():
                lines.append(f"  • {seg}: {_fmt(amt)}")
            sections.append("\n".join(lines))
    except Exception:
        pass

    # ── 6. FINANCE ────────────────────────────────────────────────
    try:
        cutoff30 = now - timedelta(days=30)
        txns = (
            db.query(FinanceTransaction)
            .filter(FinanceTransaction.tran_date >= cutoff30.date())
            .order_by(FinanceTransaction.tran_date.desc())
            .limit(100).all()
        )
        if txns:
            total_debit = sum(t.debit or 0 for t in txns)
            total_credit = sum(t.credit or 0 for t in txns)
            by_cat = defaultdict(float)
            for t in txns:
                by_cat[t.category or "Uncategorized"] += t.debit or 0
            lines = [
                f"FINANCE LAST 30 DAYS ({len(txns)} transactions | "
                f"Total Spent: {_fmt(total_debit)} | Total Received: {_fmt(total_credit)}):"
            ]
            lines.append("  Spending by category:")
            for cat, amt in sorted(by_cat.items(), key=lambda x: x[1], reverse=True)[:8]:
                lines.append(f"    • {cat}: {_fmt(amt)}")
            sections.append("\n".join(lines))

        # Budgets
        budgets = db.query(Budget).all()
        if budgets:
            lines = [f"BUDGETS ({len(budgets)}):"]
            for b in budgets:
                spent = sum(
                    t.debit or 0 for t in txns
                    if (t.category or "").lower() == b.category.lower()
                )
                pct = round(spent / b.monthly_limit * 100, 1) if b.monthly_limit else 0
                lines.append(f"  • {b.category}: Limit {_fmt(b.monthly_limit)} | Spent {_fmt(spent)} ({pct}%)")
            sections.append("\n".join(lines))

        # Savings goals
        goals = db.query(SavingsGoal).all()
        if goals:
            lines = [f"SAVINGS GOALS ({len(goals)}):"]
            for g in goals:
                pct = round(g.current_amount / g.target_amount * 100, 1) if g.target_amount else 0
                lines.append(
                    f"  • {g.name}: {_fmt(g.current_amount)} / {_fmt(g.target_amount)} ({pct}%) "
                    f"| Deadline: {g.deadline} | Priority: {g.priority}"
                )
            sections.append("\n".join(lines))

        # Unpaid bills
        bills = db.query(BillReminder).filter(BillReminder.is_paid == False).all()
        if bills:
            lines = [f"UNPAID BILLS ({len(bills)}):"]
            for b in bills:
                lines.append(f"  • {b.name}: {_fmt(b.amount)} | Due: {b.due_date} | Category: {b.category}")
            sections.append("\n".join(lines))

    except Exception:
        pass

    return "\n\n".join(sections)


SYSTEM_PROMPT = """You are an expert AI assistant for FastTrade — an algorithmic trading platform for Indian stock markets (NSE/BSE).

You have COMPLETE access to the user's real data across ALL modules:
- Trading positions (open & closed), P&L, strategies
- Condition Scanner strategies and backtest results
- Scanner signals generated in last 7 days
- Trade costs and brokerage charges
- Personal finance (transactions, budgets, savings goals, bills)

Use this data to give specific, data-driven answers. Never say you don't have access to data.

You can help with:
✅ Trade analysis — P&L, win rate, profit factor, best/worst trades
✅ Position advice — hold/exit decisions based on actual unrealized P&L
✅ Strategy analysis — which scanner strategies are working, backtest results
✅ Scanner signals — what signals fired recently, which stocks to watch
✅ Cost analysis — how much brokerage/STT is eating into profits
✅ Finance — spending patterns, budget status, savings progress, bill reminders
✅ Market education — options greeks, indicators, strategies explained
✅ Risk management — position sizing, drawdown, diversification advice
✅ Indian market specifics — NIFTY, BANKNIFTY, F&O, NSE/BSE rules

Rules:
- Be concise and direct — no fluff
- Use ₹ for Indian rupees
- Give actionable advice, not generic tips
- Reference specific numbers from the data when answering
- For follow-up questions, remember the conversation context

=== LIVE DATA FROM FASTTRADE ===
{context}
================================"""


def _call_llm(message: str, history: list, db: Session) -> str:
    if not LLM_API_KEY:
        return (
            "⚙️ AI not configured.\n\n"
            "Set **GROQ_API_KEY** in your .env file (free at console.groq.com) "
            "and restart the backend.\n\n"
            "Model used: " + LLM_MODEL
        )

    context = _build_context(db)
    system = SYSTEM_PROMPT.format(context=context)

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        resp = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={"model": LLM_MODEL, "messages": messages},
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except httpx.TimeoutException:
        return "⚠️ LLM request timed out. Check your connection."
    except httpx.HTTPStatusError as e:
        body = e.response.text[:300]
        return f"⚠️ LLM API error {e.response.status_code}: {body}"
    except Exception as e:
        return f"⚠️ LLM error: {e}"


@router.post("/query")
def chat_query(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        answer = _call_llm(req.message, req.history, db)
        return {"ok": True, "answer": answer}
    except Exception as e:
        return {"ok": False, "answer": f"Error: {str(e)}"}
