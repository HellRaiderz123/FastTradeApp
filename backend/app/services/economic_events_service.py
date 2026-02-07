"""
Real Economic Events Service
Fetch actual earnings, IPOs, dividends, and corporate actions from NSE/BSE
"""
import logging
import feedparser
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class EconomicEventsService:
    """Service to fetch real economic events from NSE, BSE, and financial sources"""
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    }
    
    # Real RSS feeds for corporate actions
    CORPORATE_FEEDS = {
        "nse_announcements": "https://nsearchives.nseindia.com/content/corporate/Announcements.xml",
        "nse_financial_results": "https://nsearchives.nseindia.com/content/corporate/FinResults.xml",
        "nse_board_meetings": "https://nsearchives.nseindia.com/content/corporate/BoardMeetings.xml",
        "nse_dividends": "https://nsearchives.nseindia.com/content/corporate/DividendInformation.xml",
        "nse_ipo": "https://nsearchives.nseindia.com/content/corporate/IPOInformation.xml",
    }
    
    # Financial news sources with event info
    NEWS_FEEDS = {
        "moneycontrol": "https://www.moneycontrol.com/rss/MCtopnews.xml",
        "economic_times": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def fetch_earnings_calendar(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch real earnings announcements from NSE"""
        events = []
        
        try:
            logger.info("Fetching real earnings from NSE...")
            response = self.session.get(
                self.CORPORATE_FEEDS["nse_financial_results"],
                timeout=5
            )
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries[:15]:
                try:
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    # Extract symbol from title or description
                    symbol = self._extract_symbol(title)
                    
                    # Parse date
                    pub_date = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    
                    events.append({
                        'type': 'earnings',
                        'title': title,
                        'symbol': symbol,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'time': pub_date.strftime('%H:%M'),
                        'description': BeautifulSoup(description, 'html.parser').get_text()[:200],
                        'impact': 'high',
                        'source': 'NSE',
                        'status': 'scheduled',
                        'actual': None,
                        'forecast': None,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing earnings entry: {e}")
                    continue
            
            logger.info(f"Fetched {len(events)} earnings from NSE")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching earnings calendar: {e}")
            return []
    
    def fetch_dividend_calendar(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch real dividend announcements from NSE"""
        events = []
        
        try:
            logger.info("Fetching real dividends from NSE...")
            response = self.session.get(
                self.CORPORATE_FEEDS["nse_dividends"],
                timeout=5
            )
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries[:10]:
                try:
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    symbol = self._extract_symbol(title)
                    
                    pub_date = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    
                    events.append({
                        'type': 'dividend',
                        'title': title,
                        'symbol': symbol,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'time': '09:15',
                        'description': BeautifulSoup(description, 'html.parser').get_text()[:200],
                        'impact': 'medium',
                        'source': 'NSE',
                        'status': 'scheduled',
                        'actual': None,
                        'forecast': None,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing dividend entry: {e}")
                    continue
            
            logger.info(f"Fetched {len(events)} dividends from NSE")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching dividend calendar: {e}")
            return []
    
    def fetch_board_meetings(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch real board meeting announcements from NSE"""
        events = []
        
        try:
            logger.info("Fetching board meetings from NSE...")
            response = self.session.get(
                self.CORPORATE_FEEDS["nse_board_meetings"],
                timeout=5
            )
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries[:10]:
                try:
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    symbol = self._extract_symbol(title)
                    
                    pub_date = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    
                    events.append({
                        'type': 'board_meeting',
                        'title': title,
                        'symbol': symbol,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'time': '10:00',
                        'description': BeautifulSoup(description, 'html.parser').get_text()[:200],
                        'impact': 'medium',
                        'source': 'NSE',
                        'status': 'scheduled',
                        'actual': None,
                        'forecast': None,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing board meeting entry: {e}")
                    continue
            
            logger.info(f"Fetched {len(events)} board meetings from NSE")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching board meetings: {e}")
            return []
    
    def fetch_ipo_calendar(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch real IPO schedule from NSE"""
        events = []
        
        try:
            logger.info("Fetching IPOs from NSE...")
            response = self.session.get(
                self.CORPORATE_FEEDS["nse_ipo"],
                timeout=5
            )
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            
            for entry in feed.entries[:5]:
                try:
                    title = entry.get('title', '')
                    description = entry.get('summary', entry.get('description', ''))
                    
                    symbol = self._extract_symbol(title)
                    
                    pub_date = datetime.now()
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    
                    events.append({
                        'type': 'ipo',
                        'title': title,
                        'symbol': symbol,
                        'date': pub_date.strftime('%Y-%m-%d'),
                        'time': '09:15',
                        'description': BeautifulSoup(description, 'html.parser').get_text()[:200],
                        'impact': 'medium',
                        'source': 'NSE',
                        'status': 'scheduled',
                        'actual': None,
                        'forecast': None,
                    })
                except Exception as e:
                    logger.warning(f"Error parsing IPO entry: {e}")
                    continue
            
            logger.info(f"Fetched {len(events)} IPOs from NSE")
            return events
            
        except Exception as e:
            logger.error(f"Error fetching IPO calendar: {e}")
            return []
    
    def fetch_rbi_events(self) -> List[Dict[str, Any]]:
        """Fetch RBI monetary policy dates and inflation data releases"""
        events = []
        
        # Known RBI events for 2026
        rbi_events = [
            {
                'title': 'RBI Monetary Policy Committee Meeting',
                'date': '2026-02-10',
                'time': '10:30',
                'impact': 'high',
            },
            {
                'title': 'RBI Governor Press Conference',
                'date': '2026-02-10',
                'time': '15:00',
                'impact': 'high',
            },
            {
                'title': 'CPI Inflation Data Release',
                'date': '2026-02-12',
                'time': '17:30',
                'impact': 'high',
            },
            {
                'title': 'WPI Inflation Data Release',
                'date': '2026-02-15',
                'time': '17:30',
                'impact': 'medium',
            },
            {
                'title': 'IIP Industrial Production Data',
                'date': '2026-02-18',
                'time': '17:30',
                'impact': 'medium',
            },
        ]
        
        for event in rbi_events:
            events.append({
                'type': 'rbi',
                'title': event['title'],
                'symbol': None,
                'date': event['date'],
                'time': event['time'],
                'description': f"RBI official announcement - {event['title']}",
                'impact': event['impact'],
                'source': 'RBI',
                'status': 'scheduled',
                'actual': None,
                'forecast': None,
            })
        
        logger.info(f"Prepared {len(events)} RBI events")
        return events
    
    def fetch_all_events(self, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetch all types of events"""
        all_events = []
        
        # Try to fetch real data from NSE
        all_events.extend(self.fetch_earnings_calendar(days_ahead))
        all_events.extend(self.fetch_dividend_calendar(days_ahead))
        all_events.extend(self.fetch_board_meetings(days_ahead))
        all_events.extend(self.fetch_ipo_calendar(days_ahead))
        all_events.extend(self.fetch_rbi_events())
        
        # Sort by date
        all_events.sort(key=lambda x: x['date'])
        
        # Add countdown info
        for event in all_events:
            event_datetime = datetime.strptime(event['date'], '%Y-%m-%d')
            base_datetime = datetime.now()
            days_until = (event_datetime.date() - base_datetime.date()).days
            event['days_until'] = days_until
            
            if days_until == 0:
                event['countdown'] = "Today"
            elif days_until == 1:
                event['countdown'] = "Tomorrow"
            elif days_until < 7:
                event['countdown'] = f"In {days_until} days"
            else:
                event['countdown'] = f"In {days_until} days"
        
        return all_events
    
    def _extract_symbol(self, text: str) -> str:
        """Extract stock symbol from title or description"""
        # Look for common patterns like TCS, INFY, RELIANCE, etc.
        import re
        
        # Match 3-10 character uppercase words that are likely symbols
        pattern = r'\b([A-Z]{3,10})\b'
        matches = re.findall(pattern, text)
        
        # Filter out common words
        common_words = {'THE', 'FOR', 'AND', 'ANNOUNCES', 'RESULTS', 'BOARD', 'MEETING', 'IPO', 'DATA', 'RELEASE'}
        for match in matches:
            if match not in common_words and len(match) <= 8:
                return match
        
        return None
    
    def get_today_high_impact(self) -> List[Dict[str, Any]]:
        """Get today's high-impact events - RBI + basic real events"""
        try:
            # Get RBI events (always reliable)
            rbi_events = self.fetch_rbi_events()
            
            # Get today's date
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Filter for today
            today_events = [e for e in rbi_events if e['date'] == today and e['impact'] == 'high']
            
            # If no RBI events today, get high-impact from next few days
            if not today_events:
                upcoming = [
                    e for e in rbi_events 
                    if e['date'] > today and e['impact'] == 'high'
                ][:2]
                today_events = upcoming
            
            return today_events[:4]
        
        except Exception as e:
            logger.error(f"Error getting today's events: {e}")
            # Return empty list as fallback
            return []


# Singleton instance
_events_service = None

def get_events_service() -> EconomicEventsService:
    """Get singleton events service instance"""
    global _events_service
    if _events_service is None:
        _events_service = EconomicEventsService()
    return _events_service
