import json
import logging
import os
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.core.market.candles import fetch_15m_candles, fetch_daily_candles, fetch_5m_candles, fetch_1h_candles
from app.core.market.zerodha_historic_fetcher import (
    fetch_and_store_daily_vix,
    initialize_vix_historic_data,
)
from app.core.exit.auto_exit import run_auto_exit
from app.core.market.expiry_exit import _expiry_day_exit_job

logger = logging.getLogger(__name__)

# ✅ ONE global scheduler
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

_DISCOVERY_DEFAULT_TIMEFRAMES = ("Day", "1 Hour", "15 Min")


def _discovery_state_path() -> Path:
    raw = os.getenv("STRATEGY_DISCOVERY_STATE_FILE", "").strip()
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parents[2] / "data" / "strategy_discovery_progress.json"


def _load_discovery_state() -> dict:
    path = _discovery_state_path()
    default_state = {"version": 1, "runs": 0, "strategy_batches": {}}
    if not path.exists():
        return default_state

    try:
        with path.open("r", encoding="utf-8") as handle:
            state = json.load(handle)
    except Exception as exc:
        logger.warning("⚠️ Could not read strategy discovery state '%s': %s", path, exc)
        return default_state

    if not isinstance(state, dict):
        return default_state

    state.setdefault("version", 1)
    state.setdefault("runs", 0)
    state.setdefault("strategy_batches", {})
    return state


def _save_discovery_state(state: dict) -> None:
    path = _discovery_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, default=str)


def _discovery_timeframes() -> list[str]:
    raw = os.getenv("STRATEGY_DISCOVERY_TIMEFRAMES", ", ".join(_DISCOVERY_DEFAULT_TIMEFRAMES)).strip()
    requested = [item.strip() for item in raw.split(",") if item.strip()]
    valid_timeframes = {"Day", "1 Hour", "15 Min", "5 Min", "1 Min"}

    resolved: list[str] = []
    for timeframe in requested:
        if timeframe in valid_timeframes and timeframe not in resolved:
            resolved.append(timeframe)

    return resolved or list(_DISCOVERY_DEFAULT_TIMEFRAMES)


def _interleave_discovery_candidates(candidates_by_timeframe: dict[str, list[dict]]) -> list[dict]:
    ordered_timeframes = [tf for tf, items in candidates_by_timeframe.items() if items]
    if not ordered_timeframes:
        return []

    combined: list[dict] = []
    max_len = max(len(candidates_by_timeframe[tf]) for tf in ordered_timeframes)
    for idx in range(max_len):
        for timeframe in ordered_timeframes:
            items = candidates_by_timeframe.get(timeframe) or []
            if idx >= len(items):
                continue
            combined.append(items[idx])
    return combined


def _slice_discovery_batch(items: list, *, start_offset: int = 0, batch_size: int = 50) -> dict:
    total = len(items)
    if total <= 0:
        return {
            "items": [],
            "total": 0,
            "start_offset": 0,
            "end_offset": 0,
            "next_offset": 0,
            "completed_cycle": True,
        }

    batch_size = max(1, int(batch_size or 1))
    start_offset = max(0, min(int(start_offset or 0), total - 1))
    end_offset = min(start_offset + batch_size, total)

    return {
        "items": list(items[start_offset:end_offset]),
        "total": total,
        "start_offset": start_offset,
        "end_offset": end_offset,
        "next_offset": 0 if end_offset >= total else end_offset,
        "completed_cycle": end_offset >= total,
    }


def _qualifies_for_auto_save(
    item: dict,
    *,
    min_score: float,
    min_annual_return: float,
    min_trades: int,
    max_drawdown: float,
) -> bool:
    summary = item.get("summary") or {}
    if item.get("error"):
        return False
    if float(item.get("score") or -1e9) < min_score:
        return False
    if float(summary.get("annual_return_pct") or 0.0) < min_annual_return:
        return False
    if int(summary.get("total_trades") or 0) < min_trades:
        return False
    if float(summary.get("max_drawdown_pct") or 0.0) > max_drawdown:
        return False
    return True


def _leaderboard_sort_key(row: dict) -> tuple:
    return (
        float(row.get("score") or -1e9),
        float(row.get("annual_return_pct") or 0.0),
        -float(row.get("max_drawdown_pct") or 0.0),
        float(row.get("sharpe_ratio") or 0.0),
        float(row.get("total_return_pct") or 0.0),
    )


def _leaderboard_entry_from_ranked_item(item: dict) -> dict | None:
    strategy = item.get("strategy") or {}
    summary = item.get("summary") or {}
    name = str(strategy.get("name") or "").strip()
    if not name or item.get("error"):
        return None
    if int(summary.get("total_trades") or 0) <= 0:
        return None

    return {
        "name": name,
        "timeframe": strategy.get("timeframe"),
        "universe": strategy.get("universe"),
        "score": float(item.get("score") or -1e9),
        "annual_return_pct": float(summary.get("annual_return_pct") or 0.0),
        "total_return_pct": float(summary.get("total_return_pct") or 0.0),
        "max_drawdown_pct": float(summary.get("max_drawdown_pct") or 0.0),
        "sharpe_ratio": float(summary.get("sharpe_ratio") or 0.0),
        "total_trades": int(summary.get("total_trades") or 0),
        "final_capital": item.get("final_capital"),
    }


def _merge_discovery_leaderboard(existing_rows: list[dict] | None, ranked_batch: list[dict] | None, *, top_n: int = 5) -> list[dict]:
    merged: dict[str, dict] = {}

    for row in existing_rows or []:
        name = str((row or {}).get("name") or "").strip()
        if name:
            merged[name] = dict(row)

    for item in ranked_batch or []:
        row = _leaderboard_entry_from_ranked_item(item)
        if not row:
            continue
        current = merged.get(row["name"])
        if current is None or _leaderboard_sort_key(row) > _leaderboard_sort_key(current):
            merged[row["name"]] = row

    return sorted(merged.values(), key=_leaderboard_sort_key, reverse=True)[: max(1, int(top_n or 5))]


def _update_twitter_sentiment():
    """Update Twitter sentiment data from tracked accounts."""
    logger.info("⏱️ Running Twitter sentiment update")
    
    db = SessionLocal()
    try:
        from app.services.twitter_service import get_twitter_service
        from app.db.models_twitter import TwitterSentiment, TwitterAlert
        from datetime import datetime, timedelta
        
        twitter_service = get_twitter_service()
        
        if not twitter_service.enabled:
            logger.debug("⏸️ Twitter API not configured - skipping sentiment update")
            return
        
        # Fetch recent tweets
        tweets = twitter_service.fetch_tweets_from_accounts(db, max_tweets=50)
        
        # Process each tweet
        processed_count = 0
        high_impact_count = 0
        alerts_created = 0
        
        for tweet_data in tweets:
            sentiment = twitter_service.process_tweet(db, tweet_data)
            if sentiment:
                processed_count += 1
                
                # Create alerts for high-impact tweets
                if sentiment.high_impact and not sentiment.alert_sent:
                    alert = TwitterAlert(
                        tweet_id=sentiment.tweet_id,
                        symbol=sentiment.primary_symbol or "MARKET",
                        alert_type="high_impact" if not sentiment.breaking_news else "breaking_news",
                        title=f"High Impact: {sentiment.primary_symbol} {sentiment.sentiment.upper()}",
                        message=sentiment.text,
                        severity="high" if sentiment.engagement_score > 70 else "medium",
                        username=sentiment.username,
                        account_credibility=tweet_data.get("credibility", 50.0),
                        sentiment=sentiment.sentiment,
                        engagement_score=sentiment.engagement_score,
                        sent=False
                    )
                    db.add(alert)
                    alerts_created += 1
                    high_impact_count += 1
                    
                    # Mark alert as sent
                    sentiment.alert_sent = True
                    db.commit()
        
        db.commit()
        
        logger.info(
            f"✅ Twitter sentiment updated: {processed_count} tweets processed, "
            f"{high_impact_count} high-impact, {alerts_created} alerts created"
        )
    except ImportError:
        logger.debug("⏸️ Twitter service not available - skipping update")
    except Exception as e:
        logger.exception(f"❌ Twitter sentiment update failed: {e}")
    finally:
        db.close()


def _update():
    logger.info("⏱️ Running 15m candle update")

    db = SessionLocal()
    try:
        fetch_15m_candles(db, "NIFTY")
        fetch_15m_candles(db, "BANKNIFTY")
        fetch_15m_candles(db, "FINNIFTY")
        # Also fetch Nifty IT sector stocks for IT-specific strategies
        nifty_it_symbols = ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "COFORGE", "PERSISTENT", "MPHASIS"]
        for sym in nifty_it_symbols:
            try:
                fetch_15m_candles(db, sym)
            except Exception as e:
                logger.warning(f"\u26a0\ufe0f Skip IT candle {sym}: {e}")
        logger.info("\u2705 15m candles updated (indices + NIFTY_IT)")
    except Exception:
        logger.exception("❌ Candle update failed")
    finally:
        db.close()


def _update_daily_vix():
    """Update daily VIX data and calculate IV Rank."""
    logger.info("⏱️ Running daily VIX update")
    
    db = SessionLocal()
    try:
        success = fetch_and_store_daily_vix(db)
        if success:
            logger.info("✅ Daily VIX updated and IV Rank calculated")
        else:
            logger.warning("⚠️ Daily VIX update partially failed")
    except Exception:
        logger.exception("❌ Daily VIX update failed")
    finally:
        db.close()


def _get_daily_symbols() -> list[str]:
    raw = os.getenv("STOCK_DAILY_SYMBOLS", "").strip()
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]

    # NIFTY 100 stocks (verified Zerodha NSE trading symbols)
    return [
        # Top 10 by weight
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
        "BHARTIARTL", "SBIN", "ITC", "HINDUNILVR", "KOTAKBANK",
        # Banks & NBFC
        "AXISBANK", "INDUSINDBK", "BAJFINANCE", "BAJAJFINSV",
        "BANKBARODA", "PNB", "IDFCFIRSTB", "FEDERALBNK", "AUBANK",
        "CHOLAFIN", "SBICARD",
        # Insurance
        "SBILIFE", "HDFCLIFE", "ICICIPRULI",
        # IT
        "WIPRO", "HCLTECH", "TECHM", "LTM", "MPHASIS", "PERSISTENT",
        # Auto
        "MARUTI", "TMPV", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT", "M&M",
        # FMCG
        "NESTLEIND", "BRITANNIA", "MARICO", "DABUR", "GODREJCP",
        "TATACONSUM", "COLPAL",
        # Pharma
        "SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "APOLLOHOSP",
        "LUPIN", "TORNTPHARM", "BIOCON",
        # Energy & Oil
        "NTPC", "POWERGRID", "ONGC", "BPCL", "IOC", "GAIL", "TATAPOWER",
        # Metals & Mining
        "JSWSTEEL", "TATASTEEL", "HINDALCO", "VEDL", "COALINDIA", "NMDC",
        # Cement
        "ULTRACEMCO", "SHREECEM", "AMBUJACEM", "ACC",
        # Infra & Engineering
        "LT", "ABB", "SIEMENS", "HAL", "BEL",
        # Consumer & Retail
        "TITAN", "ASIANPAINT", "PIDILITIND", "HAVELLS", "VOLTAS", "DMART", "TRENT",
        # Conglomerates & Others
        "ADANIENT", "ADANIPORTS", "GRASIM", "UPL",
        "NAUKRI", "ETERNAL", "IRCTC", "JIOFIN", "PAYTM",
        # Telecom & Media
        "IDEA",
    ]


def _update_daily_candles():
    """Update daily candles for swing trading."""
    days = int(os.getenv("DAILY_CANDLES_DAYS", "900"))
    symbols = _get_daily_symbols()
    logger.info("⏱️ Running daily candle update | symbols=%d | days=%d", len(symbols), days)

    db = SessionLocal()
    success = 0
    failed = 0
    try:
        for symbol in symbols:
            try:
                fetch_daily_candles(db, symbol, days=days)
                success += 1
            except Exception as e:
                failed += 1
                logger.warning(f"\u26a0\ufe0f Skip {symbol}: {e}")
        logger.info(f"\u2705 Daily candles updated: {success} ok, {failed} skipped")
    except Exception:
        logger.exception("❌ Daily candles update failed")
    finally:
        db.close()


def _auto_exit_check():
    """Check TP/SL/Trailing stops and auto-exit positions."""
    db = SessionLocal()
    try:
        exited = run_auto_exit(db)
        if exited:
            logger.info(f"🚪 Auto-exited {len(exited)} position(s): {exited}")
    except Exception:
        logger.exception("❌ Auto-exit check failed")
    finally:
        db.close()


def _update_5m_candles():
    """Update 5-minute candles for intraday strategies."""
    logger.info("⏱️ Running 5m candle update")
    db = SessionLocal()
    try:
        symbols = _get_daily_symbols()[:30]  # Top 30 liquid stocks
        for sym in ["NIFTY", "BANKNIFTY", "FINNIFTY"] + symbols:
            try:
                fetch_5m_candles(db, sym, days=30)
            except Exception as e:
                logger.warning(f"⚠️ Skip 5m {sym}: {e}")
        logger.info("✅ 5m candles updated")
    except Exception:
        logger.exception("❌ 5m candle update failed")
    finally:
        db.close()


def _update_1h_candles():
    """Update 1-hour candles for swing/intraday strategies."""
    logger.info("⏱️ Running 1h candle update")
    db = SessionLocal()
    try:
        symbols = _get_daily_symbols()
        for sym in ["NIFTY", "BANKNIFTY", "FINNIFTY"] + symbols:
            try:
                fetch_1h_candles(db, sym, days=60)
            except Exception as e:
                logger.warning(f"⚠️ Skip 1h {sym}: {e}")
        logger.info("✅ 1h candles updated")
    except Exception:
        logger.exception("❌ 1h candle update failed")
    finally:
        db.close()


def _train_ml_model():
    """Train stock ML model on NIFTY100 symbols with 500+ days of daily data (weekly job)."""
    logger.info("⏱️ Running ML model training with 500+ days of NIFTY100 data")
    
    db = SessionLocal()
    try:
        from app.core.ml.config import StockMLConfig
        from app.core.ml.stock_model import train_stock_model
        from app.db.models_candles import CandleDaily
        from sqlalchemy import func
        
        config = StockMLConfig()
        if not config.enabled:
            logger.info("⏩ ML training skipped (STOCK_ML_ENABLED=false)")
            return
        
        # Get NIFTY100 symbols (top 100 by data volume with 500+ days minimum)
        try:
            query = db.query(CandleDaily.symbol, func.count(CandleDaily.id).label('count')).group_by(
                CandleDaily.symbol
            ).having(func.count(CandleDaily.id) >= 500).order_by(
                func.count(CandleDaily.id).desc()
            ).limit(150)  # Get up to 150 symbols for better training
            
            symbols = [row[0] for row in query.all()]
            
            if not symbols:
                # Fallback: Get all symbols if 500 days not available yet
                symbols = [s[0] for s in db.query(CandleDaily.symbol).distinct().all()]
                if len(symbols) > 100:
                    symbols = symbols[:100]
        except Exception as e:
            logger.warning(f"⚠️ Error getting NIFTY100 symbols: {e}")
            symbols = _get_daily_symbols()
        
        if not symbols:
            logger.warning("⚠️ No symbols with 500+ days of data for ML training")
            return
        
        logger.info(f"📊 Training ML model on {len(symbols)} NIFTY100 symbols with 500+ days of daily candle data")
        
        # Train on daily timeframe (better for swing trading ML)
        metadata = train_stock_model(db, symbols, config)
        
        accuracy = metadata.get('accuracy', 'N/A')
        precision = metadata.get('precision', 'N/A')
        total_samples = metadata.get('total_samples', 0)
        logger.info(f"✅ ML model trained: Accuracy={accuracy}, Precision={precision}, Samples={total_samples}")
    except ImportError:
        logger.warning("⚠️ ML modules not available, skipping training")
    except Exception:
        logger.exception("❌ ML model training failed")
    finally:
        db.close()


def start_candle_scheduler():
    if scheduler.running:
        logger.warning("⚠️ Candle scheduler already running")
        return

    scheduler.add_job(
        func=_update,
        trigger="cron",
        minute="*/5",
        id="candle_15m_job",          # ✅ important
        replace_existing=True,        # ✅ important
        max_instances=1,              # ✅ prevents overlap
        coalesce=True,                # ✅ merges missed runs
    )

    scheduler.start()
    logger.info("🟢 Candle scheduler started")
    _update()  # Initial run


def start_vix_scheduler(delay_minutes: int = 2):
    """Start daily VIX update scheduler (runs at market close).
    
    Args:
        delay_minutes: Delay in minutes before running initial VIX update (default: 2 minutes)
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start VIX scheduler: main scheduler not running")
        return
    
    # Schedule daily VIX update at 3:45 PM IST (market close is 3:30 PM)
    scheduler.add_job(
        func=_update_daily_vix,
        trigger="cron",
        hour=15,
        minute=45,
        id="daily_vix_job",
        replace_existing=True,
        max_instances=1,
    )
    
    # Schedule initial run after delay to avoid blocking startup
    if delay_minutes > 0:
        from datetime import datetime, timedelta
        run_time = datetime.now() + timedelta(minutes=delay_minutes)
        scheduler.add_job(
            func=_update_daily_vix,
            trigger="date",
            run_date=run_time,
            id="vix_initial_run",
            replace_existing=True,
        )
        logger.info(f"🟢 VIX scheduler started (daily: 3:45 PM IST, initial run: {delay_minutes}m delay)")
    else:
        logger.info("🟢 VIX daily scheduler started (3:45 PM IST)")
        _update_daily_vix()


def start_daily_candles_scheduler(delay_minutes: int = 5):
    """Start daily candle update scheduler (runs after market close).
    
    Args:
        delay_minutes: Delay in minutes before running initial backfill (default: 5 minutes)
                      Set to 0 to run immediately on startup
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start daily candles scheduler: main scheduler not running")
        return

    scheduler.add_job(
        func=_update_daily_candles,
        trigger="cron",
        day_of_week="mon-fri",
        hour=15,
        minute=50,
        id="daily_candles_job",
        replace_existing=True,
        max_instances=1,
    )

    # Schedule initial backfill after delay to avoid blocking startup
    if delay_minutes > 0:
        from datetime import datetime, timedelta
        run_time = datetime.now() + timedelta(minutes=delay_minutes)
        scheduler.add_job(
            func=_update_daily_candles,
            trigger="date",
            run_date=run_time,
            id="daily_candles_initial_run",
            replace_existing=True,
        )
        logger.info(f"🟢 Daily candles scheduler started (daily: 3:50 PM IST, initial backfill: {delay_minutes}m delay)")
    else:
        logger.info("🟢 Daily candles scheduler started (3:50 PM IST)")
        _update_daily_candles()


def initialize_vix_data():
    """Initialize VIX historic data on startup."""
    logger.info("🔄 Initializing VIX historic data...")
    
    db = SessionLocal()
    try:
        success = initialize_vix_historic_data(db)
        if success:
            logger.info("✅ VIX historic data initialized")
            return True
        else:
            logger.warning("⚠️ Could not initialize VIX data from Zerodha")
            logger.info("   → Try running fetch_vix_historic_from_zerodha manually")
            return False
    except Exception as e:
        logger.exception(f"❌ VIX initialization failed: {e}")
        return False
    finally:
        db.close()


def start_auto_exit_scheduler():
    """Start TP/SL/Trailing stop monitoring (runs every 10 seconds during market hours 9:15 AM - 3:30 PM)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start auto-exit scheduler: main scheduler not running")
        return
    
    # Run every 10 seconds, but only during market hours (9:15 AM - 3:30 PM IST)
    scheduler.add_job(
        func=_auto_exit_check,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",  # 9 AM to 3 PM
        second="*/10",  # Every 10 seconds
        id="auto_exit_job",
        replace_existing=True,
        max_instances=1,
    )
    
    logger.info("🟢 Auto-exit scheduler started (every 10 seconds, market hours only)")


def start_ml_training_scheduler():
    """Start weekly ML model training (runs every Sunday at 4 AM IST)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start ML training scheduler: main scheduler not running")
        return
    
    scheduler.add_job(
        func=_train_ml_model,
        trigger="cron",
        day_of_week="sun",  # Sunday
        hour=4,  # 4 AM IST
        minute=0,
        id="ml_training_job",
        replace_existing=True,
        max_instances=1,
    )
    
    logger.info("🟢 ML training scheduler started (Sundays at 4 AM IST)")


def start_intraday_candles_scheduler(delay_minutes: int = 3):
    """Start 5m and 1h candle update schedulers.
    - 5m candles: every 10 minutes during market hours (top 30 stocks + indices)
    - 1h candles: every hour during market hours (all NIFTY100 + indices)
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start intraday candles scheduler: main scheduler not running")
        return

    # 5-minute candles: fetch every 10 minutes during market hours
    scheduler.add_job(
        func=_update_5m_candles,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute="*/10",
        id="candle_5m_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # 1-hour candles: fetch every hour during market hours
    scheduler.add_job(
        func=_update_1h_candles,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",
        minute=5,  # 5 minutes past each hour
        id="candle_1h_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # Initial backfill after delay
    if delay_minutes > 0:
        from datetime import datetime, timedelta
        run_5m = datetime.now() + timedelta(minutes=delay_minutes)
        run_1h = datetime.now() + timedelta(minutes=delay_minutes + 1)
        scheduler.add_job(
            func=_update_5m_candles,
            trigger="date",
            run_date=run_5m,
            id="candle_5m_initial_run",
            replace_existing=True,
        )
        scheduler.add_job(
            func=_update_1h_candles,
            trigger="date",
            run_date=run_1h,
            id="candle_1h_initial_run",
            replace_existing=True,
        )

    logger.info("🟢 Intraday candles scheduler started (5m: every 10min, 1h: every hour)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("🛑 Scheduler stopped")

# ── ADD THIS FUNCTION to scheduler.py ───────────────────────────────────────
def start_expiry_exit_scheduler():
    """
    Phase 2: Expiry-day force-exit job.

    Runs every minute during market hours (9:15 AM–3:20 PM IST, Mon–Fri).
    The job itself only acts when it's past the 3:15 PM cutoff AND open
    positions exist that expire today — so it's a no-op on non-expiry days.
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start expiry-exit scheduler: main scheduler not running")
        return

    scheduler.add_job(
        func=_expiry_day_exit_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",       # 9 AM to 3 PM
        minute="*",        # every minute
        id="expiry_exit_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info("🟢 Expiry-day exit scheduler started (every 1 min, 9:15–3:20 PM IST)")


def start_twitter_sentiment_scheduler():
    """
    Start Twitter sentiment monitoring (runs every 15 minutes during market hours).
    
    Fetches tweets from tracked accounts, analyzes sentiment, and creates alerts
    for high-impact tweets.
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start Twitter sentiment scheduler: main scheduler not running")
        return
    
    # Run every 15 minutes during market hours (9:15 AM - 3:30 PM IST)
    scheduler.add_job(
        func=_update_twitter_sentiment,
        trigger="cron",
        day_of_week="mon-fri",
        hour="9-15",  # 9 AM to 3 PM
        minute="*/15",  # Every 15 minutes
        id="twitter_sentiment_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    
    logger.info("🟢 Twitter sentiment scheduler started (every 15 min, market hours only)")


def _strategy_discovery_job():
    """Run batched multi-timeframe strategy discovery and persist the cursor between runs."""
    universe = os.getenv("STRATEGY_DISCOVERY_UNIVERSE", "NIFTY50").strip() or "NIFTY50"
    timeframes = _discovery_timeframes()
    max_candidates = max(int(os.getenv("STRATEGY_DISCOVERY_MAX_CANDIDATES", "500") or 500), 50)
    batch_size = max(int(os.getenv("STRATEGY_DISCOVERY_BATCH_SIZE", "50") or 50), 1)
    top_n = max(int(os.getenv("STRATEGY_DISCOVERY_TOP_N", "5") or 5), 1)
    min_score = float(os.getenv("STRATEGY_DISCOVERY_MIN_SCORE", "30") or 30)
    min_annual_return = float(os.getenv("STRATEGY_DISCOVERY_MIN_ANNUAL_RETURN", "8") or 8)
    min_trades = max(int(os.getenv("STRATEGY_DISCOVERY_MIN_TRADES", "8") or 8), 1)
    max_drawdown = float(os.getenv("STRATEGY_DISCOVERY_MAX_DRAWDOWN", "25") or 25)
    progress = _load_discovery_state()
    state_key = f"{universe}|{'|'.join(timeframes)}"
    state_row = dict((progress.get("strategy_batches") or {}).get(state_key) or {})
    cursor = int(state_row.get("next_offset", 0) or 0)

    logger.info(
        "⏱️ Running batched strategy discovery | universe=%s | timeframes=%s | batch_size=%s | cursor=%s",
        universe,
        ", ".join(timeframes),
        batch_size,
        cursor,
    )

    db = SessionLocal()
    try:
        from app.api.routes.condition_scanner import BacktestRequest, _run_backtest_for_strategy_payload
        from app.core.condition_strategy_lab import generate_candidate_strategies, score_backtest_summary, select_diverse_top
        from app.core.utils.time import now_ist
        from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest

        candidates_by_timeframe = {
            timeframe: generate_candidate_strategies(
                timeframe=timeframe,
                universe=universe,
                max_candidates=max_candidates,
            )
            for timeframe in timeframes
        }
        candidate_pool = _interleave_discovery_candidates(candidates_by_timeframe)[:max_candidates]
        batch = _slice_discovery_batch(candidate_pool, start_offset=cursor, batch_size=batch_size)
        batch_candidates = batch["items"]

        if not batch_candidates:
            logger.info("⏩ Strategy discovery skipped: no candidates available")
            return

        req = BacktestRequest(
            initial_capital=100000.0,
            position_size_pct=10.0,
            max_open_trades=5,
        )

        ranked: list[dict] = []
        for candidate in batch_candidates:
            try:
                result = _run_backtest_for_strategy_payload(candidate, req, db)
                summary = result.get("summary") or {}
                ranked.append(
                    {
                        "strategy": candidate,
                        "summary": summary,
                        "score": score_backtest_summary(summary),
                        "final_capital": result.get("final_capital"),
                        "error": result.get("error"),
                    }
                )
            except Exception as exc:
                ranked.append(
                    {
                        "strategy": candidate,
                        "summary": {},
                        "score": -1e9,
                        "final_capital": None,
                        "error": str(exc),
                    }
                )

        ranked.sort(
            key=lambda item: (
                item["score"],
                float((item.get("summary") or {}).get("annual_return_pct") or 0.0),
                -float((item.get("summary") or {}).get("max_drawdown_pct") or 0.0),
                float((item.get("summary") or {}).get("sharpe_ratio") or 0.0),
            ),
            reverse=True,
        )

        rolling_top_results = _merge_discovery_leaderboard(
            state_row.get("rolling_top_results") or [],
            ranked,
            top_n=max(top_n, 5),
        )

        qualified = [
            item
            for item in ranked
            if _qualifies_for_auto_save(
                item,
                min_score=min_score,
                min_annual_return=min_annual_return,
                min_trades=min_trades,
                max_drawdown=max_drawdown,
            )
        ]

        preview = select_diverse_top(
            qualified if qualified else ranked,
            top_n=top_n,
            max_per_family=1,
            fill_remaining=True,
        )
        to_save = select_diverse_top(
            qualified,
            top_n=top_n,
            max_per_family=1,
            fill_remaining=False,
        ) if qualified else []

        existing_names = {name for (name,) in db.query(ConditionStrategy.name).all()}
        saved: list[str] = []
        for rank, item in enumerate(to_save, start=1):
            strategy = item["strategy"]
            base_name = f"[Auto] {strategy['name']}"
            save_name = base_name
            suffix = 2
            while save_name in existing_names:
                save_name = f"{base_name} #{suffix}"
                suffix += 1

            summary = item.get("summary") or {}
            row = ConditionStrategy(
                name=save_name,
                description=(
                    f"Batched auto-discovery #{rank} | Timeframe={strategy.get('timeframe')} | "
                    f"Score={item['score']} | AnnualReturn={summary.get('annual_return_pct', 0):.1f}% | "
                    f"Sharpe={summary.get('sharpe_ratio', 0)}"
                ),
                strategy_type=strategy.get("strategy_type", "Equity Swing"),
                direction=strategy.get("direction", "BUY"),
                timeframe=strategy.get("timeframe", "Day"),
                universe=strategy.get("universe", universe),
                instruments=strategy.get("instruments", []),
                entry_conditions=strategy.get("entry_conditions", []),
                exit_config=strategy.get("exit_config", {}),
                is_active=True,
                auto_scan_enabled=False,
                auto_amount=10000.0,
            )
            db.add(row)
            db.flush()

            bt = ConditionStrategyBacktest(
                strategy_id=row.id,
                strategy_name=save_name,
                start_date="",
                end_date="",
                initial_capital=100000.0,
                final_capital=item.get("final_capital"),
                result={
                    "summary": summary,
                    "strategy": strategy,
                    "discovery_batch": {
                        "start": batch["start_offset"],
                        "end": batch["end_offset"],
                        "total": batch["total"],
                    },
                },
            )
            db.add(bt)
            db.flush()
            row.last_backtest_at = now_ist()
            row.last_backtest_id = bt.id
            existing_names.add(save_name)
            saved.append(save_name)

        db.commit()

        state_row.update(
            {
                "last_run_at": now_ist().isoformat(),
                "next_offset": batch["next_offset"],
                "pool_total": batch["total"],
                "last_batch_start": batch["start_offset"],
                "last_batch_end": batch["end_offset"],
                "last_batch_tested": len(batch_candidates),
                "qualified_count": len(qualified),
                "saved_count": len(saved),
                "saved_names": saved,
                "completed_cycle": bool(batch["completed_cycle"]),
                "cycle_count": int(state_row.get("cycle_count", 0) or 0) + (1 if batch["completed_cycle"] else 0),
                "top_results": [
                    {
                        "name": item.get("strategy", {}).get("name"),
                        "timeframe": item.get("strategy", {}).get("timeframe"),
                        "score": item.get("score"),
                        "annual_return_pct": (item.get("summary") or {}).get("annual_return_pct"),
                        "max_drawdown_pct": (item.get("summary") or {}).get("max_drawdown_pct"),
                    }
                    for item in preview[:top_n]
                ],
                "rolling_top_results": rolling_top_results[: max(top_n, 5)],
            }
        )
        progress.setdefault("strategy_batches", {})[state_key] = state_row
        progress["runs"] = int(progress.get("runs", 0) or 0) + 1
        _save_discovery_state(progress)

        logger.info(
            "✅ Strategy discovery batch complete | tested=%s | qualified=%s | saved=%s | range=%s-%s/%s | next_offset=%s",
            len(batch_candidates),
            len(qualified),
            len(saved),
            batch["start_offset"] + 1,
            batch["end_offset"],
            batch["total"],
            batch["next_offset"],
        )

        try:
            from app.services.notifications import NotificationService

            svc = NotificationService(db)
            lines = [
                "🔬 <b>Batched Strategy Discovery</b>",
                f"Universe: {universe}",
                f"Timeframes: {', '.join(timeframes)}",
                f"Range: {batch['start_offset'] + 1}-{batch['end_offset']} / {batch['total']}",
                f"Qualified: {len(qualified)} | Saved: {len(saved)}",
            ]
            if rolling_top_results:
                lines.append("")
                lines.append("🏆 Rolling Top 5")
                for idx, row in enumerate(rolling_top_results[:5], start=1):
                    lines.append(
                        f"{idx}. {row.get('name')} [{row.get('timeframe')}] | "
                        f"score={row.get('score')} | annual={row.get('annual_return_pct')}%"
                    )
            elif preview:
                lines.append("")
                for idx, item in enumerate(preview[:top_n], start=1):
                    summary = item.get("summary") or {}
                    strategy = item.get("strategy") or {}
                    lines.append(
                        f"{idx}. {strategy.get('name')} [{strategy.get('timeframe')}] | "
                        f"score={item.get('score')} | return={summary.get('annual_return_pct', 0)}%"
                    )
            svc._send_telegram("\n".join(lines))
        except Exception:
            pass

    except Exception:
        logger.exception("❌ Strategy discovery job failed")
    finally:
        db.close()


def _strategy_decay_job():
    """Daily strategy decay check at 4:30 PM IST."""
    logger.info("⏱️ Running strategy decay check")
    db = SessionLocal()
    try:
        from app.core.strategy_decay import run_decay_check_and_notify
        run_decay_check_and_notify(db)
    except Exception:
        logger.exception("❌ Strategy decay job failed")
    finally:
        db.close()


def start_strategy_decay_scheduler():
    """Run strategy decay check daily at 4:30 PM IST (after discovery at 4:15)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start strategy decay scheduler: main scheduler not running")
        return
    scheduler.add_job(
        func=_strategy_decay_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=30,
        id="strategy_decay_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("🟢 Strategy decay scheduler started (Mon-Fri at 4:30 PM IST)")


def start_strategy_discovery_scheduler():
    """Run batched strategy discovery daily at 4:15 PM IST (after candles + VIX are updated)."""
    if not scheduler.running:
        logger.warning("⚠️ Cannot start strategy discovery scheduler: main scheduler not running")
        return

    scheduler.add_job(
        func=_strategy_discovery_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=15,
        id="strategy_discovery_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("🟢 Strategy discovery scheduler started (Mon-Fri at 4:15 PM IST)")


def start_neon_sync_scheduler():
    """
    Start daily delta sync: local Docker Postgres → Neon (cloud backup).
    Runs once a day at 3:15 PM IST.

    Persistent catch-up: the last successful sync timestamp is written to
    data/neon_sync_state.json.  If the service was down for N days, the next
    run automatically syncs all rows from the entire missed window — no data
    is ever lost regardless of how many consecutive runs were skipped.
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start Neon sync scheduler: main scheduler not running")
        return

    from app.services.neon_sync import run_delta_sync

    scheduler.add_job(
        func=run_delta_sync,
        trigger="cron",
        hour=15,     # 3 PM IST
        minute=15,   # :15
        timezone="Asia/Kolkata",
        id="neon_sync_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,   # if multiple triggers fired while down, run only once
        misfire_grace_time=3600,  # allow up to 1 h late start (e.g. slow boot)
    )

    logger.info("🟢 Neon delta sync scheduler started (daily at 3:15 PM IST)")


def _zerodha_auto_login_job():
    """Auto-refresh Zerodha access token at 8 AM IST before market opens."""
    logger.info("⏱️ Running Zerodha auto-login...")
    db = SessionLocal()
    try:
        from app.services.zerodha_auto_login import run_auto_login
        token = run_auto_login(db)
        if token:
            logger.info("✅ Zerodha token refreshed successfully")
        else:
            logger.error("❌ Zerodha auto-login failed — check credentials and redirect URL")
    except Exception as e:
        logger.exception("❌ Zerodha auto-login job crashed")
    finally:
        db.close()


def start_zerodha_auto_login_scheduler():
    """
    Schedule daily Zerodha auto-login at 8:00 AM IST (before market opens at 9:15 AM).
    Only activates if ZERODHA_USER_ID and ZERODHA_PASSWORD are set in .env.
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start Zerodha auto-login scheduler: main scheduler not running")
        return

    user_id = os.getenv("ZERODHA_USER_ID", "").strip()
    password = os.getenv("ZERODHA_PASSWORD", "").strip()
    if not user_id or not password:
        logger.info("⏭️  Zerodha auto-login skipped (ZERODHA_USER_ID / ZERODHA_PASSWORD not set)")
        return

    scheduler.add_job(
        func=_zerodha_auto_login_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8,
        minute=0,
        id="zerodha_auto_login_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info("🟢 Zerodha auto-login scheduler started (Mon-Fri at 8:00 AM IST)")


def start_watchlist_analysis_scheduler():
    """
    Schedule daily AI agent analysis for all watchlist symbols at 8:45 AM IST (Mon-Fri).
    Runs before market open (9:15 AM) so decisions are ready when trading starts.
    """
    if not scheduler.running:
        logger.warning("⚠️ Cannot start watchlist analysis scheduler: main scheduler not running")
        return

    def _watchlist_analysis_job():
        try:
            from app.services.trading_agents import run_watchlist_analysis
            count = run_watchlist_analysis()
            logger.info("🤖 Watchlist AI analysis: started %d jobs", count)
        except Exception as e:
            logger.warning("⚠️ Watchlist AI analysis job failed: %s", e)

    scheduler.add_job(
        func=_watchlist_analysis_job,
        trigger="cron",
        day_of_week="mon-fri",
        hour=8,
        minute=45,
        id="watchlist_ai_analysis_job",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("🟢 Watchlist AI analysis scheduler started (Mon-Fri at 8:45 AM IST)")

