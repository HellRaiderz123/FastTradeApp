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


def _new_job(symbol: str, exchange: str) -> str:
    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "symbol": symbol,
            "exchange": exchange,
            "status": "QUEUED",        # QUEUED → RUNNING → COMPLETED / FAILED
            "step": None,              # current agent name
            "steps_done": [],          # ordered list of completed steps
            "result": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    with _jobs_lock:
        return _jobs.get(job_id)


def _update_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)
    # Broadcast progress to all connected WebSocket clients
    job = get_job(job_id)
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
                suggested_stop_loss_pct=decision.get("suggested_stop_loss_pct"),
                suggested_target_pct=decision.get("suggested_target_pct"),
                price_at_decision=_get_price_at_decision(symbol, result),
                technical_report=result.get("reports", {}).get("technical"),
                news_report=result.get("reports", {}).get("news"),
                sentiment_report=result.get("reports", {}).get("sentiment"),
                bull_report=result.get("reports", {}).get("bull_researcher"),
                bear_report=result.get("reports", {}).get("bear_researcher"),
                fundamentals_report=result.get("reports", {}).get("fundamentals"),
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

def _get_candle_data(symbol: str, timeframe: str = "1h", limit: int = 60) -> list[dict]:
    """
    Fetch OHLCV candles from the FastTradeApp DB.
    Returns a list of dicts ordered oldest-first.
    Falls back to [] on any error so downstream agents degrade gracefully.
    """
    try:
        from app.db.session import SessionLocal
        from app.db.models_candles import Candle1h, CandleDaily, Candle5m, Candle15m

        model_map = {
            "5m": Candle5m,
            "15m": Candle15m,
            "1h": Candle1h,
            "daily": CandleDaily,
        }
        model = model_map.get(timeframe)
        if model is None:
            return []

        db = SessionLocal()
        try:
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
            else:
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


# ---------------------------------------------------------------------------
# Technical indicator computation  (pure Python / numpy — no new deps)
# ---------------------------------------------------------------------------

def _compute_indicators(candles: list[dict]) -> dict:
    """
    Compute EMA, RSI, MACD, Bollinger Bands, support/resistance from candles.
    Returns a dict of indicator values and a human-readable summary string.
    """
    if not candles:
        return {"available": False, "summary": "No candle data available."}

    closes = [c["close"] for c in candles if c.get("close") is not None]
    highs  = [c["high"]  for c in candles if c.get("high")  is not None]
    lows   = [c["low"]   for c in candles if c.get("low")   is not None]
    vols   = [c.get("volume", 0) or 0 for c in candles]

    if len(closes) < 15:
        return {"available": False, "summary": "Insufficient candle data (< 15 bars)."}

    def ema(values: list, period: int) -> float:
        k = 2.0 / (period + 1)
        result = values[0]
        for v in values[1:]:
            result = v * k + result * (1 - k)
        return round(result, 2)

    def rsi(values: list, period: int = 14) -> float:
        if len(values) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, period + 1):
            diff = values[-period + i] - values[-period + i - 1]
            (gains if diff >= 0 else losses).append(abs(diff))
        avg_gain = sum(gains) / period if gains else 0.001
        avg_loss = sum(losses) / period if losses else 0.001
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    current = closes[-1]
    ema20   = ema(closes[-30:], 20) if len(closes) >= 20 else None
    ema50   = ema(closes[-60:], 50) if len(closes) >= 50 else None
    rsi14   = rsi(closes, 14)

    # MACD (12, 26, 9)
    macd_line = None
    macd_signal = None
    if len(closes) >= 35:
        fast = ema(closes[-30:], 12)
        slow = ema(closes[-40:], 26)
        macd_line = round(fast - slow, 2)

    # Recent swing support / resistance (last 20 bars)
    window = closes[-20:] if len(closes) >= 20 else closes
    support    = round(min(lows[-20:])  if len(lows)  >= 20 else min(lows), 2)
    resistance = round(max(highs[-20:]) if len(highs) >= 20 else max(highs), 2)

    # Trend direction
    if ema20 and ema50:
        trend = "UPTREND" if ema20 > ema50 and current > ema20 else (
                "DOWNTREND" if ema20 < ema50 and current < ema20 else "SIDEWAYS")
    elif ema20:
        trend = "ABOVE_EMA20" if current > ema20 else "BELOW_EMA20"
    else:
        trend = "UNKNOWN"

    # Volume signal
    avg_vol = sum(vols[-10:]) / 10 if len(vols) >= 10 else (sum(vols) / len(vols) if vols else 0)
    last_vol = vols[-1] if vols else 0
    vol_signal = "HIGH" if last_vol > avg_vol * 1.5 else ("LOW" if last_vol < avg_vol * 0.5 else "NORMAL")

    return {
        "available": True,
        "current_price": round(current, 2),
        "ema20": ema20,
        "ema50": ema50,
        "rsi14": rsi14,
        "macd_line": macd_line,
        "trend": trend,
        "support": support,
        "resistance": resistance,
        "volume_signal": vol_signal,
        "bars_analysed": len(closes),
        "summary": (
            f"Price {current:.2f} | Trend {trend} | EMA20 {ema20} | EMA50 {ema50} "
            f"| RSI {rsi14} | MACD {macd_line} | S {support} R {resistance} "
            f"| Volume {vol_signal}"
        ),
    }


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
) -> dict:
    context = {
        "technical_report": tech,
        "news_report": news,
        "sentiment_report": sentiment,
    }
    system = (
        "You are a bullish equity researcher for Indian markets. "
        "Your role is to build the strongest possible bullish case for a trade, "
        "using only the data provided. Be critical and evidence-based. "
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
) -> dict:
    context = {
        "technical_report": tech,
        "news_report": news,
        "sentiment_report": sentiment,
    }
    system = (
        "You are a bearish equity researcher for Indian markets. "
        "Your role is to build the strongest possible bearish / risk case for a trade, "
        "using only the data provided. Be critical and evidence-based. "
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


# ---------------------------------------------------------------------------
# Main pipeline orchestrator
# ---------------------------------------------------------------------------

def run_analysis_pipeline(job_id: str, symbol: str, exchange: str) -> None:
    """
    Runs the 6-agent pipeline in a background thread.
    Updates job state at each step so the caller can poll progress.
    """
    _update_job(job_id, status="RUNNING")
    steps_done: list[str] = []

    try:
        # ── Step 1: Collect data + decision history ───────────────────────
        _update_job(job_id, step="collecting_data")
        candles_1h    = _get_candle_data(symbol, "1h", limit=60)
        candles_daily = _get_candle_data(symbol, "daily", limit=60)
        candles_5m    = _get_candle_data(symbol, "5m", limit=60)
        candles_15m   = _get_candle_data(symbol, "15m", limit=60)
        # Prefer 1h for primary indicators; fall back to daily
        candles = candles_1h if len(candles_1h) >= 15 else candles_daily
        indicators = _compute_indicators(candles)
        # Multi-timeframe context for the technical analyst
        multi_tf = {
            "5m":    _compute_indicators(candles_5m)    if len(candles_5m)  >= 15 else {"available": False},
            "15m":   _compute_indicators(candles_15m)   if len(candles_15m) >= 15 else {"available": False},
            "1h":    indicators,
            "daily": _compute_indicators(candles_daily) if len(candles_daily) >= 15 else {"available": False},
        }

        news_items = _get_news_items(limit=15)
        vix        = _get_vix()
        twitter    = _get_twitter_sentiment(symbol)

        # Load past decisions for this symbol (memory injection)
        history = _load_decision_history(symbol, limit=5)

        steps_done.append("data_collection")
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 2: Technical Analyst ─────────────────────────────────────
        _update_job(job_id, step="technical_analyst")
        tech_report = _run_technical_agent(symbol, indicators, multi_tf)
        steps_done.append("technical_analyst")
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 3: News Analyst ──────────────────────────────────────────
        _update_job(job_id, step="news_analyst")
        news_report = _run_news_agent(symbol, news_items)
        steps_done.append("news_analyst")
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 4: Sentiment Analyst ─────────────────────────────────────
        _update_job(job_id, step="sentiment_analyst")
        sentiment_report = _run_sentiment_agent(symbol, vix, twitter)
        steps_done.append("sentiment_analyst")
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 5: Bull Researcher ───────────────────────────────────────
        _update_job(job_id, step="bull_researcher")
        bull_report = _run_bull_researcher(symbol, tech_report, news_report, sentiment_report)
        steps_done.append("bull_researcher")
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 6: Bear Researcher ───────────────────────────────────────
        _update_job(job_id, step="bear_researcher")
        bear_report = _run_bear_researcher(symbol, tech_report, news_report, sentiment_report)
        steps_done.append("bear_researcher")
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 7: Fundamentals Analyst ───────────────────────────────────
        _update_job(job_id, step="fundamentals_analyst")
        fund_data = _get_fundamental_data(symbol)
        fundamentals_report = _run_fundamentals_analyst(symbol, fund_data, tech_report)
        steps_done.append("fundamentals_analyst")
        _update_job(job_id, steps_done=list(steps_done))

        # ── Step 8: Trader Decision ───────────────────────────────────────
        _update_job(job_id, step="trader_decision")
        decision = _run_trader_decision(
            symbol, indicators, tech_report, news_report,
            sentiment_report, bull_report, bear_report,
            fundamentals_report,
            history=history,
        )
        steps_done.append("trader_decision")

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
            },
            "decision_history": history,
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
        # Persist to DB (non-blocking, best-effort)
        _save_decision_to_db(job_id, symbol, exchange, result)
        logger.info("trading_agents: job %s completed for %s", job_id, symbol)

    except Exception as e:
        logger.exception("trading_agents: job %s failed: %s", job_id, e)
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

def start_analysis(symbol: str, exchange: str = "NSE") -> str:
    """
    Validate inputs, create a job, start the pipeline in a daemon thread.
    Returns the job_id for polling.

    Raises ValueError for invalid symbol input.
    """
    clean_symbol   = _safe_symbol(symbol)
    clean_exchange = _safe_symbol(exchange) if exchange else "NSE"

    job_id = _new_job(clean_symbol, clean_exchange)
    thread = threading.Thread(
        target=run_analysis_pipeline,
        args=(job_id, clean_symbol, clean_exchange),
        name=f"trading-agents-{job_id[:8]}",
        daemon=True,
    )
    thread.start()
    logger.info("trading_agents: started job %s for %s:%s", job_id, clean_exchange, clean_symbol)
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
