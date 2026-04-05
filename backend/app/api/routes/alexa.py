import logging
import os
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.routes.ai_chat import _call_llm
from app.db.session import SessionLocal
from app.services.llm_service import call_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alexa", tags=["Alexa"])

ALEXA_SKILL_NAME = os.getenv("ALEXA_SKILL_NAME", "Fast Trade AI")
ALEXA_ALLOWED_SKILL_ID = os.getenv("ALEXA_ALLOWED_SKILL_ID", "").strip()
ALEXA_ENFORCE_SKILL_ID = os.getenv("ALEXA_ENFORCE_SKILL_ID", "false").strip().lower() in {"1", "true", "yes", "on"}
DEFAULT_REPROMPT = "You can ask about your portfolio, market outlook, or even general questions like explain RSI or summarize the news."
TRADING_KEYWORDS = {
    "portfolio", "position", "positions", "trade", "trades", "trading", "market", "stock", "stocks",
    "option", "options", "nifty", "bank nifty", "sensex", "risk", "profit", "loss", "scanner",
    "watchlist", "signal", "candlestick", "rsi", "macd", "zerodha", "fast trade", "fasttrade",
}


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


def _response(text: str, reprompt: str | None = None, end_session: bool = False) -> dict[str, Any]:
    spoken_text = _normalize_for_voice(text)
    payload: dict[str, Any] = {
        "version": "1.0",
        "sessionAttributes": {},
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


def _extract_question(intent: dict[str, Any]) -> str:
    slots = intent.get("slots") or {}
    for slot_name in ("question", "query", "topic", "subject", "anything"):
        slot = slots.get(slot_name) or {}
        value = (slot.get("value") or "").strip()
        if value:
            return value
    return ""


def _should_use_fasttrade_context(intent_name: str, question: str) -> bool:
    if intent_name in {"PortfolioSummaryIntent", "RiskStatusIntent", "MarketBriefIntent"}:
        return True
    normalized = question.strip().lower()
    return any(keyword in normalized for keyword in TRADING_KEYWORDS)


def _default_question(intent_name: str) -> str:
    defaults = {
        "PortfolioSummaryIntent": "Give me a short spoken summary of my portfolio, open positions, and important alerts.",
        "RiskStatusIntent": "Give me a short spoken summary of my current trading risk and any open-position concerns.",
        "MarketBriefIntent": "Give me a short spoken market brief for today.",
        "AMAZON.FallbackIntent": "Give me a short helpful answer to the user's request.",
    }
    return defaults.get(intent_name, "")


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


@router.post("/skill")
async def alexa_skill(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        logger.warning("Invalid Alexa request payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Alexa payload") from exc

    app_id = (
        payload.get("session", {}).get("application", {}).get("applicationId")
        or payload.get("context", {}).get("System", {}).get("application", {}).get("applicationId")
        or ""
    )
    if ALEXA_ALLOWED_SKILL_ID and app_id and app_id != ALEXA_ALLOWED_SKILL_ID:
        if ALEXA_ENFORCE_SKILL_ID:
            raise HTTPException(status_code=403, detail="Alexa skill ID mismatch")
        logger.warning("Alexa skill ID mismatch in non-strict mode: received=%s", app_id)

    req = payload.get("request") or {}
    req_type = req.get("type")

    if req_type == "LaunchRequest":
        return _response(
            f"Welcome to {ALEXA_SKILL_NAME}. You can ask about your portfolio, the market, or general questions.",
            reprompt=DEFAULT_REPROMPT,
        )

    if req_type == "SessionEndedRequest":
        return {"version": "1.0", "response": {"shouldEndSession": True}}

    if req_type != "IntentRequest":
        return _response("Sorry, I could not understand that Alexa request.", reprompt=DEFAULT_REPROMPT)

    intent = req.get("intent") or {}
    intent_name = intent.get("name", "")
    logger.info("Alexa intent received: %s", intent_name)

    if intent_name == "AMAZON.HelpIntent":
        return _response(
            "You can ask for your portfolio summary, current risk, a market update, or even a general question like what is RSI.",
            reprompt=DEFAULT_REPROMPT,
        )

    if intent_name in {"AMAZON.CancelIntent", "AMAZON.StopIntent", "AMAZON.NavigateHomeIntent"}:
        return _response("Goodbye.", end_session=True)

    if intent_name in {
        "AskFastTradeIntent",
        "AskNvidiaIntent",
        "GenericQuestionIntent",
        "MarketBriefIntent",
        "PortfolioSummaryIntent",
        "RiskStatusIntent",
        "AMAZON.FallbackIntent",
    } or _extract_question(intent):
        question = _extract_question(intent) or _default_question(intent_name)
        if not question:
            return _response("Please ask a question, for example: what are my open positions or what is RSI?", reprompt=DEFAULT_REPROMPT)

        use_fasttrade_context = _should_use_fasttrade_context(intent_name, question)
        answer = None

        if use_fasttrade_context:
            voice_prompt = (
                "You are replying through Alexa for Fast Trade AI. "
                "Answer in under three short sentences, optimized for voice. "
                "Do not use markdown, bullet points, or JSON. "
                "If the question is about FastTrade portfolio, risk, positions, or market context, use the available trading context. "
                f"User request: {question}"
            )
            try:
                answer, _actions = _call_llm(voice_prompt, [], db)
            except Exception as exc:
                logger.warning("Alexa Fast Trade context failed, falling back to base LLM: %s", exc)
                answer = None

        if not answer:
            answer = call_llm(
                prompt=question,
                system_prompt=(
                    "You are replying through Alexa for Fast Trade AI, a helpful voice assistant similar to ChatGPT. "
                    "You can answer both general questions and trading education questions. "
                    "Keep the answer under three short sentences. "
                    "Do not use markdown, bullet points, or JSON."
                ),
                max_tokens=180,
                temperature=0.2,
                timeout=20.0,
            )

        if not answer:
            answer = "The AI service is not responding right now. Please try again in a moment."

        return _response(answer, reprompt=DEFAULT_REPROMPT)

    return _response(
        "That intent is not configured yet. For safety, this Alexa skill is read-only for now.",
        reprompt=DEFAULT_REPROMPT,
    )
