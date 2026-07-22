"""
Market News Feed with Sentiment Analysis
Fetches real news from NSE RSS feeds (MoneyControl, Economic Times, Business Standard)
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Dict, List, Any
from datetime import datetime
from collections import Counter
import logging
import asyncio
import json

from app.services.rss_feed_service import get_rss_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


@router.get("/feed")
async def get_news_feed(
    limit: int = Query(default=20, ge=1, le=100),
    category: str = Query(default=None),
    sentiment: str = Query(default=None)
) -> Dict[str, Any]:
    """
    Get market news feed with sentiment analysis from real RSS feeds
    (MoneyControl, Economic Times, Business Standard)
    
    Args:
        limit: Number of news items to return
        category: Filter by category (Market, Stocks, Economy, RBI, IPO, Earnings, Corporate)
        sentiment: Filter by sentiment (bullish, bearish, neutral)
    
    Returns:
        news, total_count, categories, sentiment_summary, data_source, timestamp
    """
    try:
        rss_service = get_rss_service()
        logger.info("Fetching real news from RSS feeds...")
        news_items = rss_service.fetch_all_feeds()
        
        if not news_items:
            logger.warning("No news items fetched from RSS feeds - feeds may be temporarily unavailable")
            data_source = "unavailable"
        else:
            data_source = "rss_feeds"
            logger.info(f"Successfully fetched {len(news_items)} news items from RSS feeds")
        
        # Apply filters
        if category:
            news_items = [n for n in news_items if n.get('category', '').lower() == category.lower()]
        
        if sentiment:
            news_items = [n for n in news_items if n.get('sentiment', '').lower() == sentiment.lower()]
        
        # Limit results
        news_items = news_items[:limit]
        
        # Calculate sentiment summary
        sentiment_summary = {
            'bullish': len([n for n in news_items if n.get('sentiment') == 'bullish']),
            'bearish': len([n for n in news_items if n.get('sentiment') == 'bearish']),
            'neutral': len([n for n in news_items if n.get('sentiment') == 'neutral'])
        }
        
        # Get unique categories
        categories = sorted(list(set([item.get('category', 'Unknown') for item in news_items])))
        
        return {
            'news': news_items,
            'total_count': len(news_items),
            'categories': categories,
            'sentiment_summary': sentiment_summary,
            'data_source': data_source,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching news feed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Keywords to track for trending topics extraction from real news
_TRENDING_KEYWORDS = {
    'RBI': ['rbi', 'repo rate', 'monetary policy', 'reserve bank'],
    'FII/DII': ['fii', 'dii', 'foreign institutional', 'domestic institutional'],
    'Earnings': ['earnings', 'quarterly results', 'q1', 'q2', 'q3', 'q4', 'profit', 'revenue'],
    'Banking': ['bank', 'banking', 'nbfc', 'credit growth', 'npa'],
    'IT Sector': ['it sector', 'tcs', 'infosys', 'wipro', 'tech mahindra', 'hcl tech'],
    'Inflation': ['inflation', 'cpi', 'wpi', 'price rise', 'consumer price'],
    'IPO': ['ipo', 'listing', 'public offer', 'public issue'],
    'NIFTY': ['nifty', 'sensex', 'index', 'benchmark'],
    'Crude Oil': ['crude', 'oil price', 'brent', 'opec'],
    'Auto': ['auto', 'automobile', 'vehicle', 'ev', 'electric vehicle'],
    'Pharma': ['pharma', 'drug', 'healthcare', 'fda'],
    'Real Estate': ['real estate', 'realty', 'housing', 'property'],
}


@router.get("/trending")
async def get_trending_topics() -> Dict[str, Any]:
    """
    Get trending topics extracted from real RSS news headlines.
    Scans actual fetched news for keyword frequency.
    """
    try:
        rss_service = get_rss_service()
        news_items = rss_service.fetch_all_feeds()
        
        if not news_items:
            return {
                'topics': [],
                'data_source': 'unavailable',
                'timestamp': datetime.now().isoformat()
            }
        
        # Extract trending topics from real headlines
        topic_counts: Counter = Counter()
        topic_sentiment: Dict[str, List[float]] = {}
        
        for item in news_items:
            text = (item.get('title', '') + ' ' + item.get('description', '')).lower()
            sentiment_val = 0.0
            s = item.get('sentiment', 'neutral')
            if s == 'bullish':
                sentiment_val = 0.5
            elif s == 'bearish':
                sentiment_val = -0.5
            
            for keyword, patterns in _TRENDING_KEYWORDS.items():
                if any(p in text for p in patterns):
                    topic_counts[keyword] += 1
                    if keyword not in topic_sentiment:
                        topic_sentiment[keyword] = []
                    topic_sentiment[keyword].append(sentiment_val)
        
        # Build trending topics list (only include topics that actually appear)
        trending_topics = []
        for keyword, count in topic_counts.most_common(10):
            sentiments = topic_sentiment.get(keyword, [0])
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            trending_topics.append({
                'keyword': keyword,
                'mentions': count,
                'sentiment': round(avg_sentiment, 2)
            })
        
        return {
            'topics': trending_topics,
            'data_source': 'rss_feeds',
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching trending topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Keywords that indicate high-priority / alert-worthy news
_ALERT_KEYWORDS = {
    'breaking': ['breaking', 'just in', 'flash', 'urgent', 'all-time high', 'record high', 'lifetime high', 'crash', 'crisis'],
    'volatility': ['volatility', 'vix', 'wild swing', 'circuit', 'halt', 'sharp fall', 'sharp rise', 'plunge', 'surge'],
    'earnings': ['result', 'earning', 'quarterly', 'q1 result', 'q2 result', 'q3 result', 'q4 result', 'profit', 'revenue beat', 'revenue miss'],
    'regulatory': ['rbi', 'sebi', 'regulation', 'policy', 'ban', 'restriction', 'penalty', 'fine'],
}


@router.get("/stream")
async def stream_news(
    limit: int = Query(default=12, ge=1, le=50),
    interval_seconds: int = Query(default=20, ge=5, le=120),
):
    """
    Server-Sent Events stream for live headline updates.

    Emits event: `news` with payload:
      { news: [...], alerts: [...], timestamp: ... }
    """

    async def event_generator():
        last_fingerprint: str | None = None
        while True:
            try:
                rss_service = get_rss_service()
                items = rss_service.fetch_all_feeds()
                items = items[:limit]

                news_items = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    news_items.append({
                        "title": item.get("title"),
                        "description": item.get("description"),
                        "source": item.get("source"),
                        "sentiment": item.get("sentiment"),
                        "category": item.get("category"),
                        "published": item.get("published"),
                        "link": item.get("link"),
                    })

                alerts = []
                seen_titles = set()
                for item in items:
                    title = str(item.get("title") or "")
                    if not title or title in seen_titles:
                        continue
                    text_lower = title.lower()
                    for alert_type, keywords in _ALERT_KEYWORDS.items():
                        if any(kw in text_lower for kw in keywords):
                            sentiment = str(item.get("sentiment") or "neutral")
                            if alert_type == "breaking" or sentiment in ("bullish", "bearish"):
                                priority = "high"
                            elif alert_type in ("volatility", "regulatory"):
                                priority = "high"
                            else:
                                priority = "medium"
                            alerts.append({
                                "type": alert_type,
                                "message": title,
                                "timestamp": item.get("published", datetime.now().isoformat()),
                                "priority": priority,
                                "source": item.get("source", "RSS"),
                                "link": item.get("link", ""),
                            })
                            seen_titles.add(title)
                            break

                payload = {
                    "news": news_items,
                    "alerts": alerts[:10],
                    "timestamp": datetime.now().isoformat(),
                }
                payload_json = json.dumps(payload, ensure_ascii=False)
                fingerprint = str(hash(payload_json))

                if fingerprint != last_fingerprint:
                    yield f"event: news\ndata: {payload_json}\n\n"
                    last_fingerprint = fingerprint
                else:
                    yield "event: ping\ndata: {}\n\n"

            except Exception as e:
                err = json.dumps({"error": str(e), "timestamp": datetime.now().isoformat()})
                yield f"event: error\ndata: {err}\n\n"

            await asyncio.sleep(interval_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/alerts")
async def get_market_alerts() -> Dict[str, Any]:
    """
    Get market alerts derived from real RSS news.
    Extracts high-impact headlines from actual feed data.
    """
    try:
        rss_service = get_rss_service()
        news_items = rss_service.fetch_all_feeds()
        
        if not news_items:
            return {
                'alerts': [],
                'data_source': 'unavailable',
                'timestamp': datetime.now().isoformat()
            }
        
        alerts = []
        seen_titles = set()
        
        for item in news_items:
            title = item.get('title', '')
            if title in seen_titles:
                continue
            
            text_lower = title.lower()
            
            # Check if this headline matches any alert keyword category
            for alert_type, keywords in _ALERT_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    # Determine priority based on sentiment and category
                    sentiment = item.get('sentiment', 'neutral')
                    if alert_type == 'breaking' or sentiment in ('bullish', 'bearish'):
                        priority = 'high'
                    elif alert_type in ('volatility', 'regulatory'):
                        priority = 'high'
                    else:
                        priority = 'medium'
                    
                    alerts.append({
                        'type': alert_type,
                        'message': title,
                        'timestamp': item.get('published', datetime.now().isoformat()),
                        'priority': priority,
                        'source': item.get('source', 'RSS'),
                        'link': item.get('link', '')
                    })
                    seen_titles.add(title)
                    break  # Only categorize once per headline
        
        # Sort by timestamp (newest first), limit to top 10
        alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        alerts = alerts[:10]
        
        return {
            'alerts': alerts,
            'data_source': 'rss_feeds',
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching market alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
