"""
Market News Feed with Sentiment Analysis
Generate Bloomberg-style news feed
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Any
from datetime import datetime, timedelta
import logging
import random

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/news", tags=["news"])


# Mock news data with sentiment
MOCK_NEWS_ITEMS = [
    {
        "category": "Market",
        "sentiment": "bullish",
        "headlines": [
            "NIFTY 50 hits new all-time high amid strong FII inflows",
            "Indian markets extend rally as GDP growth beats estimates",
            "Sensex gains 500 points on positive global cues",
            "Market breadth remains strong with 8:1 advance-decline ratio",
            "Domestic institutions turn net buyers after 3 months",
        ]
    },
    {
        "category": "Market",
        "sentiment": "bearish",
        "headlines": [
            "NIFTY 50 corrects 2% amid profit booking at higher levels",
            "Markets decline on rising crude oil prices and inflation concerns",
            "FIIs turn net sellers, withdraw ₹3,500 crore this week",
            "Weak Q4 earnings trigger selloff in midcap stocks",
            "Global recession fears weigh on emerging markets",
        ]
    },
    {
        "category": "Market",
        "sentiment": "neutral",
        "headlines": [
            "Markets trade sideways awaiting RBI policy decision",
            "NIFTY 50 consolidates in 18,000-18,500 range",
            "Mixed global cues keep traders cautious",
            "Volatility remains elevated ahead of derivatives expiry",
        ]
    },
    {
        "category": "Stocks",
        "sentiment": "bullish",
        "headlines": [
            "Reliance Industries announces ₹75,000 crore capex plan",
            "TCS wins $2.5 billion multi-year contract from US client",
            "HDFC Bank reports 20% YoY growth in Q4 profit",
            "Infosys raises FY24 revenue guidance on strong deal pipeline",
            "ITC gets board approval for hotel demerger",
        ]
    },
    {
        "category": "Stocks",
        "sentiment": "bearish",
        "headlines": [
            "Paytm shares tumble 20% after RBI restrictions",
            "Adani stocks under pressure following Hindenburg report",
            "ICICI Bank faces regulatory scrutiny over loan practices",
            "Zomato Q4 loss widens, stock down 8%",
        ]
    },
    {
        "category": "Economy",
        "sentiment": "bullish",
        "headlines": [
            "India GDP grows 7.2% in Q4, fastest among major economies",
            "Manufacturing PMI hits 16-month high at 58.8",
            "GST collections cross ₹1.7 lakh crore for third straight month",
            "Foreign exchange reserves touch record $650 billion",
        ]
    },
    {
        "category": "Economy",
        "sentiment": "bearish",
        "headlines": [
            "Retail inflation rises to 6.2%, above RBI comfort zone",
            "Core sector growth slows to 3.2% in March",
            "Trade deficit widens to $24 billion amid import surge",
            "Industrial production growth decelerates to 4.5%",
        ]
    },
    {
        "category": "RBI",
        "sentiment": "neutral",
        "headlines": [
            "RBI keeps repo rate unchanged at 6.5% for sixth time",
            "Central bank maintains 'withdrawal of accommodation' stance",
            "RBI focuses on aligning inflation with 4% target",
            "Governor signals data-dependent approach on rates",
        ]
    },
    {
        "category": "IPO",
        "sentiment": "bullish",
        "headlines": [
            "Tata Technologies IPO subscribed 69x on strong demand",
            "IREDA shares list at 40% premium to issue price",
            "Jio Financial Services begins trading, gains 8% on debut",
        ]
    },
    {
        "category": "Global",
        "sentiment": "bullish",
        "headlines": [
            "US Fed signals pause in rate hikes, markets rally",
            "Asian stocks rise on China reopening optimism",
            "Dollar weakens, good for emerging market flows",
            "MSCI emerging markets index hits 3-month high",
        ]
    },
    {
        "category": "Global",
        "sentiment": "bearish",
        "headlines": [
            "US banking crisis spreads, Silicon Valley Bank collapses",
            "European recession fears mount as PMI contracts",
            "China growth slows to 4.5%, below expectations",
            "Oil prices surge past $95/barrel on supply concerns",
        ]
    },
    {
        "category": "Commodities",
        "sentiment": "neutral",
        "headlines": [
            "Gold trades flat near $2,000/oz amid mixed signals",
            "Silver consolidates in $23-25 range",
            "Natural gas prices stabilize after winter volatility",
        ]
    },
]


def generate_news_feed(count: int = 20, category: str = None, sentiment: str = None) -> List[Dict[str, Any]]:
    """Generate mock news feed with timestamps and sentiment"""
    news_items = []
    
    # Filter by category and sentiment if specified
    filtered_items = MOCK_NEWS_ITEMS
    if category:
        filtered_items = [item for item in filtered_items if item['category'].lower() == category.lower()]
    if sentiment:
        filtered_items = [item for item in filtered_items if item['sentiment'].lower() == sentiment.lower()]
    
    # Generate news items
    for i in range(count):
        # Pick random category
        if filtered_items:
            news_bucket = random.choice(filtered_items)
        else:
            news_bucket = random.choice(MOCK_NEWS_ITEMS)
        
        headline = random.choice(news_bucket['headlines'])
        
        # Generate timestamp (recent news)
        minutes_ago = random.randint(1, 480)  # Up to 8 hours ago
        timestamp = datetime.now() - timedelta(minutes=minutes_ago)
        
        # Sentiment score (-1 to 1)
        if news_bucket['sentiment'] == 'bullish':
            sentiment_score = random.uniform(0.5, 1.0)
        elif news_bucket['sentiment'] == 'bearish':
            sentiment_score = random.uniform(-1.0, -0.5)
        else:
            sentiment_score = random.uniform(-0.3, 0.3)
        
        # Impact level
        impact = random.choice(['high', 'medium', 'low'])
        if news_bucket['category'] in ['RBI', 'Economy']:
            impact = random.choice(['high', 'high', 'medium'])  # More likely high
        
        news_items.append({
            'id': f"news_{i}_{timestamp.timestamp()}",
            'headline': headline,
            'category': news_bucket['category'],
            'sentiment': news_bucket['sentiment'],
            'sentiment_score': round(sentiment_score, 2),
            'impact': impact,
            'timestamp': timestamp.isoformat(),
            'source': random.choice(['Bloomberg', 'Economic Times', 'Moneycontrol', 'Reuters', 'CNBC', 'Business Standard']),
            'read': False
        })
    
    # Sort by timestamp (newest first)
    news_items.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return news_items


@router.get("/feed")
async def get_news_feed(
    limit: int = Query(default=20, ge=1, le=100),
    category: str = Query(default=None),
    sentiment: str = Query(default=None)
) -> Dict[str, Any]:
    """
    Get market news feed with sentiment analysis
    
    Args:
        limit: Number of news items to return
        category: Filter by category (Market, Stocks, Economy, RBI, IPO, Global, Commodities)
        sentiment: Filter by sentiment (bullish, bearish, neutral)
    
    Returns:
        {
            "news": [...],
            "total_count": 20,
            "categories": ["Market", "Stocks", "Economy", ...],
            "sentiment_summary": {
                "bullish": 8,
                "bearish": 6,
                "neutral": 6
            },
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        # Generate news feed
        news_items = generate_news_feed(count=limit, category=category, sentiment=sentiment)
        
        # Calculate sentiment summary
        sentiment_summary = {
            'bullish': len([n for n in news_items if n['sentiment'] == 'bullish']),
            'bearish': len([n for n in news_items if n['sentiment'] == 'bearish']),
            'neutral': len([n for n in news_items if n['sentiment'] == 'neutral'])
        }
        
        # Get unique categories
        categories = list(set([item['category'] for item in MOCK_NEWS_ITEMS]))
        
        return {
            'news': news_items,
            'total_count': len(news_items),
            'categories': sorted(categories),
            'sentiment_summary': sentiment_summary,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error generating news feed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trending")
async def get_trending_topics() -> Dict[str, Any]:
    """
    Get trending topics and keywords in market news
    
    Returns:
        {
            "topics": [
                {"keyword": "RBI Policy", "mentions": 15, "sentiment": 0.2},
                {"keyword": "FII Flows", "mentions": 12, "sentiment": 0.5},
                ...
            ],
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        trending_topics = [
            {"keyword": "RBI Policy", "mentions": random.randint(10, 20), "sentiment": round(random.uniform(-0.3, 0.3), 2)},
            {"keyword": "FII Flows", "mentions": random.randint(8, 15), "sentiment": round(random.uniform(0.3, 0.7), 2)},
            {"keyword": "Earnings Season", "mentions": random.randint(12, 18), "sentiment": round(random.uniform(0.2, 0.6), 2)},
            {"keyword": "Banking Sector", "mentions": random.randint(10, 16), "sentiment": round(random.uniform(-0.2, 0.4), 2)},
            {"keyword": "IT Stocks", "mentions": random.randint(8, 14), "sentiment": round(random.uniform(0.1, 0.5), 2)},
            {"keyword": "Inflation", "mentions": random.randint(6, 12), "sentiment": round(random.uniform(-0.6, -0.2), 2)},
            {"keyword": "IPO Market", "mentions": random.randint(5, 10), "sentiment": round(random.uniform(0.3, 0.8), 2)},
        ]
        
        # Sort by mentions
        trending_topics.sort(key=lambda x: x['mentions'], reverse=True)
        
        return {
            'topics': trending_topics,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching trending topics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_market_alerts() -> Dict[str, Any]:
    """
    Get important market alerts and announcements
    
    Returns:
        {
            "alerts": [
                {
                    "type": "breaking",
                    "message": "NIFTY 50 crosses 18,500 for first time",
                    "timestamp": "2024-01-09T15:30:00",
                    "priority": "high"
                },
                ...
            ],
            "timestamp": "2024-01-09T15:30:00"
        }
    """
    try:
        alert_templates = [
            {"type": "breaking", "messages": [
                "NIFTY 50 crosses 18,500 for first time",
                "Sensex hits lifetime high of 62,000",
                "RBI announces surprise rate cut of 25 bps",
                "Government unveils ₹2 lakh crore infra package",
            ]},
            {"type": "volatility", "messages": [
                "VIX spikes 15% - increased volatility expected",
                "NIFTY Bank index swings 500 points intraday",
                "Options premiums surge ahead of expiry",
            ]},
            {"type": "technical", "messages": [
                "NIFTY 50 breaks above 200-day moving average",
                "Reliance forms bullish flag pattern",
                "Market breadth improves - 80% stocks advancing",
            ]},
            {"type": "earnings", "messages": [
                "TCS Q4 results today after market hours",
                "15 NIFTY 50 companies reporting this week",
                "IT sector earnings beat estimates by 12%",
            ]},
        ]
        
        alerts = []
        for _ in range(random.randint(2, 5)):
            alert_type = random.choice(alert_templates)
            message = random.choice(alert_type['messages'])
            minutes_ago = random.randint(1, 120)
            
            alerts.append({
                'type': alert_type['type'],
                'message': message,
                'timestamp': (datetime.now() - timedelta(minutes=minutes_ago)).isoformat(),
                'priority': random.choice(['high', 'medium', 'low'])
            })
        
        # Sort by timestamp
        alerts.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return {
            'alerts': alerts,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error fetching market alerts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
