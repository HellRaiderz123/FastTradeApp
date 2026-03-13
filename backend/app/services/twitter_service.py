"""
Twitter/X Sentiment Service
Real-time market sentiment from Twitter using tweepy and TextBlob
"""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_

# Twitter API client
try:
    import tweepy
    TWEEPY_AVAILABLE = True
except ImportError:
    TWEEPY_AVAILABLE = False
    logging.warning("tweepy not installed - Twitter sentiment disabled. Install: pip install tweepy")

# Sentiment analysis
try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False
    logging.warning("textblob not installed - using basic sentiment. Install: pip install textblob")

from app.db.models_twitter import (
    TwitterAccount, TwitterSentiment, TwitterSymbolSentiment, TwitterAlert
)

logger = logging.getLogger(__name__)


# ── SYMBOL EXTRACTION PATTERNS ──────────────────────────────────────────────
NIFTY_SYMBOLS = {
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYIT",
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "BHARTIARTL",
    "SBIN", "ITC", "HINDUNILVR", "KOTAKBANK", "AXISBANK", "BAJFINANCE",
    "MARUTI", "TMPV", "TATAMOTORS", "WIPRO", "HCLTECH", "TECHM",
    "SUNPHARMA", "CIPLA", "DRREDDY", "ULTRACEMCO", "ASIANPAINT", "LT",
}

BULLISH_KEYWORDS = [
    "bullish", "buy", "long", "call", "breakout", "rally", "surge", "uptrend",
    "resistance broken", "strong support", "accumulate", "upside", "momentum",
    "golden cross", "higher high", "buying opportunity", "positive", "gap up"
]

BEARISH_KEYWORDS = [
    "bearish", "sell", "short", "put", "breakdown", "crash", "fall", "downtrend",
    "support broken", "strong resistance", "distribute", "downside", "weakness",
    "death cross", "lower low", "selling pressure", "negative", "gap down"
]

ACTION_KEYWORDS = [
    "buy above", "sell below", "stop loss", "target", "resistance", "support",
    "entry", "exit", "breakout", "breakdown", "accumulation", "distribution"
]


class TwitterSentimentService:
    """Service for fetching and analyzing Twitter sentiment"""
    
    def __init__(self):
        self.api_key = os.getenv("TWITTER_API_KEY", "")
        self.api_secret = os.getenv("TWITTER_API_SECRET", "")
        self.access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
        self.access_secret = os.getenv("TWITTER_ACCESS_SECRET", "")
        self.bearer_token = os.getenv("TWITTER_BEARER_TOKEN", "")
        
        self.client = None
        self.enabled = bool(self.bearer_token or (self.api_key and self.api_secret))
        
        if self.enabled and TWEEPY_AVAILABLE:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Twitter API v2 client"""
        try:
            if self.bearer_token:
                # Twitter API v2 with bearer token (recommended)
                self.client = tweepy.Client(
                    bearer_token=self.bearer_token,
                    wait_on_rate_limit=True
                )
            elif self.api_key and self.api_secret:
                # OAuth 1.0a authentication
                auth = tweepy.OAuth1UserHandler(
                    self.api_key, self.api_secret,
                    self.access_token, self.access_secret
                )
                api = tweepy.API(auth, wait_on_rate_limit=True)
                self.client = tweepy.Client(
                    consumer_key=self.api_key,
                    consumer_secret=self.api_secret,
                    access_token=self.access_token,
                    access_token_secret=self.access_secret,
                    wait_on_rate_limit=True
                )
            
            logger.info("✅ Twitter API client initialized")
        except Exception as e:
            logger.error(f"❌ Twitter client initialization failed: {e}")
            self.client = None
            self.enabled = False
    
    def extract_symbols(self, text: str) -> List[str]:
        """Extract stock symbols from tweet text"""
        text_upper = text.upper()
        symbols = []
        
        # Look for cashtags ($SYMBOL)
        cashtags = re.findall(r'\$([A-Z]{2,15})', text)
        symbols.extend(cashtags)
        
        # Look for known symbols mentioned
        for symbol in NIFTY_SYMBOLS:
            if symbol in text_upper:
                symbols.append(symbol)
        
        # Remove duplicates while preserving order
        return list(dict.fromkeys(symbols))
    
    def extract_price_targets(self, text: str, symbols: List[str]) -> List[Dict[str, Any]]:
        """Extract price targets from tweet text"""
        targets = []
        
        # Pattern: "NIFTY target 24500" or "resistance at 24500"
        patterns = [
            r'(?:target|tgt)\s*(?:of|at|is)?\s*(\d+)',
            r'(?:resistance|support)\s*(?:at|near|around)\s*(\d+)',
            r'(\d+)\s*(?:resistance|support)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                price = int(match.group(1))
                if price > 100:  # Filter out noise
                    targets.append({
                        "price": price,
                        "type": "target" if "target" in text.lower() else "level"
                    })
        
        return targets[:3]  # Max 3 targets per tweet
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of tweet text"""
        sentiment = "neutral"
        score = 0.0
        confidence = 0.5
        
        text_lower = text.lower()
        
        # Count keyword matches
        bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
        bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
        
        # Use TextBlob if available
        if TEXTBLOB_AVAILABLE:
            try:
                blob = TextBlob(text)
                polarity = blob.sentiment.polarity  # -1 to 1
                subjectivity = blob.sentiment.subjectivity  # 0 to 1
                
                # Combine TextBlob with keyword analysis
                keyword_bias = (bullish_count - bearish_count) * 0.15
                score = max(-1.0, min(1.0, polarity + keyword_bias))
                confidence = max(0.3, min(1.0, (1 - subjectivity) * 0.7 + 0.3))
                
            except Exception as e:
                logger.warning(f"TextBlob analysis failed: {e}")
        else:
            # Fallback: keyword-based sentiment
            total_keywords = bullish_count + bearish_count
            if total_keywords > 0:
                score = (bullish_count - bearish_count) / total_keywords
                confidence = min(0.8, total_keywords * 0.2 + 0.3)
        
        # Determine sentiment label
        if score > 0.15:
            sentiment = "bullish"
        elif score < -0.15:
            sentiment = "bearish"
        else:
            sentiment = "neutral"
        
        return {
            "sentiment": sentiment,
            "score": round(score, 3),
            "confidence": round(confidence, 3),
            "bullish_keywords": bullish_count,
            "bearish_keywords": bearish_count
        }
    
    def calculate_engagement_score(self, tweet_data: Dict) -> float:
        """Calculate engagement score for impact weighting"""
        public_metrics = tweet_data.get("public_metrics", {})
        retweets = public_metrics.get("retweet_count", 0)
        likes = public_metrics.get("like_count", 0)
        replies = public_metrics.get("reply_count", 0)
        
        # Weighted engagement: retweets > likes > replies
        score = (retweets * 3.0) + (likes * 1.0) + (replies * 2.0)
        
        # Normalize to 0-100 scale (log scale for viral tweets)
        import math
        normalized = min(100, math.log1p(score) * 10)
        
        return round(normalized, 2)
    
    def determine_impact_level(
        self, 
        sentiment_score: float,
        engagement_score: float,
        account_credibility: float,
        symbols: List[str]
    ) -> str:
        """Determine if tweet is high/medium/low impact"""
        
        # High impact criteria:
        # 1. Strong sentiment (abs score > 0.5)
        # 2. High engagement (>50)
        # 3. Credible account (>60)
        # 4. Mentions major indices or liquid stocks
        
        major_symbols = {"NIFTY", "BANKNIFTY", "FINNIFTY", "RELIANCE", "TCS", "HDFCBANK"}
        has_major = any(s in major_symbols for s in symbols)
        
        impact_score = (
            abs(sentiment_score) * 30 +
            (engagement_score / 100) * 30 +
            (account_credibility / 100) * 25 +
            (15 if has_major else 0)
        )
        
        if impact_score >= 70:
            return "high"
        elif impact_score >= 40:
            return "medium"
        else:
            return "low"
    
    def fetch_tweets_from_accounts(
        self, 
        db: Session,
        max_tweets: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch recent tweets from tracked accounts"""
        
        if not self.enabled or not self.client:
            logger.warning("Twitter client not available - using mock data")
            return self._get_mock_tweets()
        
        # Get active tracked accounts
        accounts = db.query(TwitterAccount).filter(
            TwitterAccount.active == True
        ).all()
        
        if not accounts:
            logger.warning("No Twitter accounts configured for tracking")
            return []
        
        all_tweets = []
        
        for account in accounts[:10]:  # Limit to 10 accounts to save API calls
            try:
                # Resolve user by username, then fetch tweets by user id (API v2 requirement)
                user_resp = self.client.get_user(username=account.username)
                if not user_resp or not user_resp.data:
                    logger.warning(f"User not found on Twitter: @{account.username}")
                    continue

                user_id = user_resp.data.id
                tweets = self.client.get_users_tweets(
                    id=user_id,
                    max_results=min(10, max_tweets),
                    tweet_fields=["created_at", "public_metrics", "entities"],
                    exclude=["retweets", "replies"]
                )
                
                if tweets.data:
                    for tweet in tweets.data:
                        tweet_data = {
                            "id": tweet.id,
                            "text": tweet.text,
                            "created_at": tweet.created_at,
                            "username": account.username,
                            "account_type": account.account_type,
                            "credibility": account.credibility_score,
                            "public_metrics": {
                                "retweet_count": tweet.public_metrics.get("retweet_count", 0),
                                "like_count": tweet.public_metrics.get("like_count", 0),
                                "reply_count": tweet.public_metrics.get("reply_count", 0),
                            }
                        }
                        all_tweets.append(tweet_data)
                
                logger.info(f"Fetched {len(tweets.data) if tweets.data else 0} tweets from @{account.username}")
                
            except Exception as e:
                logger.error(f"Error fetching tweets from @{account.username}: {e}")
        
        return all_tweets[:max_tweets]
    
    def process_tweet(
        self,
        db: Session,
        tweet_data: Dict[str, Any]
    ) -> Optional[TwitterSentiment]:
        """Process a single tweet: extract symbols, analyze sentiment, store"""
        
        # Check if already processed
        existing = db.query(TwitterSentiment).filter(
            TwitterSentiment.tweet_id == str(tweet_data["id"])
        ).first()
        
        if existing:
            return existing
        
        # Extract data
        text = tweet_data["text"]
        symbols = self.extract_symbols(text)
        
        if not symbols:
            logger.debug(f"No symbols found in tweet: {text[:50]}...")
            return None
        
        # Analyze sentiment
        sentiment_result = self.analyze_sentiment(text)
        
        # Calculate scores
        engagement_score = self.calculate_engagement_score(tweet_data)
        account_credibility = tweet_data.get("credibility", 50.0)
        
        impact_level = self.determine_impact_level(
            sentiment_result["score"],
            engagement_score,
            account_credibility,
            symbols
        )
        
        # Extract price targets
        price_targets = self.extract_price_targets(text, symbols)
        
        # Extract action keywords
        action_kws = [kw for kw in ACTION_KEYWORDS if kw in text.lower()]
        
        # Determine alert flags
        high_impact = impact_level == "high"
        breaking_news = any(kw in text.lower() for kw in ["breaking", "alert", "urgent"])
        has_price_target = len(price_targets) > 0
        
        # Create record
        sentiment_record = TwitterSentiment(
            tweet_id=str(tweet_data["id"]),
            username=tweet_data["username"],
            account_type=tweet_data.get("account_type", "unknown"),
            text=text,
            created_at_twitter=tweet_data.get("created_at", datetime.utcnow()),
            retweet_count=tweet_data["public_metrics"]["retweet_count"],
            like_count=tweet_data["public_metrics"]["like_count"],
            reply_count=tweet_data["public_metrics"]["reply_count"],
            engagement_score=engagement_score,
            sentiment=sentiment_result["sentiment"],
            sentiment_score=sentiment_result["score"],
            confidence=sentiment_result["confidence"],
            symbols_mentioned=symbols,
            primary_symbol=symbols[0] if symbols else None,
            impact_level=impact_level,
            high_impact=high_impact,
            breaking_news=breaking_news,
            price_target=has_price_target,
            price_targets=price_targets if price_targets else None,
            action_keywords=action_kws if action_kws else None,
            processed=True,
            alert_sent=False
        )
        
        db.add(sentiment_record)
        db.commit()
        db.refresh(sentiment_record)

        self._create_alert_for_sentiment(
            db=db,
            sentiment_record=sentiment_record,
            account_credibility=account_credibility
        )
        
        logger.info(
            f"Processed tweet {sentiment_record.tweet_id}: "
            f"{sentiment_record.primary_symbol} {sentiment_record.sentiment} "
            f"({sentiment_record.impact_level} impact)"
        )
        
        return sentiment_record

    def _create_alert_for_sentiment(
        self,
        db: Session,
        sentiment_record: TwitterSentiment,
        account_credibility: float
    ) -> None:
        """Create alert records for high-impact or actionable tweets."""
        if not (sentiment_record.high_impact or sentiment_record.breaking_news or sentiment_record.price_target):
            return

        if sentiment_record.breaking_news and sentiment_record.high_impact:
            alert_type = "breaking_news"
            severity = "critical"
        elif sentiment_record.high_impact:
            alert_type = "high_impact"
            severity = "high"
        elif sentiment_record.price_target:
            alert_type = "price_target"
            severity = "medium"
        else:
            alert_type = "high_impact"
            severity = "low"

        existing_alert = db.query(TwitterAlert).filter(
            and_(
                TwitterAlert.tweet_id == sentiment_record.tweet_id,
                TwitterAlert.symbol == (sentiment_record.primary_symbol or "UNKNOWN"),
                TwitterAlert.alert_type == alert_type
            )
        ).first()

        if existing_alert:
            if not sentiment_record.alert_sent:
                sentiment_record.alert_sent = True
                sentiment_record.alerted_at = datetime.utcnow()
                db.commit()
            return

        title = f"{(sentiment_record.primary_symbol or 'MARKET')} {sentiment_record.sentiment.upper()} signal"
        message = sentiment_record.text[:280]

        alert = TwitterAlert(
            tweet_id=sentiment_record.tweet_id,
            symbol=sentiment_record.primary_symbol or "UNKNOWN",
            alert_type=alert_type,
            title=title,
            message=message,
            severity=severity,
            username=sentiment_record.username,
            account_credibility=account_credibility,
            sentiment=sentiment_record.sentiment,
            engagement_score=sentiment_record.engagement_score,
            sent=False,
            read=False,
            dismissed=False
        )

        sentiment_record.alert_sent = True
        sentiment_record.alerted_at = datetime.utcnow()

        db.add(alert)
        db.commit()
    
    def _get_mock_tweets(self) -> List[Dict[str, Any]]:
        """Generate mock tweets for testing without API access"""
        now = datetime.utcnow()
        
        return [
            {
                "id": "1234567890",
                "text": "NIFTY showing strong breakout above 24500 resistance. Bullish momentum building. Target 24800. #Nifty #StockMarket",
                "created_at": now - timedelta(minutes=15),
                "username": "MarketGuru",
                "account_type": "analyst",
                "credibility": 85.0,
                "public_metrics": {"retweet_count": 245, "like_count": 890, "reply_count": 67}
            },
            {
                "id": "1234567891",
                "text": "BANKNIFTY weak below 52000. Selling pressure visible. Watch for breakdown if 51800 breaks. $BANKNIFTY",
                "created_at": now - timedelta(minutes=30),
                "username": "TradingExpert",
                "account_type": "influencer",
                "credibility": 72.0,
                "public_metrics": {"retweet_count": 123, "like_count": 456, "reply_count": 34}
            },
            {
                "id": "1234567892",
                "text": "RELIANCE stock looking bullish on daily charts. Good accumulation zone around 2850-2900. Long term buy.",
                "created_at": now - timedelta(hours=1),
                "username": "StockAnalyst",
                "account_type": "analyst",
                "credibility": 78.0,
                "public_metrics": {"retweet_count": 89, "like_count": 312, "reply_count": 23}
            }
        ]


# ── SINGLETON INSTANCE ──────────────────────────────────────────────────────
_twitter_service: Optional[TwitterSentimentService] = None


def get_twitter_service() -> TwitterSentimentService:
    """Get singleton Twitter service instance"""
    global _twitter_service
    if _twitter_service is None:
        _twitter_service = TwitterSentimentService()
    return _twitter_service
