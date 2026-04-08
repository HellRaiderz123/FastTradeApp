from abc import ABC, abstractmethod
from typing import Dict, Any
import json as _json


def get_ticket(intent) -> dict:
    """Safely get intent.ticket as a dict, handling string migration artifact."""
    ticket = getattr(intent, "ticket", None) or {}
    if isinstance(ticket, str):
        try:
            return _json.loads(ticket)
        except Exception:
            return {}
    return ticket if isinstance(ticket, dict) else {}


class ExecutionAdapter(ABC):
    """
    Base interface for ALL execution engines
    (Paper, Zerodha, Future brokers)
    """

    @abstractmethod
    def execute(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute entry orders.
        Must return execution result dict.
        """
        pass

    @abstractmethod
    def mtm(self, intent) -> float:
        """
        Mark-to-market PnL.
        Returns unrealized PnL.
        """
        pass

    @abstractmethod
    def exit(self, intent) -> Dict[str, Any]:
        """
        Exit all open positions for intent.
        """
        pass

    def sync_protection(self, intent) -> Dict[str, Any]:
        """Best-effort broker-side TP/SL sync for the current position."""
        return {
            "provider": "APP_ONLY",
            "enabled": False,
            "reason": "Broker-side protection is not implemented for this execution adapter.",
        }

    def cancel_protection(self, intent) -> Dict[str, Any]:
        """Best-effort cancellation for any outstanding broker-side protection."""
        return {
            "provider": "APP_ONLY",
            "cancelled": False,
            "reason": "No broker-side protection cancellation is required for this execution adapter.",
        }

from typing import Dict, Any

class SignalResult(Dict[str, Any]):
    """
    Standard signal format used everywhere.
    """
    pass

