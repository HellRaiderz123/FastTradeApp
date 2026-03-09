import csv
import io
import logging
import os
import time
from typing import Dict, Optional

from app.core.broker.indmoney.client import INDMoneyClient

logger = logging.getLogger(__name__)


class INDMoneyInstrumentsResolver:
    """Resolve symbol to security_id using INDstocks instruments CSV with in-memory TTL cache."""

    def __init__(self, client: INDMoneyClient):
        self.client = client
        self.ttl_seconds = int(os.getenv("INDMONEY_INSTRUMENTS_CACHE_TTL_SECONDS", "900"))
        self._cache: Dict[str, str] = {}
        self._cache_ts: float = 0.0

    @staticmethod
    def _norm_symbol(symbol: str) -> str:
        return (symbol or "").strip().upper().replace(" ", "")

    @staticmethod
    def _pick(row: Dict[str, str], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip() != "":
                return str(value).strip()
        return ""

    def _parse_csv_map(self, csv_text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        if not csv_text.strip():
            return out

        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            symbol = self._pick(row, "TRADING_SYMBOL", "trading_symbol", "tradingsymbol", "SYMBOL")
            security_id = self._pick(row, "SECURITY_ID", "security_id", "SCRIP_CODE", "scrip_code")
            if not symbol or not security_id:
                continue
            out[self._norm_symbol(symbol)] = security_id
        return out

    def _refresh(self) -> None:
        merged: Dict[str, str] = {}
        for source in ("fno", "equity", "index"):
            try:
                csv_text = self.client.get_instruments_csv(source=source)
                merged.update(self._parse_csv_map(csv_text))
            except Exception as exc:
                logger.warning("INDMoney instruments fetch failed for source=%s: %s", source, exc)

        if merged:
            self._cache = merged
            self._cache_ts = time.time()
            logger.info("INDMoney instruments cache loaded: %s symbols", len(self._cache))

    def _ensure_cache(self) -> None:
        stale = (time.time() - self._cache_ts) > self.ttl_seconds
        if not self._cache or stale:
            self._refresh()

    def resolve_security_id(self, symbol: str) -> Optional[str]:
        lookup = self._norm_symbol(symbol)
        if not lookup:
            return None

        self._ensure_cache()
        return self._cache.get(lookup)


def get_indmoney_instruments_resolver(client: Optional[INDMoneyClient] = None) -> INDMoneyInstrumentsResolver:
    return INDMoneyInstrumentsResolver(client or INDMoneyClient())
