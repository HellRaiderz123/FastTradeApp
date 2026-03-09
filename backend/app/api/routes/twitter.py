"""
Twitter Sentiment API Routes
Real-time market sentiment from Twitter/X
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func, case
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

from app.db.session import SessionLocal
from app.db.models_twitter import (
    TwitterAccount, TwitterSentiment, TwitterSymbolSentiment, TwitterAlert
)
from app.services.twitter_service import get_twitter_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/twitter", tags=["twitter"])


def get_db():
    """Database dependency injection"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/sentiment/{symbol}")
async def get_symbol_sentiment(
    symbol: str,
    timeframe: str = Query(default="1h", regex="^(15m|1h|4h|1d)$"),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get Twitter sentiment for a specific symbol
    
    Args:
        symbol: Stock/index symbol (e.g., NIFTY, RELIANCE)
        timeframe: 15m, 1h, 4h, or 1d
    
    Returns:
        {
            "symbol": "NIFTY",
            "sentiment": "bullish",
            "sentiment_score": 0.65,
            "confidence": 0.78,
            "tweet_count": 45,
            "high_impact_count": 3,
            "sentiment_breakdown": {"bullish": 28, "bearish": 12, "neutral": 5},
            "top_tweets": [...],
            "trending_topics": ["breakout", "resistance"],
            "timestamp": "..."
        }
    """
    symbol = symbol.upper()
    
    # Get aggregated sentiment
    aggregated = db.query(TwitterSymbolSentiment).filter(
        and_(
            TwitterSymbolSentiment.symbol == symbol,
            TwitterSymbolSentiment.timeframe == timeframe
        )
    ).order_by(desc(TwitterSymbolSentiment.calculated_at)).first()
    
    # Get recent tweets
    hours_map = {"15m": 0.25, "1h": 1, "4h": 4, "1d": 24}
    lookback_hours = hours_map.get(timeframe, 1)
    cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
    
    recent_tweets = db.query(TwitterSentiment).filter(
        and_(
            TwitterSentiment.primary_symbol == symbol,
            TwitterSentiment.created_at_twitter >= cutoff_time
        )
    ).order_by(desc(TwitterSentiment.engagement_score)).limit(10).all()
    
    # Count by sentiment
    sentiment_counts = db.query(
        TwitterSentiment.sentiment,
        func.count(TwitterSentiment.id)
    ).filter(
        and_(
            TwitterSentiment.primary_symbol == symbol,
            TwitterSentiment.created_at_twitter >= cutoff_time
        )
    ).group_by(TwitterSentiment.sentiment).all()
    
    sentiment_breakdown = {s: c for s, c in sentiment_counts}
    total_tweets = sum(sentiment_breakdown.values())
    
    # Calculate overall sentiment if no aggregation exists
    if aggregated:
        sentiment = aggregated.sentiment_trend or "neutral"
        sentiment_score = aggregated.weighted_sentiment or 0.0
        confidence = min(1.0, total_tweets / 20)  # More tweets = higher confidence
    else:
        bullish = sentiment_breakdown.get("bullish", 0)
        bearish = sentiment_breakdown.get("bearish", 0)
        
        if total_tweets == 0:
            sentiment = "neutral"
            sentiment_score = 0.0
            confidence = 0.0
        else:
            net_sentiment = (bullish - bearish) / total_tweets
            sentiment_score = net_sentiment
            confidence = min(1.0, total_tweets / 15)
            
            if net_sentiment > 0.2:
                sentiment = "bullish"
            elif net_sentiment < -0.2:
                sentiment = "bearish"
            else:
                sentiment = "neutral"
    
    # Format top tweets
    top_tweets = [
        {
            "tweet_id": t.tweet_id,
            "username": t.username,
            "text": t.text,
            "sentiment": t.sentiment,
            "sentiment_score": t.sentiment_score,
            "engagement_score": t.engagement_score,
            "impact_level": t.impact_level,
            "created_at": t.created_at_twitter.isoformat() if t.created_at_twitter else None,
            "retweets": t.retweet_count,
            "likes": t.like_count
        }
        for t in recent_tweets
    ]
    
    # Extract trending topics
    all_keywords = []
    for tweet in recent_tweets[:20]:
        if tweet.action_keywords:
            all_keywords.extend(tweet.action_keywords)
    
    from collections import Counter
    trending_topics = [kw for kw, _ in Counter(all_keywords).most_common(5)]
    
    # Count high impact tweets
    high_impact_count = db.query(func.count(TwitterSentiment.id)).filter(
        and_(
            TwitterSentiment.primary_symbol == symbol,
            TwitterSentiment.created_at_twitter >= cutoff_time,
            TwitterSentiment.high_impact == True
        )
    ).scalar()
    
    return {
        "symbol": symbol,
        "sentiment": sentiment,
        "sentiment_score": round(sentiment_score, 3),
        "confidence": round(confidence, 3),
        "tweet_count": total_tweets,
        "high_impact_count": high_impact_count or 0,
        "sentiment_breakdown": sentiment_breakdown,
        "top_tweets": top_tweets,
        "trending_topics": trending_topics,
        "timeframe": timeframe,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/recent")
async def get_recent_tweets(
    limit: int = Query(default=20, ge=1, le=100),
    symbol: Optional[str] = None,
    sentiment: Optional[str] = None,
    impact_level: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get recent tweets with filters
    
    Args:
        limit: Max tweets to return (1-100)
        symbol: Filter by symbol
        sentiment: Filter by sentiment (bullish/bearish/neutral)
        impact_level: Filter by impact (high/medium/low)
    
    Returns:
        {
            "tweets": [...],
            "total_count": 45,
            "filters_applied": {...}
        }
    """
    query = db.query(TwitterSentiment)
    
    # Apply filters
    filters = []
    if symbol:
        filters.append(TwitterSentiment.primary_symbol == symbol.upper())
    if sentiment:
        filters.append(TwitterSentiment.sentiment == sentiment.lower())
    if impact_level:
        filters.append(TwitterSentiment.impact_level == impact_level.lower())
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Get recent tweets
    tweets = query.order_by(desc(TwitterSentiment.created_at)).limit(limit).all()
    
    # Format response
    tweet_list = [
        {
            "tweet_id": t.tweet_id,
            "username": t.username,
            "account_type": t.account_type,
            "text": t.text,
            "sentiment": t.sentiment,
            "sentiment_score": t.sentiment_score,
            "confidence": t.confidence,
            "symbols": t.symbols_mentioned,
            "primary_symbol": t.primary_symbol,
            "impact_level": t.impact_level,
            "high_impact": t.high_impact,
            "breaking_news": t.breaking_news,
            "price_targets": t.price_targets,
            "engagement_score": t.engagement_score,
            "retweets": t.retweet_count,
            "likes": t.like_count,
            "replies": t.reply_count,
            "created_at": t.created_at_twitter.isoformat() if t.created_at_twitter else None
        }
        for t in tweets
    ]
    
    return {
        "tweets": tweet_list,
        "total_count": len(tweet_list),
        "filters_applied": {
            "symbol": symbol,
            "sentiment": sentiment,
            "impact_level": impact_level
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/trending")
async def get_trending_symbols(
    timeframe: str = Query(default="1h", regex="^(15m|1h|4h|1d)$"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get trending symbols based on Twitter activity
    
    Returns symbols ranked by:
    - Tweet volume
    - High-impact tweet count
    - Sentiment strength
    - Engagement score
    """
    hours_map = {"15m": 0.25, "1h": 1, "4h": 4, "1d": 24}
    lookback_hours = hours_map.get(timeframe, 1)
    cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)
    
    # Aggregate by symbol
    symbol_stats = db.query(
        TwitterSentiment.primary_symbol,
        func.count(TwitterSentiment.id).label("tweet_count"),
        func.sum(TwitterSentiment.engagement_score).label("total_engagement"),
        func.avg(TwitterSentiment.sentiment_score).label("avg_sentiment"),
        func.sum(
            case((TwitterSentiment.high_impact == True, 1), else_=0)
        ).label("high_impact_count")
    ).filter(
        and_(
            TwitterSentiment.primary_symbol.isnot(None),
            TwitterSentiment.created_at_twitter >= cutoff_time
        )
    ).group_by(
        TwitterSentiment.primary_symbol
    ).order_by(
        desc("high_impact_count"),
        desc("tweet_count")
    ).limit(limit).all()
    
    # Format results
    trending = []
    for stat in symbol_stats:
        # Determine trend
        if stat.avg_sentiment > 0.2:
            trend = "bullish"
        elif stat.avg_sentiment < -0.2:
            trend = "bearish"
        else:
            trend = "neutral"
        
        trending.append({
            "symbol": stat.primary_symbol,
            "tweet_count": stat.tweet_count,
            "high_impact_count": stat.high_impact_count,
            "total_engagement": int(stat.total_engagement or 0),
            "avg_engagement": round((stat.total_engagement or 0) / stat.tweet_count, 2),
            "sentiment": trend,
            "sentiment_score": round(stat.avg_sentiment or 0, 3),
            "trending_rank": len(trending) + 1
        })
    
    return {
        "trending": trending,
        "timeframe": timeframe,
        "total_symbols": len(trending),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/alerts")
async def get_alerts(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get high-impact Twitter alerts
    
    Returns recent high-impact alerts for user notification
    """
    query = db.query(TwitterAlert)
    
    if unread_only:
        query = query.filter(TwitterAlert.read == False)
    
    alerts = query.order_by(desc(TwitterAlert.created_at)).limit(limit).all()
    
    alert_list = [
        {
            "id": a.id,
            "tweet_id": a.tweet_id,
            "symbol": a.symbol,
            "alert_type": a.alert_type,
            "title": a.title,
            "message": a.message,
            "severity": a.severity,
            "username": a.username,
            "sentiment": a.sentiment,
            "engagement_score": a.engagement_score,
            "read": a.read,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in alerts
    ]
    
    return {
        "alerts": alert_list,
        "total_count": len(alert_list),
        "unread_only": unread_only,
        "timestamp": datetime.now().isoformat()
    }


@router.post("/alerts/{alert_id}/mark-read")
async def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Mark an alert as read"""
    alert = db.query(TwitterAlert).filter(TwitterAlert.id == alert_id).first()
    
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert.read = True
    db.commit()
    
    return {"success": True, "alert_id": alert_id, "read": True}


@router.post("/update")
async def trigger_twitter_update(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Manually trigger Twitter sentiment update
    (normally runs via scheduler)
    """
    twitter_service = get_twitter_service()
    
    if not twitter_service.enabled:
        raise HTTPException(
            status_code=503,
            detail="Twitter API not configured. Set TWITTER_BEARER_TOKEN in .env"
        )
    
    try:
        # Fetch recent tweets
        tweets = twitter_service.fetch_tweets_from_accounts(db, max_tweets=50)
        
        # Process each tweet
        processed_count = 0
        high_impact_count = 0
        
        for tweet_data in tweets:
            sentiment = twitter_service.process_tweet(db, tweet_data)
            if sentiment:
                processed_count += 1
                if sentiment.high_impact:
                    high_impact_count += 1
        
        return {
            "success": True,
            "tweets_fetched": len(tweets),
            "tweets_processed": processed_count,
            "high_impact": high_impact_count,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Twitter update failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts")
async def get_tracked_accounts(
    active_only: bool = Query(default=True),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Get list of tracked Twitter accounts"""
    query = db.query(TwitterAccount)
    
    if active_only:
        query = query.filter(TwitterAccount.active == True)
    
    accounts = query.order_by(desc(TwitterAccount.credibility_score)).all()
    
    account_list = [
        {
            "id": a.id,
            "username": a.username,
            "display_name": a.display_name,
            "account_type": a.account_type,
            "follower_count": a.follower_count,
            "verified": a.verified,
            "credibility_score": a.credibility_score,
            "impact_weight": a.impact_weight,
            "active": a.active,
            "last_tweet_at": a.last_tweet_at.isoformat() if a.last_tweet_at else None
        }
        for a in accounts
    ]
    
    return {
        "accounts": account_list,
        "total_count": len(account_list),
        "active_only": active_only
    }


@router.post("/accounts")
async def add_tracked_account(
    username: str,
    account_type: str = "analyst",
    credibility_score: float = 50.0,
    impact_weight: float = 1.0,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """Add a new Twitter account to track"""
    
    # Check if already exists
    existing = db.query(TwitterAccount).filter(
        TwitterAccount.username == username
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Account already being tracked")
    
    account = TwitterAccount(
        username=username,
        account_type=account_type,
        credibility_score=credibility_score,
        impact_weight=impact_weight,
        active=True
    )
    
    db.add(account)
    db.commit()
    db.refresh(account)
    
    return {
        "success": True,
        "account": {
            "id": account.id,
            "username": account.username,
            "account_type": account.account_type,
            "credibility_score": account.credibility_score
        }
    }
