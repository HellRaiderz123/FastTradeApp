import logging
import os
import re
import time
from datetime import timedelta
from typing import Any

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.api.routes.ai_chat import _call_llm
from app.core.utils.time import now_ist
from app.db.models_alexa import AlexaInteractionLog, AlexaMemory
from app.db.models_notification import Notification
from app.db.models_twitter import TwitterAlert
from app.db.models_watchlist import Watchlist
from app.db.session import SessionLocal
from app.services.alexa_proactive_alerts import get_alexa_proactive_alert_service
from app.services.llm_service import call_llm
from app.services.market_data import get_option_chain, get_spot
from app.services.rss_feed_service import get_rss_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alexa", tags=["Alexa"])

ALEXA_SKILL_NAME = os.getenv("ALEXA_SKILL_NAME", "Fast Trade AI")
ALEXA_ALLOWED_SKILL_ID = os.getenv("ALEXA_ALLOWED_SKILL_ID", "").strip()
ALEXA_ENFORCE_SKILL_ID = os.getenv("ALEXA_ENFORCE_SKILL_ID", "false").strip().lower() in {"1", "true", "yes", "on"}
ALEXA_VOICE_TRADING_ENABLED = os.getenv("ALEXA_VOICE_TRADING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
ALEXA_PROGRESSIVE_RESPONSE_ENABLED = os.getenv("ALEXA_PROGRESSIVE_RESPONSE_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_REPROMPT = "How can I help with Fast Trade?"
DEFAULT_REPROMPT_HI = "मैं Fast Trade में कैसे मदद कर सकती हूँ?"
TRADING_KEYWORDS = {
    "portfolio", "position", "positions", "trade", "trades", "trading", "market", "stock", "stocks",
    "option", "options", "nifty", "bank nifty", "sensex", "risk", "profit", "loss", "scanner",
    "watchlist", "signal", "candlestick", "rsi", "macd", "zerodha", "fast trade", "fasttrade",
    "sentiment", "gainer", "loser", "earnings",
}
TRADE_ACTION_KEYWORDS = {
    "buy", "sell", "exit", "close", "square off", "book profit", "paper trade", "order", "enter trade",
}
ALERT_SUMMARY_KEYWORDS = {
    "alert", "alerts", "notification", "notifications", "warning", "warnings", "signal", "signals", "scanner",
    "breaking news", "important update", "risk alert",
}
MEMORY_TYPE_TO_KEY = {"note": "notes", "reminder": "reminders", "journal": "journal"}
WATCHLIST_SYMBOL_ALIASES = {
    "tcs": "TCS",
    "t c s": "TCS",
    "tata consultancy services": "TCS",
    "reliance": "RELIANCE",
    "reliance industries": "RELIANCE",
    "infosys": "INFY",
    "infy": "INFY",
    "hdfc bank": "HDFCBANK",
    "h d f c bank": "HDFCBANK",
    "icici bank": "ICICIBANK",
    "state bank of india": "SBIN",
    "sbi": "SBIN",
}
ALEXA_LIVE_MARKET_CONTEXT_ENABLED = os.getenv("ALEXA_LIVE_MARKET_CONTEXT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}
try:
    ALEXA_MAX_CONVERSATION_TURNS = max(2, min(10, int(os.getenv("ALEXA_MAX_CONVERSATION_TURNS", "5"))))
except ValueError:
    ALEXA_MAX_CONVERSATION_TURNS = 5
_USER_MEMORY: dict[str, dict[str, list[str]]] = {}
_USER_CONVERSATIONS: dict[str, list[dict[str, str]]] = {}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_for_voice(text: str) -> str:
    if not text:
        return "Sorry, I could not generate a response right now."

    cleaned = text.replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.replace("₹", " rupees ")
    cleaned = cleaned.replace("P&L", "profit and loss")
    cleaned = cleaned.replace("&", " and ")
    cleaned = cleaned.replace("%", " percent")
    cleaned = re.sub(r"[*_`#>-]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > 700:
        cleaned = cleaned[:697].rsplit(" ", 1)[0] + "..."

    return cleaned or "Sorry, I could not generate a response right now."


def _response(
    text: str,
    reprompt: str | None = None,
    end_session: bool = False,
    session_attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spoken_text = _normalize_for_voice(text)
    payload: dict[str, Any] = {
        "version": "1.0",
        "sessionAttributes": session_attributes or {},
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": spoken_text,
            },
            "card": {
                "type": "Simple",
                "title": ALEXA_SKILL_NAME,
                "content": spoken_text,
            },
            "shouldEndSession": end_session,
        },
    }

    if reprompt and not end_session:
        payload["response"]["reprompt"] = {
            "outputSpeech": {
                "type": "PlainText",
                "text": _normalize_for_voice(reprompt),
            }
        }

    return payload


def _progressive_message(is_hindi: bool) -> str:
    return "एक क्षण, मैं यह देखती हूँ।" if is_hindi else "Let me check that for you."


def _short_text(value: Any, limit: int = 500) -> str:
    if value is None:
        return ""
    text = re.sub(r"\s+", " ", str(value).replace("\r", " ").replace("\n", " ")).strip()
    if len(text) > limit:
        return text[:limit].rsplit(" ", 1)[0] + "..."
    return text


def _sanitize_slots(intent: dict[str, Any]) -> dict[str, str]:
    slots = intent.get("slots") or {}
    safe_slots: dict[str, str] = {}
    for name, slot in slots.items():
        value = ""
        if isinstance(slot, dict):
            value = _slot_text(slot)
        safe_slots[str(name)] = _short_text(value, 120)
    return safe_slots


def _analytics_question_text(intent_name: str, question: str) -> str:
    cleaned = _short_text(question, 300)
    if cleaned:
        return cleaned
    if intent_name == "AMAZON.FallbackIntent":
        return "[Unavailable: Alexa FallbackIntent did not provide the original spoken phrase]"
    return ""


def _build_request_snapshot(payload: dict[str, Any], question: str = "") -> dict[str, Any]:
    request_data = payload.get("request") or {}
    intent = request_data.get("intent") or {}
    session = payload.get("session") or {}
    intent_name = str(intent.get("name") or "")
    analytics_question = _analytics_question_text(intent_name, question)
    snapshot = {
        "type": request_data.get("type"),
        "timestamp": request_data.get("timestamp"),
        "locale": request_data.get("locale"),
        "intent": intent_name,
        "question": analytics_question,
        "slots": _sanitize_slots(intent),
        "new_session": bool(session.get("new")),
        "session_attribute_keys": sorted(list((session.get("attributes") or {}).keys())),
    }
    if intent_name == "AMAZON.FallbackIntent" and not _short_text(question, 300):
        snapshot["raw_utterance_available"] = False
        snapshot["note"] = "Alexa custom skills do not expose the original spoken transcript for FallbackIntent requests."
    return snapshot


def _build_response_snapshot(response_payload: dict[str, Any]) -> dict[str, Any]:
    response = response_payload.get("response") or {}
    output_speech = response.get("outputSpeech") or {}
    reprompt = ((response.get("reprompt") or {}).get("outputSpeech") or {})
    card = response.get("card") or {}
    return {
        "should_end_session": bool(response.get("shouldEndSession")),
        "text": _short_text(output_speech.get("text") or output_speech.get("ssml") or "", 500),
        "reprompt": _short_text(reprompt.get("text") or reprompt.get("ssml") or "", 220),
        "card_title": _short_text(card.get("title") or "", 120),
        "card_content": _short_text(card.get("content") or "", 500),
    }


def _log_alexa_interaction(
    db: Session,
    *,
    payload: dict[str, Any],
    response_payload: dict[str, Any],
    user_id: str,
    locale: str,
    request_type: str,
    intent_name: str,
    question: str = "",
    used_fasttrade_context: bool = False,
    is_alert_request: bool = False,
    success: bool = True,
    error_message: str | None = None,
    started_at: float | None = None,
) -> None:
    latency_ms = round((time.perf_counter() - started_at) * 1000, 2) if started_at is not None else None
    request_meta = _build_request_snapshot(payload, question)
    response_meta = _build_response_snapshot(response_payload)

    try:
        db.add(
            AlexaInteractionLog(
                user_id=user_id or "anonymous",
                locale=locale or "en-US",
                request_type=request_type or "unknown",
                intent_name=intent_name or None,
                question=_analytics_question_text(intent_name, question) or None,
                spoken_response=response_meta.get("text") or None,
                request_id=str((payload.get("request") or {}).get("requestId") or "") or None,
                session_id=str((payload.get("session") or {}).get("sessionId") or "") or None,
                application_id=str(
                    (payload.get("session", {}).get("application", {}) or {}).get("applicationId")
                    or (payload.get("context", {}).get("System", {}).get("application", {}) or {}).get("applicationId")
                    or ""
                ) or None,
                response_status_code=200,
                latency_ms=latency_ms,
                used_fasttrade_context=used_fasttrade_context,
                is_alert_request=is_alert_request,
                success=success,
                error_message=_short_text(error_message, 500) or None,
                request_payload=request_meta,
                response_payload=response_meta,
            )
        )
        db.commit()
        logger.info(
            "Alexa analytics | type=%s intent=%s success=%s latency_ms=%s question=%s",
            request_type,
            intent_name or "-",
            success,
            latency_ms,
            _short_text(question, 120) or "-",
        )
    except Exception as exc:
        _rollback_quietly(db)
        logger.warning("Alexa analytics log failed: %s", exc)


async def _send_progressive_response(payload: dict[str, Any], text: str) -> None:
    if not ALEXA_PROGRESSIVE_RESPONSE_ENABLED:
        return

    request_id = str(payload.get("request", {}).get("requestId") or "").strip()
    system_context = payload.get("context", {}).get("System", {}) or {}
    api_access_token = str(system_context.get("apiAccessToken") or "").strip()
    api_endpoint = str(system_context.get("apiEndpoint") or "https://api.amazonalexa.com").rstrip("/")

    if not request_id or not api_access_token:
        return

    directive_payload = {
        "header": {"requestId": request_id},
        "directive": {
            "type": "VoicePlayer.Speak",
            "speech": _normalize_for_voice(text),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{api_endpoint}/v1/directives",
                headers={
                    "Authorization": f"Bearer {api_access_token}",
                    "Content-Type": "application/json",
                },
                json=directive_payload,
            )
            if response.status_code >= 400:
                logger.warning(
                    "Alexa progressive response failed: status=%s body=%s",
                    response.status_code,
                    response.text[:200],
                )
    except Exception as exc:
        logger.debug("Alexa progressive response unavailable: %s", exc)


def _slot_text(slot: dict[str, Any]) -> str:
    value = str(slot.get("value") or "").strip()
    if value:
        return value

    resolutions = (slot.get("resolutions") or {}).get("resolutionsPerAuthority") or []
    for resolution in resolutions:
        for item in resolution.get("values") or []:
            resolved = str(((item.get("value") or {}).get("name") or "")).strip()
            if resolved:
                return resolved
    return ""


def _extract_question(intent: dict[str, Any]) -> str:
    slots = intent.get("slots") or {}
    for slot_name in (
        "question",
        "query",
        "topic",
        "subject",
        "anything",
        "note",
        "reminder",
        "preference",
        "stock",
        "stockName",
        "symbol",
        "ticker",
        "company",
        "item",
        "watchItem",
    ):
        slot = slots.get(slot_name) or {}
        value = _slot_text(slot) if isinstance(slot, dict) else str(slot or "").strip()
        if value:
            return value
    return ""


def _get_user_id(payload: dict[str, Any]) -> str:
    return (
        payload.get("session", {}).get("user", {}).get("userId")
        or payload.get("context", {}).get("System", {}).get("user", {}).get("userId")
        or "anonymous"
    )


def _get_user_memory(user_id: str) -> dict[str, list[str]]:
    if user_id not in _USER_MEMORY:
        _USER_MEMORY[user_id] = {"notes": [], "reminders": [], "journal": [], "watchlist": []}
    return _USER_MEMORY[user_id]


def _get_recent_conversation(user_id: str) -> list[dict[str, str]]:
    if user_id not in _USER_CONVERSATIONS:
        _USER_CONVERSATIONS[user_id] = []
    return _USER_CONVERSATIONS[user_id]


def _remember_conversation_turn(user_id: str, role: str, content: str) -> None:
    if role not in {"user", "assistant"}:
        return
    cleaned = _normalize_for_voice(content)
    if not cleaned or cleaned.startswith("Sorry, I could not generate"):
        return

    history = _get_recent_conversation(user_id)
    if history and history[-1].get("role") == role and history[-1].get("content") == cleaned:
        return

    history.append({"role": role, "content": cleaned})
    _USER_CONVERSATIONS[user_id] = history[-(ALEXA_MAX_CONVERSATION_TURNS * 2):]


def _conversation_as_text(user_id: str) -> str:
    history = _get_recent_conversation(user_id)[-(ALEXA_MAX_CONVERSATION_TURNS * 2):]
    if not history:
        return ""

    lines: list[str] = []
    for item in history:
        speaker = "User" if item.get("role") == "user" else "Assistant"
        content = str(item.get("content") or "").strip()
        if content:
            lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def _get_locale(payload: dict[str, Any]) -> str:
    return (payload.get("request", {}).get("locale") or "en-US").strip()


def _is_hindi_locale(payload: dict[str, Any]) -> bool:
    return _get_locale(payload).lower().startswith("hi")


def _extract_list_items(text: str) -> list[str]:
    items = [
        part.strip(" .")
        for part in re.split(r",|\band\b|\baur\b|और", text, flags=re.IGNORECASE)
        if part.strip()
    ]
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:8]


def _normalize_watchlist_item(item: str) -> str:
    cleaned = str(item or "").strip()
    if not cleaned:
        return ""

    cleaned = re.sub(
        r"\b(add|put|save|watch|track|stock|share|shares|company|my|the|to|into|in|on|for|please|watch\s*list|watchlist)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,-")
    if not cleaned:
        return ""

    if re.fullmatch(r"(?:[A-Za-z]\s*){2,10}", cleaned):
        collapsed = re.sub(r"\s+", "", cleaned).upper()
        if 2 <= len(collapsed) <= 10:
            cleaned = collapsed

    alias = WATCHLIST_SYMBOL_ALIASES.get(cleaned.lower())
    if alias:
        return alias

    return cleaned.upper()


def _dedupe_items(items: list[str], limit: int) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = str(item).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key not in seen:
            seen.add(key)
            unique.append(normalized)
    return unique[-limit:]


def _primary_market_symbol(question: str) -> str:
    normalized = question.strip().lower()
    if "banknifty" in normalized or "bank nifty" in normalized:
        return "BANKNIFTY"
    if "finnifty" in normalized or "fin nifty" in normalized:
        return "FINNIFTY"
    return "NIFTY"


def _build_live_market_context(question: str, user_memory: dict[str, list[str]]) -> str:
    if not ALEXA_LIVE_MARKET_CONTEXT_ENABLED:
        return ""

    parts: list[str] = []

    try:
        nifty = get_spot("NIFTY")
        banknifty = get_spot("BANKNIFTY")
        india_vix = get_spot("NIFTYVIX")
        vix_tone = "low volatility" if india_vix < 13 else "elevated volatility" if india_vix > 18 else "moderate volatility"
        parts.append(f"NIFTY spot is {nifty:.2f}.")
        parts.append(f"BANKNIFTY spot is {banknifty:.2f}.")
        parts.append(f"India VIX is {india_vix:.2f}, which suggests {vix_tone}.")
    except Exception as exc:
        logger.debug("Alexa live index snapshot unavailable: %s", exc)

    try:
        underlying = _primary_market_symbol(question)
        reference_spot = None
        try:
            reference_spot = get_spot(underlying)
        except Exception:
            reference_spot = None

        chain = get_option_chain(underlying)
        if not chain.empty:
            strikes = sorted({int(float(strike)) for strike in chain["strike"].dropna().tolist()})
            if strikes:
                atm = min(strikes, key=lambda strike: abs(strike - reference_spot)) if reference_spot else strikes[len(strikes) // 2]
                window = 150 if underlying == "NIFTY" else 300
                nearby = [str(strike) for strike in strikes if abs(strike - atm) <= window][:7]
                if nearby:
                    parts.append(f"{underlying} option chain near ATM {atm} is available around strikes {', '.join(nearby)}.")
    except Exception as exc:
        logger.debug("Alexa live option snapshot unavailable: %s", exc)

    if user_memory.get("watchlist"):
        parts.append("Saved watchlist: " + ", ".join(user_memory["watchlist"][-5:]) + ".")

    return " ".join(parts)


def _rollback_quietly(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _alexa_watchlist_name(user_id: str) -> str:
    safe_id = re.sub(r"[^a-zA-Z0-9]+", "-", user_id).strip("-") or "anonymous"
    return f"Alexa Voice Watchlist {safe_id[:18]}"


def _load_persistent_user_memory(db: Session, user_id: str) -> dict[str, list[str]]:
    user_memory = _get_user_memory(user_id)
    try:
        records = (
            db.query(AlexaMemory)
            .filter(AlexaMemory.user_id == user_id, AlexaMemory.is_active == True)
            .order_by(AlexaMemory.created_at.desc())
            .limit(50)
            .all()
        )
        grouped = {"notes": [], "reminders": [], "journal": []}
        for record in reversed(records):
            key = MEMORY_TYPE_TO_KEY.get((record.memory_type or "").strip().lower())
            if key and record.content:
                grouped[key].append(record.content.strip())
        for key, values in grouped.items():
            if values:
                user_memory[key] = _dedupe_items(values, 10)

        watchlist = (
            db.query(Watchlist)
            .filter(Watchlist.created_by == f"alexa:{user_id}", Watchlist.is_active == True)
            .order_by(Watchlist.updated_at.desc())
            .first()
        )
        if watchlist and isinstance(watchlist.symbols, list):
            user_memory["watchlist"] = _dedupe_items([str(symbol) for symbol in watchlist.symbols], 15)
    except Exception as exc:
        _rollback_quietly(db)
        logger.warning("Alexa persistent memory load failed for %s: %s", user_id, exc)
    return user_memory


def _save_memory_record(db: Session, user_id: str, memory_type: str, content: str, locale: str) -> bool:
    cleaned = content.strip()
    if not cleaned:
        return False
    try:
        latest = (
            db.query(AlexaMemory)
            .filter(
                AlexaMemory.user_id == user_id,
                AlexaMemory.memory_type == memory_type,
                AlexaMemory.is_active == True,
            )
            .order_by(AlexaMemory.created_at.desc())
            .first()
        )
        if latest and (latest.content or "").strip().lower() == cleaned.lower():
            return True

        db.add(AlexaMemory(user_id=user_id, memory_type=memory_type, content=cleaned, locale=locale))
        db.commit()
        return True
    except Exception as exc:
        _rollback_quietly(db)
        logger.warning("Alexa persistent save failed for %s/%s: %s", user_id, memory_type, exc)
        return False


def _save_watchlist(db: Session, user_id: str, items: list[str] | None = None, clear: bool = False) -> list[str] | None:
    try:
        watchlist = (
            db.query(Watchlist)
            .filter(Watchlist.created_by == f"alexa:{user_id}")
            .order_by(Watchlist.updated_at.desc())
            .first()
        )
        if not watchlist and clear:
            return []

        if not watchlist:
            try:
                db.execute(
                    text(
                        """
                        SELECT setval(
                            pg_get_serial_sequence('watchlists', 'id'),
                            COALESCE((SELECT MAX(id) FROM watchlists), 1),
                            CASE WHEN EXISTS (SELECT 1 FROM watchlists) THEN true ELSE false END
                        )
                        """
                    )
                )
            except Exception as exc:
                logger.debug("Watchlist sequence sync skipped for %s: %s", user_id, exc)

            watchlist = Watchlist(
                name=_alexa_watchlist_name(user_id),
                description="Persistent watchlist created from Alexa voice commands",
                symbols=[],
                color="#8b5cf6",
                icon="mic",
                is_default=False,
                is_active=True,
                created_by=f"alexa:{user_id}",
            )
            db.add(watchlist)
            db.flush()

        current_symbols = watchlist.symbols if isinstance(watchlist.symbols, list) else []
        current_symbols = _dedupe_items([str(symbol).upper() for symbol in current_symbols], 15)

        if clear:
            watchlist.symbols = []
        else:
            normalized_items = _dedupe_items([str(item).strip().upper() for item in (items or [])], 15)
            watchlist.symbols = _dedupe_items(current_symbols + normalized_items, 15)

        db.commit()
        db.refresh(watchlist)
        return [str(symbol) for symbol in (watchlist.symbols or [])]
    except Exception as exc:
        _rollback_quietly(db)
        logger.warning("Alexa watchlist persistence failed for %s: %s", user_id, exc)
        return None


def _should_use_fasttrade_context(intent_name: str, question: str) -> bool:
    if intent_name in {
        "PortfolioSummaryIntent",
        "RiskStatusIntent",
        "MarketBriefIntent",
        "MorningBriefingIntent",
        "TradeActionIntent",
        "NewsSummaryIntent",
        "WatchlistSummaryIntent",
        "TopMoversIntent",
        "EarningsCalendarIntent",
        "AlertSummaryIntent",
        "MarketSentimentIntent",
    }:
        return True
    normalized = question.strip().lower()
    return any(keyword in normalized for keyword in TRADING_KEYWORDS)


def _is_alert_summary_request(intent_name: str, question: str) -> bool:
    if intent_name == "AlertSummaryIntent":
        return True
    normalized = question.strip().lower()
    return any(keyword in normalized for keyword in ALERT_SUMMARY_KEYWORDS)


def _build_alert_context(question: str, db: Session) -> str:
    normalized = question.strip().lower()
    critical_only = any(term in normalized for term in {"critical", "urgent", "important", "high priority"})
    trade_focus = any(term in normalized for term in {"trade", "position", "pnl", "stop loss", "take profit", "sl", "tp"})
    twitter_focus = any(term in normalized for term in {"twitter", "x alert", "sentiment", "social"})
    news_focus = any(term in normalized for term in {"news", "headline", "breaking"})

    summaries: list[str] = []

    try:
        notification_query = db.query(Notification).filter(Notification.read == False)
        if critical_only:
            notification_query = notification_query.filter(Notification.priority.in_(["high", "critical"]))
        notifications = notification_query.order_by(Notification.created_at.desc()).limit(6).all()
        if trade_focus:
            trade_types = {"trade_executed", "trade_failed", "tp_hit", "sl_hit", "trailing_sl_hit", "pnl_threshold"}
            filtered = [item for item in notifications if (item.type or "") in trade_types]
            if filtered:
                notifications = filtered
        for item in notifications[:3]:
            title = str(item.title or item.message or "notification").strip()
            priority = str(item.priority or "medium").lower()
            summaries.append(f"{priority} app notification: {title}")
    except Exception as exc:
        logger.debug("Alexa notification fetch unavailable: %s", exc)

    try:
        twitter_query = db.query(TwitterAlert).filter(TwitterAlert.dismissed == False)
        if critical_only:
            twitter_query = twitter_query.filter(TwitterAlert.severity.in_(["critical", "high"]))
        twitter_alerts = twitter_query.order_by(TwitterAlert.created_at.desc()).limit(6).all()
        if twitter_focus or not trade_focus:
            for item in twitter_alerts[:2]:
                severity = str(item.severity or "medium").lower()
                symbol = str(item.symbol or "market")
                title = str(item.title or item.message or "Twitter alert").strip()
                summaries.append(f"{severity} social alert on {symbol}: {title}")
    except Exception as exc:
        logger.debug("Alexa Twitter alert fetch unavailable: %s", exc)

    try:
        if news_focus or not summaries:
            rss_items = get_rss_service().fetch_all_feeds(categories=["moneycontrol_market", "economic_times"])
            for item in rss_items[:12]:
                title = str(item.get("title") or "").strip()
                text = f"{title} {item.get('description') or ''}".lower()
                if any(term in text for term in {"breaking", "alert", "rbi", "volatility", "surge", "plunge", "earnings"}):
                    source = str(item.get("source") or "RSS")
                    summaries.append(f"market news alert from {source}: {title}")
                    if len(summaries) >= 5:
                        break
    except Exception as exc:
        logger.debug("Alexa live news alert fetch unavailable: %s", exc)

    deduped = _dedupe_items(summaries, 5)
    return " ".join(deduped) if deduped else "No unread in-app notifications or high-priority market alerts are available right now."


def _is_trade_action_request(intent_name: str, question: str) -> bool:
    if intent_name == "TradeActionIntent":
        return True
    normalized = question.strip().lower()
    return any(keyword in normalized for keyword in TRADE_ACTION_KEYWORDS)


def _default_question(intent_name: str) -> str:
    defaults = {
        "PortfolioSummaryIntent": "Give me a short spoken summary of my portfolio, open positions, and important alerts.",
        "RiskStatusIntent": "Give me a short spoken summary of my current trading risk and any open-position concerns.",
        "MarketBriefIntent": "Give me a short spoken market brief for today.",
        "MarketSentimentIntent": "Give me a short spoken market sentiment summary and say whether the tone looks bullish, bearish, or mixed.",
        "MorningBriefingIntent": "Give me a short morning briefing with market outlook, portfolio context, and one practical focus item for today.",
        "NewsSummaryIntent": "Give me a short spoken summary of the most important market and stock news right now.",
        "WatchlistSummaryIntent": "Give me a short spoken summary of my watchlist and the most actionable names.",
        "TopMoversIntent": "Give me a short spoken summary of top gainers and losers or the key movers to watch today.",
        "EarningsCalendarIntent": "Give me a short spoken summary of important earnings or economic events coming up soon.",
        "TradingLessonIntent": "Teach me one short practical trading lesson for today.",
        "StrategyExplainerIntent": "Explain the requested trading strategy in simple words with one caution.",
        "AlertSummaryIntent": "Give me a short spoken summary of my most important alerts or watchlist signals.",
        "AMAZON.FallbackIntent": "Give me a short helpful answer to the user's request.",
    }
    return defaults.get(intent_name, "")


def _normalize_generic_voice_question(question: str, intent_name: str, is_hindi: bool) -> str:
    cleaned = _short_text(question or "", 220).strip()
    if not cleaned:
        return ""

    generic_intents = {
        "GenericQuestionIntent",
        "AskNvidiaIntent",
        "AskFastTradeIntent",
        "StrategyExplainerIntent",
    }
    if intent_name not in generic_intents:
        return cleaned

    lowered = cleaned.lower()
    if re.match(r"^(what|who|when|where|why|how|is|are|can|do|does|should|tell me|explain|define)\b", lowered):
        return cleaned

    token_count = len(re.findall(r"[a-zA-Z0-9%+.-]+", cleaned))
    if 1 <= token_count <= 4:
        if is_hindi:
            return f"Explain briefly what {cleaned} is and why it matters, in simple Hindi or Hinglish."
        return f"Explain briefly what {cleaned} is and why it matters in simple terms."

    return cleaned


@router.get("/health")
def alexa_health() -> dict[str, Any]:
    return {
        "ok": True,
        "endpoint": "/alexa/skill",
        "skill_name": ALEXA_SKILL_NAME,
        "read_only": True,
    }


@router.get("/skill")
def alexa_skill_info() -> dict[str, Any]:
    return {
        "ok": True,
        "message": "Alexa skill endpoint is live. Alexa should call this URL with POST requests.",
        "endpoint": "/alexa/skill",
        "skill_name": ALEXA_SKILL_NAME,
    }


@router.get("/proactive/status")
def alexa_proactive_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    service = get_alexa_proactive_alert_service(db)
    return {
        "ok": True,
        **service.get_status(),
    }


@router.post("/proactive/test")
def alexa_proactive_test(
    message: str = "Fast Trade test alert. Review your latest critical notifications.",
    severity: str = "high",
    user_id: str | None = None,
    locale: str = "en-US",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = get_alexa_proactive_alert_service(db)
    result = service.send_notification(
        title=f"{ALEXA_SKILL_NAME} test alert",
        message=message,
        severity=(severity or "high").strip().lower(),
        user_id=user_id,
        locale=locale,
    )
    return {
        "ok": bool(result.get("ok")),
        "result": result,
    }


@router.get("/analytics/summary")
def alexa_analytics_summary(days: int = 30, db: Session = Depends(get_db)) -> dict[str, Any]:
    days = max(1, min(365, int(days or 30)))
    cutoff = now_ist() - timedelta(days=days)

    total_requests = (
        db.query(func.count(AlexaInteractionLog.id))
        .filter(AlexaInteractionLog.created_at >= cutoff)
        .scalar()
        or 0
    )
    successful_requests = (
        db.query(func.count(AlexaInteractionLog.id))
        .filter(AlexaInteractionLog.created_at >= cutoff, AlexaInteractionLog.success == True)
        .scalar()
        or 0
    )
    avg_latency_ms = (
        db.query(func.avg(AlexaInteractionLog.latency_ms))
        .filter(AlexaInteractionLog.created_at >= cutoff)
        .scalar()
        or 0
    )

    top_intents = (
        db.query(AlexaInteractionLog.intent_name, func.count(AlexaInteractionLog.id).label("count"))
        .filter(AlexaInteractionLog.created_at >= cutoff)
        .group_by(AlexaInteractionLog.intent_name)
        .order_by(func.count(AlexaInteractionLog.id).desc())
        .limit(10)
        .all()
    )
    locale_breakdown = (
        db.query(AlexaInteractionLog.locale, func.count(AlexaInteractionLog.id).label("count"))
        .filter(AlexaInteractionLog.created_at >= cutoff)
        .group_by(AlexaInteractionLog.locale)
        .order_by(func.count(AlexaInteractionLog.id).desc())
        .all()
    )

    return {
        "ok": True,
        "days": days,
        "total_requests": int(total_requests),
        "successful_requests": int(successful_requests),
        "failed_requests": int(total_requests) - int(successful_requests),
        "avg_latency_ms": round(float(avg_latency_ms or 0), 2),
        "fasttrade_context_requests": (
            db.query(func.count(AlexaInteractionLog.id))
            .filter(AlexaInteractionLog.created_at >= cutoff, AlexaInteractionLog.used_fasttrade_context == True)
            .scalar()
            or 0
        ),
        "alert_requests": (
            db.query(func.count(AlexaInteractionLog.id))
            .filter(AlexaInteractionLog.created_at >= cutoff, AlexaInteractionLog.is_alert_request == True)
            .scalar()
            or 0
        ),
        "top_intents": [
            {"intent_name": intent_name or "(unknown)", "count": int(count)}
            for intent_name, count in top_intents
        ],
        "locale_breakdown": [
            {"locale": locale or "unknown", "count": int(count)}
            for locale, count in locale_breakdown
        ],
    }


@router.get("/analytics/recent")
def alexa_analytics_recent(
    limit: int = 50,
    intent_name: str | None = None,
    user_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    limit = max(1, min(200, int(limit or 50)))
    query = db.query(AlexaInteractionLog).order_by(AlexaInteractionLog.created_at.desc())
    if intent_name:
        query = query.filter(AlexaInteractionLog.intent_name == intent_name)
    if user_id:
        query = query.filter(AlexaInteractionLog.user_id == user_id)
    rows = query.limit(limit).all()
    return {
        "ok": True,
        "count": len(rows),
        "items": [row.to_dict() for row in rows],
    }


@router.post("/skill")
async def alexa_skill(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    request_started = time.perf_counter()
    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("Invalid Alexa request payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Alexa payload") from exc

    user_id = _get_user_id(payload)
    locale = _get_locale(payload)
    req = payload.get("request") or {}
    req_type = req.get("type")
    is_hindi = _is_hindi_locale(payload)
    default_reprompt = DEFAULT_REPROMPT_HI if is_hindi else DEFAULT_REPROMPT

    analytics: dict[str, Any] = {
        "request_type": str(req_type or "unknown"),
        "intent_name": "",
        "question": "",
        "used_fasttrade_context": False,
        "is_alert_request": False,
        "success": True,
        "error_message": None,
    }

    def finalize_response(response_payload: dict[str, Any]) -> dict[str, Any]:
        _log_alexa_interaction(
            db,
            payload=payload,
            response_payload=response_payload,
            user_id=user_id,
            locale=locale,
            request_type=analytics["request_type"],
            intent_name=analytics["intent_name"],
            question=analytics["question"],
            used_fasttrade_context=bool(analytics["used_fasttrade_context"]),
            is_alert_request=bool(analytics["is_alert_request"]),
            success=bool(analytics["success"]),
            error_message=analytics["error_message"],
            started_at=request_started,
        )
        return response_payload

    def respond(
        text: str,
        reprompt: str | None = None,
        end_session: bool = False,
        session_attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return finalize_response(
            _response(
                text,
                reprompt=reprompt,
                end_session=end_session,
                session_attributes=session_attributes,
            )
        )

    app_id = (
        payload.get("session", {}).get("application", {}).get("applicationId")
        or payload.get("context", {}).get("System", {}).get("application", {}).get("applicationId")
        or ""
    )
    if ALEXA_ALLOWED_SKILL_ID and app_id and app_id != ALEXA_ALLOWED_SKILL_ID:
        if ALEXA_ENFORCE_SKILL_ID:
            analytics["success"] = False
            analytics["error_message"] = "Alexa skill ID mismatch"
            _log_alexa_interaction(
                db,
                payload=payload,
                response_payload={"response": {"shouldEndSession": True}},
                user_id=user_id,
                locale=locale,
                request_type=analytics["request_type"],
                intent_name="skill-id-mismatch",
                question="",
                success=False,
                error_message="Alexa skill ID mismatch",
                started_at=request_started,
            )
            raise HTTPException(status_code=403, detail="Alexa skill ID mismatch")
        logger.warning("Alexa skill ID mismatch in non-strict mode: received=%s", app_id)

    if req_type == "LaunchRequest":
        analytics["intent_name"] = "LaunchRequest"
        welcome_intro = (
            f"{ALEXA_SKILL_NAME} में आपका स्वागत है।"
            if is_hindi
            else f"Welcome to {ALEXA_SKILL_NAME}."
        )
        welcome_text = f"{welcome_intro} {default_reprompt}".strip()
        return respond(welcome_text, reprompt=default_reprompt)

    if req_type == "SessionEndedRequest":
        analytics["intent_name"] = "SessionEndedRequest"
        return finalize_response({"version": "1.0", "response": {"shouldEndSession": True}})

    if req_type == "AlexaSkillEvent.ProactiveSubscriptionChanged":
        analytics["intent_name"] = "AlexaSkillEvent.ProactiveSubscriptionChanged"
        service = get_alexa_proactive_alert_service(db)
        body = req.get("body") or {}
        subscriptions = [
            str(item.get("eventName") or "").strip()
            for item in (body.get("subscriptions") or [])
            if str(item.get("eventName") or "").strip()
        ]
        analytics["question"] = ", ".join(subscriptions)
        result = service.record_subscription_change(
            user_id=user_id,
            locale=locale,
            subscriptions=subscriptions,
            request_timestamp=str(req.get("timestamp") or "").strip() or None,
        )
        logger.info("Alexa proactive subscription updated: %s", result)
        return finalize_response({"version": "1.0", "response": {"shouldEndSession": True}, "ok": True})

    if req_type != "IntentRequest":
        analytics["intent_name"] = str(req_type or "unknown")
        return respond(
            "माफ़ कीजिए, मैं इस Alexa request को समझ नहीं पाई。" if is_hindi else "Sorry, I could not understand that Alexa request.",
            reprompt=default_reprompt,
        )

    intent = req.get("intent") or {}
    intent_name = intent.get("name", "")
    analytics["intent_name"] = intent_name
    logger.info("Alexa intent received: %s", intent_name)

    if intent_name == "AMAZON.HelpIntent":
        help_text = (
            "आप पोर्टफोलियो समरी, रिस्क स्टेटस, मार्केट न्यूज़, मार्केट सेंटिमेंट, वॉचलिस्ट समरी, ट्रेडिंग लेसन, या सामान्य सवाल पूछ सकते हैं। आप रिमाइंडर, जर्नल नोट और वॉचलिस्ट भी सेव कर सकते हैं।"
            if is_hindi
            else "You can ask for your portfolio summary, current risk, market news, market sentiment, watchlist summary, a trading lesson, or a general question like what is RSI. You can also save reminders, journal notes, and watchlist names."
        )
        return respond(help_text, reprompt=default_reprompt)

    if intent_name == "AMAZON.FallbackIntent":
        analytics["question"] = "[Unavailable: Alexa FallbackIntent did not provide the original spoken phrase]"
        fallback_text = (
            "मुझे वह साफ़ सुनाई नहीं दिया। आप पोर्टफोलियो, मार्केट ब्रीफ, या alerts के बारे में पूछ सकते हैं।"
            if is_hindi
            else "I didn't catch that. You can ask about your portfolio, a market brief, or alerts."
        )
        return respond(fallback_text, reprompt=default_reprompt)

    if intent_name in {"AMAZON.CancelIntent", "AMAZON.StopIntent", "AMAZON.NavigateHomeIntent"}:
        return respond("ठीक है, फिर मिलते हैं।" if is_hindi else "Goodbye.", end_session=True)

    session_attrs = payload.get("session", {}).get("attributes") or {}
    pending_trade_request = str(session_attrs.get("pending_trade_request") or "").strip()
    user_memory = _load_persistent_user_memory(db, user_id)

    if intent_name in {"ConfirmTradeIntent", "AMAZON.YesIntent"}:
        analytics["question"] = pending_trade_request
        if not pending_trade_request:
            return respond(
                "अभी कन्फर्म करने के लिए कोई pending trade request नहीं है।" if is_hindi else "There is no pending trade request to confirm right now.",
                reprompt=default_reprompt,
            )

        if ALEXA_VOICE_TRADING_ENABLED:
            return respond(
                (
                    f"मैंने यह trade idea confirm कर लिया है: {pending_trade_request}. सुरक्षा के लिए live execution से पहले इसे Fast Trade में review कर लें।"
                    if is_hindi
                    else f"I confirmed the trade idea: {pending_trade_request}. For safety, please review it in Fast Trade before any live execution."
                ),
                reprompt="आप कोई और मार्केट अपडेट भी पूछ सकते हैं।" if is_hindi else "You can ask for another market or portfolio update.",
                session_attributes={},
            )

        return respond(
            (
                f"मैंने यह trade idea capture कर लिया है: {pending_trade_request}. सुरक्षा के लिए live voice trading बंद है, इसलिए order place करने से पहले इसे Fast Trade app में review करें।"
                if is_hindi
                else f"I captured the trade idea: {pending_trade_request}. Live voice trading is disabled for safety, so please review it in the Fast Trade app before placing any order."
            ),
            reprompt="आप कोई और मार्केट अपडेट भी पूछ सकते हैं।" if is_hindi else "You can ask for another market or portfolio update.",
            session_attributes={},
        )

    if intent_name in {"CancelTradeIntent", "AMAZON.NoIntent"}:
        analytics["question"] = pending_trade_request
        if pending_trade_request:
            return respond(
                "ठीक है, pending trade request cancel कर दी गई है।" if is_hindi else "Okay, I cancelled the pending trade request.",
                reprompt=default_reprompt,
                session_attributes={},
            )
        return respond("ठीक है, कुछ भी बदला नहीं गया।" if is_hindi else "Okay, nothing was changed.", reprompt=default_reprompt)

    if intent_name == "RememberPreferenceIntent":
        memory_text = _extract_question(intent)
        analytics["question"] = memory_text
        if not memory_text:
            return respond(
                "कृपया बताइए कि आपको क्या याद रखना है।" if is_hindi else "Please tell me what you want me to remember.",
                reprompt="उदाहरण के लिए कहें, मेरी low risk trades की preference याद रखो।" if is_hindi else "For example, say remember that I prefer low risk trades.",
            )
        user_memory["notes"] = _dedupe_items(user_memory.get("notes", []) + [memory_text], 10)
        _save_memory_record(db, user_id, "note", memory_text, locale)
        return respond(
            f"ठीक है, मैंने यह preference save कर ली है: {memory_text}." if is_hindi else f"Okay, I saved this preference: {memory_text}.",
            reprompt="आप पूछ सकते हैं कि तुम्हें क्या याद है या मेरा morning briefing दो।" if is_hindi else "You can also ask what do you remember or ask for your morning briefing.",
        )

    if intent_name == "SetReminderIntent":
        reminder_text = _extract_question(intent)
        analytics["question"] = reminder_text
        if not reminder_text:
            return respond(
                "कृपया reminder text बताइए।" if is_hindi else "Please tell me the reminder text.",
                reprompt="उदाहरण के लिए कहें, मुझे 9 30 AM पर Nifty review करने की याद दिलाओ।" if is_hindi else "For example, say remind me to review Nifty at 9 30 AM.",
            )
        user_memory["reminders"] = _dedupe_items(user_memory.get("reminders", []) + [reminder_text], 10)
        _save_memory_record(db, user_id, "reminder", reminder_text, locale)
        return respond(
            f"ठीक है, मैंने यह reminder save कर लिया है: {reminder_text}." if is_hindi else f"Okay, I saved this reminder: {reminder_text}.",
            reprompt="आप पूछ सकते हैं कि तुम्हें क्या याद है या मार्केट अपडेट दो।" if is_hindi else "You can ask what do you remember or ask for a market update.",
        )

    if intent_name == "JournalNoteIntent":
        note_text = _extract_question(intent)
        analytics["question"] = note_text
        if not note_text:
            return respond(
                "कृपया वह journal note बताइए जिसे आप save करना चाहते हैं।" if is_hindi else "Please tell me the journal note you want to save.",
                reprompt="उदाहरण के लिए कहें, note that I exited early due to fear."
                if not is_hindi
                else "उदाहरण के लिए कहें, journal में लिखो कि मैं डर की वजह से जल्दी निकल गया।",
            )
        user_memory["journal"] = _dedupe_items(user_memory.get("journal", []) + [note_text], 10)
        _save_memory_record(db, user_id, "journal", note_text, locale)
        return respond(
            f"ठीक है, मैंने यह trading note save कर लिया है: {note_text}." if is_hindi else f"Okay, I saved this trading note: {note_text}.",
            reprompt="आप कभी भी मुझसे अपने journal notes review करने को कह सकते हैं।" if is_hindi else "You can ask me to review your journal notes anytime.",
        )

    if intent_name == "AddToWatchlistIntent":
        watchlist_text = _extract_question(intent)
        analytics["question"] = watchlist_text
        if not watchlist_text:
            return respond(
                "कृपया stock name बताइए जिसे watchlist में जोड़ना है।" if is_hindi else "Please tell me which stock name you want to add to the watchlist.",
                reprompt="उदाहरण के लिए कहें, add Reliance and Infosys to my watchlist."
                if not is_hindi
                else "उदाहरण के लिए कहें, मेरी watchlist में Reliance और Infosys जोड़ो।",
            )
        items = _extract_list_items(watchlist_text) or [watchlist_text.strip()]
        normalized_items = _dedupe_items(
            [normalized for normalized in (_normalize_watchlist_item(item) for item in items) if normalized],
            15,
        )
        if not normalized_items:
            return respond(
                "कृपया valid stock name बताइए, जैसे TCS या Reliance।"
                if is_hindi
                else "Please say a valid stock name, like TCS or Reliance.",
                reprompt=default_reprompt,
            )
        user_memory["watchlist"] = _dedupe_items(user_memory.get("watchlist", []) + normalized_items, 15)
        persisted_watchlist = _save_watchlist(db, user_id, normalized_items)
        if persisted_watchlist is not None:
            user_memory["watchlist"] = persisted_watchlist
        spoken_items = ", ".join(normalized_items)
        return respond(
            f"ठीक है, मैंने {spoken_items} को आपकी watchlist में जोड़ दिया है।" if is_hindi else f"Okay, I added {spoken_items} to your watchlist.",
            reprompt="अब आप कह सकते हैं, मेरी watchlist summary दो।" if is_hindi else "Now you can ask for your watchlist summary.",
        )

    if intent_name == "ClearWatchlistIntent":
        user_memory["watchlist"] = []
        analytics["question"] = "clear watchlist"
        _save_watchlist(db, user_id, clear=True)
        return respond(
            "ठीक है, आपकी watchlist साफ कर दी गई है।" if is_hindi else "Okay, I cleared your watchlist.",
            reprompt=default_reprompt,
        )

    if intent_name in {"RecallMemoryIntent", "ListRemindersIntent", "ReviewJournalIntent"}:
        analytics["question"] = intent_name
        notes = user_memory.get("notes", [])
        reminders = user_memory.get("reminders", [])
        journal_notes = user_memory.get("journal", [])
        watchlist_items = user_memory.get("watchlist", [])
        parts: list[str] = []
        if notes:
            parts.append(("मुझे यह याद है: " if is_hindi else "I remember: ") + "; ".join(notes[-3:]))
        if reminders:
            parts.append(("आपके recent reminders हैं: " if is_hindi else "Your recent reminders are: ") + "; ".join(reminders[-3:]))
        if journal_notes:
            parts.append(("आपके latest trading notes हैं: " if is_hindi else "Your latest trading notes are: ") + "; ".join(journal_notes[-3:]))
        if watchlist_items:
            parts.append(("आपकी saved watchlist है: " if is_hindi else "Your saved watchlist is: ") + "; ".join(watchlist_items[-6:]))
        if not parts:
            return respond(
                "अभी कोई saved note, reminder, journal entry, या watchlist item नहीं है।" if is_hindi else "I do not have any saved notes, reminders, journal entries, or watchlist items yet.",
                reprompt="कहें, मेरी low risk trades की preference याद रखो।" if is_hindi else "Try saying remember that I prefer low risk trades.",
            )
        return respond(
            " ".join(parts),
            reprompt="आप एक और reminder, journal note, या morning briefing पूछ सकते हैं।" if is_hindi else "You can add another reminder, journal note, or ask for your morning briefing.",
        )

    if intent_name in {
        "AskFastTradeIntent",
        "AskNvidiaIntent",
        "GenericQuestionIntent",
        "MorningBriefingIntent",
        "MarketBriefIntent",
        "MarketSentimentIntent",
        "NewsSummaryIntent",
        "WatchlistSummaryIntent",
        "TopMoversIntent",
        "EarningsCalendarIntent",
        "TradingLessonIntent",
        "StrategyExplainerIntent",
        "AlertSummaryIntent",
        "PortfolioSummaryIntent",
        "RiskStatusIntent",
        "TradeActionIntent",
    } or _extract_question(intent):
        raw_question = _extract_question(intent)
        question = _normalize_generic_voice_question(raw_question or _default_question(intent_name), intent_name, is_hindi)
        analytics["question"] = raw_question

        if intent_name == "WatchlistSummaryIntent" and user_memory.get("watchlist"):
            watchlist_text = ", ".join(user_memory["watchlist"][-8:])
            question = (
                f"Give me a short spoken summary of this user watchlist: {watchlist_text}. Mention which names deserve attention and one simple caution."
            )

        if not question:
            return respond(
                "कृपया एक सवाल पूछिए, जैसे मेरे open positions क्या हैं, RSI क्या है, या Reliance buy करो।"
                if is_hindi
                else "Please ask a question, for example: what are my open positions, what is RSI, or buy Reliance for a paper trade draft.",
                reprompt=default_reprompt,
            )

        if _is_trade_action_request(intent_name, question):
            trade_summary = _normalize_for_voice(question)
            analytics["question"] = trade_summary
            return respond(
                (
                    f"मैंने यह trade request सुनी: {trade_summary}. सुरक्षा के लिए voice trading confirmation मांगती है और default रूप से paper-only रहती है। Continue करने के लिए confirm trade कहें या cancel trade कहें।"
                    if is_hindi
                    else f"I heard a trade request: {trade_summary}. For safety, voice trading requires confirmation and stays paper-only by default. Say confirm trade to continue or cancel trade to stop."
                ),
                reprompt="कहें confirm trade या cancel trade।" if is_hindi else "Say confirm trade or cancel trade.",
                session_attributes={"pending_trade_request": trade_summary},
            )

        await _send_progressive_response(payload, _progressive_message(is_hindi))

        conversation_history = _get_recent_conversation(user_id)[-(ALEXA_MAX_CONVERSATION_TURNS * 2):]
        conversation_context = _conversation_as_text(user_id)
        is_alert_request = _is_alert_summary_request(intent_name, question)
        use_fasttrade_context = _should_use_fasttrade_context(intent_name, question) or bool(conversation_history)
        analytics["used_fasttrade_context"] = use_fasttrade_context
        analytics["is_alert_request"] = is_alert_request

        live_market_context = _build_live_market_context(question, user_memory) if use_fasttrade_context else ""
        alert_context = _build_alert_context(question, db) if is_alert_request else ""
        if intent_name == "AlertSummaryIntent" and alert_context.startswith("No unread"):
            no_alerts_text = (
                "अभी कोई unread app notification या high priority market alert नहीं है।"
                if is_hindi
                else "There are no unread app notifications or high priority market alerts right now."
            )
            return respond(no_alerts_text, reprompt=default_reprompt)
        if intent_name == "AlertSummaryIntent" and alert_context:
            question = f"Summarize these actual current Fast Trade alerts for voice: {alert_context}"
        answer = None
        language_instruction = (
            "Reply in simple Hindi or natural Hinglish. Use at most two short voice-friendly sentences and keep it under 60 words."
            if is_hindi
            else "Answer in at most two short sentences, optimized for voice, and keep it under 60 words."
        )
        continuity_instruction = (
            "Recent conversation context ko use karke follow-up sawalon ka natural jawab do."
            if is_hindi
            else "Use the recent conversation to resolve follow-up questions naturally."
        )

        if use_fasttrade_context:
            prompt_parts = [
                "You are Fast Trade AI, a calm financial voice assistant for traders and investors.",
                language_instruction,
                continuity_instruction,
                "Use plain language, highlight one relevant risk or caution when useful, and avoid jargon overload.",
                "Avoid dramatic, slang, or aggressive phrasing.",
                "Do not use markdown, bullet points, or JSON.",
                "If the user says only a short keyword like Google, RSI, or Tesla, treat it as a request for a brief explanation instead of refusing it as a web search.",
                "If the question is about FastTrade portfolio, risk, positions, or market context, use the available trading context.",
            ]
            if live_market_context:
                prompt_parts.append(f"Live market snapshot: {live_market_context}")
            if alert_context:
                prompt_parts.append(f"Current alert context: {alert_context}")
            prompt_parts.append(f"User request: {question}")
            voice_prompt = " ".join(prompt_parts)
            try:
                answer, _actions = _call_llm(voice_prompt, conversation_history, db)
            except Exception as exc:
                logger.warning("Alexa Fast Trade context failed, falling back to base LLM: %s", exc)
                answer = None

        if not answer:
            fallback_prompt_parts: list[str] = []
            if conversation_context:
                fallback_prompt_parts.append(f"Recent conversation:\n{conversation_context}")
            if live_market_context:
                fallback_prompt_parts.append(f"Live market snapshot:\n{live_market_context}")
            if alert_context:
                fallback_prompt_parts.append(f"Current alert context:\n{alert_context}")
            fallback_prompt_parts.append(f"Current user request:\n{question}")
            fallback_prompt = "\n\n".join(fallback_prompt_parts)

            answer = call_llm(
                prompt=fallback_prompt,
                system_prompt=(
                    "You are Fast Trade AI, a helpful voice assistant similar to ChatGPT. "
                    "You can answer both general questions and trading education questions. "
                    f"{language_instruction} "
                    f"{continuity_instruction} "
                    "Use clear spoken language and keep the response easy to understand. "
                    "Avoid dramatic, slang, or aggressive phrasing. "
                    "If the user only says a short keyword like Google, RSI, or Tesla, interpret it as asking what it is and answer directly. "
                    "Do not claim you cannot search the web unless the user explicitly asks for live real-time web results. "
                    "If live market data or recent conversation is provided, use it directly instead of guessing. "
                    "Do not use markdown, bullet points, or JSON."
                ),
                max_tokens=120,
                temperature=0.2,
                timeout=20.0,
            )

        if not answer:
            analytics["success"] = False
            analytics["error_message"] = "AI service did not return an answer"
            answer = "AI service अभी respond नहीं कर रही है, कृपया थोड़ी देर में फिर कोशिश करें।" if is_hindi else "The AI service is not responding right now. Please try again in a moment."

        _remember_conversation_turn(user_id, "user", question)
        _remember_conversation_turn(user_id, "assistant", answer)
        return respond(answer, reprompt=default_reprompt)

    return respond(
        "यह intent अभी configure नहीं है। सुरक्षा के लिए यह Alexa skill अभी read-only mode में है।" if is_hindi else "That intent is not configured yet. For safety, this Alexa skill is read-only for now.",
        reprompt=default_reprompt,
    )
