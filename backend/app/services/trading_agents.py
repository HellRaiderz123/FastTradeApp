"""
TradingAgents — Multi-Agent LLM Analysis Pipeline for FastTradeApp
Inspired by: github.com/TauricResearch/TradingAgents

Implements a sequential pipeline of specialised LLM agents that mirror a
real trading-firm structure, adapted for Indian equity markets (NSE/BSE):

  1. Technical Analyst      — price action, indicators, key levels
  2. News Analyst           — RSS news macro + stock-specific impact
  3. Sentiment Analyst      — VIX, Twitter sentiment, market breadth
  4. Bull Researcher        — makes the bullish case
  5. Bear Researcher        — makes the bearish case
  6. Fundamentals Analyst   — valuation, growth, financial health
    7. Trader Agent           — synthesises all reports → BUY / SELL / HOLD
    8. Risk Manager           — enforces volatility/liquidity/event constraints
    9. Portfolio Manager      — enforces portfolio-level exposure constraints

All data comes from existing FastTradeApp infrastructure:
  - Candles DB (SQLAlchemy)
  - rss_feed_service (MoneyControl, ET, BS)
  - Twitter sentiment DB
  - Zerodha VIX quote

Jobs run in background threads.  Callers poll /ai-analysis/status/{job_id}.
No new Python packages required — uses existing httpx + llm_service + DB.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import re
import threading
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import quote
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event-loop reference — set by main.py at startup so background threads can
# schedule async WebSocket broadcasts without blocking.
# ---------------------------------------------------------------------------
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Called once at app startup to register the running event loop."""
    global _event_loop
    _event_loop = loop


def _ws_broadcast(payload: dict) -> None:
    """Fire-and-forget WebSocket broadcast from a sync background thread."""
    if _event_loop is None or _event_loop.is_closed():
        return
    try:
        from app.services.websocket import manager
        asyncio.run_coroutine_threadsafe(manager.broadcast(payload), _event_loop)
    except Exception as e:
        logger.debug("WS broadcast skipped: %s", e)

# ---------------------------------------------------------------------------
# In-memory job store  {job_id: JobState}
# ---------------------------------------------------------------------------
# TTL: completed / failed jobs are cleaned up after RESULT_TTL_MINUTES.
RESULT_TTL_MINUTES = 60
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_CHECKPOINT_DIR = Path(__file__).resolve().parents[2] / "data_cache" / "ai_checkpoints"

# Background desk state for bulk symbol queues (Nifty100 / Holdings)
_desk_state: dict[str, dict[str, Any]] = {
    "nifty100": {"status": "idle", "last_run_at": None, "queued": 0, "last_error": None},
    "holdings": {"status": "idle", "last_run_at": None, "queued": 0, "last_error": None},
}


def _update_desk_progress_locked(job: dict[str, Any]) -> None:
    """Update aggregate + per-symbol desk progress from a job update. Requires _jobs_lock."""
    desk_key = str(job.get("desk_key") or "").strip()
    if not desk_key:
        return

    state = _desk_state.get(desk_key)
    if not state:
        return

    symbol = str(job.get("symbol") or "").strip().upper()
    if not symbol:
        return

    by_symbol = state.setdefault("by_symbol", {})
    by_symbol[symbol] = {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "step": job.get("step"),
        "error": job.get("error"),
        "updated_at": datetime.utcnow().isoformat(),
    }

    statuses = [str((item or {}).get("status") or "").upper() for item in by_symbol.values()]
    total = int(state.get("symbol_count") or len(by_symbol) or 0)
    running = sum(1 for s in statuses if s == "RUNNING")
    completed = sum(1 for s in statuses if s == "COMPLETED")
    failed = sum(1 for s in statuses if s == "FAILED")
    queued = max(0, total - completed - failed - running)

    state["running"] = running
    state["completed"] = completed
    state["failed"] = failed
    state["remaining"] = queued
    state["processed"] = completed + failed
    # Keep legacy field used by existing UI while also exposing richer counters.
    state["queued"] = queued

    if total > 0 and (completed + failed) >= total:
        state["status"] = "completed_with_errors" if failed > 0 else "completed"


def _checkpoint_file(symbol: str, exchange: str) -> Path:
    key = f"{exchange.strip().upper()}_{symbol.strip().upper()}"
    safe_key = re.sub(r"[^A-Z0-9_.-]", "_", key)
    return _CHECKPOINT_DIR / f"{safe_key}.json"


def _load_checkpoint(symbol: str, exchange: str) -> Optional[dict]:
    path = _checkpoint_file(symbol, exchange)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception as e:
        logger.warning("trading_agents: failed to load checkpoint %s: %s", path, e)
        return None


def _save_checkpoint(
    symbol: str,
    exchange: str,
    *,
    step: str,
    steps_done: list[str],
    context: dict,
    error: Optional[str] = None,
) -> None:
    try:
        _CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        path = _checkpoint_file(symbol, exchange)
        payload = {
            "version": 1,
            "symbol": symbol,
            "exchange": exchange,
            "step": step,
            "steps_done": list(steps_done),
            "context": context,
            "status": "FAILED" if error else "RUNNING",
            "error": error,
            "updated_at": datetime.utcnow().isoformat(),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        logger.warning("trading_agents: failed to save checkpoint for %s:%s: %s", exchange, symbol, e)


def _clear_checkpoint(symbol: str, exchange: str) -> None:
    path = _checkpoint_file(symbol, exchange)
    try:
        if path.exists():
            path.unlink()
    except Exception as e:
        logger.warning("trading_agents: failed to clear checkpoint %s: %s", path, e)


def clear_analysis_checkpoint(symbol: str, exchange: str = "NSE") -> bool:
    path = _checkpoint_file(symbol, exchange)
    if not path.exists():
        return False
    _clear_checkpoint(symbol, exchange)
    return True


def _new_job(symbol: str, exchange: str, desk_key: str | None = None) -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "symbol": symbol,
            "exchange": exchange,
            "desk_key": (desk_key or "").strip() or None,
            "status": "QUEUED",        # QUEUED → RUNNING → COMPLETED / FAILED
            "step": None,              # current agent name
            "steps_done": [],          # ordered list of completed steps
            "result": None,
            "error": None,
            "resumed_from_checkpoint": False,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }
        _update_desk_progress_locked(_jobs[job_id])
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    with _jobs_lock:
        return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs) -> None:
    job: Optional[dict[str, Any]] = None
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)
            _update_desk_progress_locked(_jobs[job_id])
            job = dict(_jobs[job_id])
    # Broadcast progress to all connected WebSocket clients
    if job:
        _ws_broadcast({
            "type": "ai_analysis_progress",
            "data": {
                "job_id": job_id,
                "symbol": job.get("symbol"),
                "status": job.get("status"),
                "step": job.get("step"),
                "steps_done": job.get("steps_done", []),
            },
        })


def cleanup_expired_jobs() -> int:
    """Remove jobs older than RESULT_TTL_MINUTES. Call periodically if desired."""
    cutoff = datetime.utcnow() - timedelta(minutes=RESULT_TTL_MINUTES)
    removed = 0
    with _jobs_lock:
        expired = [
            jid for jid, j in _jobs.items()
            if j["status"] in ("COMPLETED", "FAILED")
            and datetime.fromisoformat(j["created_at"]) < cutoff
        ]
        for jid in expired:
            del _jobs[jid]
            removed += 1
    return removed


# ---------------------------------------------------------------------------
# DB persistence — save decision + load history for same symbol
# ---------------------------------------------------------------------------

def _get_price_at_decision(symbol: str, result: dict) -> Optional[float]:
    """
    Try to get the real-time price via Zerodha quote.
    Falls back to last candle close from data_summary.
    """
    # 1. Try Zerodha live quote
    try:
        from app.services.zerodha import KiteConnectService
        kite = KiteConnectService()
        q = kite.get_full_quote(symbol)
        if q:
            price = float(q.get("last_price") or 0)
            if price > 0:
                logger.debug("trading_agents: live price %.2f for %s from Zerodha", price, symbol)
                return price
    except Exception as e:
        logger.debug("trading_agents: Zerodha price fetch failed for %s: %s", symbol, e)
    # 2. Fall back to last candle close
    price = result.get("data_summary", {}).get("current_price")
    if price:
        return float(price)
    return None


def _save_decision_to_db(job_id: str, symbol: str, exchange: str, result: dict) -> None:
    """Persist a completed analysis to the ai_decisions table."""
    try:
        from app.db.session import SessionLocal
        from app.db.models_ai_decisions import AIDecision

        decision = result.get("decision", {})
        db = SessionLocal()
        try:
            row = AIDecision(
                job_id=job_id,
                symbol=symbol,
                exchange=exchange,
                action=decision.get("action"),
                confidence=decision.get("confidence"),
                conviction=decision.get("conviction"),
                time_horizon=decision.get("time_horizon"),
                risk_level=decision.get("risk_level"),
                rationale=decision.get("rationale"),
                execution_allowed=decision.get("execution_allowed"),
                manager_block_reason=(
                    "; ".join(decision.get("manager_enforcement", {}).get("reasons", []))
                    if isinstance(decision.get("manager_enforcement", {}).get("reasons", []), list)
                    else None
                ),
                suggested_stop_loss_pct=decision.get("suggested_stop_loss_pct"),
                suggested_target_pct=decision.get("suggested_target_pct"),
                price_at_decision=_get_price_at_decision(symbol, result),
                technical_report=result.get("reports", {}).get("technical"),
                news_report=result.get("reports", {}).get("news"),
                sentiment_report=result.get("reports", {}).get("sentiment"),
                bull_report=result.get("reports", {}).get("bull_researcher"),
                bear_report=result.get("reports", {}).get("bear_researcher"),
                fundamentals_report=result.get("reports", {}).get("fundamentals"),
                risk_manager_report=result.get("reports", {}).get("risk_manager"),
                portfolio_manager_report=result.get("reports", {}).get("portfolio_manager"),
            )
            db.add(row)
            db.commit()
            logger.info("trading_agents: decision saved to DB for %s (job %s)", symbol, job_id)
        finally:
            db.close()
    except Exception as e:
        logger.warning("trading_agents: failed to save decision to DB: %s", e)


def _load_decision_history(symbol: str, limit: int = 5) -> list[dict]:
    """
    Load the N most recent decisions for this symbol from DB.
    Returns a compact list suitable for injecting into the Trader prompt.
    """
    try:
        from app.db.session import SessionLocal
        from app.db.models_ai_decisions import AIDecision
        from sqlalchemy import desc

        db = SessionLocal()
        try:
            rows = (
                db.query(AIDecision)
                .filter(AIDecision.symbol == symbol)
                .order_by(desc(AIDecision.analysed_at))
                .limit(limit)
                .all()
            )
            return [
                {
                    "date": r.analysed_at.isoformat() if r.analysed_at else None,
                    "action": r.action,
                    "confidence": r.confidence,
                    "conviction": r.conviction,
                    "rationale": r.rationale,
                    "execution_allowed": r.execution_allowed,
                    "manager_block_reason": r.manager_block_reason,
                    "outcome_correct": r.outcome_correct,
                    "actual_return_pct": r.actual_return_pct,
                    "reflection": r.reflection,
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        logger.debug("trading_agents: history load failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Outcome evaluator — called by a scheduled job
# ---------------------------------------------------------------------------

def evaluate_pending_outcomes(evaluation_days: int = 3) -> int:
    """
    For each un-evaluated decision older than `evaluation_days` days,
    fetch the current candle close price and compute whether the
    BUY/SELL call was directionally correct.

    Returns the number of rows updated.
    """
    try:
        from app.db.session import SessionLocal
        from app.db.models_ai_decisions import AIDecision
        from sqlalchemy import and_

        cutoff = datetime.utcnow() - timedelta(days=evaluation_days)
        db = SessionLocal()
        updated = 0
        try:
            pending = (
                db.query(AIDecision)
                .filter(
                    and_(
                        AIDecision.outcome_evaluated_at.is_(None),
                        AIDecision.analysed_at <= cutoff,
                        AIDecision.action.in_(["BUY", "SELL"]),
                    )
                )
                .all()
            )

            for row in pending:
                candles = _get_candle_data(row.symbol, "daily", limit=5)
                if not candles:
                    continue
                latest_close = candles[-1].get("close")
                if not latest_close or not row.price_at_decision:
                    continue

                actual_return = (
                    (latest_close - row.price_at_decision) / row.price_at_decision * 100
                )
                correct = (
                    1 if (row.action == "BUY" and actual_return > 0) or
                         (row.action == "SELL" and actual_return < 0)
                    else 0
                )

                # Generate a brief reflection via LLM
                reflection = _generate_reflection(row, actual_return, correct)

                row.outcome_evaluated_at = datetime.utcnow()
                row.price_at_evaluation  = round(latest_close, 2)
                row.actual_return_pct    = round(actual_return, 2)
                row.outcome_correct      = correct
                row.reflection           = reflection
                updated += 1

            db.commit()
        finally:
            db.close()
        return updated
    except Exception as e:
        logger.warning("trading_agents: outcome evaluation failed: %s", e)
        return 0


def _generate_reflection(row: Any, actual_return: float, correct: int) -> Optional[str]:
    """Ask the LLM to write a one-sentence reflection on a past decision."""
    try:
        from app.services.llm_service import call_llm, is_available
        if not is_available():
            return None
        direction = "up" if actual_return > 0 else "down"
        outcome_word = "correct" if correct else "incorrect"
        prompt = (
            f"We called {row.action} on {row.symbol} with rationale: '{row.rationale}'. "
            f"{evaluation_days_label(row)} later, the price moved {direction} by "
            f"{abs(actual_return):.1f}% — making the call {outcome_word}. "
            "Write one concise sentence reflecting on what the analysis got right or wrong."
        )
        return call_llm(prompt, max_tokens=120, temperature=0.3, timeout=20.0)
    except Exception:
        return None


def evaluation_days_label(row: Any) -> str:
    try:
        delta = datetime.utcnow() - row.analysed_at.replace(tzinfo=None)
        return f"{delta.days} day{'s' if delta.days != 1 else ''}"
    except Exception:
        return "some days"


# ---------------------------------------------------------------------------
# Helper: sanitise symbol input (alphanumeric + common NSE chars only)
# ---------------------------------------------------------------------------
_SYMBOL_RE = re.compile(r"^[A-Z0-9&\-\.]{1,30}$")


def _safe_symbol(symbol: str) -> str:
    """Uppercase and validate symbol to prevent prompt injection."""
    clean = symbol.strip().upper()
    if not _SYMBOL_RE.match(clean):
        raise ValueError(f"Invalid symbol: {symbol!r}")
    return clean


# ---------------------------------------------------------------------------
# Data collection helpers
# ---------------------------------------------------------------------------

def _get_candle_data(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 60,
    min_required: int = 1,
    allow_backfill: bool = True,
) -> list[dict]:
    """
    Fetch OHLCV candles from the FastTradeApp DB.
    Returns a list of dicts ordered oldest-first.
    Falls back to [] on any error so downstream agents degrade gracefully.
    """
    try:
        from app.db.session import SessionLocal
        from app.db.models_candles import Candle1h, CandleDaily, Candle5m, Candle15m
        from app.core.market.candles import fetch_5m_candles, fetch_15m_candles, fetch_1h_candles, fetch_daily_candles

        model_map = {
            "5m": Candle5m,
            "15m": Candle15m,
            "1h": Candle1h,
            "daily": CandleDaily,
        }
        model = model_map.get(timeframe)
        if model is None:
            return []

        def _query_rows(db) -> list[dict]:
            if timeframe == "daily":
                rows = (
                    db.query(model)
                    .filter(model.symbol == symbol)
                    .order_by(model.date.desc())
                    .limit(limit)
                    .all()
                )
                return [
                    {
                        "date": str(r.date),
                        "open": r.open,
                        "high": r.high,
                        "low": r.low,
                        "close": r.close,
                        "volume": r.volume,
                    }
                    for r in reversed(rows)
                ]

            rows = (
                db.query(model)
                .filter(model.symbol == symbol)
                .order_by(model.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "ts": r.timestamp.isoformat() if r.timestamp else None,
                    "open": r.open,
                    "high": r.high,
                    "low": r.low,
                    "close": r.close,
                    "volume": r.volume,
                }
                for r in reversed(rows)
            ]

        backfill_map = {
            "5m": (fetch_5m_candles, 100),
            "15m": (fetch_15m_candles, 120),
            "1h": (fetch_1h_candles, 365),
            "daily": (fetch_daily_candles, 2000),
        }

        db = SessionLocal()
        try:
            payload = _query_rows(db)
            if len(payload) >= min_required or not allow_backfill:
                return payload

            # Backfill from Zerodha if this symbol/timeframe is missing or too sparse.
            fetcher = backfill_map.get(timeframe)
            if not fetcher:
                return payload

            try:
                fetch_fn, days = fetcher
                logger.info(
                    "trading_agents: insufficient %s candles for %s (%d/%d). Backfilling from Zerodha.",
                    timeframe,
                    symbol,
                    len(payload),
                    min_required,
                )
                fetch_fn(db, symbol, days=days)
                payload = _query_rows(db)
                if len(payload) >= min_required:
                    logger.info(
                        "trading_agents: Zerodha backfill succeeded for %s %s (%d rows)",
                        symbol,
                        timeframe,
                        len(payload),
                    )
            except Exception as backfill_err:
                logger.warning(
                    "trading_agents: Zerodha backfill failed for %s %s: %s",
                    symbol,
                    timeframe,
                    backfill_err,
                )

            return payload
        finally:
            db.close()
    except Exception as e:
        logger.warning("trading_agents: candle fetch failed: %s", e)
        return []


def _get_news_items(limit: int = 15) -> list[dict]:
    """Fetch recent news from RSS feeds (already in FastTradeApp)."""
    try:
        from app.services.rss_feed_service import get_rss_service
        svc = get_rss_service()
        items = svc.fetch_all_feeds()
        return items[:limit]
    except Exception as e:
        logger.warning("trading_agents: news fetch failed: %s", e)
        return []


def _get_vix() -> Optional[float]:
    """Fetch India VIX last price from Zerodha."""
    try:
        from app.services.zerodha import KiteConnectService
        kite = KiteConnectService()
        quote = kite.get_full_quote("INDIA VIX")
        if quote:
            return float(quote.get("last_price", 16.0))
    except Exception as e:
        logger.warning("trading_agents: VIX fetch failed: %s", e)
    return None


def _get_twitter_sentiment(symbol: str) -> Optional[dict]:
    """Fetch Twitter/X sentiment for a symbol from the local DB."""
    try:
        from app.db.session import SessionLocal
        from app.db.models_twitter import TwitterSymbolSentiment
        from sqlalchemy import desc

        db = SessionLocal()
        try:
            row = (
                db.query(TwitterSymbolSentiment)
                .filter(TwitterSymbolSentiment.symbol == symbol)
                .order_by(desc(TwitterSymbolSentiment.updated_at))
                .first()
            )
            if row:
                return {
                    "symbol": row.symbol,
                    "sentiment": row.sentiment,
                    "score": row.sentiment_score,
                    "tweet_count": row.tweet_count,
                }
        finally:
            db.close()
    except Exception as e:
        logger.debug("trading_agents: twitter sentiment fetch failed: %s", e)
    return None


def _get_portfolio_snapshot() -> dict:
    """
    Build a compact portfolio context for manager agents.
    Uses open execution intents and latest capital snapshot when available.
    """
    snapshot = {
        "open_positions_count": 0,
        "gross_open_exposure": 0.0,
        "concentration_pct": 0.0,
        "largest_exposure_symbol": None,
        "by_symbol": {},
        "capital": None,
        "daily_pnl": None,
        "daily_loss_pct": None,
    }
    try:
        from app.db.session import SessionLocal
        from app.db.models_intent import ExecutionIntent
        from app.db.models import DailyCapital

        db = SessionLocal()
        try:
            open_positions = (
                db.query(ExecutionIntent)
                .filter(ExecutionIntent.status == "EXECUTED", ExecutionIntent.closed_at.is_(None))
                .all()
            )

            by_symbol: dict[str, dict[str, Any]] = {}
            gross_exposure = 0.0
            for pos in open_positions:
                sym = (pos.underlying or "UNKNOWN").strip().upper() or "UNKNOWN"
                exposure = float(pos.margin_required or pos.entry_credit or 0.0)
                gross_exposure += abs(exposure)
                if sym not in by_symbol:
                    by_symbol[sym] = {"open_positions": 0, "gross_exposure": 0.0}
                by_symbol[sym]["open_positions"] += 1
                by_symbol[sym]["gross_exposure"] += abs(exposure)

            max_symbol = None
            max_exposure = 0.0
            for sym, data in by_symbol.items():
                if data["gross_exposure"] > max_exposure:
                    max_exposure = data["gross_exposure"]
                    max_symbol = sym

            latest_capital = (
                db.query(DailyCapital)
                .order_by(DailyCapital.trade_date.desc())
                .first()
            )
            capital = float(latest_capital.closing_capital) if latest_capital and latest_capital.closing_capital else None
            daily_pnl = float(latest_capital.daily_pnl) if latest_capital and latest_capital.daily_pnl is not None else None

            snapshot.update({
                "open_positions_count": len(open_positions),
                "gross_open_exposure": round(gross_exposure, 2),
                "concentration_pct": round((max_exposure / gross_exposure) * 100, 2) if gross_exposure > 0 else 0.0,
                "largest_exposure_symbol": max_symbol,
                "by_symbol": by_symbol,
                "capital": round(capital, 2) if capital else None,
                "daily_pnl": round(daily_pnl, 2) if daily_pnl is not None else None,
                "daily_loss_pct": (
                    round(abs(daily_pnl) / capital * 100, 2)
                    if capital and daily_pnl is not None and daily_pnl < 0
                    else 0.0
                ),
            })
        finally:
            db.close()
    except Exception as e:
        logger.debug("trading_agents: portfolio snapshot fetch failed: %s", e)
    return snapshot


# ---------------------------------------------------------------------------
# Technical indicator computation  (pure Python / numpy — no new deps)
# ---------------------------------------------------------------------------

def _compute_indicators(candles: list[dict], timeframe: str = "15m") -> dict:
    """
    Delegates to the TA engine so journal and scanner use identical logic.
    Falls back to a minimal summary dict if candles are insufficient.
    """
    if not candles:
        return {"available": False, "summary": "No candle data available."}

    try:
        from app.core.signals.ta_engine import (
            ta_signal_15m_from_candles,
            _ta_signal_daily_from_df,
        )
        import pandas as pd

        if timeframe == "daily" and len(candles) >= 200:
            df = pd.DataFrame(
                [
                    {
                        "close": float(c.get("close") or 0),
                        "high": float(c.get("high") or 0),
                        "low": float(c.get("low") or 0),
                        "open": float(c.get("open") or 0),
                        "volume": float(c.get("volume") or 0),
                    }
                    for c in candles
                ]
            )
            sig = _ta_signal_daily_from_df(df)
        else:
            sig = ta_signal_15m_from_candles(candles)

        if not sig or sig.get("signal") == "NO_TRADE" and not sig.get("indicators"):
            return {"available": False, "summary": sig.get("reason", "Insufficient data")}

        ind = sig.get("indicators") or {}
        current_price = ind.get("sma_20") or ind.get("ema_20") or ind.get("ema_50") or 0
        # Prefer actual last close from candles
        try:
            current_price = float(candles[-1].get("close") or current_price)
        except Exception:
            pass

        closes = [float(c.get("close") or 0) for c in candles if c.get("close")]
        highs  = [float(c.get("high")  or 0) for c in candles if c.get("high")]
        lows   = [float(c.get("low")   or 0) for c in candles if c.get("low")]
        support    = round(min(lows[-20:])  if len(lows)  >= 20 else (min(lows)  if lows  else 0), 2)
        resistance = round(max(highs[-20:]) if len(highs) >= 20 else (max(highs) if highs else 0), 2)

        bias = sig.get("bias", "NEUTRAL")
        trend = "UPTREND" if bias == "BULLISH" else ("DOWNTREND" if bias == "BEARISH" else "SIDEWAYS")

        vols = [float(c.get("volume") or 0) for c in candles]
        avg_vol  = sum(vols[-10:]) / 10 if len(vols) >= 10 else (sum(vols) / len(vols) if vols else 0)
        last_vol = vols[-1] if vols else 0
        vol_signal = "HIGH" if last_vol > avg_vol * 1.5 else ("LOW" if last_vol < avg_vol * 0.5 else "NORMAL")

        return {
            "available": True,
            "current_price": round(current_price, 2),
            "ema20": ind.get("ema_20"),
            "ema50": ind.get("ema_50"),
            "rsi14": ind.get("rsi"),
            "macd_line": ind.get("macd_hist"),
            "adx": ind.get("adx"),
            "stoch_k": ind.get("stoch_k"),
            "trend": trend,
            "bias": bias,
            "signal": sig.get("signal"),
            "confidence": sig.get("confidence"),
            "support": support,
            "resistance": resistance,
            "volume_signal": vol_signal,
            "bars_analysed": len(closes),
            "quality_score": sig.get("quality_score", 0),
            "trade_readiness_score": sig.get("trade_readiness_score", 0),
            "summary": (
                f"Price {current_price:.2f} | {trend} | Bias {bias} | "
                f"RSI {ind.get('rsi', '?')} | ADX {ind.get('adx', '?')} | "
                f"S {support} R {resistance} | Vol {vol_signal} | "
                f"Signal {sig.get('signal')} ({sig.get('confidence', 0):.0f}%)"
            ),
        }
    except Exception as e:
        logger.warning("trading_agents: _compute_indicators TA engine call failed: %s", e)
        return {"available": False, "summary": f"TA engine error: {e}"}


# ---------------------------------------------------------------------------
# LLM agent calls — each returns a dict (parsed from LLM JSON output)
# ---------------------------------------------------------------------------

def _llm_agent(
    agent_name: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 600,
) -> dict:
    """
    Call the LLM and parse a JSON dict from the response.
    Returns {"error": reason} if unavailable or parsing fails.
    """
    from app.services.llm_service import call_llm, is_available, extract_json

    if not is_available():
        return {"error": "LLM_API_KEY not configured"}

    raw = call_llm(
        prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=0.15,
        timeout=45.0,
    )
    if not raw:
        return {"error": f"{agent_name}: LLM returned empty response"}

    parsed = extract_json(raw)
    if not parsed:
        # Fallback: try to parse the whole response as JSON
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw_response": raw[:500]}

    return parsed


def _run_technical_agent(symbol: str, indicators: dict, multi_tf: Optional[dict] = None) -> dict:
    system = (
        "You are a senior technical analyst for Indian equity markets (NSE/BSE). "
        "Analyse the provided multi-timeframe price data and indicator values. "
        "Always respond with a single valid JSON object and nothing else."
    )
    tf_section = ""
    if multi_tf:
        available = {tf: d for tf, d in multi_tf.items() if d.get("available", True)}
        if available:
            compact = {
                tf: {
                    k: v for k, v in d.items()
                    if k in ("current_price", "trend", "rsi14", "ema20", "ema50",
                             "macd_line", "support", "resistance", "volume_signal")
                }
                for tf, d in available.items()
            }
            tf_section = f"\nMulti-Timeframe Summary:\n{json.dumps(compact, indent=2)}"
    user = (
        f"Symbol: {symbol}\n"
        f"Primary Indicator Data (1h/daily):\n{json.dumps(indicators, indent=2)}"
        f"{tf_section}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"trend": "BULLISH|BEARISH|SIDEWAYS", '
        '"rsi_interpretation": "OVERBOUGHT|NEUTRAL|OVERSOLD", '
        '"momentum": "STRONG|MODERATE|WEAK", '
        '"key_support": <number>, '
        '"key_resistance": <number>, '
        '"signals": ["..."], '
        '"mtf_alignment": "ALIGNED_BULL|ALIGNED_BEAR|MIXED|UNAVAILABLE", '
        '"summary": "2-3 sentence technical outlook including multi-timeframe view"}'
    )
    return _llm_agent("TechnicalAnalyst", system, user, max_tokens=500)


def _run_news_agent(symbol: str, news_items: list[dict]) -> dict:
    # Summarise news to avoid huge prompts
    headlines = [
        {"title": n.get("title", "")[:120], "sentiment": n.get("sentiment", "neutral")}
        for n in news_items[:12]
    ]
    system = (
        "You are a senior news analyst specialising in Indian financial markets. "
        "Evaluate how recent news headlines may impact trading sentiment. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Symbol being analysed: {symbol}\n"
        f"Recent Market Headlines (max 12):\n{json.dumps(headlines, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"macro_tone": "RISK_ON|RISK_OFF|NEUTRAL", '
        '"stock_relevance": "HIGH|MEDIUM|LOW", '
        '"key_themes": ["..."], '
        '"news_impact": "POSITIVE|NEGATIVE|NEUTRAL", '
        '"summary": "2-3 sentence news outlook for this symbol"}'
    )
    return _llm_agent("NewsAnalyst", system, user, max_tokens=400)


def _run_sentiment_agent(symbol: str, vix: Optional[float], twitter: Optional[dict]) -> dict:
    sentiment_data = {
        "vix": vix,
        "vix_interpretation": (
            "LOW_VOLATILITY" if vix and vix < 15 else
            "MODERATE_VOLATILITY" if vix and vix < 20 else
            "ELEVATED_VOLATILITY" if vix and vix < 25 else
            "HIGH_VOLATILITY" if vix else "UNKNOWN"
        ),
        "twitter_sentiment": twitter,
    }
    system = (
        "You are a market sentiment analyst for Indian equity markets. "
        "Evaluate overall market mood from VIX and social sentiment data. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Symbol: {symbol}\n"
        f"Sentiment Data:\n{json.dumps(sentiment_data, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"market_mood": "FEARFUL|CAUTIOUS|NEUTRAL|OPTIMISTIC|GREEDY", '
        '"vix_signal": "BULLISH|NEUTRAL|BEARISH", '
        '"social_signal": "BULLISH|NEUTRAL|BEARISH|UNAVAILABLE", '
        '"overall_sentiment": "BULLISH|BEARISH|NEUTRAL", '
        '"summary": "2-3 sentence sentiment outlook"}'
    )
    return _llm_agent("SentimentAnalyst", system, user, max_tokens=350)


def _run_bull_researcher(
    symbol: str,
    tech: dict,
    news: dict,
    sentiment: dict,
    counter_bear: Optional[dict] = None,
    round_no: int = 1,
    total_rounds: int = 1,
) -> dict:
    context = {
        "technical_report": tech,
        "news_report": news,
        "sentiment_report": sentiment,
        "debate_round": round_no,
        "total_rounds": total_rounds,
    }
    if counter_bear:
        context["bear_counterarguments"] = counter_bear
    system = (
        "You are a bullish equity researcher for Indian markets. "
        "Your role is to build the strongest possible bullish case for a trade, "
        "using only the data provided. Be critical and evidence-based. "
        "When bear arguments are provided, rebut them directly with evidence. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Symbol: {symbol}\n"
        f"Analyst Reports:\n{json.dumps(context, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"bull_thesis": "concise bullish thesis in 2-3 sentences", '
        '"key_catalysts": ["..."], '
        '"bull_confidence": <0.0-1.0>, '
        '"suggested_action": "BUY|HOLD", '
        '"price_target_upside_pct": <number or null>}'
    )
    return _llm_agent("BullResearcher", system, user, max_tokens=450)


def _run_bear_researcher(
    symbol: str,
    tech: dict,
    news: dict,
    sentiment: dict,
    counter_bull: Optional[dict] = None,
    round_no: int = 1,
    total_rounds: int = 1,
) -> dict:
    context = {
        "technical_report": tech,
        "news_report": news,
        "sentiment_report": sentiment,
        "debate_round": round_no,
        "total_rounds": total_rounds,
    }
    if counter_bull:
        context["bull_counterarguments"] = counter_bull
    system = (
        "You are a bearish equity researcher for Indian markets. "
        "Your role is to build the strongest possible bearish / risk case for a trade, "
        "using only the data provided. Be critical and evidence-based. "
        "When bull arguments are provided, rebut them directly with evidence. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Symbol: {symbol}\n"
        f"Analyst Reports:\n{json.dumps(context, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"bear_thesis": "concise bearish thesis in 2-3 sentences", '
        '"key_risks": ["..."], '
        '"bear_confidence": <0.0-1.0>, '
        '"suggested_action": "SELL|HOLD", '
        '"price_target_downside_pct": <number or null>}'
    )
    return _llm_agent("BearResearcher", system, user, max_tokens=450)


def _get_fundamental_data(symbol: str) -> dict:
    """
    Fetch fundamental metrics for a symbol using Yahoo Finance public endpoints.
    Falls back to a stable baseline payload if remote data is unavailable.
    """
    def _to_float(v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            return float(v)
        except Exception:
            return None

    def _round(v: Optional[float], digits: int = 2) -> Optional[float]:
        return round(v, digits) if isinstance(v, (int, float)) else None

    # NSE symbols on Yahoo are commonly represented as SYMBOL.NS.
    # We first try NSE suffix, then plain symbol fallback.
    candidates = [f"{symbol}.NS", symbol]
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    for candidate in candidates:
        try:
            # Endpoint 1: Quote snapshot (fast path for PE/PB/dividend)
            q_url = (
                "https://query1.finance.yahoo.com/v7/finance/quote?symbols="
                + quote(candidate)
            )
            q_req = Request(q_url, headers=headers)
            with urlopen(q_req, timeout=8) as res:
                quote_json = json.loads(res.read().decode("utf-8"))

            quote_rows = (
                quote_json.get("quoteResponse", {}).get("result", [])
                if isinstance(quote_json, dict)
                else []
            )
            q = quote_rows[0] if quote_rows else {}

            # Endpoint 2: Fundamentals modules (best-effort for ROE/debt/growth)
            f_url = (
                "https://query1.finance.yahoo.com/v10/finance/quoteSummary/"
                + quote(candidate)
                + "?modules=financialData,defaultKeyStatistics,summaryDetail"
            )
            f_req = Request(f_url, headers=headers)
            with urlopen(f_req, timeout=8) as res:
                fund_json = json.loads(res.read().decode("utf-8"))

            summary_rows = (
                fund_json.get("quoteSummary", {}).get("result", [])
                if isinstance(fund_json, dict)
                else []
            )
            s = summary_rows[0] if summary_rows else {}
            fd = s.get("financialData", {}) if isinstance(s, dict) else {}
            ks = s.get("defaultKeyStatistics", {}) if isinstance(s, dict) else {}
            sd = s.get("summaryDetail", {}) if isinstance(s, dict) else {}

            # Yahoo fields may be raw objects or scalars, normalize both.
            def _raw(obj: Any) -> Any:
                if isinstance(obj, dict) and "raw" in obj:
                    return obj.get("raw")
                return obj

            pe_ratio = _to_float(q.get("trailingPE") or _raw(ks.get("trailingPE")))
            pb_ratio = _to_float(q.get("priceToBook") or _raw(ks.get("priceToBook")))
            roe = _to_float(_raw(fd.get("returnOnEquity")))
            debt_to_equity = _to_float(_raw(fd.get("debtToEquity")))
            rev_growth = _to_float(_raw(fd.get("revenueGrowth")))
            earn_growth = _to_float(_raw(fd.get("earningsGrowth")))
            div_yield = _to_float(q.get("dividendYield") or _raw(sd.get("dividendYield")))
            fcf = _to_float(_raw(fd.get("freeCashflow")))
            total_rev = _to_float(_raw(fd.get("totalRevenue")))
            book_value = _to_float(q.get("bookValue") or _raw(ks.get("bookValue")))

            fundamentals = {
                "pe_ratio": _round(pe_ratio, 2),
                "pb_ratio": _round(pb_ratio, 2),
                "roe_pct": _round(roe * 100, 2) if roe is not None else None,
                "debt_to_equity": _round(debt_to_equity / 100.0, 3) if debt_to_equity is not None else None,
                "revenue_growth_yoy_pct": _round(rev_growth * 100, 2) if rev_growth is not None else None,
                "earnings_growth_yoy_pct": _round(earn_growth * 100, 2) if earn_growth is not None else None,
                "dividend_yield_pct": _round(div_yield * 100, 2) if div_yield is not None else None,
                "fcf_margin_pct": (
                    _round((fcf / total_rev) * 100, 2)
                    if fcf is not None and total_rev not in (None, 0)
                    else None
                ),
                "book_value_per_share": _round(book_value, 2),
            }

            return {
                "symbol": symbol,
                "provider_symbol": candidate,
                "fundamentals": fundamentals,
                "source": "yahoo_finance",
            }
        except Exception as e:
            logger.debug("trading_agents: fundamentals fetch failed for %s: %s", candidate, e)

    # Stable fallback (deterministic, non-random)
    return {
        "symbol": symbol,
        "provider_symbol": None,
        "fundamentals": {
            "pe_ratio": None,
            "pb_ratio": None,
            "roe_pct": None,
            "debt_to_equity": None,
            "revenue_growth_yoy_pct": None,
            "earnings_growth_yoy_pct": None,
            "dividend_yield_pct": None,
            "fcf_margin_pct": None,
            "book_value_per_share": None,
        },
        "source": "unavailable_fallback",
    }


def _run_fundamentals_analyst(
    symbol: str,
    fundamentals: dict,
    tech: dict,
) -> dict:
    """
    Analyse valuation, growth, and financial health.
    Takes fundamentals data + technical analysis context.
    """
    context = {
        "symbol": symbol,
        "fundamentals": fundamentals.get("fundamentals", {}),
        "technical_context": {
            "trend": tech.get("trend"),
            "support": tech.get("key_support"),
            "resistance": tech.get("key_resistance"),
        },
    }
    system = (
        "You are a fundamental equity analyst specialising in Indian markets. "
        "Analyse valuation metrics, growth prospects, and financial health. "
        "Compare multiples to market averages. Assess whether the stock is cheap or expensive. "
        "Be balanced and critical. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Symbol: {symbol}\n"
        f"Fundamental Data:\n{json.dumps(context, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"valuation_assessment": "UNDERVALUED|FAIRLY_VALUED|OVERVALUED", '
        '"growth_outlook": "HIGH|MODERATE|LOW", '
        '"financial_health": "STRONG|AVERAGE|WEAK", '
        '"key_metrics": ["..."], '
        '"risks": ["..."], '
        '"fundamentals_signal": "BULLISH|NEUTRAL|BEARISH", '
        '"summary": "2-3 sentence fundamental outlook"}'
    )
    return _llm_agent("FundamentalsAnalyst", system, user, max_tokens=450)


def _run_trader_decision(
    symbol: str,
    indicators: dict,
    tech: dict,
    news: dict,
    sentiment: dict,
    bull: dict,
    bear: dict,
    fundamentals: dict | None = None,
    history: list[dict] | None = None,
) -> dict:
    all_reports = {
        "technical_indicators": indicators,
        "technical_analyst_report": tech,
        "news_analyst_report": news,
        "sentiment_analyst_report": sentiment,
        "bull_researcher_report": bull,
        "bear_researcher_report": bear,
    }
    if fundamentals:
        all_reports["fundamentals_analyst_report"] = fundamentals
    history_block = ""
    if history:
        history_block = (
            f"\nPast Decisions for {symbol} (most recent first — use for learning):\n"
            + json.dumps(history, indent=2)
            + "\n"
        )
    system = (
        "You are a professional trader at an Indian equity fund. "
        "You receive research from analysts and two opposing researchers (bull/bear). "
        "You also receive a memory of past decisions and their outcomes for this symbol. "
        "Learn from past mistakes and successes. "
        "Your job is to make the final trading decision by weighing all evidence. "
        "Be decisive. This is NOT financial advice — it is a research simulation. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Symbol: {symbol}\n"
        f"{history_block}"
        f"All Research Reports:\n{json.dumps(all_reports, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"action": "BUY|SELL|HOLD", '
        '"confidence": <0.0-1.0>, '
        '"conviction": "HIGH|MEDIUM|LOW", '
        '"rationale": "3-4 sentence final reasoning", '
        '"key_factors": ["..."], '
        '"time_horizon": "INTRADAY|SWING|POSITIONAL", '
        '"risk_level": "LOW|MEDIUM|HIGH", '
        '"suggested_stop_loss_pct": <number or null>, '
        '"suggested_target_pct": <number or null>}'
    )
    return _llm_agent("TraderDecision", system, user, max_tokens=600)


def _run_risk_manager(
    symbol: str,
    decision: dict,
    indicators: dict,
    tech: dict,
    news: dict,
    sentiment: dict,
    bull: dict,
    bear: dict,
    fundamentals: dict | None,
    portfolio_snapshot: dict,
) -> dict:
    context = {
        "symbol": symbol,
        "trader_decision": decision,
        "technical_indicators": indicators,
        "reports": {
            "technical": tech,
            "news": news,
            "sentiment": sentiment,
            "bull": bull,
            "bear": bear,
            "fundamentals": fundamentals,
        },
        "portfolio_snapshot": portfolio_snapshot,
    }
    system = (
        "You are a risk manager at a professional trading desk. "
        "Enforce risk controls for volatility, liquidity, event risk and daily drawdown. "
        "You can override the trader recommendation when risk is excessive. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Risk Review Input:\n{json.dumps(context, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"volatility_regime": "LOW|NORMAL|ELEVATED|HIGH", '
        '"liquidity_risk": "LOW|MEDIUM|HIGH", '
        '"event_risk": "LOW|MEDIUM|HIGH", '
        '"max_position_size_pct": <number 0-100>, '
        '"risk_budget_pct": <number 0-100>, '
        '"allowed_action": "BUY|SELL|HOLD", '
        '"approval": <true|false>, '
        '"hard_limits": ["..."], '
        '"summary": "2-3 sentence risk verdict"}'
    )
    return _llm_agent("RiskManager", system, user, max_tokens=500)


def _run_portfolio_manager(
    symbol: str,
    decision: dict,
    risk_report: dict,
    portfolio_snapshot: dict,
) -> dict:
    context = {
        "symbol": symbol,
        "trader_decision": decision,
        "risk_manager_report": risk_report,
        "portfolio_snapshot": portfolio_snapshot,
    }
    system = (
        "You are a portfolio manager responsible for final position approval. "
        "Validate concentration, open exposures, and total portfolio risk before execution. "
        "When unsure, prefer HOLD over adding risk. "
        "Always respond with a single valid JSON object and nothing else."
    )
    user = (
        f"Portfolio Review Input:\n{json.dumps(context, indent=2)}\n\n"
        "Respond with exactly this JSON structure:\n"
        '{"approval": <true|false>, '
        '"approved_action": "BUY|SELL|HOLD", '
        '"suggested_allocation_pct": <number 0-100>, '
        '"max_quantity": <integer or null>, '
        '"reasons": ["..."], '
        '"summary": "2-3 sentence portfolio-level verdict"}'
    )
    return _llm_agent("PortfolioManager", system, user, max_tokens=450)


def _as_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "yes", "approved", "1"}:
            return True
        if text in {"false", "no", "rejected", "0"}:
            return False
    return default


def _normalize_action(action: Any) -> str:
    text = str(action or "").upper().strip()
    return text if text in {"BUY", "SELL", "HOLD"} else "HOLD"


def _apply_manager_enforcement(decision: dict, risk_report: dict, portfolio_report: dict) -> dict:
    """Preserve the research recommendation while gating executable actions."""
    merged = dict(decision or {})
    requested_action = _normalize_action(merged.get("action"))
    risk_allowed_action = _normalize_action(risk_report.get("allowed_action"))
    pm_approved_action = _normalize_action(portfolio_report.get("approved_action"))

    reasons: list[str] = []
    blocked = False
    recommended_action = requested_action

    risk_approved = _as_bool(risk_report.get("approval"), default=True)
    portfolio_approved = _as_bool(portfolio_report.get("approval"), default=True)

    if not risk_approved:
        blocked = True
        reasons.append("Risk manager rejected the trade")

    if risk_allowed_action == "HOLD" and requested_action in {"BUY", "SELL"}:
        blocked = True
        reasons.append("Risk manager restricted action to HOLD")

    if not portfolio_approved:
        blocked = True
        reasons.append("Portfolio manager rejected the trade")

    if not blocked and risk_allowed_action in {"BUY", "SELL"} and risk_allowed_action != recommended_action:
        recommended_action = risk_allowed_action
        reasons.append(f"Action adjusted to {risk_allowed_action} by risk manager")

    if not blocked and pm_approved_action in {"BUY", "SELL", "HOLD"} and pm_approved_action != recommended_action:
        if pm_approved_action == "HOLD":
            blocked = True
            reasons.append("Portfolio manager restricted action to HOLD")
        else:
            recommended_action = pm_approved_action
            reasons.append(f"Action adjusted to {pm_approved_action} by portfolio manager")

    executable_action = recommended_action if recommended_action in {"BUY", "SELL"} and not blocked else "HOLD"

    merged["action"] = recommended_action
    merged["execution_allowed"] = executable_action in {"BUY", "SELL"}
    merged["manager_enforcement"] = {
        "blocked": blocked,
        "risk_approved": risk_approved,
        "portfolio_approved": portfolio_approved,
        "risk_allowed_action": risk_allowed_action,
        "portfolio_approved_action": pm_approved_action,
        "requested_action": requested_action,
        "recommended_action": recommended_action,
        "executable_action": executable_action,
        "final_action": executable_action,
        "reasons": reasons,
    }
    return merged


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------

def run_analysis_pipeline(job_id: str, symbol: str, exchange: str, debate_rounds: int = 1) -> None:
    """
    Runs the multi-agent pipeline in a background thread.
    Updates job state at each step so the caller can poll progress.
    """
    checkpoint = _load_checkpoint(symbol, exchange)
    steps_done: list[str] = list(checkpoint.get("steps_done", [])) if checkpoint else []
    context: dict[str, Any] = dict(checkpoint.get("context", {})) if checkpoint else {}
    _update_job(
        job_id,
        status="RUNNING",
        steps_done=list(steps_done),
        resumed_from_checkpoint=bool(checkpoint),
    )
    current_step = "collecting_data"

    try:
        # ── Step 1: Collect data + decision history ───────────────────────
        _update_job(job_id, step="collecting_data")
        need_data_collection = (
            "data_collection" not in steps_done
            or any(k not in context for k in [
                "candles_1h", "candles_daily", "candles_5m", "candles_15m",
                "indicators", "multi_tf", "news_items", "vix", "twitter",
                "history", "portfolio_snapshot",
            ])
        )
        if need_data_collection:
            candles_1h = _get_candle_data(symbol, "1h", limit=60, min_required=15)
            candles_daily = _get_candle_data(symbol, "daily", limit=60, min_required=15)
            candles_5m = _get_candle_data(symbol, "5m", limit=60, min_required=15)
            candles_15m = _get_candle_data(symbol, "15m", limit=60, min_required=15)
            candles = candles_1h if len(candles_1h) >= 15 else candles_daily
            indicators = _compute_indicators(candles, timeframe="1h" if len(candles_1h) >= 15 else "daily")
            multi_tf = {
                "5m": _compute_indicators(candles_5m, timeframe="15m") if len(candles_5m) >= 15 else {"available": False},
                "15m": _compute_indicators(candles_15m, timeframe="15m") if len(candles_15m) >= 15 else {"available": False},
                "1h": indicators,
                "daily": _compute_indicators(candles_daily, timeframe="daily") if len(candles_daily) >= 15 else {"available": False},
            }
            news_items = _get_news_items(limit=15)
            vix = _get_vix()
            twitter = _get_twitter_sentiment(symbol)
            history = _load_decision_history(symbol, limit=5)
            portfolio_snapshot = _get_portfolio_snapshot()
            context.update({
                "candles_1h": candles_1h,
                "candles_daily": candles_daily,
                "candles_5m": candles_5m,
                "candles_15m": candles_15m,
                "indicators": indicators,
                "multi_tf": multi_tf,
                "news_items": news_items,
                "vix": vix,
                "twitter": twitter,
                "history": history,
                "portfolio_snapshot": portfolio_snapshot,
                "debate_rounds": max(1, min(3, int(debate_rounds))),
            })
            if "data_collection" not in steps_done:
                steps_done.append("data_collection")
            _save_checkpoint(symbol, exchange, step="data_collection", steps_done=steps_done, context=context)
        else:
            candles_1h = context["candles_1h"]
            candles_daily = context["candles_daily"]
            candles_5m = context["candles_5m"]
            candles_15m = context["candles_15m"]
            indicators = context["indicators"]
            multi_tf = context["multi_tf"]
            news_items = context["news_items"]
            vix = context["vix"]
            twitter = context["twitter"]
            history = context["history"]
            portfolio_snapshot = context["portfolio_snapshot"]
        debate_rounds = max(1, min(3, int(context.get("debate_rounds", debate_rounds))))
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 2: Technical Analyst ─────────────────────────────────────
        current_step = "technical_analyst"
        _update_job(job_id, step="technical_analyst")
        if "technical_analyst" not in steps_done or "tech_report" not in context:
            tech_report = _run_technical_agent(symbol, indicators, multi_tf)
            context["tech_report"] = tech_report
            if "technical_analyst" not in steps_done:
                steps_done.append("technical_analyst")
            _save_checkpoint(symbol, exchange, step="technical_analyst", steps_done=steps_done, context=context)
        else:
            tech_report = context["tech_report"]
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 3: News Analyst ──────────────────────────────────────────
        current_step = "news_analyst"
        _update_job(job_id, step="news_analyst")
        if "news_analyst" not in steps_done or "news_report" not in context:
            news_report = _run_news_agent(symbol, news_items)
            context["news_report"] = news_report
            if "news_analyst" not in steps_done:
                steps_done.append("news_analyst")
            _save_checkpoint(symbol, exchange, step="news_analyst", steps_done=steps_done, context=context)
        else:
            news_report = context["news_report"]
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 4: Sentiment Analyst ─────────────────────────────────────
        current_step = "sentiment_analyst"
        _update_job(job_id, step="sentiment_analyst")
        if "sentiment_analyst" not in steps_done or "sentiment_report" not in context:
            sentiment_report = _run_sentiment_agent(symbol, vix, twitter)
            context["sentiment_report"] = sentiment_report
            if "sentiment_analyst" not in steps_done:
                steps_done.append("sentiment_analyst")
            _save_checkpoint(symbol, exchange, step="sentiment_analyst", steps_done=steps_done, context=context)
        else:
            sentiment_report = context["sentiment_report"]
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 5: Bull Researcher ───────────────────────────────────────
        current_step = "bull_researcher"
        _update_job(job_id, step="bull_researcher")
        if "bull_researcher" not in steps_done or "bull_report" not in context:
            bull_report = _run_bull_researcher(
                symbol,
                tech_report,
                news_report,
                sentiment_report,
                round_no=1,
                total_rounds=debate_rounds,
            )
            context["bull_report"] = bull_report
            if "bull_researcher" not in steps_done:
                steps_done.append("bull_researcher")
            _save_checkpoint(symbol, exchange, step="bull_researcher", steps_done=steps_done, context=context)
        else:
            bull_report = context["bull_report"]
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 6: Bear Researcher ───────────────────────────────────────
        current_step = "bear_researcher"
        _update_job(job_id, step="bear_researcher")
        if "bear_researcher" not in steps_done or "bear_report" not in context:
            debate_transcript: list[dict[str, Any]] = []
            bear_report = _run_bear_researcher(
                symbol,
                tech_report,
                news_report,
                sentiment_report,
                counter_bull=bull_report,
                round_no=1,
                total_rounds=debate_rounds,
            )
            debate_transcript.append(
                {
                    "round": 1,
                    "bull": {
                        "thesis": bull_report.get("bull_thesis"),
                        "confidence": bull_report.get("bull_confidence"),
                    },
                    "bear": {
                        "thesis": bear_report.get("bear_thesis"),
                        "confidence": bear_report.get("bear_confidence"),
                    },
                }
            )

            if debate_rounds > 1:
                bull_current = bull_report
                bear_current = bear_report
                for round_no in range(2, debate_rounds + 1):
                    bull_current = _run_bull_researcher(
                        symbol,
                        tech_report,
                        news_report,
                        sentiment_report,
                        counter_bear=bear_current,
                        round_no=round_no,
                        total_rounds=debate_rounds,
                    )
                    bear_current = _run_bear_researcher(
                        symbol,
                        tech_report,
                        news_report,
                        sentiment_report,
                        counter_bull=bull_current,
                        round_no=round_no,
                        total_rounds=debate_rounds,
                    )
                    debate_transcript.append(
                        {
                            "round": round_no,
                            "bull": {
                                "thesis": bull_current.get("bull_thesis"),
                                "confidence": bull_current.get("bull_confidence"),
                            },
                            "bear": {
                                "thesis": bear_current.get("bear_thesis"),
                                "confidence": bear_current.get("bear_confidence"),
                            },
                        }
                    )
                bull_report = bull_current
                bear_report = bear_current

            context["bull_report"] = bull_report
            context["bear_report"] = bear_report
            context["debate_transcript"] = debate_transcript
            context["debate_rounds_used"] = debate_rounds
            if "bear_researcher" not in steps_done:
                steps_done.append("bear_researcher")
            _save_checkpoint(symbol, exchange, step="bear_researcher", steps_done=steps_done, context=context)
        else:
            bear_report = context["bear_report"]
            debate_transcript = context.get("debate_transcript", [])
            debate_rounds = int(context.get("debate_rounds_used", debate_rounds))
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 7: Fundamentals Analyst ───────────────────────────────────
        current_step = "fundamentals_analyst"
        _update_job(job_id, step="fundamentals_analyst")
        if "fundamentals_analyst" not in steps_done or "fund_data" not in context or "fundamentals_report" not in context:
            fund_data = _get_fundamental_data(symbol)
            fundamentals_report = _run_fundamentals_analyst(symbol, fund_data, tech_report)
            context["fund_data"] = fund_data
            context["fundamentals_report"] = fundamentals_report
            if "fundamentals_analyst" not in steps_done:
                steps_done.append("fundamentals_analyst")
            _save_checkpoint(symbol, exchange, step="fundamentals_analyst", steps_done=steps_done, context=context)
        else:
            fund_data = context["fund_data"]
            fundamentals_report = context["fundamentals_report"]
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 8: Trader Decision ───────────────────────────────────────
        current_step = "trader_decision"
        _update_job(job_id, step="trader_decision")
        if "trader_decision" not in steps_done or "decision" not in context:
            decision = _run_trader_decision(
                symbol, indicators, tech_report, news_report,
                sentiment_report, bull_report, bear_report,
                fundamentals_report,
                history=history,
            )
            context["decision"] = decision
            if "trader_decision" not in steps_done:
                steps_done.append("trader_decision")
            _save_checkpoint(symbol, exchange, step="trader_decision", steps_done=steps_done, context=context)
        else:
            decision = context["decision"]
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 9: Risk Manager ──────────────────────────────────────────
        current_step = "risk_manager"
        _update_job(job_id, step="risk_manager")
        if "risk_manager" not in steps_done or "risk_report" not in context:
            risk_report = _run_risk_manager(
                symbol,
                decision,
                indicators,
                tech_report,
                news_report,
                sentiment_report,
                bull_report,
                bear_report,
                fundamentals_report,
                portfolio_snapshot,
            )
            context["risk_report"] = risk_report
            if "risk_manager" not in steps_done:
                steps_done.append("risk_manager")
            _save_checkpoint(symbol, exchange, step="risk_manager", steps_done=steps_done, context=context)
        else:
            risk_report = context["risk_report"]
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 10: Portfolio Manager ────────────────────────────────────
        current_step = "portfolio_manager"
        _update_job(job_id, step="portfolio_manager")
        if "portfolio_manager" not in steps_done or "portfolio_report" not in context:
            portfolio_report = _run_portfolio_manager(symbol, decision, risk_report, portfolio_snapshot)
            context["portfolio_report"] = portfolio_report
            if "portfolio_manager" not in steps_done:
                steps_done.append("portfolio_manager")
            _save_checkpoint(symbol, exchange, step="portfolio_manager", steps_done=steps_done, context=context)
        else:
            portfolio_report = context["portfolio_report"]
        _update_job(job_id, steps_done=list(steps_done))

        # Enforce manager approvals before any downstream execution path.
        decision = _apply_manager_enforcement(decision, risk_report, portfolio_report)

        # ── Assemble final result ─────────────────────────────────────────
        result = {
            "symbol": symbol,
            "exchange": exchange,
            "analysed_at": datetime.utcnow().isoformat(),
            "decision": decision,
            "reports": {
                "technical": tech_report,
                "news": news_report,
                "sentiment": sentiment_report,
                "bull_researcher": bull_report,
                "bear_researcher": bear_report,
                "fundamentals": fundamentals_report,
                "risk_manager": risk_report,
                "portfolio_manager": portfolio_report,
            },
            "data_summary": {
                "candles_used": indicators.get("bars_analysed", 0),
                "current_price": indicators.get("current_price"),
                "candle_timeframe": "1h" if len(candles_1h) >= 15 else "daily",
                "timeframes_available": [tf for tf, d in multi_tf.items() if d.get("available", True)],
                "news_items_used": len(news_items),
                "vix": vix,
                "twitter_available": twitter is not None,
                "history_decisions_used": len(history),
                "portfolio_open_positions": portfolio_snapshot.get("open_positions_count", 0),
                "portfolio_concentration_pct": portfolio_snapshot.get("concentration_pct", 0.0),
                "risk_manager_approved": _as_bool(risk_report.get("approval"), default=True),
                "portfolio_manager_approved": _as_bool(portfolio_report.get("approval"), default=True),
                "execution_allowed": bool(decision.get("execution_allowed", False)),
                "debate_rounds": debate_rounds,
            },
            "decision_history": history,
            "debate_transcript": debate_transcript,
            "portfolio_snapshot": portfolio_snapshot,
            "disclaimer": (
                "This analysis is generated by AI agents for research purposes only. "
                "It is NOT financial or investment advice. Trade at your own risk."
            ),
        }

        _update_job(
            job_id,
            status="COMPLETED",
            step=None,
            steps_done=steps_done,
            result=result,
            completed_at=datetime.utcnow().isoformat(),
        )
        _clear_checkpoint(symbol, exchange)
        # Persist to DB (non-blocking, best-effort)
        _save_decision_to_db(job_id, symbol, exchange, result)
        logger.info("trading_agents: job %s completed for %s", job_id, symbol)

    except Exception as e:
        logger.exception("trading_agents: job %s failed: %s", job_id, e)
        _save_checkpoint(
            symbol,
            exchange,
            step=current_step,
            steps_done=steps_done,
            context=context,
            error=str(e),
        )
        _update_job(
            job_id,
            status="FAILED",
            step=None,
            steps_done=steps_done,
            error=str(e),
            completed_at=datetime.utcnow().isoformat(),
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def start_analysis(
    symbol: str,
    exchange: str = "NSE",
    debate_rounds: int = 1,
    desk_key: str | None = None,
    run_async: bool = True,
) -> str:
    """
    Validate inputs, create a job, and run the pipeline.
    Returns the job_id for polling.

    Raises ValueError for invalid symbol input.
    """
    clean_symbol   = _safe_symbol(symbol)
    clean_exchange = _safe_symbol(exchange) if exchange else "NSE"
    debate_rounds = max(1, min(3, int(debate_rounds)))
    checkpoint = _load_checkpoint(clean_symbol, clean_exchange)

    job_id = _new_job(clean_symbol, clean_exchange, desk_key=desk_key)
    _update_job(job_id, resumed_from_checkpoint=bool(checkpoint))
    if run_async:
        thread = threading.Thread(
            target=run_analysis_pipeline,
            args=(job_id, clean_symbol, clean_exchange, debate_rounds),
            name=f"trading-agents-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        logger.info("trading_agents: started async job %s for %s:%s", job_id, clean_exchange, clean_symbol)
    else:
        logger.info("trading_agents: running sync job %s for %s:%s", job_id, clean_exchange, clean_symbol)
        run_analysis_pipeline(job_id, clean_symbol, clean_exchange, debate_rounds)
    return job_id


def run_watchlist_analysis(exchange: str = "NSE") -> int:
    """
    Run the AI analysis pipeline for every symbol across all active watchlists.
    Called by the pre-market scheduler.  Returns the number of jobs started.
    """
    import time as _time

    try:
        from app.db.session import SessionLocal
        from app.db.models_watchlist import Watchlist

        db = SessionLocal()
        try:
            watchlists = db.query(Watchlist).filter(Watchlist.is_active == True).all()  # noqa: E712
            symbols: set[str] = set()
            for wl in watchlists:
                for s in (wl.symbols or []):
                    sym = str(s).strip().upper()
                    if sym:
                        symbols.add(sym)
        finally:
            db.close()
    except Exception as e:
        logger.warning("run_watchlist_analysis: failed to load watchlists: %s", e)
        return 0

    count = 0
    for sym in sorted(symbols):
        try:
            start_analysis(sym, exchange)
            count += 1
            _time.sleep(3)  # stagger LLM calls to avoid rate-limiting
        except Exception as e:
            logger.warning("run_watchlist_analysis: skipping %s: %s", sym, e)

    logger.info("run_watchlist_analysis: launched %d jobs for watchlist symbols", count)
    return count


# Semaphore caps concurrent LLM threads to avoid rate-limiting
_BULK_ANALYSIS_SEMAPHORE = threading.Semaphore(5)


def _queue_symbol_analysis(symbols: list[str], exchange: str = "NSE", debate_rounds: int = 2, *, desk_key: str) -> int:
    """Queue async analysis jobs for a list of symbols with max-5 concurrency."""
    count = 0
    try:
        with _jobs_lock:
            _desk_state[desk_key] = {
                "status": "running",
                "last_run_at": datetime.utcnow().isoformat(),
                "queued": len(symbols),
                "running": 0,
                "completed": 0,
                "failed": 0,
                "remaining": len(symbols),
                "processed": 0,
                "last_error": None,
                "symbol_count": len(symbols),
                "by_symbol": {
                    sym: {
                        "job_id": None,
                        "status": "QUEUED",
                        "step": None,
                        "error": None,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                    for sym in symbols
                },
            }

        def _run_with_semaphore(sym: str) -> None:
            with _BULK_ANALYSIS_SEMAPHORE:
                try:
                    start_analysis(sym, exchange, debate_rounds=debate_rounds, desk_key=desk_key, run_async=False)
                except Exception as e:
                    logger.warning("%s queue: skipping %s: %s", desk_key, sym, e)
                    with _jobs_lock:
                        state = _desk_state.get(desk_key) or {}
                        by_symbol = state.get("by_symbol") or {}
                        if sym in by_symbol:
                            by_symbol[sym].update({
                                "status": "FAILED",
                                "error": str(e),
                                "updated_at": datetime.utcnow().isoformat(),
                            })
                        state["last_error"] = str(e)

        threads = []
        for sym in symbols:
            t = threading.Thread(
                target=_run_with_semaphore,
                args=(sym,),
                name=f"{desk_key}-{sym}",
                daemon=True,
            )
            t.start()
            threads.append(t)
            count += 1

        with _jobs_lock:
            state = _desk_state.get(desk_key, {})
            state["status"] = "queued"
            state["queued"] = len(symbols)
            _desk_state[desk_key] = state

    except Exception as e:
        with _jobs_lock:
            _desk_state[desk_key]["status"] = "failed"
            _desk_state[desk_key]["last_error"] = str(e)
        raise

    logger.info("%s: launched %d async jobs (max 5 concurrent)", desk_key, count)
    return count


def run_nifty100_reconciliation(exchange: str = "NSE", debate_rounds: int = 2) -> int:
    """Queue background AI analysis jobs for the Nifty100 universe."""
    from app.core.market.scheduler import _get_daily_symbols

    symbols = _get_daily_symbols()
    return _queue_symbol_analysis(symbols, exchange=exchange, debate_rounds=debate_rounds, desk_key="nifty100")


def run_holdings_reconciliation(exchange: str = "NSE", debate_rounds: int = 2) -> int:
    """Queue background AI analysis jobs for current Zerodha holdings."""
    try:
        from app.core.broker.zerodha.client import get_kite_client

        kite = get_kite_client()
        holdings = kite.holdings() or []
        symbols = []
        for row in holdings:
            sym = str(row.get("tradingsymbol") or row.get("symbol") or "").strip().upper()
            if sym:
                symbols.append(sym)
        symbols = sorted(set(symbols))
    except Exception as e:
        logger.warning("holdings reconciliation: failed to load holdings: %s", e)
        symbols = []

    return _queue_symbol_analysis(symbols, exchange=exchange, debate_rounds=debate_rounds, desk_key="holdings")


def _serialize_latest_decision(row: Any) -> dict[str, Any]:
    risk_report = row.risk_manager_report if isinstance(row.risk_manager_report, dict) else {}
    portfolio_report = row.portfolio_manager_report if isinstance(row.portfolio_manager_report, dict) else {}
    stored_action = _normalize_action(row.action)
    risk_allowed_action = _normalize_action(risk_report.get("allowed_action")) if risk_report else None
    portfolio_approved_action = _normalize_action(portfolio_report.get("approved_action")) if portfolio_report else None
    recommendation_action = stored_action
    if stored_action == "HOLD" and not row.execution_allowed and risk_allowed_action in {"BUY", "SELL"}:
        # Legacy rows saved before recommendations were separated from execution gates.
        recommendation_action = risk_allowed_action
    executable_action = stored_action if row.execution_allowed and stored_action in {"BUY", "SELL"} else "HOLD"

    return {
        "job_id": row.job_id,
        "symbol": row.symbol,
        "exchange": row.exchange,
        "action": stored_action,
        "recommendation_action": recommendation_action,
        "executable_action": executable_action,
        "confidence": row.confidence,
        "conviction": row.conviction,
        "time_horizon": row.time_horizon,
        "risk_level": row.risk_level,
        "rationale": row.rationale,
        "execution_allowed": row.execution_allowed,
        "manager_block_reason": row.manager_block_reason,
        "risk_allowed_action": risk_allowed_action,
        "risk_approved": _as_bool(risk_report.get("approval"), default=True) if risk_report else None,
        "portfolio_approved_action": portfolio_approved_action,
        "portfolio_approved": _as_bool(portfolio_report.get("approval"), default=True) if portfolio_report else None,
        "analysed_at": row.analysed_at.isoformat() if getattr(row, "analysed_at", None) else None,
    }


def _serialize_job_decision(job: dict[str, Any]) -> Optional[dict[str, Any]]:
    result = job.get("result") or {}
    if not isinstance(result, dict):
        return None
    decision = result.get("decision") or {}
    if not isinstance(decision, dict):
        return None
    symbol = str(result.get("symbol") or job.get("symbol") or "").strip().upper()
    if not symbol:
        return None
    reports = result.get("reports") or {}
    risk_report = reports.get("risk_manager") if isinstance(reports.get("risk_manager"), dict) else {}
    portfolio_report = reports.get("portfolio_manager") if isinstance(reports.get("portfolio_manager"), dict) else {}
    enforcement = decision.get("manager_enforcement") if isinstance(decision.get("manager_enforcement"), dict) else {}
    stored_action = _normalize_action(decision.get("action"))
    recommendation_action = _normalize_action(enforcement.get("recommended_action") or stored_action)
    executable_action = _normalize_action(enforcement.get("executable_action") or enforcement.get("final_action"))
    return {
        "job_id": job.get("job_id"),
        "symbol": symbol,
        "exchange": result.get("exchange") or job.get("exchange"),
        "action": stored_action,
        "recommendation_action": recommendation_action,
        "executable_action": executable_action,
        "confidence": decision.get("confidence"),
        "conviction": decision.get("conviction"),
        "time_horizon": decision.get("time_horizon"),
        "risk_level": decision.get("risk_level"),
        "rationale": decision.get("rationale"),
        "execution_allowed": decision.get("execution_allowed"),
        "manager_block_reason": (
            "; ".join(enforcement.get("reasons", []))
            if isinstance(enforcement.get("reasons", []), list)
            else None
        ),
        "risk_allowed_action": _normalize_action(risk_report.get("allowed_action")) if risk_report else None,
        "risk_approved": _as_bool(risk_report.get("approval"), default=True) if risk_report else None,
        "portfolio_approved_action": _normalize_action(portfolio_report.get("approved_action")) if portfolio_report else None,
        "portfolio_approved": _as_bool(portfolio_report.get("approval"), default=True) if portfolio_report else None,
        "analysed_at": result.get("analysed_at") or job.get("completed_at"),
    }


def _is_newer_decision(candidate: Optional[dict[str, Any]], current: Optional[dict[str, Any]]) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    c_ts = str(candidate.get("analysed_at") or "")
    cur_ts = str(current.get("analysed_at") or "")
    return c_ts > cur_ts


def _latest_in_memory_decisions_by_symbol(desk_key: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    with _jobs_lock:
        for job in _jobs.values():
            if str(job.get("desk_key") or "") != desk_key:
                continue
            if str(job.get("status") or "").upper() != "COMPLETED":
                continue
            parsed = _serialize_job_decision(job)
            if not parsed:
                continue
            sym = str(parsed.get("symbol") or "")
            if _is_newer_decision(parsed, latest.get(sym)):
                latest[sym] = parsed
    return latest


def get_reconciliation_desk_snapshot(limit: int = 40) -> dict[str, Any]:
    """Return latest AI decisions plus current holdings for the reconciliation desk."""
    from sqlalchemy import desc

    try:
        from app.db.session import SessionLocal
        from app.db.models_ai_decisions import AIDecision
        from app.core.broker.zerodha.client import get_kite_client
        from app.core.market.scheduler import _get_daily_symbols

        db = SessionLocal()
        try:
            symbols = _get_daily_symbols()
            rows = (
                db.query(AIDecision)
                .filter(AIDecision.symbol.in_(symbols))
                .order_by(AIDecision.symbol.asc(), desc(AIDecision.analysed_at))
                .all()
            )
            latest_by_symbol: dict[str, Any] = {}
            for row in rows:
                if row.symbol not in latest_by_symbol:
                    latest_by_symbol[row.symbol] = _serialize_latest_decision(row)

            in_memory_nifty = _latest_in_memory_decisions_by_symbol("nifty100")
            for sym, decision in in_memory_nifty.items():
                if _is_newer_decision(decision, latest_by_symbol.get(sym)):
                    latest_by_symbol[sym] = decision

            nifty100_rows = [
                row
                for row in latest_by_symbol.values()
            ]
            nifty100_rows.sort(key=lambda item: (item.get("analysed_at") or "", item.get("confidence") or 0), reverse=True)
            nifty100_action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
            for row in nifty100_rows:
                action = str(row.get("recommendation_action") or row.get("action") or "HOLD").upper()
                if action not in nifty100_action_counts:
                    action = "HOLD"
                nifty100_action_counts[action] += 1

            holdings = []
            try:
                kite = get_kite_client()
                holdings = kite.holdings() or []
            except Exception as e:
                logger.warning("get_reconciliation_desk_snapshot: holdings load failed: %s", e)

            holding_symbols = []
            for row in holdings:
                sym = str(row.get("tradingsymbol") or row.get("symbol") or "").strip().upper()
                if sym:
                    holding_symbols.append(sym)

            holding_latest = (
                db.query(AIDecision)
                .filter(AIDecision.symbol.in_(holding_symbols or ["__NONE__"]))
                .order_by(AIDecision.symbol.asc(), desc(AIDecision.analysed_at))
                .all()
            )
            latest_holding_by_symbol: dict[str, Any] = {}
            for row in holding_latest:
                if row.symbol not in latest_holding_by_symbol:
                    latest_holding_by_symbol[row.symbol] = _serialize_latest_decision(row)

            in_memory_holdings = _latest_in_memory_decisions_by_symbol("holdings")
            for sym, decision in in_memory_holdings.items():
                if _is_newer_decision(decision, latest_holding_by_symbol.get(sym)):
                    latest_holding_by_symbol[sym] = decision

            holding_rows = []
            for row in holdings:
                sym = str(row.get("tradingsymbol") or row.get("symbol") or "").strip().upper()
                if not sym:
                    continue
                decision = latest_holding_by_symbol.get(sym)
                holding_rows.append({
                    "symbol": sym,
                    "quantity": row.get("quantity") or row.get("net_quantity") or 0,
                    "average_price": row.get("average_price") or row.get("average_price") or 0,
                    "last_price": row.get("last_price") or 0,
                    "pnl": row.get("pnl") or row.get("m2m") or 0,
                    "decision": decision if decision else None,
                })

            top_buys = [
                row for row in nifty100_rows
                if str(row.get("recommendation_action") or row.get("action") or "").upper() == "BUY"
            ][:limit]
            top_sells = [
                row for row in nifty100_rows
                if str(row.get("recommendation_action") or row.get("action") or "").upper() == "SELL"
            ][:limit]

            return {
                "nifty100": {
                    "state": dict(_desk_state.get("nifty100", {})),
                    "latest": nifty100_rows[:limit],
                    "buy_recommendations": top_buys[:10],
                    "sell_recommendations": top_sells[:10],
                    "action_counts": nifty100_action_counts,
                    "symbol_count": len(symbols),
                },
                "holdings": {
                    "state": dict(_desk_state.get("holdings", {})),
                    "rows": holding_rows,
                },
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning("get_reconciliation_desk_snapshot failed: %s", e)
        return {
            "nifty100": {"state": dict(_desk_state.get("nifty100", {})), "latest": [], "buy_recommendations": [], "sell_recommendations": [], "symbol_count": 0},
            "holdings": {"state": dict(_desk_state.get("holdings", {})), "rows": []},
        }
