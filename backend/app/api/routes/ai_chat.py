from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta, date
from collections import defaultdict
import json
import logging
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
from app.db import finance_repo
from app.api.schemas.finance import (
    BudgetCreate, SavingsGoalCreate, BillReminderCreate, FinanceTransactionCreate
)

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

You have COMPLETE access to the user's real data AND the ability to take real actions via built-in tools.

DATA ACCESS:
- Trading positions (open & closed), P&L, strategies
- Condition Scanner strategies and backtest results
- Scanner signals generated in last 7 days
- Trade costs and brokerage charges
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

ANALYSIS YOU CAN DO:
✅ Trade analysis — P&L, win rate, profit factor, best/worst trades
✅ Position advice — hold/exit decisions based on actual unrealized P&L
✅ Strategy analysis — which scanner strategies are working, backtest results
✅ Scanner signals — what signals fired recently, which stocks to watch
✅ Cost analysis — how much brokerage/STT is eating into profits
✅ Finance — spending patterns, budget status, savings progress, bill reminders
✅ Market education — options greeks, indicators, strategies explained
✅ Risk management — position sizing, drawdown, diversification advice
✅ Indian market specifics — NIFTY, BANKNIFTY, F&O, NSE/BSE rules

CRITICAL RULES:
- NEVER say you cannot perform actions — you have tools for all the above
- When the user asks to DO something, call the appropriate tool immediately
- Be concise and direct — no fluff
- Use ₹ for Indian rupees
- Reference specific numbers from the data when answering
- After performing an action, confirm what was done with the key details

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
            "description": "Place a real stock buy or sell order on Zerodha. Use when the user asks to buy or sell shares/stocks. Supports CNC (delivery), MIS (intraday), NRML (F&O overnight).",
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
                },
                "required": ["symbol", "action", "quantity"],
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
            intent = (
                db.query(ExecutionIntent)
                .filter(
                    ExecutionIntent.underlying.ilike(f"%{args['underlying']}%"),
                    ExecutionIntent.status == "EXECUTED",
                    ExecutionIntent.closed_at.is_(None),
                )
                .order_by(ExecutionIntent.created_at.desc())
                .first()
            )
            if not intent:
                return {"success": False, "error": f"No open position found for '{args['underlying']}'"}
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
            symbol = args["symbol"].upper().strip()
            action = args["action"].upper()
            quantity = int(args["quantity"])
            product = args.get("product", "CNC").upper()
            order_type = args.get("order_type", "MARKET").upper()
            exchange = args.get("exchange", "NSE").upper()
            price = args.get("price")
            dry_run = bool(args.get("dry_run", False))

            if order_type == "LIMIT" and price is None:
                return {"success": False, "error": "price is required for LIMIT orders"}
            if quantity <= 0:
                return {"success": False, "error": "quantity must be greater than 0"}

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

            try:
                from app.core.broker.zerodha.client import get_kite_client
                kite = get_kite_client()
            except Exception as e:
                return {"success": False, "error": f"Zerodha not connected: {str(e)}"}

            try:
                order_id = kite.place_order(
                    variety=kite.VARIETY_REGULAR,
                    exchange=exchange,
                    tradingsymbol=symbol,
                    transaction_type=(
                        kite.TRANSACTION_TYPE_BUY if action == "BUY"
                        else kite.TRANSACTION_TYPE_SELL
                    ),
                    quantity=quantity,
                    order_type=(
                        kite.ORDER_TYPE_MARKET if order_type == "MARKET"
                        else kite.ORDER_TYPE_LIMIT
                    ),
                    product={
                        "CNC": kite.PRODUCT_CNC,
                        "MIS": kite.PRODUCT_MIS,
                        "NRML": kite.PRODUCT_NRML,
                    }.get(product, kite.PRODUCT_CNC),
                    validity=kite.VALIDITY_DAY,
                    price=price if order_type == "LIMIT" else None,
                )
                logger.info(
                    "AI placed trade: %s %s x%s %s %s order_id=%s",
                    action, symbol, quantity, product, order_type, order_id,
                )
                return {
                    "success": True,
                    "action": "placed_trade",
                    "order_id": str(order_id),
                    "symbol": symbol,
                    "trade_action": action,
                    "quantity": quantity,
                    "product": product,
                    "order_type": order_type,
                    "exchange": exchange,
                    "price": price,
                }
            except Exception as e:
                logger.error("AI place_trade error: %s", e)
                return {"success": False, "error": str(e)}

        else:
            return {"success": False, "error": f"Unknown tool: {name}"}

    except Exception as e:
        logger.exception("Tool execution error for %s: %s", name, e)
        return {"success": False, "error": str(e)}

# ── Agentic LLM call with function-calling loop ────────────────────────────

def _call_llm(message: str, history: list, db: Session) -> tuple[str, list]:
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
            "Model used: " + LLM_MODEL,
            [],
        )

    context = _build_context(db)
    system = SYSTEM_PROMPT.format(context=context)

    messages = [{"role": "system", "content": system}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    actions_taken: list[dict] = []
    max_tool_rounds = 5  # prevent infinite loops

    for _round in range(max_tool_rounds):
        try:
            resp = httpx.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
                json={"model": LLM_MODEL, "messages": messages, "tools": TOOLS, "tool_choice": "auto"},
                timeout=30.0,
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            return "⚠️ LLM request timed out. Check your connection.", actions_taken
        except httpx.HTTPStatusError as e:
            return f"⚠️ LLM API error {e.response.status_code}: {e.response.text[:300]}", actions_taken
        except Exception as e:
            return f"⚠️ LLM error: {e}", actions_taken

        response_data = resp.json()
        choice = response_data["choices"][0]
        assistant_message = choice["message"]
        finish_reason = choice.get("finish_reason", "stop")

        # Add assistant's response (with or without tool calls) to message history
        messages.append(assistant_message)

        if finish_reason != "tool_calls" or not assistant_message.get("tool_calls"):
            # No tool call — return the final text answer
            return assistant_message.get("content") or "", actions_taken

        # Execute each tool call
        for tc in assistant_message["tool_calls"]:
            tool_name = tc["function"]["name"]
            try:
                tool_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                tool_args = {}

            logger.info("AI tool call: %s(%s)", tool_name, tool_args)
            result = _execute_tool(tool_name, tool_args, db)
            actions_taken.append({"tool": tool_name, "args": tool_args, "result": result})

            # Feed tool result back to LLM
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result),
            })

    # Exhausted rounds — ask LLM to summarize with what we have
    return "I completed the requested actions. Please review the action details above.", actions_taken


@router.post("/query")
def chat_query(req: ChatRequest, db: Session = Depends(get_db)):
    try:
        answer, actions = _call_llm(req.message, req.history, db)
        return {"ok": True, "answer": answer, "actions": actions}
    except Exception as e:
        return {"ok": False, "answer": f"Error: {str(e)}", "actions": []}
