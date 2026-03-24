"""
Strategy Decay Tracker
Compares live win rate vs backtest win rate per strategy.
Flags strategies that have degraded beyond threshold.
"""
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session

from app.db.models_intent import ExecutionIntent
from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest

logger = logging.getLogger(__name__)

# A strategy is "decayed" if live win rate drops more than this below backtest win rate
DECAY_THRESHOLD_PCT = 20.0   # e.g. backtest=60%, live=38% → decayed
MIN_LIVE_TRADES = 5          # need at least this many live trades to judge


def _get_backtest_win_rate(db: Session, strategy_name: str) -> float | None:
    """Return win rate % from the most recent backtest for this strategy name."""
    bt = (
        db.query(ConditionStrategyBacktest)
        .filter(ConditionStrategyBacktest.strategy_name == strategy_name)
        .order_by(ConditionStrategyBacktest.created_at.desc())
        .first()
    )
    if not bt:
        return None
    result = bt.result_dict
    summary = result.get("summary") or result
    total = summary.get("total_trades") or 0
    wins = summary.get("winning_trades") or summary.get("wins") or 0
    if total < 1:
        return None
    return round(wins / total * 100, 1)


def compute_decay_report(db: Session, lookback_days: int = 30) -> list[dict]:
    """
    For each strategy that has live closed trades in the last `lookback_days`,
    compare live win rate vs backtest win rate and return a decay report.
    """
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    trades = (
        db.query(ExecutionIntent)
        .filter(
            ExecutionIntent.status == "CLOSED",
            ExecutionIntent.pnl.isnot(None),
            ExecutionIntent.closed_at >= cutoff,
            ExecutionIntent.strategy.isnot(None),
        )
        .all()
    )

    # Group by strategy
    by_strategy: dict = defaultdict(lambda: {"wins": 0, "losses": 0, "pnls": []})
    for t in trades:
        s = by_strategy[t.strategy]
        pnl = t.pnl or 0.0
        s["pnls"].append(pnl)
        if pnl >= 0:
            s["wins"] += 1
        else:
            s["losses"] += 1

    report = []
    for strategy_name, data in by_strategy.items():
        total = data["wins"] + data["losses"]
        if total < MIN_LIVE_TRADES:
            status = "INSUFFICIENT_DATA"
            live_win_rate = round(data["wins"] / total * 100, 1) if total else None
            backtest_win_rate = _get_backtest_win_rate(db, strategy_name)
            report.append({
                "strategy": strategy_name,
                "live_trades": total,
                "live_wins": data["wins"],
                "live_losses": data["losses"],
                "live_win_rate": live_win_rate,
                "backtest_win_rate": backtest_win_rate,
                "decay_gap": None,
                "status": status,
                "total_pnl": round(sum(data["pnls"]), 2),
            })
            continue

        live_win_rate = round(data["wins"] / total * 100, 1)
        backtest_win_rate = _get_backtest_win_rate(db, strategy_name)
        decay_gap = None
        if backtest_win_rate is not None:
            decay_gap = round(backtest_win_rate - live_win_rate, 1)

        if decay_gap is not None and decay_gap >= DECAY_THRESHOLD_PCT:
            status = "DECAYED"
        elif decay_gap is not None and decay_gap >= DECAY_THRESHOLD_PCT / 2:
            status = "WARNING"
        elif backtest_win_rate is None:
            status = "NO_BACKTEST"
        else:
            status = "HEALTHY"

        report.append({
            "strategy": strategy_name,
            "live_trades": total,
            "live_wins": data["wins"],
            "live_losses": data["losses"],
            "live_win_rate": live_win_rate,
            "backtest_win_rate": backtest_win_rate,
            "decay_gap": decay_gap,
            "status": status,
            "total_pnl": round(sum(data["pnls"]), 2),
        })

    # Sort: DECAYED first, then WARNING, then rest
    order = {"DECAYED": 0, "WARNING": 1, "HEALTHY": 2, "NO_BACKTEST": 3, "INSUFFICIENT_DATA": 4}
    report.sort(key=lambda x: order.get(x["status"], 9))
    return report


def run_decay_check_and_notify(db: Session):
    """Run decay check and send Telegram alert if any strategies are DECAYED or WARNING."""
    report = compute_decay_report(db, lookback_days=30)
    if not report:
        logger.info("📊 Strategy decay check: no live trades in last 30 days")
        return

    decayed = [r for r in report if r["status"] == "DECAYED"]
    warnings = [r for r in report if r["status"] == "WARNING"]

    logger.info(
        "📊 Strategy decay check: %d total, %d decayed, %d warnings",
        len(report), len(decayed), len(warnings),
    )

    if not decayed and not warnings:
        return

    try:
        from app.services.notifications import NotificationService
        svc = NotificationService(db)

        lines = ["📉 <b>Strategy Decay Alert</b>"]
        if decayed:
            lines.append("\n🔴 <b>DECAYED</b> (stop or review):")
            for r in decayed:
                lines.append(
                    f"  • {r['strategy']}: live {r['live_win_rate']}% vs backtest {r['backtest_win_rate']}% "
                    f"(gap: -{r['decay_gap']}%)"
                )
        if warnings:
            lines.append("\n🟡 <b>WARNING</b> (monitor closely):")
            for r in warnings:
                lines.append(
                    f"  • {r['strategy']}: live {r['live_win_rate']}% vs backtest {r['backtest_win_rate']}% "
                    f"(gap: -{r['decay_gap']}%)"
                )

        svc._send_telegram("\n".join(lines))
    except Exception as e:
        logger.warning("⚠️ Decay notification failed: %s", e)
