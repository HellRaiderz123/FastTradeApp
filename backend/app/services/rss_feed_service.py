"""
RSS Feed Service for NSE India News
Fetches real-time news from NSE RSS feeds
"""
import feedparser
import logging
from typing import List, Dict, Any
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class NSERSSFeedService:
    """Service to fetch and parse NSE India RSS feeds"""
    
    # Real RSS Feed URLs from Indian Financial News Sites
    NSE_FEEDS = {
        "moneycontrol": "https://www.moneycontrol.com/rss/MCtopnews.xml",
        "moneycontrol_market": "https://www.moneycontrol.com/rss/marketreports.xml",
        "economic_times": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
        "business_standard": "https://www.business-standard.com/rss/home_page_top_stories.rss",
        "business_standard_market": "https://www.business-standard.com/rss/markets-106.rss",
    }
    
    # User agent to mimic browser
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def fetch_feed(self, feed_url: str, feed_source: str = "RSS", timeout: int = 5) -> List[Dict[str, Any]]:
        """
        Fetch and parse a single RSS feed
        
        Args:
            feed_url: URL of the RSS feed
            feed_source: Name of the feed source
            timeout: Request timeout in seconds (default 5)
            
        Returns:
            List of parsed news items
        """
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            # Fetch the feed with short timeout
            response = self.session.get(feed_url, timeout=timeout)
            response.raise_for_status()
            
            # Parse RSS feed
            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                logger.warning(f"No entries found in feed: {feed_url}")
                return []
            
            # Map source names
            source_map = {
                "moneycontrol": "MoneyControl",
                "moneycontrol_market": "MoneyControl Markets",
                "economic_times": "Economic Times",
                "business_standard": "Business Standard",
                "business_standard_market": "BS Markets",
            }
            source_display = source_map.get(feed_source, feed_source)
            
            items = []
            for entry in feed.entries[:20]:  # Limit to 20 items per feed
                try:
                    # Parse publication date
                    pub_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    else:
                        pub_date = datetime.now()
                    
                    # Extract description (remove HTML tags)
                    description = entry.get('summary', entry.get('description', ''))
                    if description:
                        soup = BeautifulSoup(description, 'html.parser')
                        description = soup.get_text().strip()[:300]  # Max 300 chars
                    
                    # Determine category and sentiment
                    title = entry.get('title', 'No title')
                    category = self._categorize_news(title, description)
                    sentiment = self._analyze_sentiment(title, description)
                    
                    items.append({
                        'title': title,
                        'description': description,
                        'link': entry.get('link', ''),
                        'published': pub_date.strftime('%Y-%m-%d %H:%M:%S'),
                        'category': category,
                        'sentiment': sentiment,
                        'source': source_display
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing RSS entry: {e}")
                    continue
            
            return items
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching RSS feed: {feed_url}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error parsing feed {feed_url}: {e}", exc_info=True)
            return []
    
    def fetch_all_feeds(self, categories: List[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch multiple RSS feeds
        
        Args:
            categories: List of feed categories to fetch. If None, fetches all.
            
        Returns:
            Combined list of news items from all feeds
        """
        if categories is None:
            categories = list(self.NSE_FEEDS.keys())
        
        all_items = []
        for category in categories:
            if category in self.NSE_FEEDS:
                feed_url = self.NSE_FEEDS[category]
                logger.info(f"Fetching RSS feed: {category} from {feed_url}")
                items = self.fetch_feed(feed_url, feed_source=category)
                all_items.extend(items)
        
        # Sort by publication date (newest first)
        all_items.sort(key=lambda x: x['published'], reverse=True)
        
        return all_items
    
    def _categorize_news(self, title: str, description: str) -> str:
        """
        Categorize news based on content
        
        Returns:
            Category string: Market, Stocks, Economy, RBI, IPO, Earnings, or Corporate
        """
        text = (title + ' ' + description).lower()
        
        # Keywords for categorization
        if any(word in text for word in ['earning', 'result', 'profit', 'loss', 'revenue', 'eps', 'quarterly']):
            return 'Earnings'
        elif any(word in text for word in ['ipo', 'listing', 'public offer', 'issue']):
            return 'IPO'
        elif any(word in text for word in ['dividend', 'buyback', 'split', 'bonus', 'rights']):
            return 'Corporate'
        elif any(word in text for word in ['merger', 'acquisition', 'takeover', 'demerger']):
            return 'Corporate'
        elif any(word in text for word in ['board meeting', 'agm', 'egm', 'annual general']):
            return 'Corporate'
        elif any(word in text for word in ['rbi', 'monetary policy', 'repo rate', 'interest rate']):
            return 'RBI'
        elif any(word in text for word in ['gdp', 'inflation', 'cpi', 'wpi', 'iip', 'pmi']):
            return 'Economy'
        elif any(word in text for word in ['nifty', 'sensex', 'market', 'index', 'fii', 'dii']):
            return 'Market'
        else:
            return 'Stocks'
    
    def _analyze_sentiment(self, title: str, description: str) -> str:
        """
        Basic sentiment analysis on news content
        
        Returns:
            Sentiment string: bullish, bearish, or neutral
        """
        text = (title + ' ' + description).lower()
        
        # Bullish keywords
        bullish_words = [
            'gain', 'surge', 'rally', 'rise', 'up', 'high', 'record', 'growth',
            'profit', 'beat', 'exceed', 'positive', 'strong', 'boost', 'improve',
            'expansion', 'acquisition', 'approval', 'dividend', 'bonus'
        ]
        
        # Bearish keywords
        bearish_words = [
            'loss', 'fall', 'decline', 'down', 'drop', 'plunge', 'crash', 'weak',
            'miss', 'below', 'negative', 'concern', 'warning', 'risks', 'penalty',
            'investigation', 'fraud', 'default', 'delay'
        ]
        
        bullish_count = sum(1 for word in bullish_words if word in text)
        bearish_count = sum(1 for word in bearish_words if word in text)
        
        if bullish_count > bearish_count + 1:
            return 'bullish'
        elif bearish_count > bullish_count + 1:
            return 'bearish'
        else:
            return 'neutral'


# Singleton instance
_rss_service = None

def get_rss_service() -> NSERSSFeedService:
    """Get singleton RSS service instance"""
    global _rss_service
    if _rss_service is None:
        _rss_service = NSERSSFeedService()
    return _rss_service
