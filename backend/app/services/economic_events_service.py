"""
Real Economic Events Service
Fetch actual earnings, IPOs, dividends, and corporate actions from NSE/BSE
"""
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

import feedparser
import requests
from bs4 import BeautifulSoup

from app.services.rss_feed_service import get_rss_service

logger = logging.getLogger(__name__)


class EconomicEventsService:
    """Service to fetch recent live events from working RSS/news feeds and official sources when available."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36',
    }

    # Official endpoints are attempted first, but many public NSE archive XML URLs are no longer stable.
    CORPORATE_FEEDS = {
        "nse_financial_results": "https://nsearchives.nseindia.com/content/corporate/FinResults.xml",
        "nse_board_meetings": "https://nsearchives.nseindia.com/content/corporate/BoardMeetings.xml",
        "nse_dividends": "https://nsearchives.nseindia.com/content/corporate/DividendInformation.xml",
        "nse_ipo": "https://nsearchives.nseindia.com/content/corporate/IPOInformation.xml",
    }
    RSS_SOURCE_CATEGORIES = ["moneycontrol", "moneycontrol_market", "economic_times"]
    HIGH_IMPACT_TERMS = {
        "rbi", "repo", "monetary policy", "mpc", "cpi", "inflation", "gdp", "fed", "earnings", "results"
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def _parse_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        text = str(value or "").strip()
        if not text:
            return datetime.now()

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                continue
        return datetime.now()

    def _extract_event_datetime(self, text: str, fallback: datetime) -> datetime:
        normalized = re.sub(r"(\d{1,2})(st|nd|rd|th)", r"\1", (text or "").lower())
        month_map = {
            "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
            "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
            "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
        }
        current_year = fallback.year

        patterns = [
            re.finditer(r"\b(?P<day>\d{1,2})\s+(?P<month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+(?P<year>\d{2,4}))?\b", normalized),
            re.finditer(r"\b(?P<month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(?P<day>\d{1,2})(?:,?\s*(?P<year>\d{2,4}))?\b", normalized),
            re.finditer(r"\b(?P<day>\d{1,2})[/-](?P<month>\d{1,2})(?:[/-](?P<year>\d{2,4}))?\b", normalized),
        ]

        for matches in patterns:
            for match in matches:
                try:
                    day = int(match.group("day"))
                    month_token = match.group("month")
                    month = int(month_token) if month_token.isdigit() else month_map.get(month_token[:3], fallback.month)
                    year_token = match.groupdict().get("year")
                    year = int(year_token) if year_token else current_year
                    if year < 100:
                        year += 2000
                    candidate = datetime(year, month, day, fallback.hour, fallback.minute)
                    if candidate < fallback - timedelta(days=45):
                        continue
                    if candidate > fallback + timedelta(days=180):
                        continue
                    return candidate
                except Exception:
                    continue

        return fallback

    def _impact_from_text(self, text: str, default: str = "medium") -> str:
        normalized = (text or "").lower()
        if any(term in normalized for term in self.HIGH_IMPACT_TERMS):
            return "high"
        if any(term in normalized for term in {"dividend", "buyback", "agm", "board meeting", "ipo", "listing"}):
            return "medium"
        return default

    def _extract_symbol(self, text: str) -> Optional[str]:
        pattern = r'\b([A-Z][A-Z0-9]{2,9})\b'
        matches = re.findall(pattern, text or "")
        common_words = {
            'THE', 'FOR', 'AND', 'ANNOUNCES', 'RESULTS', 'BOARD', 'MEETING', 'IPO', 'DATA', 'RELEASE',
            'RBI', 'INDIA', 'WITH', 'FROM', 'THIS', 'THAT', 'ET', 'GDP', 'CPI', 'WPI'
        }
        for match in matches:
            if match not in common_words and len(match) <= 10:
                return match
        return None

    def _build_event(
        self,
        *,
        event_type: str,
        title: str,
        description: str,
        source: str,
        when: datetime,
        impact: str,
        symbol: Optional[str] = None,
        link: str = "",
    ) -> Dict[str, Any]:
        return {
            'type': event_type,
            'title': title.strip() or 'Untitled event',
            'symbol': symbol,
            'date': when.strftime('%Y-%m-%d'),
            'time': when.strftime('%H:%M'),
            'description': description.strip()[:220],
            'impact': impact,
            'source': source,
            'status': 'scheduled' if when.date() >= datetime.now().date() else 'reported',
            'actual': None,
            'forecast': None,
            'link': link,
        }

    def _fetch_official_feed_events(
        self,
        feed_url: str,
        *,
        event_type: str,
        days_ahead: int,
        default_impact: str,
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        try:
            response = self.session.get(feed_url, timeout=5)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            for entry in feed.entries[:limit]:
                title = entry.get('title', '')
                description_html = entry.get('summary', entry.get('description', ''))
                description = BeautifulSoup(description_html, 'html.parser').get_text(' ', strip=True)
                when = datetime.now()
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    when = datetime(*entry.published_parsed[:6])
                when = self._extract_event_datetime(f"{title} {description}", when)
                events.append(
                    self._build_event(
                        event_type=event_type,
                        title=title,
                        description=description,
                        source='NSE',
                        when=when,
                        impact=self._impact_from_text(f"{title} {description}", default_impact),
                        symbol=self._extract_symbol(f"{title} {description}"),
                        link=entry.get('link', ''),
                    )
                )
        except Exception as exc:
            logger.info("Official feed unavailable for %s, falling back to live RSS/news: %s", event_type, exc)
        return self._dedupe_and_filter(events, days_ahead=days_ahead)

    def _fetch_live_news_events(
        self,
        *,
        event_type: str,
        keywords: Iterable[str],
        days_ahead: int,
        default_impact: str = 'medium',
        preferred_categories: Optional[Iterable[str]] = None,
        allow_category_match_without_keyword: bool = False,
    ) -> List[Dict[str, Any]]:
        rss_service = get_rss_service()
        items = rss_service.fetch_all_feeds(categories=self.RSS_SOURCE_CATEGORIES)
        preferred = {c.lower() for c in (preferred_categories or [])}
        keyword_list = [keyword.lower() for keyword in keywords]
        events: List[Dict[str, Any]] = []

        for item in items:
            title = str(item.get('title') or '').strip()
            description = str(item.get('description') or '').strip()
            text = f"{title} {description}".strip()
            if not text:
                continue

            normalized = text.lower()
            category = str(item.get('category') or '').lower()
            keyword_hit = any(keyword in normalized for keyword in keyword_list)
            category_hit = category in preferred if preferred else False
            if not keyword_hit and not (allow_category_match_without_keyword and category_hit):
                continue

            published_at = self._parse_datetime(item.get('published'))
            event_when = self._extract_event_datetime(text, published_at)
            concrete_type = event_type
            if event_type == 'economic' and any(term in normalized for term in ('rbi', 'repo', 'monetary policy', 'mpc')):
                concrete_type = 'rbi'

            events.append(
                self._build_event(
                    event_type=concrete_type,
                    title=title,
                    description=description,
                    source=str(item.get('source') or 'RSS'),
                    when=event_when,
                    impact=self._impact_from_text(text, default_impact),
                    symbol=self._extract_symbol(text),
                    link=str(item.get('link') or ''),
                )
            )

        return self._dedupe_and_filter(events, days_ahead=days_ahead)

    def _dedupe_and_filter(
        self,
        events: List[Dict[str, Any]],
        *,
        days_ahead: int,
        keep_recent_days: int = 7,
    ) -> List[Dict[str, Any]]:
        today = datetime.now().date()
        earliest = today - timedelta(days=min(max(keep_recent_days, 2), 7))
        latest = today + timedelta(days=max(days_ahead, 1))

        deduped: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for event in sorted(events, key=lambda item: (item.get('date', ''), item.get('time', ''), item.get('title', '')), reverse=False):
            event_date = self._parse_datetime(event.get('date')).date()
            if event_date < earliest or event_date > latest:
                continue

            key = (
                str(event.get('type') or ''),
                str(event.get('date') or ''),
                str(event.get('title') or '').strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)

        deduped.sort(key=lambda item: (item.get('date', ''), item.get('time', ''), item.get('title', '')))
        return deduped

    def fetch_earnings_calendar(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch live earnings-related events from official feeds where available, else current RSS news."""
        events = self._fetch_official_feed_events(
            self.CORPORATE_FEEDS["nse_financial_results"],
            event_type='earnings',
            days_ahead=days_ahead,
            default_impact='high',
        )
        if events:
            return events
        return self._fetch_live_news_events(
            event_type='earnings',
            keywords=['earnings', 'results', 'quarterly', 'q1', 'q2', 'q3', 'q4', 'eps'],
            preferred_categories=['earnings'],
            days_ahead=days_ahead,
            default_impact='high',
        )

    def fetch_dividend_calendar(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch live dividend and corporate payout events."""
        events = self._fetch_official_feed_events(
            self.CORPORATE_FEEDS["nse_dividends"],
            event_type='dividend',
            days_ahead=days_ahead,
            default_impact='medium',
            limit=12,
        )
        if events:
            return events
        return self._fetch_live_news_events(
            event_type='dividend',
            keywords=['dividend', 'buyback', 'bonus', 'stock split', 'rights issue'],
            preferred_categories=['corporate'],
            days_ahead=days_ahead,
            default_impact='medium',
        )

    def fetch_board_meetings(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch live board meeting and AGM-related announcements."""
        events = self._fetch_official_feed_events(
            self.CORPORATE_FEEDS["nse_board_meetings"],
            event_type='board_meeting',
            days_ahead=days_ahead,
            default_impact='medium',
            limit=12,
        )
        if events:
            return events
        return self._fetch_live_news_events(
            event_type='board_meeting',
            keywords=['board meeting', 'agm', 'egm', 'annual general meeting'],
            preferred_categories=['corporate'],
            days_ahead=days_ahead,
            default_impact='medium',
        )

    def fetch_ipo_calendar(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch live IPO and listing updates."""
        events = self._fetch_official_feed_events(
            self.CORPORATE_FEEDS["nse_ipo"],
            event_type='ipo',
            days_ahead=days_ahead,
            default_impact='medium',
            limit=10,
        )
        if events:
            return events
        return self._fetch_live_news_events(
            event_type='ipo',
            keywords=['ipo', 'listing', 'public issue', 'public offer', 'offer for sale'],
            preferred_categories=['ipo'],
            days_ahead=days_ahead,
            default_impact='medium',
        )

    def fetch_rbi_events(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch live RBI and macro-economic events from current financial news."""
        rbi_events = self._fetch_live_news_events(
            event_type='rbi',
            keywords=['rbi', 'repo rate', 'monetary policy', 'mpc', 'reserve bank'],
            preferred_categories=['rbi'],
            days_ahead=days_ahead,
            default_impact='high',
            allow_category_match_without_keyword=True,
        )
        macro_events = self._fetch_live_news_events(
            event_type='economic',
            keywords=['inflation', 'cpi', 'wpi', 'gdp', 'pmi', 'iip', 'economic data', 'trade balance'],
            preferred_categories=['economy'],
            days_ahead=days_ahead,
            default_impact='high',
            allow_category_match_without_keyword=True,
        )
        return self._dedupe_and_filter(rbi_events + macro_events, days_ahead=days_ahead)

    def fetch_all_events(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch live event signals across earnings, macro, IPO, dividend, and corporate categories."""
        all_events: List[Dict[str, Any]] = []
        all_events.extend(self.fetch_earnings_calendar(days_ahead))
        all_events.extend(self.fetch_dividend_calendar(days_ahead))
        all_events.extend(self.fetch_board_meetings(days_ahead))
        all_events.extend(self.fetch_ipo_calendar(days_ahead))
        all_events.extend(self.fetch_rbi_events(days_ahead))

        all_events = self._dedupe_and_filter(all_events, days_ahead=days_ahead)

        for event in all_events:
            event_datetime = self._parse_datetime(event['date'])
            base_datetime = datetime.now()
            days_until = (event_datetime.date() - base_datetime.date()).days
            event['days_until'] = days_until

            if days_until < 0:
                event['countdown'] = 'Completed'
            elif days_until == 0:
                event['countdown'] = 'Today'
            elif days_until == 1:
                event['countdown'] = 'Tomorrow'
            elif days_until < 7:
                event['countdown'] = f'In {days_until} days'
            else:
                event['countdown'] = f'In {days_until // 7} week{"s" if days_until // 7 > 1 else ""}'

        return all_events

    def get_today_high_impact(self) -> List[Dict[str, Any]]:
        """Get today's or nearest upcoming high-impact live events."""
        try:
            events = self.fetch_all_events(days_ahead=7)
            today = datetime.now().strftime('%Y-%m-%d')

            today_events = [e for e in events if e.get('date') == today and e.get('impact') == 'high']
            if not today_events:
                today_events = [e for e in events if e.get('impact') == 'high'][:4]

            return today_events[:4]
        except Exception as e:
            logger.error(f"Error getting today's events: {e}")
            return []


# Singleton instance
_events_service = None

def get_events_service() -> EconomicEventsService:
    """Get singleton events service instance"""
    global _events_service
    if _events_service is None:
        _events_service = EconomicEventsService()
    return _events_service
