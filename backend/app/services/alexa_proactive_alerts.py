"""Alexa proactive alert delivery using Amazon Proactive Events API."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.db.models_alexa import AlexaMemory

logger = logging.getLogger(__name__)

ALEXA_PROACTIVE_ALERTS_ENABLED = os.getenv("ALEXA_PROACTIVE_ALERTS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
ALEXA_PROACTIVE_CLIENT_ID = (os.getenv("ALEXA_PROACTIVE_CLIENT_ID") or os.getenv("ALEXA_LWA_CLIENT_ID") or "").strip()
ALEXA_PROACTIVE_CLIENT_SECRET = (os.getenv("ALEXA_PROACTIVE_CLIENT_SECRET") or os.getenv("ALEXA_LWA_CLIENT_SECRET") or "").strip()
ALEXA_PROACTIVE_STAGE = (os.getenv("ALEXA_PROACTIVE_STAGE", "development") or "development").strip().lower()
ALEXA_PROACTIVE_API_BASE = (os.getenv("ALEXA_PROACTIVE_API_BASE", "https://api.amazonalexa.com") or "https://api.amazonalexa.com").rstrip("/")
ALEXA_PROACTIVE_EVENT_NAME = os.getenv("ALEXA_PROACTIVE_EVENT_NAME", "AMAZON.MessageAlert.Activated").strip() or "AMAZON.MessageAlert.Activated"
ALEXA_SKILL_NAME = os.getenv("ALEXA_SKILL_NAME", "Fast Trade AI").strip() or "Fast Trade AI"
try:
    ALEXA_PROACTIVE_DEDUPE_SECONDS = max(60, int(os.getenv("ALEXA_PROACTIVE_DEDUPE_SECONDS", "600")))
except ValueError:
    ALEXA_PROACTIVE_DEDUPE_SECONDS = 600

_RECENT_EVENT_CACHE: dict[str, datetime] = {}
_IN_MEMORY_SUBSCRIBERS: dict[str, dict[str, Any]] = {}


class AlexaProactiveAlertService:
    """Send high-priority Fast Trade alerts to Alexa as proactive notifications."""

    def __init__(self, db: Session):
        self.db = db

    def is_configured(self) -> bool:
        return bool(
            ALEXA_PROACTIVE_ALERTS_ENABLED
            and ALEXA_PROACTIVE_CLIENT_ID
            and ALEXA_PROACTIVE_CLIENT_SECRET
        )

    def get_status(self) -> Dict[str, Any]:
        subscribed_users = self.get_subscribed_users()
        return {
            "enabled": ALEXA_PROACTIVE_ALERTS_ENABLED,
            "configured": self.is_configured(),
            "stage": ALEXA_PROACTIVE_STAGE,
            "event_name": ALEXA_PROACTIVE_EVENT_NAME,
            "subscriber_count": len(subscribed_users),
            "subscribers": subscribed_users,
        }

    def record_subscription_change(
        self,
        *,
        user_id: str,
        locale: str,
        subscriptions: List[str],
        request_timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        cleaned_subscriptions = [str(item).strip() for item in subscriptions if str(item).strip()]
        enabled = ALEXA_PROACTIVE_EVENT_NAME in cleaned_subscriptions or bool(cleaned_subscriptions)
        payload = {
            "enabled": enabled,
            "subscriptions": cleaned_subscriptions,
            "updated_at": request_timestamp or datetime.now(timezone.utc).isoformat(),
        }

        _IN_MEMORY_SUBSCRIBERS[user_id] = {
            "user_id": user_id,
            "locale": locale or "en-US",
            "enabled": enabled,
            "subscriptions": cleaned_subscriptions,
            "updated_at": payload["updated_at"],
        }

        try:
            record = (
                self.db.query(AlexaMemory)
                .filter(
                    AlexaMemory.user_id == user_id,
                    AlexaMemory.memory_type == "proactive_subscription",
                )
                .order_by(AlexaMemory.updated_at.desc())
                .first()
            )
            if record:
                record.content = json.dumps(payload)
                record.locale = locale or record.locale or "en-US"
                record.is_active = enabled
            else:
                self.db.add(
                    AlexaMemory(
                        user_id=user_id,
                        memory_type="proactive_subscription",
                        content=json.dumps(payload),
                        locale=locale or "en-US",
                        is_active=enabled,
                    )
                )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.info("Stored Alexa proactive subscription for %s in memory fallback only: %s", user_id, exc)

        return {
            "user_id": user_id,
            "enabled": enabled,
            "subscriptions": cleaned_subscriptions,
        }

    def get_subscribed_users(self) -> List[Dict[str, str]]:
        users: List[Dict[str, str]] = []
        seen: set[str] = set()
        try:
            records = (
                self.db.query(AlexaMemory)
                .filter(AlexaMemory.memory_type == "proactive_subscription")
                .order_by(AlexaMemory.updated_at.desc())
                .limit(200)
                .all()
            )
            for record in records:
                user_id = str(record.user_id or "").strip()
                if not user_id or user_id in seen:
                    continue
                seen.add(user_id)

                enabled = bool(record.is_active)
                subscriptions: List[str] = []
                try:
                    payload = json.loads(record.content or "{}")
                    enabled = bool(payload.get("enabled", enabled))
                    subscriptions = [str(item).strip() for item in payload.get("subscriptions", []) if str(item).strip()]
                except Exception:
                    subscriptions = []

                if not enabled:
                    continue
                if subscriptions and ALEXA_PROACTIVE_EVENT_NAME not in subscriptions:
                    continue

                users.append({
                    "user_id": user_id,
                    "locale": record.locale or "en-US",
                })
        except Exception as exc:
            logger.info("Alexa proactive subscriber lookup is using in-memory fallback: %s", exc)

        for user_id, payload in _IN_MEMORY_SUBSCRIBERS.items():
            if user_id in seen or not payload.get("enabled"):
                continue
            subscriptions = [str(item).strip() for item in payload.get("subscriptions", []) if str(item).strip()]
            if subscriptions and ALEXA_PROACTIVE_EVENT_NAME not in subscriptions:
                continue
            users.append({
                "user_id": user_id,
                "locale": str(payload.get("locale") or "en-US"),
            })
            seen.add(user_id)

        return users

    def _get_access_token(self) -> Optional[str]:
        if not self.is_configured():
            return None

        try:
            response = httpx.post(
                "https://api.amazon.com/auth/o2/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": ALEXA_PROACTIVE_CLIENT_ID,
                    "client_secret": ALEXA_PROACTIVE_CLIENT_SECRET,
                    "scope": "alexa::proactive_events",
                },
                timeout=10.0,
            )
            response.raise_for_status()
            return str(response.json().get("access_token") or "").strip() or None
        except Exception as exc:
            logger.warning("Failed to obtain Alexa proactive-events token: %s", exc)
            return None

    def _should_skip_duplicate(self, dedupe_key: str) -> bool:
        now = datetime.now(timezone.utc)
        stale_keys = [
            key for key, timestamp in _RECENT_EVENT_CACHE.items()
            if (now - timestamp).total_seconds() > ALEXA_PROACTIVE_DEDUPE_SECONDS
        ]
        for key in stale_keys:
            _RECENT_EVENT_CACHE.pop(key, None)

        last_sent = _RECENT_EVENT_CACHE.get(dedupe_key)
        if last_sent and (now - last_sent).total_seconds() < ALEXA_PROACTIVE_DEDUPE_SECONDS:
            return True

        _RECENT_EVENT_CACHE[dedupe_key] = now
        return False

    def send_notification(
        self,
        *,
        title: str,
        message: str,
        severity: str = "high",
        user_id: Optional[str] = None,
        locale: Optional[str] = None,
        reference_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "reason": "not-configured"}

        recipients = (
            [{"user_id": user_id, "locale": locale or "en-US"}]
            if user_id
            else self.get_subscribed_users()
        )
        if not recipients:
            return {"ok": False, "reason": "no-subscribers"}

        access_token = self._get_access_token()
        if not access_token:
            return {"ok": False, "reason": "token-unavailable"}

        attempted = 0
        sent = 0
        errors: List[str] = []
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=4)
        creator_name = f"{ALEXA_SKILL_NAME} {severity.title()} Alerts"[:60]

        for recipient in recipients:
            target_user = str(recipient.get("user_id") or "").strip()
            target_locale = str(recipient.get("locale") or locale or "en-US").strip() or "en-US"
            if not target_user:
                continue

            dedupe_key = f"{target_user}:{severity}:{title.strip().lower()}:{message.strip().lower()[:120]}"
            if self._should_skip_duplicate(dedupe_key):
                continue

            attempted += 1
            event_payload = {
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "referenceId": reference_id or f"fasttrade-{severity}-{uuid4().hex[:18]}",
                "expiryTime": expiry.isoformat().replace("+00:00", "Z"),
                "event": {
                    "name": ALEXA_PROACTIVE_EVENT_NAME,
                    "payload": {
                        "state": {
                            "status": "UNREAD",
                            "freshness": "NEW",
                        },
                        "messageGroup": {
                            "creator": {
                                "name": creator_name,
                            },
                            "count": 1,
                        },
                    },
                },
                "localizedAttributes": [
                    {
                        "locale": target_locale,
                    }
                ],
                "relevantAudience": {
                    "type": "Unicast",
                    "payload": {
                        "user": target_user,
                    },
                },
            }

            try:
                response = httpx.post(
                    f"{ALEXA_PROACTIVE_API_BASE}/v1/proactiveEvents/stages/{ALEXA_PROACTIVE_STAGE}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=event_payload,
                    timeout=10.0,
                )
                response.raise_for_status()
                sent += 1
            except Exception as exc:
                errors.append(f"{target_user}: {exc}")
                logger.warning("Alexa proactive alert failed for %s: %s", target_user, exc)

        return {
            "ok": sent > 0,
            "attempted": attempted,
            "sent": sent,
            "errors": errors,
        }


def get_alexa_proactive_alert_service(db: Session) -> AlexaProactiveAlertService:
    return AlexaProactiveAlertService(db)
