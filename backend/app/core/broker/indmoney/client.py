import os
from typing import Any, Dict

import requests


class INDMoneyClient:
    """Minimal INDMoney HTTP client for order placement.

    The exact upstream schema can vary by account setup. This client keeps
    endpoint and payload style configurable through env vars.
    """

    def __init__(self):
        self.base_url = os.getenv("INDMONEY_BASE_URL", "https://api.indstocks.com").rstrip("/")
        self.api_key = os.getenv("INDMONEY_API_KEY", "")
        self.access_token = os.getenv("INDMONEY_ACCESS_TOKEN", "")
        self.client_id = os.getenv("INDMONEY_CLIENT_ID", "")
        self.order_path = os.getenv("INDMONEY_ORDER_PATH", "/order")
        self.payload_style = os.getenv("INDMONEY_PAYLOAD_STYLE", "flat").lower()
        self.timeout = int(os.getenv("INDMONEY_HTTP_TIMEOUT_SECONDS", "15"))

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def _headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.access_token:
            # INDstocks expects raw token value in Authorization header.
            headers["Authorization"] = self.access_token
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        if self.client_id:
            headers["X-CLIENT-ID"] = self.client_id
        return headers

    def headers(self) -> Dict[str, str]:
        """Expose request headers for other INDMoney helper services."""
        return self._headers()

    def _build_payload(self, order: Dict[str, Any]) -> Dict[str, Any]:
        if self.payload_style == "wrapped":
            return {"order": order}
        return order

    def _extract_order_id(self, response_json: Dict[str, Any]) -> str:
        candidates = [
            response_json.get("order_id"),
            response_json.get("id"),
            (response_json.get("data") or {}).get("order_id") if isinstance(response_json.get("data"), dict) else None,
            (response_json.get("data") or {}).get("id") if isinstance(response_json.get("data"), dict) else None,
        ]
        for value in candidates:
            if value:
                return str(value)
        return ""

    def place_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_configured():
            raise RuntimeError("INDMoney is not configured. Set INDMONEY_BASE_URL in .env")

        url = f"{self.base_url}{self.order_path}"
        payload = self._build_payload(order)

        response = requests.post(
            url,
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )

        if response.status_code >= 400:
            raise RuntimeError(
                f"INDMoney order failed ({response.status_code}): {response.text[:500]}"
            )

        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text}

        if isinstance(body, dict) and str(body.get("status", "")).lower() == "error":
            raise RuntimeError(f"INDMoney order error: {body.get('message') or body}")

        order_id = self._extract_order_id(body)
        return {
            "order_id": order_id,
            "response": body,
        }

    def get_instruments_csv(self, source: str) -> str:
        """Fetch instruments CSV from INDstocks by source (fno/equity/index)."""
        if not self.access_token:
            raise RuntimeError("INDMoney access token missing. Set INDMONEY_ACCESS_TOKEN in .env")

        url = f"{self.base_url}/market/instruments"
        response = requests.get(
            url,
            params={"source": source},
            headers=self._headers(),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"INDMoney instruments fetch failed ({response.status_code}): {response.text[:500]}"
            )
        return response.text

    def get_portfolio_positions(self, segment: str = "derivative", product: str = "margin") -> Dict[str, Any]:
        """Fetch positions from INDstocks portfolio endpoint."""
        if not self.access_token:
            raise RuntimeError("INDMoney access token missing. Set INDMONEY_ACCESS_TOKEN in .env")

        url = f"{self.base_url}/portfolio/positions"
        response = requests.get(
            url,
            params={"segment": segment, "product": product},
            headers=self._headers(),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"INDMoney positions fetch failed ({response.status_code}): {response.text[:500]}"
            )

        try:
            body = response.json()
        except Exception:
            return {"raw": response.text}
        return body

    def get_order_book(self) -> Dict[str, Any]:
        """Fetch current day order book from INDstocks."""
        if not self.access_token:
            raise RuntimeError("INDMoney access token missing. Set INDMONEY_ACCESS_TOKEN in .env")

        url = f"{self.base_url}/order-book"
        response = requests.get(
            url,
            headers=self._headers(),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"INDMoney order book fetch failed ({response.status_code}): {response.text[:500]}"
            )
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}

    def get_trade_book(self, segment: str = "DERIVATIVE") -> Dict[str, Any]:
        """Fetch current day trade book for a given segment."""
        if not self.access_token:
            raise RuntimeError("INDMoney access token missing. Set INDMONEY_ACCESS_TOKEN in .env")

        url = f"{self.base_url}/trade-book"
        response = requests.get(
            url,
            params={"segment": segment},
            headers=self._headers(),
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"INDMoney trade book fetch failed ({response.status_code}): {response.text[:500]}"
            )
        try:
            return response.json()
        except Exception:
            return {"raw": response.text}


def get_indmoney_client() -> INDMoneyClient:
    return INDMoneyClient()
