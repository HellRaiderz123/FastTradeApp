import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.api.routes.alexa import alexa_skill


class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        return self._payload


async def _noop_progressive(*args, **kwargs):
    return None


class _FakeDB:
    pass


def test_generic_single_word_question_is_rewritten_as_explainer(monkeypatch):
    monkeypatch.setattr("app.api.routes.alexa._log_alexa_interaction", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "app.api.routes.alexa._load_persistent_user_memory",
        lambda db, user_id: {"notes": [], "reminders": [], "journal": [], "watchlist": []},
    )
    monkeypatch.setattr("app.api.routes.alexa._send_progressive_response", _noop_progressive)

    captured = {}

    def _fake_call_llm(*, prompt, system_prompt, max_tokens, temperature, timeout):
        captured["prompt"] = prompt
        return "Google is a technology company best known for search, Android, and cloud services."

    monkeypatch.setattr("app.api.routes.alexa.call_llm", _fake_call_llm)

    payload = {
        "version": "1.0",
        "session": {
            "new": False,
            "sessionId": "SessionId.test.generic",
            "application": {"applicationId": "amzn1.ask.skill.test"},
            "user": {"userId": "amzn1.ask.account.test"},
        },
        "request": {
            "type": "IntentRequest",
            "requestId": "EdwRequestId.test.generic",
            "locale": "en-IN",
            "timestamp": "2026-04-08T10:05:00Z",
            "intent": {
                "name": "GenericQuestionIntent",
                "slots": {
                    "question": {"name": "question", "value": "google"}
                },
            },
        },
    }

    response = asyncio.run(alexa_skill(_FakeRequest(payload), db=_FakeDB()))

    assert response["response"]["outputSpeech"]["text"].startswith("Google is a technology company")
    lowered_prompt = captured["prompt"].lower()
    assert "what google is" in lowered_prompt or "what is google" in lowered_prompt
