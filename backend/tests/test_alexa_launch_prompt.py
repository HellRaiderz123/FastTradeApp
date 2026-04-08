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


class _FakeDB:
    pass


def test_launch_request_speaks_follow_up_question(monkeypatch):
    monkeypatch.setattr("app.api.routes.alexa._log_alexa_interaction", lambda *args, **kwargs: None)

    payload = {
        "version": "1.0",
        "session": {
            "new": True,
            "sessionId": "SessionId.test",
            "application": {"applicationId": "amzn1.ask.skill.test"},
            "user": {"userId": "amzn1.ask.account.test"},
        },
        "request": {
            "type": "LaunchRequest",
            "requestId": "EdwRequestId.test",
            "locale": "en-IN",
            "timestamp": "2026-04-08T10:00:00Z",
        },
    }

    response = asyncio.run(alexa_skill(_FakeRequest(payload), db=_FakeDB()))

    spoken = response["response"]["outputSpeech"]["text"]

    assert "Welcome to Fast Trade AI." in spoken
    assert "How can I help with Fast Trade?" in spoken
    assert response["response"]["shouldEndSession"] is False
