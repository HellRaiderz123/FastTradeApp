# Twitter/X Sentiment Integration - Complete Setup Guide

## Overview
Real-time market sentiment analysis from Twitter/X with automated alerts for high-impact tweets.

**Features:**
- ✅ Real-time sentiment tracking from market influencers, analysts, and financial media
- ✅ Symbol-specific sentiment analysis (NIFTY, BANKNIFTY, stocks, etc.)
- ✅ High-impact tweet alerts via Toast notifications
- ✅ Trending symbols based on Twitter activity
- ✅ Engagement-weighted sentiment scoring
- ✅ Dashboard widget with draggable layout
- ✅ Automatic symbol extraction and price target detection
- ✅ Background scheduler (updates every 15 minutes during market hours)

## Architecture

### Backend Components
1. **Database Models** (`app/db/models_twitter.py`):
   - `TwitterAccount`: Tracked accounts (influencers, analysts, media)
   - `TwitterSentiment`: Individual tweets with sentiment analysis
   - `TwitterSymbolSentiment`: Aggregated sentiment per symbol
   - `TwitterAlert`: High-impact alerts for user notifications

2. **Service Layer** (`app/services/twitter_service.py`):
   - Twitter API v2 client (tweepy)
   - Sentiment analysis (TextBlob)
   - Symbol extraction from tweet text
   - Impact scoring (engagement + credibility + sentiment strength)
   - Price target detection

3. **API Routes** (`app/api/routes/twitter.py`):
   - `GET /twitter/sentiment/{symbol}` - Symbol-specific sentiment
   - `GET /twitter/recent` - Recent tweets with filters
   - `GET /twitter/trending` - Trending symbols by activity
   - `GET /twitter/alerts` - High-impact alerts
   - `POST /twitter/accounts` - Add tracked account
   - `POST /twitter/update` - Manual update trigger

4. **Scheduler** (`app/core/market/scheduler.py`):
   - `_update_twitter_sentiment()` - Runs every 15 min during market hours
   - Fetches tweets, analyzes sentiment, creates alerts
   - Auto-registers in `main.py` startup

### Frontend Components
1. **Twitter Sentiment Widget** (`web/src/components/TwitterSentimentWidget.tsx`):
   - Draggable dashboard widget
   - Overall sentiment display
   - Trending symbols
   - Recent tweets list
   - Real-time updates (60s interval)

2. **Twitter Alerts Monitor** (`web/src/components/TwitterAlerts.tsx`):
   - Background monitor (runs silently)
   - Toast notifications for high-impact tweets
   - Optional alerts panel component

3. **API Client** (`web/src/lib/api.ts`):
   - `twitterAPI.getSymbolSentiment()`
   - `twitterAPI.getTrending()`
   - `twitterAPI.getAlerts()`
   - Full TypeScript interface

## Installation

### 1. Install Python Dependencies

```bash
cd backend
pip install tweepy==4.14.0 textblob==0.18.0
```

Or add to `requirements.txt`:
```
tweepy==4.14.0
textblob==0.18.0
```

### 2. Download TextBlob Corpora
```bash
python -m textblob.download_corpora
```

### 3. Get Twitter API Credentials

#### Option A: Twitter API v2 (Recommended)
1. Go to https://developer.twitter.com/en/portal/dashboard
2. Create a new app or use existing
3. Navigate to "Keys and tokens"
4. Copy **Bearer Token** (read-only access, easiest setup)

#### Option B: OAuth 1.0a (Full access)
1. Same developer portal
2. Copy:
   - API Key
   - API Secret
   - Access Token
   - Access Secret

### 4. Configure Environment Variables

Add to `backend/.env`:

```bash
# Twitter API v2 (Recommended - read-only access)
TWITTER_BEARER_TOKEN=your_bearer_token_here

# OR OAuth 1.0a (if you need write access)
# TWITTER_API_KEY=your_api_key
# TWITTER_API_SECRET=your_api_secret
# TWITTER_ACCESS_TOKEN=your_access_token
# TWITTER_ACCESS_SECRET=your_access_secret
```

**Note:** Only `TWITTER_BEARER_TOKEN` is required for sentiment analysis (read-only).

### 5. Create Database Tables

The tables auto-create on server startup, but you can manually migrate:

```bash
cd backend
python -c "from app.db.session import engine; from app.db.models_twitter import TwitterAccount; TwitterAccount.metadata.create_all(engine)"
```

### 6. Seed Twitter Accounts

```bash
cd backend
python seed_twitter_accounts.py
```

This adds default accounts:
- NSE India (@NSEIndia)
- BSE India (@BSEIndia)
- SEBI (@SEBI_India)
- Economic Times (@economictimes)
- Moneycontrol (@moneycontrolcom)
- CNBC TV18 (@CNBCTV18News)
- BloombergQuint (@BloombergQuint)
- Zerodha (@ZerodhaOnline)
- And more...

**⚠️ Important:** Update usernames in `seed_twitter_accounts.py` with actual active Twitter handles of Indian market influencers!

### 7. Restart Backend Server

```bash
cd backend
uvicorn app.main:main --reload
```

Check logs for:
```
🟢 Twitter sentiment scheduler started (every 15 min, market hours only)
✅ Schedulers started for live data updates + TP/SL monitoring + expiry auto-exit + Twitter sentiment
```

## Usage

### Dashboard Widget
1. Navigate to Dashboard page
2. Unlock layout (lock icon in top-right)
3. Drag Twitter Sentiment widget to preferred position
4. Lock layout to save

### Symbol-Specific Sentiment
```typescript
// In your code
const response = await twitterAPI.getSymbolSentiment('NIFTY', '1h');
console.log(response.data.sentiment); // "bullish", "bearish", "neutral"
console.log(response.data.sentiment_score); // -1.0 to 1.0
console.log(response.data.confidence); // 0.0 to 1.0
console.log(response.data.top_tweets); // Recent tweets
```

### High-Impact Alerts
Automatically shown as Toast notifications when:
- Sentiment score > 0.5 (strong bullish) or < -0.5 (strong bearish)
- Engagement score > 50
- Account credibility > 60
- Mentions major symbols (NIFTY, BANKNIFTY, etc.)

### Trending Symbols
```typescript
const trending = await twitterAPI.getTrending('1h', 10);
// Returns symbols ranked by tweet volume + high-impact count
```

## Configuration

### Adjust Tracking Accounts

**Add account via API:**
```bash
curl -X POST http://localhost:8000/api/twitter/accounts \
  -H "Content-Type: application/json" \
  -d '{
    "username": "MarketGuru",
    "account_type": "analyst",
    "credibility_score": 75.0,
    "impact_weight": 1.2
  }'
```

**Add account via database:**
```python
from app.db.session import SessionLocal
from app.db.models_twitter import TwitterAccount

db = SessionLocal()
account = TwitterAccount(
    username="TradingExpert",
    account_type="influencer",
    credibility_score=80.0,
    impact_weight=1.3,
    active=True
)
db.add(account)
db.commit()
```

### Adjust Scheduler Frequency

Edit `app/core/market/scheduler.py`:
```python
scheduler.add_job(
    func=_update_twitter_sentiment,
    trigger="cron",
    minute="*/10",  # Change from */15 to */10 for every 10 minutes
    ...
)
```

### Alert Thresholds

Edit `app/services/twitter_service.py`:
```python
def determine_impact_level(self, sentiment_score, engagement_score, account_credibility, symbols):
    # Adjust these weights
    impact_score = (
        abs(sentiment_score) * 30 +  # Increase for stronger sentiment bias
        (engagement_score / 100) * 30 +
        (account_credibility / 100) * 25 +
        (15 if has_major else 0)
    )
    
    if impact_score >= 70:  # Lower threshold for more alerts
        return "high"
    ...
```

## API Rate Limits

**Twitter API Free Tier:**
- 500,000 tweets/month
- Rate limit: 450 requests per 15-minute window

**Optimization:**
- Default: 10 tweets per account, max 10 accounts = 100 tweets per update
- Schedule: Every 15 min = 96 updates/day = 9,600 tweets/day = 288,000/month
- **Well within free tier limits!**

To reduce API usage:
1. Track fewer accounts
2. Increase scheduler interval (e.g., every 30 min)
3. Use mock data during development

## Mock Data (Testing Without API Keys)

If `TWITTER_BEARER_TOKEN` not set, service returns mock tweets automatically.

Enable/disable in `twitter_service.py`:
```python
def fetch_tweets_from_accounts(self, db, max_tweets=100):
    if not self.enabled or not self.client:
        return self._get_mock_tweets()  # Returns 3 sample tweets
```

## Troubleshooting

### "Twitter API not configured" Error
**Solution:** Set `TWITTER_BEARER_TOKEN` in `backend/.env`

### No Tweets Showing
**Causes:**
1. No accounts tracked → Run `seed_twitter_accounts.py`
2. Invalid API credentials → Check Twitter Developer Portal
3. Scheduler not running → Check backend logs for "Twitter sentiment scheduler started"
4. Accounts have no recent tweets → Wait 15 min for next update or trigger manually

**Manual trigger:**
```bash
curl -X POST http://localhost:8000/api/twitter/update
```

### High API Usage
**Solutions:**
1. Reduce tracked accounts
2. Increase scheduler interval
3. Filter accounts by `track_symbols` instead of tracking all

### Sentiment Always Neutral
**Causes:**
1. TextBlob corpora not installed → `python -m textblob.download_corpora`
2. Tweets don't contain market keywords → Adjust `BULLISH_KEYWORDS`/`BEARISH_KEYWORDS`
3. Weak sentiment in actual tweets → Working as intended

### Alerts Not Showing
**Check:**
1. Alert severity settings (only "high" and "critical" show toasts by default)
2. Toast notification permissions
3. Browser console for errors
4. Background monitor is imported in `App.tsx`

## Performance Considerations

**Database Growth:**
- Tweets stored indefinitely by default
- **Recommended:** Add cleanup job to delete tweets older than 30 days

**Add to scheduler:**
```python
def _cleanup_old_tweets():
    from datetime import datetime, timedelta
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=30)
        deleted = db.query(TwitterSentiment).filter(
            TwitterSentiment.created_at < cutoff
        ).delete()
        db.commit()
        logger.info(f"🧹 Cleaned up {deleted} old tweets")
    finally:
        db.close()

scheduler.add_job(
    func=_cleanup_old_tweets,
    trigger="cron",
    hour=2,  # 2 AM daily
    id="twitter_cleanup_job",
    replace_existing=True
)
```

## Best Practices

1. **Account Selection:**
   - Verify accounts: Use verified accounts with high follower counts
   - Credibility scoring: Assign higher scores to official sources
   - Impact weighting: Boost influencers with proven track records

2. **Sentiment Tuning:**
   - Monitor false positives/negatives
   - Adjust keyword lists in `twitter_service.py`
   - Consider using ML model instead of TextBlob for better accuracy

3. **Alert Fatigue:**
   - Start with conservative thresholds
   - Only alert on "high" and "critical" severity
   - Group alerts by symbol to reduce spam

4. **Privacy & Compliance:**
   - Only track public accounts
   - Respect Twitter's Terms of Service
   - Don't store user data unnecessarily

## Advanced: ML-Based Sentiment

For better accuracy, replace TextBlob with Hugging Face transformers:

```bash
pip install transformers torch
```

```python
from transformers import pipeline

classifier = pipeline("sentiment-analysis", 
                     model="finiteautomata/bertweet-base-sentiment-analysis")

def analyze_sentiment(self, text):
    result = classifier(text[:512])[0]  # BERT has 512 token limit
    label = result['label']  # POS/NEG/NEU
    score = result['score']
    
    sentiment_map = {'POS': 'bullish', 'NEG': 'bearish', 'NEU': 'neutral'}
    return {
        'sentiment': sentiment_map.get(label, 'neutral'),
        'score': score if label == 'POS' else -score,
        'confidence': score
    }
```

## Support & Contributing

Issues: Report in project GitHub Issues
Updates: Check for new versions in releases
Customization: Fork and modify as needed

---

**Next Steps:**
1. Get Twitter Bearer Token → Add to `.env`
2. Run `seed_twitter_accounts.py` → Add tracked accounts
3. Restart backend → Check logs for "Twitter sentiment scheduler started"
4. View Dashboard → See Twitter widget in action
5. Wait 15 min OR trigger manual update → See tweets populate
6. Watch for high-impact alerts → Toast notifications appear

**Pro Tip:** Combine Twitter sentiment with existing TA signals for multi-factor confirmation!
