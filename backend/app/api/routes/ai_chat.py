from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta, date
from collections import defaultdict
import json
import logging
import os
import re
import httpx

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest
from app.db.models_scanner_signal import ScannerSignalHistory
from app.db.models_watchlist import Watchlist
from app.db.models_finance import (
    FinanceTransaction, Budget, SavingsGoal, BillReminder, RecurringTransaction
)
from app.db.models_trade_costs import TradeCost
from app.db import finance_repo
from app.api.schemas.finance import (
    BudgetCreate, SavingsGoalCreate, BillReminderCreate, FinanceTransactionCreate
)
from app.services.llm_service import get_model_candidates, request_chat_completion

logger = logging.getLogger(__name__)

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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except Exception:
        return default


def _as_bool(val, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in {"1", "true", "yes", "y", "on"}
    return default


def _preferred_tool_choice(message: str, history: list | None = None):
    """Return the tool_choice value for the first LLM round.

    Forcing a specific tool for clearly-intent messages reduces round trips
    and avoids the LLM stalling without a tool call on unambiguous requests.
    """
    normalized = " ".join(str(message or "").lower().split())

    # Market data / price lookup
    if re.search(
        r"\b(price|ltp|quote|trading at|current price|what is .{0,20} at|how much is)\b",
        normalized,
    ):
        return {"type": "function", "function": {"name": "get_stock_quote"}}

    # Portfolio overview
    if re.search(
        r"\b(portfolio|my positions|open trades|total p&?l|how much (am i|have i) (up|down|made|lost))\b",
        normalized,
    ):
        return {"type": "function", "function": {"name": "get_portfolio_summary"}}

    # Market sentiment
    if re.search(
        r"\b(market (sentiment|outlook|mood|bias)|nifty (prediction|direction|today)|bullish|bearish|vix|pcr)\b",
        normalized,
    ):
        return {"type": "function", "function": {"name": "get_market_sentiment"}}

    # News
    if re.search(
        r"\b(news|headlines|latest|today.*news|market update|geopolit)\b",
        normalized,
    ):
        return {"type": "function", "function": {"name": "get_market_news_summary"}}

    # Orders placed today
    if re.search(
        r"\b(orders? today|what did i (buy|sell|order) today|today.*orders?|my orders?)\b",
        normalized,
    ):
        return {"type": "function", "function": {"name": "get_orders_today"}}

    # Trade journal / review
    if re.search(
        r"\b(journal|review.*trades?|trade.*review|win rate|performance|coaching)\b",
        normalized,
    ):
        return {"type": "function", "function": {"name": "review_trade_journal"}}

    return "auto"


def _normalize_voice_answer(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(r"[*_`#]+", "", cleaned)
    cleaned = re.sub(r"\n\s*[-•]\s*", "; ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalize_trade_symbol(raw_symbol: str) -> str:
    symbol = str(raw_symbol or "").upper().strip()
    symbol = re.sub(r"^(?:NSE|BSE)\s*[:\-]\s*", "", symbol)
    symbol = re.sub(r"\s+", "", symbol)
    symbol = re.sub(r"^[^A-Z0-9]+", "", symbol)
    symbol = re.sub(r"[^A-Z0-9&-]+$", "", symbol)
    return symbol


def _extract_direct_ai_action(message: str):
    text = str(message or "").strip()
    normalized = " ".join(text.lower().split())
    if not normalized:
        return None

    geopolitical_match = re.search(
        r"\b(iran|israel|gaza|ukraine|russia|china|taiwan|middle\s+east|war|conflict|missile|ceasefire|sanctions?)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if geopolitical_match and re.search(r"\b(news|update|updates|latest|today|happening|status|brief|summary|war|conflict)\b", normalized, flags=re.IGNORECASE):
        return "get_market_news_summary", {"limit": 12, "keyword": geopolitical_match.group(1)}

    if re.search(r"\b(today'?s?|latest|market)\s+news\b|\bnews\s+(today|now)\b|\b(headlines?|updates?)\b", normalized, flags=re.IGNORECASE):
        topic_match = re.search(r"(?:news|update|headlines?)\s+(?:on|about)\s+([a-z0-9\s\-]{2,40})", normalized, flags=re.IGNORECASE)
        args = {"limit": 8}
        if topic_match:
            args["keyword"] = topic_match.group(1).strip()
        return "get_market_news_summary", args

    if re.search(r"\b(scanner|signals?)\b.*\b(this week|weekly|last 7 days|past week)\b", normalized, flags=re.IGNORECASE):
        return "get_recent_scanner_signals", {"days": 7}

    if re.search(r"\b(brokerage|charges|stt|costs?)\b", normalized, flags=re.IGNORECASE):
        days_match = re.search(r"\b(last|past)\s+(\d{1,3})\s+days\b", normalized)
        days = int(days_match.group(2)) if days_match else 30
        return "get_trade_cost_summary", {"days": max(1, min(days, 365))}

    generic_close_match = re.search(
        r"(?:close|exit|square\s*off)(?:\s+my|\s+the)?\s+(?:(current|latest|open|active)\s+)?(?:position|postion|trade)\b",
        normalized,
        flags=re.IGNORECASE,
    )
    if generic_close_match:
        return "close_position", {"reference": (generic_close_match.group(1) or "current").lower()}

    close_match = re.search(
        r"(?:close|exit|square\s*off)(?:\s+my|\s+the)?(?:\s+(?:position|postion|trade)(?:\s+in)?)?\s+([A-Za-z][A-Za-z0-9&.-]+)",
        text,
        flags=re.IGNORECASE,
    )
    if close_match:
        candidate = close_match.group(1).upper()
        if candidate.lower() in {"current", "latest", "open", "active", "position", "postion", "trade"}:
            return "close_position", {"reference": "current"}
        return "close_position", {"underlying": candidate}

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
    }

    # Prefer explicit quantity + share/qty phrasing so text like
    # "buy one share of TCS" does not mis-detect "ONE" as symbol.
    trade_match = re.search(
        r"\b(buy|sell)\b\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s*(?:share|shares|qty|quantity|lot|lots)\s*(?:of\s+)?([A-Za-z][A-Za-z0-9&.-]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not trade_match:
        # Fallback for compact forms like "buy TCS" or "sell 2 TCS"
        trade_match = re.search(
            r"\b(buy|sell)\b\s*(?:(\d+)\s*)?(?:of\s+)?([A-Za-z][A-Za-z0-9&.-]+)",
            text,
            flags=re.IGNORECASE,
        )
    if trade_match:
        action = trade_match.group(1).upper()
        qty_raw = str(trade_match.group(2) or "1").strip().lower()
        quantity = int(qty_raw) if qty_raw.isdigit() else int(number_words.get(qty_raw, 1))
        symbol = _normalize_trade_symbol(trade_match.group(3))

        if not symbol:
            return None

        # Ignore accidental symbol captures from confirmation words.
        if symbol in {"YES", "NO", "CONFIRM", "PLACE", "NOW", "EXECUTE"}:
            return None

        product = "MIS" if re.search(r"\bmis\b", normalized) else "NRML" if re.search(r"\bnrml\b", normalized) else "CNC"
        price_match = re.search(r"(?:limit(?:\s+price)?|at)\s*₹?\s*(\d+(?:\.\d+)?)", normalized)
        use_market = "market" in normalized or not price_match
        order_type = "MARKET" if use_market else "LIMIT"
        price = None if use_market else float(price_match.group(1))
        dry_run = any(term in normalized for term in ("dry run", "paper trade", "paper only", "simulate"))
        confirmed = any(term in normalized for term in ("confirm", "place now", "execute now", "confirm and place"))
        return "place_trade", {
            "symbol": symbol,
            "action": action,
            "quantity": quantity,
            "product": product,
            "order_type": order_type,
            "exchange": "NSE",
            "price": price,
            "dry_run": dry_run,
            "confirmed": confirmed,
        }

    return None


def _summarize_direct_action(tool_name: str, result: dict, voice_mode: bool = False) -> str:
    if not result.get("success"):
        text = result.get("error") or "Action failed."
        return _normalize_voice_answer(text) if voice_mode else text

    if tool_name == "get_market_news_summary":
        headlines = result.get("headlines") or []
        topic = (result.get("query_topic") or "").strip()
        if not headlines:
            if topic:
                text = f"I could not find fresh headlines matching '{topic}' in current feeds."
            else:
                text = "No fresh market headlines are available right now."
            return _normalize_voice_answer(text) if voice_mode else text

        top_titles = [str(h.get("title") or "").strip() for h in headlines[:3] if isinstance(h, dict)]
        top_titles = [t for t in top_titles if t]
        if topic:
            prefix = f"Latest headlines related to {topic}: "
        else:
            prefix = "Latest market headlines: "
        text = prefix + " | ".join(top_titles)
        return _normalize_voice_answer(text) if voice_mode else text

    if result.get("requires_confirmation"):
        preview = result.get("order_preview") or result.get("confirmation_preview") or {}
        if preview.get("trade_action"):
            text = (
                f"Order ready: {preview.get('trade_action')} {preview.get('quantity')} {preview.get('symbol')} "
                f"as a {preview.get('order_type')} {preview.get('product')} order on {preview.get('exchange')}. "
                "Please confirm to execute."
            )
        else:
            target = preview.get("symbol") or preview.get("name") or "item"
            text = f"Confirmation needed for {result.get('action', 'action').replace('_', ' ')} on {target}."
        return _normalize_voice_answer(text) if voice_mode else text

    if result.get("action") == "placed_trade":
        text = (
            f"Order placed: {result.get('trade_action')} {result.get('quantity')} {result.get('symbol')}. "
            f"Order ID {result.get('order_id')}."
        )
        return _normalize_voice_answer(text) if voice_mode else text

    if result.get("action") == "simulated_trade":
        preview = result.get("would_place") or {}
        text = (
            f"Dry run ready: {preview.get('trade_action')} {preview.get('quantity')} {preview.get('symbol')} "
            f"via {preview.get('order_type')} {preview.get('product')}. No live order was placed."
        )
        return _normalize_voice_answer(text) if voice_mode else text

    if result.get("action") == "closed_position":
        text = f"Closed the {result.get('underlying')} position."
        return _normalize_voice_answer(text) if voice_mode else text

    text = result.get("message") or f"Completed {tool_name.replace('_', ' ')}."
    return _normalize_voice_answer(text) if voice_mode else text


# AI trade safety controls (override via backend .env)
AI_REQUIRE_TRADE_CONFIRMATION = _env_bool("AI_REQUIRE_TRADE_CONFIRMATION", True)
AI_MAX_ORDER_QTY = _env_int("AI_MAX_ORDER_QTY", 500)
AI_MAX_OPEN_POSITIONS = _env_int("AI_MAX_OPEN_POSITIONS", 10)
AI_MAX_DAILY_LOSS_INR = _env_float("AI_MAX_DAILY_LOSS_INR", 0.0)  # 0 disables daily loss guard
_AI_MARKET_PROTECTION_RAW = _env_int("AI_MARKET_PROTECTION_PCT", 2)
AI_MARKET_PROTECTION_PCT = max(0, min(_AI_MARKET_PROTECTION_RAW, 100))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ChatRequest(BaseModel):
    message: str
    history: list = []
    voice_mode: bool = False
    assistant_style: str | None = None


def _fmt(val):
    if val is None:
        return "N/A"
    return f"₹{val:,.2f}"


def _calc_profit_factor(win_total: float, loss_total: float):
    if abs(loss_total or 0) < 1e-9:
        return None
    return round(abs(float(win_total) / float(loss_total)), 2)


def _trade_time_bucket(dt: datetime | None) -> str:
    if not dt:
        return "Unknown"
    minutes = (dt.hour * 60) + dt.minute
    if minutes < 10 * 60:
        return "09:15-10:00"
    if minutes < 11 * 60:
        return "10:00-11:00"
    if minutes < (12 * 60 + 30):
        return "11:00-12:30"
    if minutes < 14 * 60:
        return "12:30-14:00"
    if minutes < (15 * 60 + 30):
        return "14:00-15:30"
    return "After-hours"


def _summarize_trade_group(trades: list[ExecutionIntent]) -> dict:
    total = sum((t.pnl or 0) for t in trades)
    wins = [t for t in trades if (t.pnl or 0) > 0]
    losses = [t for t in trades if (t.pnl or 0) < 0]
    avg_pnl = round(total / len(trades), 2) if trades else 0.0
    return {
        "trades": len(trades),
        "pnl": round(total, 2),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
        "avg_pnl": avg_pnl,
        "avg_win": round(sum((t.pnl or 0) for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum((t.pnl or 0) for t in losses) / len(losses), 2) if losses else 0.0,
    }


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

You have COMPLETE access to the user's real data AND the ability to take real actions via built-in tools.

DATA ACCESS:
- Trading positions (open & closed), P&L, strategies
- Condition Scanner strategies and backtest results
- Scanner signals generated in last 7 days
- Trade costs and brokerage charges
- Market news feeds, trending topics, and sentiment-tagged headlines
- Major global macro and geopolitical headlines present in the fetched news feeds (e.g., wars, sanctions, oil shocks)
- Personal finance (transactions, budgets, savings goals, bills)

ACTIONS YOU CAN PERFORM (use your tools — do not say you cannot do these):
✅ create_budget — "Add a Food budget of ₹3000"
✅ update_budget — "Change my Travel budget to ₹8000"
✅ delete_budget — "Remove the Shopping budget"
✅ create_savings_goal — "Create a savings goal: New Bike, ₹50000, by Dec 2026"
✅ update_savings_goal_progress — "Update my Emergency Fund to ₹25000"
✅ create_bill_reminder — "Add a reminder for Electricity bill ₹1200 due on 10th April"
✅ mark_bill_paid — "Mark my Internet bill as paid"
✅ add_transaction — "Record ₹450 spent on lunch under Food"
✅ run_scanner — "Run the RSI Oversold scanner"
✅ close_position — "Close my NIFTY position" / "Exit the BANKNIFTY trade"
✅ place_trade — "Buy 10 shares of SBI at market price CNC" / "Sell 5 RELIANCE shares MIS"
✅ place_trade dry run — "Dry run: buy 10 shares of SBI at market CNC"
✅ get_stock_quote — "What is WIPRO trading at?" / "Price of RELIANCE" / "HDFC Bank LTP"
✅ get_portfolio_summary — "What's my portfolio?" / "How much am I up today?" / "Show my open positions"
✅ set_position_sl_tp — "Set SL on my WIPRO at 280" / "Put a 2% trailing stop on RELIANCE" / "Set TP at 1500"
✅ get_orders_today — "What orders did I place today?" / "Show today's order book"
✅ get_market_sentiment — "What is NIFTY prediction today?" / "Is market bullish or bearish now?"
✅ get_market_news_summary — "Today's market news" / "Top headlines right now"
✅ get_recent_scanner_signals — "What scanner signals fired this week?"
✅ get_trade_cost_summary — "How much am I spending on brokerage?"
✅ get_strategy_metrics — "How many trades did strategy X take and over what period?"
✅ get_watchlist_gameplan — "Build my pre-market game plan" / "Rank my watchlist for today"
✅ review_trade_journal — "Review my last 30 days of trades" / "What patterns are hurting my performance?"
✅ trade_autopsy — "Autopsy my last NIFTY trade" / "Coach me on my most recent loss"

ANALYSIS YOU CAN DO:
✅ Trade analysis — P&L, win rate, profit factor, best/worst trades
✅ Position advice — hold/exit decisions based on actual unrealized P&L
✅ Strategy analysis — which scanner strategies are working, backtest results
✅ Scanner signals — what signals fired recently, which stocks to watch
✅ Pre-market planning — rank your watchlist using signals, sentiment, and open exposure
✅ Journal coaching — highlight best/worst setups, time-of-day issues, and repeated mistakes
✅ Trade autopsy — review the latest closed trade with discipline and exit-quality notes
✅ Cost analysis — how much brokerage/STT is eating into profits
✅ Finance — spending patterns, budget status, savings progress, bill reminders
✅ Market education — options greeks, indicators, strategies explained
✅ Risk management — position sizing, drawdown, diversification advice
✅ Indian market specifics — NIFTY, BANKNIFTY, F&O, NSE/BSE rules
✅ NIFTY outlook — sentiment score, fear-greed, momentum, and directional bias
✅ News intelligence — today's market headlines, sentiment tilt, and top themes
✅ Geopolitical briefings — summarize wars/conflicts/headlines from available feeds and explain market impact (oil, risk sentiment, sectors)

CRITICAL RULES:
- NEVER say you cannot perform actions — you have tools for all the above
- When the user asks to DO something, call the appropriate tool immediately
- Do NOT block trade placement because another position is open or in loss; multiple positions are allowed
- Do NOT ask user to close an existing position unless user explicitly asks for risk checks or asks to close it
- If user asks to place a trade, execute place_trade (or place_trade with dry_run=true when they ask for dry run)
- For live trade placement: first call place_trade with confirmed=false to get explicit confirmation step
- If user confirms ("yes", "confirm", "place now", "execute"), call place_trade again with confirmed=true using the same order details
- Enforce hard risk limits from backend settings; if a limit is breached, clearly explain which guardrail blocked the order
- Be concise and direct — no fluff
- Use ₹ for Indian rupees
- Reference specific numbers from the data when answering
- After performing an action, confirm what was done with the key details
- NEVER invent numbers, dates, or charges
- For strategy performance/trade-count questions, call get_strategy_metrics first and use only returned fields
- If a field is missing, explicitly say "data not available" instead of estimating
- If numbers conflict, say they conflict and show both values with source labels
- Do not infer strategy style (intraday/swing/positional) unless explicitly present in returned fields; for timeframe, quote the exact timeframe value from tool output
- Do not say geopolitical requests are out of scope; use get_market_news_summary and provide a factual update from current feeds
- If a requested topic is not present in current feeds, say so explicitly and then provide the closest relevant headlines

=== LIVE DATA FROM FASTTRADE ===
{context}
================================"""


# ── Agentic tool definitions ───────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_budget",
            "description": "Create a monthly spending budget for a category. Use when the user asks to set or add a budget.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Budget category name (e.g. Food, Travel, Entertainment, Shopping)"},
                    "monthly_limit": {"type": "number", "description": "Monthly spending limit in INR"},
                    "alert_threshold": {"type": "number", "description": "Alert when spending reaches this percentage of the limit. Default is 80."},
                },
                "required": ["category", "monthly_limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_budget",
            "description": "Update the monthly limit of an existing budget for a category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "The budget category to update"},
                    "monthly_limit": {"type": "number", "description": "New monthly limit in INR"},
                },
                "required": ["category", "monthly_limit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_budget",
            "description": "Delete an existing budget by category name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "The budget category to delete"},
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_savings_goal",
            "description": "Create a new savings goal. Use when the user wants to save for something specific.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the savings goal (e.g. New Laptop, Emergency Fund, Vacation)"},
                    "target_amount": {"type": "number", "description": "Target savings amount in INR"},
                    "deadline": {"type": "string", "description": "Deadline date in YYYY-MM-DD format"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"], "description": "Priority level, default medium"},
                    "category": {"type": "string", "description": "Optional category for the goal"},
                },
                "required": ["name", "target_amount", "deadline"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_savings_goal_progress",
            "description": "Update the current saved amount for a savings goal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Exact name of the savings goal"},
                    "current_amount": {"type": "number", "description": "New current saved amount in INR"},
                },
                "required": ["name", "current_amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_bill_reminder",
            "description": "Add a bill reminder so the user gets notified before the due date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Bill name (e.g. Electricity, Internet, Rent)"},
                    "amount": {"type": "number", "description": "Bill amount in INR"},
                    "due_date": {"type": "string", "description": "Due date in YYYY-MM-DD format"},
                    "category": {"type": "string", "description": "Bill category (e.g. Utilities, Rent, Subscriptions)"},
                    "reminder_days": {"type": "number", "description": "How many days before due date to remind. Default 3."},
                },
                "required": ["name", "amount", "due_date", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_bill_paid",
            "description": "Mark a bill as paid by its name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the bill to mark as paid"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_transaction",
            "description": "Record a financial transaction (an expense or income). Use when the user says they spent or received money.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Description of the transaction"},
                    "amount": {"type": "number", "description": "Amount in INR (positive number)"},
                    "transaction_type": {"type": "string", "enum": ["expense", "income"], "description": "Whether this is an expense (debit) or income (credit)"},
                    "category": {"type": "string", "description": "Category (e.g. Food, Travel, Salary, Freelance)"},
                    "tran_date": {"type": "string", "description": "Date in YYYY-MM-DD format. Defaults to today if not specified."},
                },
                "required": ["description", "amount", "transaction_type", "category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_sentiment",
            "description": "Fetch current market sentiment and NIFTY directional bias using VIX, PCR, market breadth, and index momentum.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_news_summary",
            "description": "Fetch today's market news headlines with sentiment summary and trending topics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of headlines to fetch. Default 8, max 20."},
                    "keyword": {"type": "string", "description": "Optional topic filter keyword, e.g., iran, war, oil, rbi, banking."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_scanner_signals",
            "description": "Fetch scanner signals generated in recent days without rerunning scanner strategies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback in days. Default 7, max 90."},
                    "strategy_name": {"type": "string", "description": "Optional strategy name filter (partial match)."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trade_cost_summary",
            "description": "Summarize brokerage and trading charges over a recent lookback window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback in days. Default 30, max 365."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_strategy_metrics",
            "description": "Fetch exact strategy metrics from database: timeframe, backtest period, total trades, return, sharpe, win rate, and recent signal count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_name": {"type": "string", "description": "Name or partial name of the strategy"},
                },
                "required": ["strategy_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_watchlist_gameplan",
            "description": "Build a pre-market or watchlist game plan using the user's saved watchlists, recent scanner signals, and market sentiment. Use for prompts like 'build my pre-market plan' or 'rank my watchlist'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "watchlist_name": {"type": "string", "description": "Optional watchlist name. If omitted, use the default or most recent active watchlist."},
                    "top_n": {"type": "integer", "description": "How many symbols to prioritize. Default 8, max 25."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_watchlist",
            "description": "Create a new watchlist. Use when user asks to create a watchlist with a specific name and optional starter symbols.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Watchlist name, e.g. Swing Picks"},
                    "description": {"type": "string", "description": "Optional description"},
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional initial symbols, e.g. [\"RELIANCE\", \"INFY\"]"
                    },
                    "is_default": {"type": "boolean", "description": "Set true to make this the default watchlist."}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_watchlist_symbol",
            "description": "Add a symbol to a watchlist by name (or default watchlist if not provided).",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Symbol to add, e.g. RELIANCE"},
                    "watchlist_name": {"type": "string", "description": "Optional watchlist name. If omitted, uses default/most recent active watchlist."}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_watchlist_symbol",
            "description": "Remove a symbol from a watchlist. This is destructive and requires explicit confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Symbol to remove, e.g. RELIANCE"},
                    "watchlist_name": {"type": "string", "description": "Optional watchlist name. If omitted, uses default/most recent active watchlist."},
                    "confirmed": {"type": "boolean", "description": "Set true only after user explicitly confirms deletion."}
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "review_trade_journal",
            "description": "Review recent closed trades and summarize journal patterns like win rate, expectancy, best/worst strategy, time-of-day weakness, and coaching flags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Lookback period in days. Default 30."},
                    "focus": {"type": "string", "description": "Optional focus area such as strategy, discipline, exits, or time-of-day."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trade_autopsy",
            "description": "Analyze a recent closed trade using actual FastTrade data. Use when the user asks for a trade autopsy, coaching review, or post-trade breakdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "underlying": {"type": "string", "description": "Optional symbol to focus on, such as NIFTY, BANKNIFTY, or RELIANCE."},
                    "intent_id": {"type": "string", "description": "Optional exact FastTrade intent ID if the user mentions a specific trade."},
                    "lookback_days": {"type": "integer", "description": "Lookback period for finding the trade. Default 90."}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_scanner",
            "description": "Trigger a condition scanner strategy to scan for signals now. Use when user asks to run a scanner or find signals for a strategy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy_name": {"type": "string", "description": "Name or partial name of the scanner strategy to run"},
                },
                "required": ["strategy_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "close_position",
            "description": "Manually exit/close an open trading position. Use when user asks to close or exit a specific position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "underlying": {"type": "string", "description": "Symbol name of the position to close (e.g. NIFTY, BANKNIFTY, RELIANCE)"},
                },
                "required": ["underlying"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_trade",
            "description": "Place a real stock buy or sell order on Zerodha. Use when the user asks to buy or sell shares/stocks. Supports CNC (delivery), MIS (intraday), NRML (F&O overnight). Do not require closing other open positions first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "NSE/BSE tradingsymbol (e.g. SBIN, RELIANCE, INFY, TCS, HDFCBANK). No spaces."},
                    "action": {"type": "string", "enum": ["BUY", "SELL"], "description": "Whether to buy or sell"},
                    "quantity": {"type": "integer", "description": "Number of shares to buy or sell"},
                    "product": {"type": "string", "enum": ["CNC", "MIS", "NRML"], "description": "CNC = delivery, MIS = intraday, NRML = F&O overnight. Default CNC for stocks."},
                    "order_type": {"type": "string", "enum": ["MARKET", "LIMIT"], "description": "MARKET = execute at best price, LIMIT = execute at specified price. Default MARKET."},
                    "price": {"type": "number", "description": "Limit price in INR. Required only when order_type is LIMIT."},
                    "exchange": {"type": "string", "enum": ["NSE", "BSE"], "description": "Exchange to place order on. Default NSE."},
                    "dry_run": {"type": "boolean", "description": "If true, simulate order placement and return what would be sent without placing any real order."},
                    "confirmed": {"type": "boolean", "description": "Set true only after user explicitly confirms the exact order details for live placement."},
                },
                "required": ["symbol", "action", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_quote",
            "description": "Fetch the current live price (LTP), OHLC, volume, and circuit limits for any NSE/BSE stock or index. Use whenever the user asks for a price, quote, or 'what is X trading at'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "NSE tradingsymbol or index name, e.g. WIPRO, RELIANCE, NIFTY, BANKNIFTY"},
                    "exchange": {"type": "string", "enum": ["NSE", "BSE", "NFO"], "description": "Exchange. Default NSE for stocks, use NFO for F&O instruments."},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_summary",
            "description": "Return a live summary of all open positions including total unrealized P&L, individual position details, margin used, and risk concentration. Use when user asks about their portfolio, total P&L, or overall position status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_closed_today": {"type": "boolean", "description": "If true, also include trades closed today. Default false."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_position_sl_tp",
            "description": "Set or update stop-loss (SL), take-profit (TP), or trailing SL on an open position in FastTrade. Use when user says 'set SL at X', 'put a stop at X', 'set target at X', or 'add trailing stop'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "underlying": {"type": "string", "description": "Symbol of the open position to update, e.g. WIPRO, NIFTY"},
                    "sl": {"type": "number", "description": "Stop-loss price in INR. Set to null to leave unchanged."},
                    "tp": {"type": "number", "description": "Take-profit price in INR. Set to null to leave unchanged."},
                    "trailing_sl_pct": {"type": "number", "description": "Trailing stop-loss as a percentage of price, e.g. 2.0 for 2%. Set to null to leave unchanged."},
                },
                "required": ["underlying"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_orders_today",
            "description": "Fetch all orders placed on Zerodha today. Use when user asks what orders they placed today, order status, or to see today's order book.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── Tool executor ──────────────────────────────────────────────────────────

def _execute_tool(name: str, args: dict, db: Session) -> dict:
    """Execute a single tool call and return a result dict."""
    try:
        if name == "create_budget":
            existing = (
                db.query(Budget)
                .filter(
                    Budget.category.ilike(args["category"]),
                    Budget.month == datetime.now().strftime("%Y-%m"),
                )
                .first()
            )
            if existing:
                existing.monthly_limit = args["monthly_limit"]
                if "alert_threshold" in args:
                    existing.alert_threshold = args["alert_threshold"]
                db.commit()
                return {"success": True, "action": "updated_budget", "category": args["category"], "monthly_limit": args["monthly_limit"]}
            payload = BudgetCreate(
                category=args["category"],
                monthly_limit=args["monthly_limit"],
                alert_threshold=args.get("alert_threshold", 80),
            )
            budget = finance_repo.create_budget(db, payload)
            return {"success": True, "action": "created_budget", "id": budget.id, "category": budget.category, "monthly_limit": budget.monthly_limit}

        elif name == "update_budget":
            budget = (
                db.query(Budget)
                .filter(
                    Budget.category.ilike(args["category"]),
                    Budget.month == datetime.now().strftime("%Y-%m"),
                )
                .first()
            )
            if not budget:
                return {"success": False, "error": f"No budget found for category '{args['category']}'"}
            budget.monthly_limit = args["monthly_limit"]
            db.commit()
            return {"success": True, "action": "updated_budget", "category": args["category"], "monthly_limit": args["monthly_limit"]}

        elif name == "delete_budget":
            budget = (
                db.query(Budget)
                .filter(Budget.category.ilike(args["category"]))
                .first()
            )
            if not budget:
                return {"success": False, "error": f"No budget found for '{args['category']}'"}
            db.delete(budget)
            db.commit()
            return {"success": True, "action": "deleted_budget", "category": args["category"]}

        elif name == "create_savings_goal":
            deadline = args["deadline"]
            if isinstance(deadline, str):
                deadline = date.fromisoformat(deadline)
            payload = SavingsGoalCreate(
                name=args["name"],
                target_amount=args["target_amount"],
                deadline=deadline,
                priority=args.get("priority", "medium"),
                category=args.get("category"),
            )
            goal = finance_repo.create_savings_goal(db, payload)
            return {"success": True, "action": "created_savings_goal", "id": goal.id, "name": goal.name, "target_amount": goal.target_amount, "deadline": str(goal.deadline)}

        elif name == "update_savings_goal_progress":
            goal = db.query(SavingsGoal).filter(SavingsGoal.name.ilike(f"%{args['name']}%")).first()
            if not goal:
                return {"success": False, "error": f"No savings goal matching '{args['name']}'"}
            goal.current_amount = args["current_amount"]
            db.commit()
            pct = round(goal.current_amount / goal.target_amount * 100, 1) if goal.target_amount else 0
            return {"success": True, "action": "updated_savings_goal", "name": goal.name, "current_amount": goal.current_amount, "progress_pct": pct}

        elif name == "create_bill_reminder":
            due_date = args["due_date"]
            if isinstance(due_date, str):
                due_date = date.fromisoformat(due_date)
            payload = BillReminderCreate(
                name=args["name"],
                amount=args["amount"],
                due_date=due_date,
                category=args["category"],
                reminder_days=int(args.get("reminder_days", 3)),
            )
            bill = finance_repo.create_bill_reminder(db, payload)
            return {"success": True, "action": "created_bill_reminder", "id": bill.id, "name": bill.name, "amount": bill.amount, "due_date": str(bill.due_date)}

        elif name == "mark_bill_paid":
            bill = db.query(BillReminder).filter(BillReminder.name.ilike(f"%{args['name']}%"), BillReminder.is_paid == False).first()
            if not bill:
                return {"success": False, "error": f"No unpaid bill matching '{args['name']}'"}
            bill.is_paid = True
            db.commit()
            return {"success": True, "action": "marked_bill_paid", "name": bill.name, "amount": bill.amount}

        elif name == "add_transaction":
            tran_date = args.get("tran_date")
            if tran_date:
                tran_date = date.fromisoformat(tran_date)
            else:
                tran_date = date.today()
            is_expense = args["transaction_type"] == "expense"
            payload = FinanceTransactionCreate(
                tran_date=tran_date,
                description=args["description"],
                debit=args["amount"] if is_expense else 0.0,
                credit=0.0 if is_expense else args["amount"],
                balance=0.0,
                category=args["category"],
                source="AI",
            )
            txns = finance_repo.create_transactions(db, [payload])
            txn = txns[0]
            return {"success": True, "action": "added_transaction", "id": txn.id, "description": txn.description, "amount": args["amount"], "type": args["transaction_type"], "category": txn.category, "date": str(txn.tran_date)}

        elif name == "get_market_sentiment":
            try:
                resp = httpx.get(
                    "http://localhost:8000/sentiment/overall",
                    timeout=20.0,
                )
                if resp.status_code != 200:
                    return {"success": False, "error": f"Sentiment API returned HTTP {resp.status_code}"}

                data = resp.json() if isinstance(resp.json(), dict) else {}
                components = data.get("components", {}) if isinstance(data.get("components"), dict) else {}
                momentum = components.get("momentum", {}) if isinstance(components.get("momentum"), dict) else {}
                return {
                    "success": True,
                    "action": "market_sentiment",
                    "sentiment": data.get("sentiment"),
                    "sentiment_score": data.get("sentiment_score"),
                    "fear_greed_index": data.get("fear_greed_index"),
                    "fear_greed_interpretation": data.get("fear_greed_interpretation"),
                    "nifty_change_percent": momentum.get("nifty_change_percent"),
                    "momentum_state": momentum.get("state"),
                    "timestamp": data.get("timestamp"),
                    "raw": data,
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch market sentiment: {str(e)}"}

        elif name == "get_market_news_summary":
            limit = max(1, min(int(args.get("limit", 8)), 20))
            keyword = str(args.get("keyword") or "").strip().lower()
            try:
                feed_resp = httpx.get(
                    f"http://localhost:8000/news/feed?limit={limit}",
                    timeout=20.0,
                )
                if feed_resp.status_code != 200:
                    return {"success": False, "error": f"News API returned HTTP {feed_resp.status_code}"}

                feed_data = feed_resp.json() if isinstance(feed_resp.json(), dict) else {}
                items = feed_data.get("news", []) if isinstance(feed_data.get("news"), list) else []
                topic_match_count = None
                if keyword:
                    filtered_items = []
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        haystack = " ".join(
                            str(item.get(k, ""))
                            for k in ("title", "description", "category", "source")
                        ).lower()
                        if keyword in haystack:
                            filtered_items.append(item)
                    topic_match_count = len(filtered_items)
                    if filtered_items:
                        items = filtered_items

                headlines = []
                for item in items[:limit]:
                    if not isinstance(item, dict):
                        continue
                    headlines.append({
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "source": item.get("source"),
                        "sentiment": item.get("sentiment"),
                        "category": item.get("category"),
                        "published": item.get("published"),
                        "link": item.get("link"),
                    })

                trending_topics = []
                try:
                    trending_resp = httpx.get("http://localhost:8000/news/trending", timeout=10.0)
                    if trending_resp.status_code == 200 and isinstance(trending_resp.json(), dict):
                        trending_topics = (trending_resp.json().get("topics") or [])[:5]
                except Exception:
                    trending_topics = []

                sentiment_summary = feed_data.get("sentiment_summary") if isinstance(feed_data.get("sentiment_summary"), dict) else {}
                return {
                    "success": True,
                    "action": "market_news_summary",
                    "headline_count": len(headlines),
                    "headlines": headlines,
                    "query_topic": keyword or None,
                    "topic_match_count": topic_match_count,
                    "sentiment_summary": sentiment_summary,
                    "trending_topics": trending_topics,
                    "data_source": feed_data.get("data_source"),
                    "timestamp": feed_data.get("timestamp"),
                }
            except Exception as e:
                return {"success": False, "error": f"Failed to fetch market news: {str(e)}"}

        elif name == "get_recent_scanner_signals":
            days = max(1, min(int(args.get("days", 7)), 90))
            cutoff = datetime.utcnow() - timedelta(days=days)

            query = db.query(ScannerSignalHistory).filter(ScannerSignalHistory.first_seen_at >= cutoff)
            strategy_name = str(args.get("strategy_name") or "").strip()
            if strategy_name:
                query = query.filter(ScannerSignalHistory.strategy_name.ilike(f"%{strategy_name}%"))

            signals = query.order_by(ScannerSignalHistory.first_seen_at.desc()).limit(500).all()
            if not signals:
                scope = f" for strategy '{strategy_name}'" if strategy_name else ""
                return {
                    "success": True,
                    "action": "recent_scanner_signals",
                    "days": days,
                    "signal_count": 0,
                    "message": f"No scanner signals fired in the last {days} days{scope}.",
                    "signals": [],
                }

            symbol_counts = defaultdict(int)
            strategy_counts = defaultdict(int)
            recent_rows = []
            for sig in signals:
                sym = (sig.symbol or "").upper().strip()
                st_name = sig.strategy_name or "Unknown"
                if sym:
                    symbol_counts[sym] += 1
                strategy_counts[st_name] += 1
                if len(recent_rows) < 12:
                    recent_rows.append({
                        "symbol": sig.symbol,
                        "strategy": sig.strategy_name,
                        "direction": sig.direction,
                        "ltp": sig.ltp,
                        "change_percent": sig.change_percent,
                        "first_seen_at": sig.first_seen_at.isoformat() if sig.first_seen_at else None,
                    })

            top_symbols = sorted(symbol_counts.items(), key=lambda item: item[1], reverse=True)[:8]
            top_strategies = sorted(strategy_counts.items(), key=lambda item: item[1], reverse=True)[:8]
            return {
                "success": True,
                "action": "recent_scanner_signals",
                "days": days,
                "signal_count": len(signals),
                "top_symbols": [{"symbol": sym, "count": count} for sym, count in top_symbols],
                "top_strategies": [{"strategy": st, "count": count} for st, count in top_strategies],
                "signals": recent_rows,
            }

        elif name == "get_trade_cost_summary":
            from sqlalchemy import func

            days = max(1, min(int(args.get("days", 30)), 365))
            cutoff = datetime.utcnow() - timedelta(days=days)
            summary = (
                db.query(
                    func.sum(TradeCost.total_cost).label("total_costs"),
                    func.sum(TradeCost.brokerage).label("total_brokerage"),
                    func.sum(TradeCost.stt_ctt).label("total_stt"),
                    func.sum(TradeCost.gst).label("total_gst"),
                    func.sum(TradeCost.exchange_txn_charge).label("total_exchange"),
                    func.count(TradeCost.id).label("total_trades"),
                )
                .filter(TradeCost.trade_date >= cutoff)
                .first()
            )

            total_trades = int(summary.total_trades or 0)
            total_costs = round(float(summary.total_costs or 0.0), 2)
            total_brokerage = round(float(summary.total_brokerage or 0.0), 2)
            total_stt = round(float(summary.total_stt or 0.0), 2)
            total_gst = round(float(summary.total_gst or 0.0), 2)
            total_exchange = round(float(summary.total_exchange or 0.0), 2)

            return {
                "success": True,
                "action": "trade_cost_summary",
                "days": days,
                "total_trades": total_trades,
                "total_costs": total_costs,
                "total_brokerage": total_brokerage,
                "total_stt": total_stt,
                "total_gst": total_gst,
                "total_exchange": total_exchange,
                "avg_cost_per_trade": round((total_costs / total_trades), 2) if total_trades else 0.0,
                "message": "No trade cost records found in this period." if total_trades == 0 else None,
            }

        elif name == "get_strategy_metrics":
            strategy = (
                db.query(ConditionStrategy)
                .filter(ConditionStrategy.name.ilike(f"%{args['strategy_name']}%"))
                .first()
            )
            if not strategy:
                return {"success": False, "error": f"No strategy matching '{args['strategy_name']}'"}

            bt = None
            if strategy.last_backtest_id:
                bt = db.query(ConditionStrategyBacktest).filter(
                    ConditionStrategyBacktest.id == strategy.last_backtest_id
                ).first()

            summary = (bt.result_dict or {}).get("summary", {}) if bt else {}
            cutoff7 = datetime.utcnow() - timedelta(days=7)
            recent_signals_count = (
                db.query(ScannerSignalHistory)
                .filter(
                    ScannerSignalHistory.strategy_id == strategy.id,
                    ScannerSignalHistory.first_seen_at >= cutoff7,
                )
                .count()
            )

            total_trades = (
                summary.get("total_trades")
                if summary.get("total_trades") is not None
                else summary.get("trades")
            )
            win_rate = (
                summary.get("win_rate")
                if summary.get("win_rate") is not None
                else summary.get("win_rate_pct")
            )

            period_days = None
            if bt and bt.start_date and bt.end_date:
                try:
                    period_days = (date.fromisoformat(bt.end_date) - date.fromisoformat(bt.start_date)).days
                except Exception:
                    period_days = None

            trades_per_day = None
            try:
                if period_days and period_days > 0 and total_trades is not None:
                    trades_per_day = round(float(total_trades) / float(period_days), 4)
            except Exception:
                trades_per_day = None

            return {
                "success": True,
                "action": "strategy_metrics",
                "strategy": {
                    "id": strategy.id,
                    "name": strategy.name,
                    "direction": strategy.direction,
                    "timeframe": strategy.timeframe,
                    "universe": strategy.universe,
                    "is_active": bool(strategy.is_active),
                },
                "backtest": {
                    "available": bt is not None,
                    "backtest_id": bt.id if bt else None,
                    "start_date": bt.start_date if bt else None,
                    "end_date": bt.end_date if bt else None,
                    "period_days": period_days,
                    "total_trades": total_trades,
                    "trades_per_day": trades_per_day,
                    "total_return_pct": summary.get("total_return_pct"),
                    "annual_return_pct": summary.get("annual_return_pct"),
                    "sharpe_ratio": summary.get("sharpe_ratio"),
                    "win_rate": win_rate,
                    "profit_factor": summary.get("profit_factor"),
                    "max_drawdown_pct": summary.get("max_drawdown_pct"),
                },
                "signals": {
                    "last_7d_count": recent_signals_count,
                    "last_scan": strategy.last_scan.isoformat() if strategy.last_scan else None,
                    "last_signal_count": strategy.last_signal_count,
                },
                "source": {
                    "strategy_table": "condition_strategies",
                    "backtest_table": "condition_strategy_backtests",
                    "signals_table": "scanner_signal_history",
                },
            }

        elif name == "get_watchlist_gameplan":
            watchlist = None
            if args.get("watchlist_name"):
                watchlist = (
                    db.query(Watchlist)
                    .filter(
                        Watchlist.name.ilike(f"%{args['watchlist_name']}%"),
                        Watchlist.is_active == True,
                    )
                    .order_by(Watchlist.is_default.desc(), Watchlist.updated_at.desc())
                    .first()
                )
            if not watchlist:
                watchlist = (
                    db.query(Watchlist)
                    .filter(Watchlist.is_active == True)
                    .order_by(Watchlist.is_default.desc(), Watchlist.updated_at.desc())
                    .first()
                )
            if not watchlist:
                return {"success": False, "error": "No active watchlists found. Create a watchlist first."}

            raw_symbols = watchlist.symbols or []
            if isinstance(raw_symbols, str):
                try:
                    raw_symbols = json.loads(raw_symbols)
                except Exception:
                    raw_symbols = [s.strip() for s in raw_symbols.split(",") if s.strip()]

            top_n = max(1, min(int(args.get("top_n", 8)), 25))
            symbols = [str(s).upper().strip() for s in raw_symbols if str(s).strip()][:top_n]
            if not symbols:
                return {"success": False, "error": f"Watchlist '{watchlist.name}' has no symbols yet."}

            cutoff7 = datetime.utcnow() - timedelta(days=7)
            recent_signals = (
                db.query(ScannerSignalHistory)
                .filter(ScannerSignalHistory.first_seen_at >= cutoff7)
                .order_by(ScannerSignalHistory.first_seen_at.desc())
                .limit(300)
                .all()
            )

            by_symbol = defaultdict(lambda: {
                "signal_count": 0,
                "strategies": [],
                "direction": None,
                "ltp": None,
                "change_percent": None,
                "status": None,
                "latest_signal_at": None,
            })
            for sig in recent_signals:
                sym = (sig.symbol or "").upper().strip()
                if sym not in symbols:
                    continue
                row = by_symbol[sym]
                row["signal_count"] += 1
                if sig.strategy_name and sig.strategy_name not in row["strategies"]:
                    row["strategies"].append(sig.strategy_name)
                if row["latest_signal_at"] is None or (sig.first_seen_at and sig.first_seen_at > row["latest_signal_at"]):
                    row["latest_signal_at"] = sig.first_seen_at
                    row["direction"] = sig.direction
                    row["ltp"] = sig.ltp
                    row["change_percent"] = sig.change_percent
                    row["status"] = sig.status

            open_positions = (
                db.query(ExecutionIntent)
                .filter(ExecutionIntent.status == "EXECUTED", ExecutionIntent.closed_at.is_(None))
                .all()
            )
            open_symbols = {(p.underlying or "").upper().strip(): p for p in open_positions}

            ranked = []
            for sym in symbols:
                signal_info = by_symbol[sym]
                direction = (signal_info.get("direction") or "").upper()
                priority_score = signal_info["signal_count"] * 3
                if direction in {"LONG", "BUY", "BULLISH"}:
                    priority_score += 1
                if open_symbols.get(sym):
                    priority_score += 2
                if signal_info.get("change_percent") is not None and abs(signal_info["change_percent"] or 0) >= 1:
                    priority_score += 1

                ranked.append({
                    "symbol": sym,
                    "priority_score": priority_score,
                    "recent_signal_count": signal_info["signal_count"],
                    "latest_direction": signal_info.get("direction"),
                    "latest_strategy": ", ".join(signal_info.get("strategies", [])[:3]) or None,
                    "latest_ltp": signal_info.get("ltp"),
                    "change_percent": signal_info.get("change_percent"),
                    "latest_status": signal_info.get("status"),
                    "latest_signal_at": signal_info["latest_signal_at"].isoformat() if signal_info.get("latest_signal_at") else None,
                    "has_open_position": sym in open_symbols,
                })

            ranked.sort(
                key=lambda row: (row["priority_score"], row["recent_signal_count"], row["has_open_position"]),
                reverse=True,
            )

            market_sentiment = {}
            try:
                resp = httpx.get("http://localhost:8000/sentiment/overall", timeout=15.0)
                if resp.status_code == 200 and isinstance(resp.json(), dict):
                    raw = resp.json()
                    market_sentiment = {
                        "sentiment": raw.get("sentiment"),
                        "sentiment_score": raw.get("sentiment_score"),
                        "fear_greed_index": raw.get("fear_greed_index"),
                        "fear_greed_interpretation": raw.get("fear_greed_interpretation"),
                    }
            except Exception:
                market_sentiment = {}

            notes = []
            if market_sentiment.get("sentiment"):
                notes.append(
                    f"Overall market tone is {market_sentiment['sentiment']} ({market_sentiment.get('sentiment_score', 'N/A')})."
                )
            if not any(row["recent_signal_count"] for row in ranked):
                notes.append("No recent scanner signals found for this watchlist in the last 7 days.")
            if ranked and ranked[0]["recent_signal_count"]:
                notes.append(f"Highest-priority symbol right now is {ranked[0]['symbol']} based on recent signal activity.")

            return {
                "success": True,
                "action": "watchlist_gameplan",
                "watchlist": {
                    "id": watchlist.id,
                    "name": watchlist.name,
                    "symbol_count": len(symbols),
                    "symbols": symbols,
                },
                "market_sentiment": market_sentiment,
                "priorities": ranked,
                "notes": notes,
            }

        elif name == "create_watchlist":
            wl_name = str(args.get("name") or "").strip()
            if not wl_name:
                return {"success": False, "error": "Watchlist name is required."}

            existing = db.query(Watchlist).filter(Watchlist.name.ilike(wl_name)).first()
            if existing:
                return {"success": False, "error": f"Watchlist '{existing.name}' already exists."}

            raw_symbols = args.get("symbols") or []
            symbols = sorted({str(s).strip().upper() for s in raw_symbols if str(s).strip()})
            is_default = bool(args.get("is_default", False))
            if is_default:
                db.query(Watchlist).filter(Watchlist.is_active == True).update({"is_default": False})  # noqa: E712

            wl = Watchlist(
                name=wl_name,
                description=(args.get("description") or None),
                symbols=symbols,
                is_default=is_default,
                is_active=True,
            )
            db.add(wl)
            db.commit()
            db.refresh(wl)
            return {
                "success": True,
                "action": "created_watchlist",
                "id": wl.id,
                "name": wl.name,
                "symbol_count": len(symbols),
                "symbols": symbols,
                "message": f"Created watchlist '{wl.name}' with {len(symbols)} symbols.",
            }

        elif name in {"add_watchlist_symbol", "remove_watchlist_symbol"}:
            symbol = str(args.get("symbol") or "").strip().upper()
            if not symbol:
                return {"success": False, "error": "Symbol is required."}

            watchlist = None
            wl_name = (args.get("watchlist_name") or "").strip()
            if wl_name:
                watchlist = (
                    db.query(Watchlist)
                    .filter(
                        Watchlist.name.ilike(f"%{wl_name}%"),
                        Watchlist.is_active == True,
                    )
                    .order_by(Watchlist.is_default.desc(), Watchlist.updated_at.desc())
                    .first()
                )
            if not watchlist:
                watchlist = (
                    db.query(Watchlist)
                    .filter(Watchlist.is_active == True)
                    .order_by(Watchlist.is_default.desc(), Watchlist.updated_at.desc())
                    .first()
                )
            if not watchlist:
                return {"success": False, "error": "No active watchlist found. Create one first."}

            symbols = list(watchlist.symbols or [])
            if name == "add_watchlist_symbol":
                if symbol in symbols:
                    return {
                        "success": True,
                        "action": "watchlist_symbol_exists",
                        "watchlist": watchlist.name,
                        "symbol": symbol,
                        "message": f"{symbol} is already in {watchlist.name}.",
                    }
                symbols.append(symbol)
                watchlist.symbols = sorted(set(symbols))
                db.commit()
                db.refresh(watchlist)
                return {
                    "success": True,
                    "action": "watchlist_symbol_added",
                    "watchlist": watchlist.name,
                    "symbol": symbol,
                    "symbol_count": len(watchlist.symbols or []),
                    "message": f"Added {symbol} to {watchlist.name}.",
                }

            confirmed = bool(args.get("confirmed", False))
            if not confirmed:
                return {
                    "success": True,
                    "action": "watchlist_remove_confirmation_required",
                    "requires_confirmation": True,
                    "message": f"Please confirm removal of {symbol} from {watchlist.name}.",
                    "confirmation_preview": {
                        "watchlist": watchlist.name,
                        "symbol": symbol,
                        "operation": "remove_watchlist_symbol",
                    },
                }

            if symbol not in symbols:
                return {"success": False, "error": f"{symbol} is not present in {watchlist.name}."}
            symbols.remove(symbol)
            watchlist.symbols = symbols
            db.commit()
            db.refresh(watchlist)
            return {
                "success": True,
                "action": "watchlist_symbol_removed",
                "watchlist": watchlist.name,
                "symbol": symbol,
                "symbol_count": len(watchlist.symbols or []),
                "message": f"Removed {symbol} from {watchlist.name}.",
            }

        elif name == "review_trade_journal":
            days = max(7, min(int(args.get("days", 30)), 365))
            focus = (args.get("focus") or "general").strip().lower()
            cutoff = datetime.utcnow() - timedelta(days=days)
            trades = (
                db.query(ExecutionIntent)
                .filter(ExecutionIntent.closed_at.isnot(None), ExecutionIntent.closed_at >= cutoff)
                .order_by(ExecutionIntent.closed_at.desc())
                .limit(500)
                .all()
            )
            if not trades:
                return {"success": False, "error": f"No closed trades found in the last {days} days."}

            total_pnl = sum((t.pnl or 0) for t in trades)
            wins = [t for t in trades if (t.pnl or 0) > 0]
            losses = [t for t in trades if (t.pnl or 0) < 0]
            win_total = sum((t.pnl or 0) for t in wins)
            loss_total = sum((t.pnl or 0) for t in losses)
            avg_win = round(win_total / len(wins), 2) if wins else 0.0
            avg_loss = round(loss_total / len(losses), 2) if losses else 0.0
            expectancy = round(total_pnl / len(trades), 2) if trades else 0.0

            by_strategy = defaultdict(list)
            by_day = defaultdict(list)
            by_time = defaultdict(list)
            exit_reasons = defaultdict(int)
            for trade in trades:
                by_strategy[trade.strategy or "Unknown"].append(trade)
                dt = trade.closed_at or trade.created_at
                if dt:
                    by_day[dt.strftime("%A")].append(trade)
                by_time[_trade_time_bucket(trade.created_at or trade.closed_at)].append(trade)
                exit_reasons[(trade.exit_reason or "Unspecified")] += 1

            strategy_rows = []
            for strategy_name, items in by_strategy.items():
                stats = _summarize_trade_group(items)
                strategy_rows.append({"strategy": strategy_name, **stats})
            strategy_rows.sort(key=lambda row: (row["pnl"], row["win_rate"]), reverse=True)

            day_rows = []
            for day_name, items in by_day.items():
                stats = _summarize_trade_group(items)
                day_rows.append({"day": day_name, **stats})
            day_rows.sort(key=lambda row: row["pnl"], reverse=True)

            time_rows = []
            for bucket, items in by_time.items():
                stats = _summarize_trade_group(items)
                time_rows.append({"time_block": bucket, **stats})
            time_rows.sort(key=lambda row: row["pnl"], reverse=True)

            best_trade = max(trades, key=lambda t: t.pnl or float("-inf"))
            worst_trade = min(trades, key=lambda t: t.pnl or float("inf"))

            coaching_flags = []
            if wins and losses and abs(avg_loss) > avg_win:
                coaching_flags.append("Average losses are larger than average winners.")
            weak_block = next((row for row in sorted(time_rows, key=lambda r: r["pnl"]) if row["trades"] >= 2 and row["pnl"] < 0), None)
            if weak_block:
                coaching_flags.append(
                    f"Weakest time block is {weak_block['time_block']} with {weak_block['trades']} trades and P&L of {_fmt(weak_block['pnl'])}."
                )
            manual_loss_count = sum(1 for t in losses if "manual" in (t.exit_reason or "").lower())
            if manual_loss_count >= 2:
                coaching_flags.append("Multiple losing trades were closed manually; review exit discipline.")
            if not coaching_flags:
                coaching_flags.append("No major red flags detected from journal stats in this lookback.")

            return {
                "success": True,
                "action": "journal_review",
                "focus": focus,
                "period_days": days,
                "summary": {
                    "total_trades": len(trades),
                    "winners": len(wins),
                    "losers": len(losses),
                    "win_rate": round(len(wins) / len(trades) * 100, 1),
                    "total_pnl": round(total_pnl, 2),
                    "avg_win": avg_win,
                    "avg_loss": avg_loss,
                    "expectancy": expectancy,
                    "profit_factor": _calc_profit_factor(win_total, loss_total),
                },
                "best_trade": {
                    "symbol": best_trade.underlying,
                    "strategy": best_trade.strategy,
                    "pnl": best_trade.pnl,
                    "closed_at": best_trade.closed_at.isoformat() if best_trade.closed_at else None,
                },
                "worst_trade": {
                    "symbol": worst_trade.underlying,
                    "strategy": worst_trade.strategy,
                    "pnl": worst_trade.pnl,
                    "closed_at": worst_trade.closed_at.isoformat() if worst_trade.closed_at else None,
                },
                "by_strategy": strategy_rows[:8],
                "by_day_of_week": day_rows,
                "by_time_block": time_rows,
                "top_exit_reasons": sorted(exit_reasons.items(), key=lambda item: item[1], reverse=True)[:6],
                "coaching_flags": coaching_flags,
            }

        elif name == "trade_autopsy":
            lookback_days = max(7, min(int(args.get("lookback_days", 90)), 365))
            cutoff = datetime.utcnow() - timedelta(days=lookback_days)
            query = db.query(ExecutionIntent).filter(
                ExecutionIntent.closed_at.isnot(None),
                ExecutionIntent.closed_at >= cutoff,
            )
            if args.get("intent_id"):
                query = query.filter(ExecutionIntent.intent_id == args["intent_id"])
            elif args.get("underlying"):
                query = query.filter(ExecutionIntent.underlying.ilike(f"%{args['underlying']}%"))

            trade = query.order_by(ExecutionIntent.closed_at.desc()).first()
            if not trade:
                return {"success": False, "error": "No matching closed trade found for autopsy."}

            hold_minutes = None
            if trade.created_at and trade.closed_at:
                hold_minutes = round((trade.closed_at - trade.created_at).total_seconds() / 60, 1)

            exit_reason = trade.exit_reason or "Unspecified"
            peak_profit_capture_pct = None
            if trade.max_unrealized_pnl and trade.max_unrealized_pnl > 0 and trade.pnl is not None:
                peak_profit_capture_pct = round((trade.pnl / trade.max_unrealized_pnl) * 100, 1)

            strengths = []
            coaching_flags = []
            if trade.tp is not None:
                strengths.append("Take-profit was defined on this trade.")
            if trade.sl is not None:
                strengths.append("Stop-loss was defined on this trade.")
            if trade.trailing_sl_pct:
                strengths.append(f"Trailing stop was enabled at {trade.trailing_sl_pct}%.")

            if "manual" in exit_reason.lower():
                coaching_flags.append("Manual exit recorded — verify it matched your written exit plan.")
            if peak_profit_capture_pct is not None and peak_profit_capture_pct < 30:
                coaching_flags.append(
                    f"Trade kept only {peak_profit_capture_pct}% of its peak open profit; review exit timing and trailing rules."
                )
            if (trade.pnl or 0) < 0 and trade.sl is None:
                coaching_flags.append("Losing trade had no saved stop-loss value; add one for cleaner risk control.")
            if (trade.pnl or 0) < 0 and trade.max_unrealized_pnl and trade.max_unrealized_pnl > 0:
                coaching_flags.append("The trade was green before closing red; focus on protecting open gains sooner.")
            if not coaching_flags:
                coaching_flags.append("System data looks orderly; review chart context and execution timing for nuance.")

            return {
                "success": True,
                "action": "trade_autopsy",
                "trade": {
                    "intent_id": trade.intent_id,
                    "symbol": trade.underlying,
                    "strategy": trade.strategy,
                    "opened_at": trade.created_at.isoformat() if trade.created_at else None,
                    "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
                    "holding_minutes": hold_minutes,
                    "pnl": trade.pnl,
                    "entry_credit": trade.entry_credit,
                    "avg_price": trade.avg_price,
                    "max_unrealized_pnl": trade.max_unrealized_pnl,
                    "peak_profit_capture_pct": peak_profit_capture_pct,
                    "exit_reason": exit_reason,
                    "tp": trade.tp,
                    "sl": trade.sl,
                    "trailing_sl_pct": trade.trailing_sl_pct,
                },
                "strengths": strengths,
                "coaching_flags": coaching_flags,
            }

        elif name == "run_scanner":
            strategy = (
                db.query(ConditionStrategy)
                .filter(ConditionStrategy.name.ilike(f"%{args['strategy_name']}%"))
                .first()
            )
            if not strategy:
                return {"success": False, "error": f"No scanner strategy matching '{args['strategy_name']}'. Check available strategies."}
            try:
                resp = httpx.post(
                    f"http://localhost:8000/condition-scanner/scan/{strategy.id}",
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    signals = data.get("signals", [])
                    return {"success": True, "action": "ran_scanner", "strategy": strategy.name, "signals_found": len(signals), "signals": [s.get("symbol") for s in signals[:10]]}
                else:
                    return {"success": False, "error": f"Scanner returned HTTP {resp.status_code}"}
            except Exception as e:
                return {"success": False, "error": f"Scanner call failed: {str(e)}"}

        elif name == "close_position":
            underlying = str(args.get("underlying") or "").strip().upper()
            reference = str(args.get("reference") or "").strip().lower()

            open_query = db.query(ExecutionIntent).filter(
                ExecutionIntent.status == "EXECUTED",
                ExecutionIntent.closed_at.is_(None),
            )

            if underlying:
                intent = (
                    open_query
                    .filter(ExecutionIntent.underlying.ilike(f"%{underlying}%"))
                    .order_by(ExecutionIntent.created_at.desc())
                    .first()
                )
                if not intent:
                    return {"success": False, "error": f"No open position found for '{underlying}'"}
            else:
                open_positions = open_query.order_by(ExecutionIntent.created_at.desc()).all()
                if not open_positions:
                    return {"success": False, "error": "No open positions found right now."}

                if reference in {"current", "latest", "open", "active", "position", "trade", ""}:
                    if reference in {"current", "latest"} or len(open_positions) == 1:
                        intent = open_positions[0]
                    else:
                        symbols = ", ".join(dict.fromkeys(pos.underlying for pos in open_positions[:5]))
                        return {
                            "success": False,
                            "error": f"You have multiple open positions ({symbols}). Please specify which symbol to close.",
                        }
                else:
                    intent = open_positions[0]

            try:
                resp = httpx.post(
                    f"http://localhost:8000/exit/manual/{intent.intent_id}",
                    timeout=30.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {"success": True, "action": "closed_position", "underlying": intent.underlying, "strategy": intent.strategy, "pnl": data.get("final_pnl")}
                else:
                    return {"success": False, "error": f"Exit returned HTTP {resp.status_code}: {resp.text[:200]}"}
            except Exception as e:
                return {"success": False, "error": f"Exit call failed: {str(e)}"}

        elif name == "place_trade":
            symbol = _normalize_trade_symbol(args["symbol"])
            action = args["action"].upper()
            quantity = int(args["quantity"])
            product = args.get("product", "CNC").upper()
            order_type = args.get("order_type", "MARKET").upper()
            exchange = args.get("exchange", "NSE").upper()
            price = args.get("price")
            dry_run = _as_bool(args.get("dry_run", False))
            confirmed = _as_bool(args.get("confirmed", False))

            if not symbol:
                return {"success": False, "error": "Invalid or empty trading symbol."}

            if order_type == "LIMIT" and price is None:
                return {"success": False, "error": "price is required for LIMIT orders"}
            if quantity <= 0:
                return {"success": False, "error": "quantity must be greater than 0"}
            if quantity > AI_MAX_ORDER_QTY:
                return {
                    "success": False,
                    "error": (
                        f"Order blocked by risk guardrail: quantity {quantity} exceeds "
                        f"AI_MAX_ORDER_QTY={AI_MAX_ORDER_QTY}"
                    ),
                }

            open_positions_count = (
                db.query(ExecutionIntent)
                .filter(
                    ExecutionIntent.status == "EXECUTED",
                    ExecutionIntent.closed_at.is_(None),
                )
                .count()
            )
            if open_positions_count >= AI_MAX_OPEN_POSITIONS:
                return {
                    "success": False,
                    "error": (
                        "Order blocked by risk guardrail: "
                        f"open positions {open_positions_count} reached limit "
                        f"AI_MAX_OPEN_POSITIONS={AI_MAX_OPEN_POSITIONS}"
                    ),
                }

            if AI_MAX_DAILY_LOSS_INR > 0:
                day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                closed_today = (
                    db.query(ExecutionIntent)
                    .filter(
                        ExecutionIntent.closed_at.isnot(None),
                        ExecutionIntent.closed_at >= day_start,
                    )
                    .all()
                )
                realized_pnl_today = sum(t.pnl or 0 for t in closed_today)
                if realized_pnl_today <= -abs(AI_MAX_DAILY_LOSS_INR):
                    return {
                        "success": False,
                        "error": (
                            "Order blocked by risk guardrail: "
                            f"today realized P&L is ₹{realized_pnl_today:,.2f}, below daily loss limit "
                            f"₹{-abs(AI_MAX_DAILY_LOSS_INR):,.2f}"
                        ),
                    }

            if dry_run:
                return {
                    "success": True,
                    "action": "simulated_trade",
                    "dry_run": True,
                    "would_place": {
                        "symbol": symbol,
                        "trade_action": action,
                        "quantity": quantity,
                        "product": product,
                        "order_type": order_type,
                        "exchange": exchange,
                        "price": price,
                    },
                    "message": "Dry run only. No order was placed.",
                }

            if AI_REQUIRE_TRADE_CONFIRMATION and not confirmed:
                return {
                    "success": True,
                    "action": "trade_confirmation_required",
                    "requires_confirmation": True,
                    "message": "Please confirm this live order. Send: confirm place trade.",
                    "order_preview": {
                        "symbol": symbol,
                        "trade_action": action,
                        "quantity": quantity,
                        "product": product,
                        "order_type": order_type,
                        "exchange": exchange,
                        "price": price,
                    },
                }

            try:
                from app.core.broker.zerodha.client import get_kite_client
                kite = get_kite_client()
            except Exception as e:
                return {"success": False, "error": f"Zerodha not connected: {str(e)}"}

            try:
                # KiteConnect does not accept a market_protection kwarg.
                # Zerodha requires MARKET orders on NSE/BSE to have a price
                # tolerance buffer.  We implement this by converting MARKET
                # orders to LIMIT orders priced at LTP ± AI_MARKET_PROTECTION_PCT%.
                # This is identical to what Zerodha's own web UI does internally.
                effective_order_type = order_type
                effective_price = price

                if order_type == "MARKET" and AI_MARKET_PROTECTION_PCT > 0:
                    try:
                        from app.services.zerodha import KiteConnectService
                        _svc = KiteConnectService()
                        ltp = _svc.get_ltp(symbol)
                        if ltp and ltp > 0:
                            pct = AI_MARKET_PROTECTION_PCT / 100.0
                            if action == "BUY":
                                effective_price = round(ltp * (1 + pct), 2)
                            else:
                                effective_price = round(ltp * (1 - pct), 2)
                            effective_order_type = "LIMIT"
                            logger.info(
                                "Market protection: converting MARKET→LIMIT for %s %s "
                                "ltp=%.2f protection=%s%% effective_price=%.2f",
                                action, symbol, ltp, AI_MARKET_PROTECTION_PCT, effective_price,
                            )
                        else:
                            logger.warning(
                                "Could not fetch LTP for %s; falling back to plain MARKET order", symbol
                            )
                    except Exception as mp_err:
                        logger.warning(
                            "Market protection LTP fetch failed (%s); falling back to plain MARKET order", mp_err
                        )

                order_payload = {
                    "variety": kite.VARIETY_REGULAR,
                    "exchange": exchange,
                    "tradingsymbol": symbol,
                    "transaction_type": (
                        kite.TRANSACTION_TYPE_BUY if action == "BUY"
                        else kite.TRANSACTION_TYPE_SELL
                    ),
                    "quantity": quantity,
                    "order_type": (
                        kite.ORDER_TYPE_LIMIT if effective_order_type == "LIMIT"
                        else kite.ORDER_TYPE_MARKET
                    ),
                    "product": {
                        "CNC": kite.PRODUCT_CNC,
                        "MIS": kite.PRODUCT_MIS,
                        "NRML": kite.PRODUCT_NRML,
                    }.get(product, kite.PRODUCT_CNC),
                    "validity": kite.VALIDITY_DAY,
                    "price": effective_price if effective_order_type == "LIMIT" else None,
                }

                order_id = kite.place_order(**order_payload)
                logger.info(
                    "AI placed trade: %s %s x%s %s effective_type=%s price=%s order_id=%s",
                    action, symbol, quantity, product,
                    effective_order_type, effective_price, order_id,
                )

                # ── Write to trade journal ─────────────────────────────────
                try:
                    import uuid as _uuid
                    from app.core.utils.time import now_ist as _now_ist
                    _intent_id = f"AI-{_uuid.uuid4().hex[:12].upper()}"
                    _ticket = {
                        "legs": [
                            {
                                "symbol": symbol,
                                "action": action,
                                "quantity": quantity,
                                "product": product,
                                "order_type": effective_order_type,
                                "exchange": exchange,
                                "price": effective_price,
                                "order_id": str(order_id),
                            }
                        ]
                    }
                    _intent = ExecutionIntent(
                        run_id=0,
                        intent_id=_intent_id,
                        strategy="AI_TRADE",
                        underlying=symbol,
                        ticket=_ticket,
                        status="EXECUTED",
                        executed=True,
                        expires_at=_now_ist(),
                        avg_price=effective_price,
                        entry_credit=effective_price if action == "SELL" else None,
                        execution_result={
                            "order_id": str(order_id),
                            "action": action,
                            "quantity": quantity,
                            "product": product,
                            "exchange": exchange,
                            "order_type": effective_order_type,
                            "price": effective_price,
                            "placed_via": "AI_CHAT",
                        },
                    )
                    db.add(_intent)
                    db.commit()
                    logger.info("AI trade journal entry created: %s", _intent_id)
                    # Create StockHolding for holdings tracking
                    try:
                        from app.api.routes.holdings import create_stock_holding, has_open_holding
                        if not has_open_holding(db, symbol):
                            create_stock_holding(
                                db,
                                symbol=symbol,
                                direction=action,
                                quantity=quantity,
                                entry_price=float(effective_price or 0),
                                strategy_name="AI_TRADE",
                                source="AI_CHAT",
                                execution_mode="LIVE",
                                order_id=str(order_id),
                            )
                            db.commit()
                    except Exception as _h_err:
                        logger.warning("Could not create AI StockHolding: %s", _h_err)
                except Exception as _journal_err:
                    logger.warning("Could not write AI trade to journal: %s", _journal_err)
                # ─────────────────────────────────────────────────────────────

                return {
                    "success": True,
                    "action": "placed_trade",
                    "order_id": str(order_id),
                    "symbol": symbol,
                    "trade_action": action,
                    "quantity": quantity,
                    "product": product,
                    "order_type": order_type,
                    "effective_order_type": effective_order_type,
                    "exchange": exchange,
                    "price": effective_price,
                }
            except Exception as e:
                logger.error("AI place_trade error: %s", e)
                return {"success": False, "error": str(e)}

        elif name == "get_stock_quote":
            raw_symbol = _normalize_trade_symbol(str(args.get("symbol") or ""))
            if not raw_symbol:
                return {"success": False, "error": "symbol is required"}
            exchange = str(args.get("exchange") or "NSE").upper()
            try:
                from app.services.zerodha import KiteConnectService
                svc = KiteConnectService()
                # Try full quote first (OHLC + volume)
                data = svc.get_full_quote(raw_symbol)
                if data is None:
                    return {"success": False, "error": f"Could not fetch quote for {raw_symbol}. Check Zerodha connection and symbol."}
                return {
                    "success": True,
                    "symbol": raw_symbol,
                    "exchange": exchange,
                    "ltp": data.get("last_price"),
                    "open": (data.get("ohlc") or {}).get("open"),
                    "high": (data.get("ohlc") or {}).get("high"),
                    "low": (data.get("ohlc") or {}).get("low"),
                    "close": (data.get("ohlc") or {}).get("close"),
                    "volume": data.get("volume"),
                    "buy_quantity": data.get("buy_quantity"),
                    "sell_quantity": data.get("sell_quantity"),
                    "lower_circuit": data.get("lower_circuit_limit"),
                    "upper_circuit": data.get("upper_circuit_limit"),
                    "oi": data.get("oi"),
                }
            except Exception as e:
                return {"success": False, "error": f"Quote fetch failed: {e}"}

        elif name == "get_portfolio_summary":
            include_closed_today = _as_bool(args.get("include_closed_today", False))
            open_pos = (
                db.query(ExecutionIntent)
                .filter(ExecutionIntent.status == "EXECUTED", ExecutionIntent.closed_at.is_(None))
                .order_by(ExecutionIntent.created_at.desc())
                .all()
            )
            total_unrealized = sum(t.unrealized_pnl or 0 for t in open_pos)
            positions = []
            for t in open_pos:
                positions.append({
                    "symbol": t.underlying,
                    "strategy": t.strategy,
                    "entry_price": t.avg_price,
                    "unrealized_pnl": t.unrealized_pnl,
                    "sl": t.sl,
                    "tp": t.tp,
                    "trailing_sl_pct": t.trailing_sl_pct,
                    "opened_at": t.created_at.isoformat() if t.created_at else None,
                })

            result = {
                "success": True,
                "open_count": len(open_pos),
                "total_unrealized_pnl": round(total_unrealized, 2),
                "positions": positions,
            }

            if include_closed_today:
                today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                closed_today = (
                    db.query(ExecutionIntent)
                    .filter(
                        ExecutionIntent.closed_at.isnot(None),
                        ExecutionIntent.closed_at >= today_start,
                    )
                    .all()
                )
                realized_pnl_today = sum(t.pnl or 0 for t in closed_today)
                result["closed_today"] = len(closed_today)
                result["realized_pnl_today"] = round(realized_pnl_today, 2)
                result["total_pnl_today"] = round(total_unrealized + realized_pnl_today, 2)

            return result

        elif name == "set_position_sl_tp":
            underlying = _normalize_trade_symbol(str(args.get("underlying") or ""))
            if not underlying:
                return {"success": False, "error": "underlying symbol is required"}
            intent = (
                db.query(ExecutionIntent)
                .filter(
                    ExecutionIntent.status == "EXECUTED",
                    ExecutionIntent.closed_at.is_(None),
                    ExecutionIntent.underlying.ilike(f"%{underlying}%"),
                )
                .order_by(ExecutionIntent.created_at.desc())
                .first()
            )
            if not intent:
                return {"success": False, "error": f"No open position found for '{underlying}'"}

            updated = []
            if "sl" in args and args["sl"] is not None:
                intent.sl = float(args["sl"])
                updated.append(f"SL=₹{args['sl']}")
            if "tp" in args and args["tp"] is not None:
                intent.tp = float(args["tp"])
                updated.append(f"TP=₹{args['tp']}")
            if "trailing_sl_pct" in args and args["trailing_sl_pct"] is not None:
                intent.trailing_sl_pct = float(args["trailing_sl_pct"])
                updated.append(f"Trailing SL={args['trailing_sl_pct']}%")

            if not updated:
                return {"success": False, "error": "Provide at least one of: sl, tp, trailing_sl_pct"}

            db.commit()
            return {
                "success": True,
                "action": "updated_sl_tp",
                "symbol": intent.underlying,
                "intent_id": intent.intent_id,
                "updated": updated,
                "sl": intent.sl,
                "tp": intent.tp,
                "trailing_sl_pct": intent.trailing_sl_pct,
            }

        elif name == "get_orders_today":
            try:
                from app.core.broker.zerodha.client import get_kite_client
                kite = get_kite_client()
            except Exception as e:
                return {"success": False, "error": f"Zerodha not connected: {e}"}
            try:
                orders = kite.orders() or []
                today_str = datetime.utcnow().strftime("%Y-%m-%d")
                today_orders = []
                for o in orders:
                    order_ts = str(o.get("order_timestamp") or o.get("exchange_timestamp") or "")
                    if today_str in order_ts or not order_ts:
                        today_orders.append({
                            "order_id": o.get("order_id"),
                            "symbol": o.get("tradingsymbol"),
                            "exchange": o.get("exchange"),
                            "action": o.get("transaction_type"),
                            "quantity": o.get("quantity"),
                            "filled_quantity": o.get("filled_quantity"),
                            "price": o.get("price") or o.get("average_price"),
                            "order_type": o.get("order_type"),
                            "product": o.get("product"),
                            "status": o.get("status"),
                            "timestamp": order_ts,
                        })
                return {
                    "success": True,
                    "total_orders": len(today_orders),
                    "orders": today_orders,
                }
            except Exception as e:
                return {"success": False, "error": f"Could not fetch orders: {e}"}

        else:
            return {"success": False, "error": f"Unknown tool: {name}"}

    except Exception as e:
        logger.exception("Tool execution error for %s: %s", name, e)
        return {"success": False, "error": str(e)}

# ── Agentic LLM call with function-calling loop ────────────────────────────

def _call_llm(
    message: str,
    history: list,
    db: Session,
    voice_mode: bool = False,
    assistant_style: str | None = None,
) -> tuple[str, list]:
    """
    Run the LLM with agentic tool support.
    Returns (answer_text, actions_list).
    actions_list contains dicts describing each action taken.
    """
    if not LLM_API_KEY:
        return (
            "⚙️ AI not configured.\n\n"
            "Set **GROQ_API_KEY** in your .env file (free at console.groq.com) "
            "and restart the backend.\n\n"
            "Model used: " + ", ".join(get_model_candidates()),
            [],
        )

    context = _build_context(db)
    system = SYSTEM_PROMPT.format(context=context)

    requested_style = (assistant_style or "").strip().lower()
    if voice_mode or requested_style == "jarvis":
        system += """

JARVIS VOICE MODE:
- Sound like a calm, elite trading copilot.
- Reply in 1 to 3 crisp spoken sentences unless the user asks for detail.
- Put the answer or action first, then one short risk note if needed.
- For live orders, summarize the order preview and wait for explicit confirmation before execution.
- Avoid filler, markdown, bullet points, or verbose explanations in voice mode.
"""

    messages = [{"role": "system", "content": system}]
    for h in history[-20:]:
        # Skip malformed history entries (e.g. empty assistant messages from
        # previous failed turns) — Groq 400s if content='' with no tool_calls.
        if not h.get("content") and h.get("role") == "assistant":
            continue
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    actions_taken: list[dict] = []
    max_tool_rounds = 8  # prevent infinite loops
    tool_choice = _preferred_tool_choice(message, history)

    for _round in range(max_tool_rounds):
        response_data, model_used, error = request_chat_completion(
            messages,
            tools=TOOLS,
            tool_choice=tool_choice,
            timeout=30.0,
        )
        if not response_data:
            return f"⚠️ LLM error: {error or 'No response from configured models'}", actions_taken

        choice = response_data["choices"][0]
        assistant_message = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        safe_message: dict = {"role": "assistant"}
        if assistant_message.get("tool_calls"):
            safe_message["tool_calls"] = assistant_message["tool_calls"]
            raw_content = assistant_message.get("content")
            if raw_content:
                safe_message["content"] = raw_content
        else:
            content_str = assistant_message.get("content") or ""
            safe_message["content"] = content_str

        has_tool_calls = bool(assistant_message.get("tool_calls"))

        if has_tool_calls:
            messages.append(safe_message)

            for tc in assistant_message["tool_calls"]:
                tool_name = tc["function"]["name"]
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info("AI tool call via %s: %s(%s)", model_used or LLM_MODEL, tool_name, tool_args)
                result = _execute_tool(tool_name, tool_args, db)
                actions_taken.append({"tool": tool_name, "args": tool_args, "result": result, "model": model_used})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })
                tool_choice = "auto"

            continue  # next round — let LLM summarise tool results

        # No tool calls — this is (or should be) the final text answer.
        final_text = assistant_message.get("content") or ""

        if final_text:
            # Only append meaningful assistant messages to history
            messages.append(safe_message)
            if voice_mode or requested_style == "jarvis":
                final_text = _normalize_voice_answer(final_text)
            return final_text, actions_taken

        # Empty content + no tool calls: provider ignored forced tool_choice.
        # Retry with tool_choice="auto" so the LLM picks freely.
        # Do NOT append the empty message — it would become "last from assistant".
        if tool_choice != "auto":
            tool_choice = "auto"
            continue

        # Already auto and still empty — give up gracefully
        return "Sorry, I could not get a response. Please try again.", actions_taken

    # Exhausted tool rounds — ask LLM one final time without tool access to summarise
    messages.append({
        "role": "user",
        "content": (
            "Please summarise what you found and what actions were completed based on the tool results above. "
            "Keep it concise and do not call any more tools."
        ),
    })
    response_data, _, error = request_chat_completion(messages, timeout=30.0)
    if response_data:
        final_text = response_data["choices"][0]["message"].get("content") or ""
        if voice_mode or requested_style == "jarvis":
            final_text = _normalize_voice_answer(final_text)
        return final_text, actions_taken
    if error:
        logger.warning("AI chat final summary failed across configured models: %s", error)
    return "I completed the requested actions. Please review the results above.", actions_taken


@router.post("/query")
def chat_query(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        voice_mode = bool(req.voice_mode) or (req.assistant_style or "").strip().lower() == "jarvis"

        direct_action = _extract_direct_ai_action(req.message)
        if direct_action:
            tool_name, tool_args = direct_action
            result = _execute_tool(tool_name, tool_args, db)
            actions = [{"tool": tool_name, "args": tool_args, "result": result}]
            answer = _summarize_direct_action(tool_name, result, voice_mode=voice_mode)
            return {"ok": True, "answer": answer, "actions": actions}

        answer, actions = _call_llm(
            req.message,
            req.history,
            db,
            voice_mode=voice_mode,
            assistant_style=req.assistant_style,
        )
        return {"ok": True, "answer": answer, "actions": actions}
    except Exception as e:
        return {"ok": False, "answer": f"Error: {str(e)}", "actions": []}
