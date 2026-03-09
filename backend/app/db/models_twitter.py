"""
Twitter Sentiment Database Models
Stores tweets, sentiment analysis, and tracked accounts for market sentiment
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, Index
from datetime import datetime

from app.db.session import Base
from app.core.utils.time import now_ist


class TwitterAccount(Base):
    """Accounts to track for market sentiment (influencers, analysts, financial media)"""
    __tablename__ = "twitter_accounts"

    id = Column(Integer, primary_key=True, index=True)
    
    # Account details
    username = Column(String(255), unique=True, index=True, nullable=False)
    display_name = Column(String(500))
    account_type = Column(String(100), index=True)  # "analyst", "influencer", "media", "official"
    
    # Credibility & weighting
    follower_count = Column(Integer, default=0)
    verified = Column(Boolean, default=False)
    credibility_score = Column(Float, default=50.0)  # 0-100 scale
    impact_weight = Column(Float, default=1.0)  # Multiplier for sentiment scoring
    
    # Tracking settings
    active = Column(Boolean, default=True, index=True)
    track_symbols = Column(JSON, nullable=True)  # ["NIFTY", "BANKNIFTY", ...] or null for all
    
    # Metadata
    last_tweet_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)

    __table_args__ = (
        Index('ix_twitter_accounts_active_type', 'active', 'account_type'),
    )


class TwitterSentiment(Base):
    """Individual tweets with sentiment analysis"""
    __tablename__ = "twitter_sentiment"

    id = Column(Integer, primary_key=True, index=True)
    
    # Tweet metadata
    tweet_id = Column(String(100), unique=True, index=True, nullable=False)
    username = Column(String(255), index=True, nullable=False)
    account_type = Column(String(100))
    
    # Tweet content
    text = Column(Text, nullable=False)
    created_at_twitter = Column(DateTime(timezone=True), index=True)
    
    # Engagement metrics
    retweet_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    reply_count = Column(Integer, default=0)
    engagement_score = Column(Float, default=0.0)  # Calculated impact score
    
    # Sentiment analysis
    sentiment = Column(String(50), index=True)  # "bullish", "bearish", "neutral"
    sentiment_score = Column(Float)  # -1.0 to 1.0
    confidence = Column(Float)  # 0.0 to 1.0
    
    # Symbol extraction and impact
    symbols_mentioned = Column(JSON)  # ["NIFTY", "RELIANCE", ...]
    primary_symbol = Column(String(50), index=True, nullable=True)
    impact_level = Column(String(50), index=True)  # "high", "medium", "low"
    
    # Alert flags
    high_impact = Column(Boolean, default=False, index=True)  # Triggers alerts
    breaking_news = Column(Boolean, default=False)
    price_target = Column(Boolean, default=False)
    
    # Extracted insights
    price_targets = Column(JSON, nullable=True)  # [{"symbol": "NIFTY", "target": 24500, "type": "resistance"}]
    action_keywords = Column(JSON, nullable=True)  # ["buying opportunity", "sell", "breakout"]
    
    # Processing metadata
    processed = Column(Boolean, default=False, index=True)
    alert_sent = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), default=now_ist, index=True)
    alerted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_twitter_sentiment_symbol_time', 'primary_symbol', 'created_at_twitter'),
        Index('ix_twitter_sentiment_high_impact_unalerted', 'high_impact', 'alert_sent'),
        Index('ix_twitter_sentiment_created_desc', 'created_at', postgresql_ops={'created_at': 'DESC'}),
    )


class TwitterSymbolSentiment(Base):
    """Aggregated sentiment per symbol (calculated periodically)"""
    __tablename__ = "twitter_symbol_sentiment"

    id = Column(Integer, primary_key=True, index=True)
    
    # Symbol and timeframe
    symbol = Column(String(50), index=True, nullable=False)
    timeframe = Column(String(50), index=True)  # "15m", "1h", "4h", "1d"
    
    # Aggregated metrics
    tweet_count = Column(Integer, default=0)
    bullish_count = Column(Integer, default=0)
    bearish_count = Column(Integer, default=0)
    neutral_count = Column(Integer, default=0)
    
    # Sentiment scores
    avg_sentiment = Column(Float)  # -1.0 to 1.0
    weighted_sentiment = Column(Float)  # Weighted by account credibility and engagement
    sentiment_momentum = Column(Float)  # Change from previous period
    
    # Engagement metrics
    total_engagement = Column(Integer, default=0)
    avg_engagement = Column(Float, default=0.0)
    high_impact_tweets = Column(Integer, default=0)
    
    # Trend detection
    sentiment_trend = Column(String(50))  # "strengthening_bullish", "weakening_bullish", etc.
    trend_strength = Column(Float)  # 0-100 scale
    
    # Top contributors
    top_accounts = Column(JSON, nullable=True)  # [{"username": "...", "sentiment": "bullish", "impact": 85}]
    key_topics = Column(JSON, nullable=True)  # ["breakout", "resistance", "earnings"]
    
    # Timestamps
    period_start = Column(DateTime(timezone=True), index=True)
    period_end = Column(DateTime(timezone=True))
    calculated_at = Column(DateTime(timezone=True), default=now_ist)

    __table_args__ = (
        Index('ix_twitter_symbol_sentiment_symbol_timeframe', 'symbol', 'timeframe', 'period_start'),
    )


class TwitterAlert(Base):
    """High-impact Twitter alerts sent to users"""
    __tablename__ = "twitter_alerts"

    id = Column(Integer, primary_key=True, index=True)
    
    # Alert details
    tweet_id = Column(String(100), index=True, nullable=False)
    symbol = Column(String(50), index=True, nullable=False)
    alert_type = Column(String(50), index=True)  # "high_impact", "breaking_news", "price_target", "trend_shift"
    
    # Alert content
    title = Column(String(500))
    message = Column(Text)
    severity = Column(String(50))  # "critical", "high", "medium", "low"
    
    # Source
    username = Column(String(255))
    account_credibility = Column(Float)
    
    # Tweet metrics
    sentiment = Column(String(50))
    engagement_score = Column(Float)
    
    # Delivery status
    sent = Column(Boolean, default=False, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    # User interaction
    read = Column(Boolean, default=False)
    dismissed = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_ist, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_twitter_alerts_unsent', 'sent', 'created_at'),
    )
