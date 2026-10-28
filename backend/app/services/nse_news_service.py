import asyncio
import io
import logging
import re
from datetime import datetime
from typing import List, Optional, Set
import feedparser
import fitz  # PyMuPDF
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DisclosedNewsItem(BaseModel):
    source: str  # "NSE_OFFICIAL" or "BSE_OFFICIAL"
    symbol: str
    company_name: str
    headline: str
    description: Optional[str] = ""
    pdf_url: Optional[str] = None
    pdf_summary: Optional[str] = None
    category: str
    materiality_score: float = Field(ge=0.0, le=1.0)
    is_high_impact: bool
    published_at: str


class NSENewsService:
    NSE_BASE_URL = "https://www.nseindia.com"
    NSE_ANNOUNCEMENTS_ENDPOINT = "/api/corporate-announcements?index=equities"

    BSE_API_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"
    BSE_NOTICES_XML = "https://www.bseindia.com/data/xml/notices.xml"

    HEADERS_BSE = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.bseindia.com/corporates/ann.html",
        "Origin": "https://www.bseindia.com",
    }

    HIGH_IMPACT_PATTERNS = [
        r"order\s*win|awarded|contract|bagged",
        r"dividend|bonus|split|buyback",
        r"financial\s*results|quarterly\s*results|earnings|loss|profit",
        r"acquisition|merger|demerger|amalgamation|takeover",
        r"usfda|form\s*483|warning\s*letter|eir|approval",
        r"credit\s*rating|upgrade|downgrade",
        r"resignation|appointment\s*of\s*(ceo|cfo|md)",
    ]

    NOISE_PATTERNS = [
        r"loss\s*of\s*share\s*certificate",
        r"duplicate\s*share\s*certificate",
        r"trading\s*window\s*closure",
        r"newspaper\s*publication",
    ]

    def _calculate_materiality(self, text: str) -> tuple[float, bool]:
        text_lower = text.lower()
        if any(re.search(pat, text_lower) for pat in self.NOISE_PATTERNS):
            return 0.1, False

        score = 0.35
        for pat in self.HIGH_IMPACT_PATTERNS:
            if re.search(pat, text_lower):
                score += 0.35

        score = min(score, 1.0)
        return round(score, 2), (score >= 0.65)

    async def _extract_text_from_pdf(self, pdf_url: str) -> Optional[str]:
        if not pdf_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(pdf_url)
                if resp.status_code == 200:
                    with fitz.open(stream=io.BytesIO(resp.content), filetype="pdf") as doc:
                        pages = [doc[i].get_text() for i in range(min(2, len(doc)))]
                        raw_text = " ".join(pages)
                        return " ".join(raw_text.split())[:1200]
        except Exception:
            return None
        return None

    async def fetch_bse_announcements(self) -> List[DisclosedNewsItem]:
        """Fetches directly from BSE's live announcements JSON feed."""
        items: List[DisclosedNewsItem] = []
        # Local seen set per call — avoids singleton deduplication bug
        seen: Set[str] = set()
        today_str = datetime.now().strftime("%Y%m%d")

        params = {
            "pageno": "1",
            "strCat": "-1",
            "strPrevDate": today_str,
            "strScrip": "",
            "strSearch": "P",
            "strToDate": today_str,
            "strType": "C",
            "subcategory": "",
        }

        try:
            async with httpx.AsyncClient(headers=self.HEADERS_BSE, timeout=10.0) as client:
                resp = await client.get(self.BSE_API_URL, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    rows = data.get("Table", [])
                    for row in rows[:30]:
                        symbol = row.get("SCRIP_CD", "")
                        company_name = row.get("SLONGNAME", symbol)
                        headline = row.get("NEWSSUB", "") or row.get("HEADLINE", "")
                        pdf_file = row.get("ATTACHMENTNAME", "")
                        pdf_url = f"https://www.bseindia.com/xml-data/corpfiling/AttachLive/{pdf_file}" if pdf_file else None

                        event_hash = f"BSE_{symbol}_{row.get('NEWSID', headline[:20])}"
                        if event_hash in seen:
                            continue
                        seen.add(event_hash)

                        materiality, is_high_impact = self._calculate_materiality(f"{headline} {company_name}")
                        pdf_summary = await self._extract_text_from_pdf(pdf_url) if is_high_impact and pdf_url else None

                        items.append(
                            DisclosedNewsItem(
                                source="BSE_OFFICIAL",
                                symbol=str(symbol),
                                company_name=company_name,
                                headline=headline,
                                description=row.get("CATEGORYNAME", ""),
                                pdf_url=pdf_url,
                                pdf_summary=pdf_summary,
                                category=row.get("CATEGORYNAME", "Corporate Filing"),
                                materiality_score=materiality,
                                is_high_impact=is_high_impact,
                                published_at=row.get("NEWS_DT", datetime.now().isoformat()),
                            )
                        )
                    if items:
                        return items
        except Exception as e:
            logger.warning(f"BSE JSON API fetch failed: {e}. Trying BSE XML notices fallback.")

        # Fallback: BSE Notices RSS/XML
        try:
            feed = feedparser.parse(self.BSE_NOTICES_XML)
            for entry in feed.entries[:20]:
                title = entry.get("title", "")
                link = entry.get("link", "")
                if link in seen:
                    continue
                seen.add(link)

                materiality, is_high_impact = self._calculate_materiality(title)
                items.append(
                    DisclosedNewsItem(
                        source="BSE_OFFICIAL",
                        symbol="BSE_NOTICE",
                        company_name="BSE Notice",
                        headline=title,
                        description=entry.get("summary", ""),
                        pdf_url=link if link.endswith(".pdf") else None,
                        category="Notice",
                        materiality_score=materiality,
                        is_high_impact=is_high_impact,
                        published_at=entry.get("published", datetime.now().isoformat()),
                    )
                )
        except Exception as e:
            logger.error(f"BSE XML fallback error: {e}")

        return items

    def _fetch_nse_rows_sync(self) -> list:
        """Sync helper — runs in a thread executor so it doesn't block the event loop."""
        import json as _json
        import urllib.parse
        import requests as _req

        _HEADERS = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
        }
        url = f"{self.NSE_BASE_URL}{self.NSE_ANNOUNCEMENTS_ENDPOINT}"

        # 1. Direct fetch
        try:
            r = _req.get(url, headers=_HEADERS, timeout=20)
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else data.get("data", [])
                if rows:
                    logger.info("nse_news: direct fetch OK (%d rows)", len(rows))
                    return rows
            logger.warning("nse_news: direct fetch status %s", r.status_code)
        except Exception as e:
            logger.warning("nse_news: direct fetch failed: %s", e)

        # 2. allorigins proxy fallback
        try:
            proxy = f"https://api.allorigins.win/get?url={urllib.parse.quote(url, safe='')}"
            r = _req.get(proxy, timeout=30)
            if r.status_code == 200:
                contents = r.json().get("contents") or "null"
                data = _json.loads(contents)
                if data:
                    rows = data if isinstance(data, list) else data.get("data", [])
                    if rows:
                        logger.info("nse_news: allorigins proxy OK (%d rows)", len(rows))
                        return rows
        except Exception as e:
            logger.warning("nse_news: allorigins proxy failed: %s", e)

        logger.warning("nse_news: no data from any source")
        return []

    async def fetch_nse_announcements(self) -> List[DisclosedNewsItem]:
        """Fetch NSE corporate announcements — Mac UA + correct Referer + allorigins fallback."""
        loop = asyncio.get_event_loop()
        rows = await loop.run_in_executor(None, self._fetch_nse_rows_sync)

        # Local seen set per call — avoids singleton deduplication bug
        seen: Set[str] = set()

        if not rows:
            return []

        items: List[DisclosedNewsItem] = []
        for row in rows:
            symbol = row.get("symbol", "").strip()
            desc = row.get("desc", "")
            headline = desc or row.get("attchmntText", "")
            att_url = row.get("attchmntFile")

            if not symbol or not headline:
                continue

            event_hash = f"NSE_{symbol}_{row.get('seq_id', headline[:20])}"
            if event_hash in seen:
                continue
            seen.add(event_hash)

            materiality, is_high_impact = self._calculate_materiality(f"{headline} {desc}")
            pdf_summary = await self._extract_text_from_pdf(att_url) if is_high_impact and att_url else None

            items.append(
                DisclosedNewsItem(
                    source="NSE_OFFICIAL",
                    symbol=symbol,
                    company_name=row.get("sm_name", symbol),
                    headline=headline,
                    description=row.get("attchmntText", desc),
                    pdf_url=att_url,
                    pdf_summary=pdf_summary,
                    category=row.get("smIndustry") or "Corporate Filing",
                    materiality_score=materiality,
                    is_high_impact=is_high_impact,
                    published_at=row.get("sort_date", datetime.now().isoformat()),
                )
            )
        logger.info("nse_news: returning %d announcements", len(items))
        return items
