"""
Seed Twitter Accounts for Sentiment Tracking
Run this script to add default Twitter accounts to track for market sentiment.
"""

import sys
from pathlib import Path

# Add backend path to sys.path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.db.session import SessionLocal
from app.db.models_twitter import TwitterAccount

# Default accounts to track (Indian market influencers, analysts, and financial media)
DEFAULT_ACCOUNTS = [
    {
        "username": "NSEIndia",
        "display_name": "National Stock Exchange of India",
        "account_type": "official",
        "follower_count": 500000,
        "verified": True,
        "credibility_score": 95.0,
        "impact_weight": 1.5,
        "track_symbols": ["NIFTY", "BANKNIFTY", "FINNIFTY"]
    },
    {
        "username": "BSEIndia",
        "display_name": "Bombay Stock Exchange",
        "account_type": "official",
        "follower_count": 400000,
        "verified": True,
        "credibility_score": 95.0,
        "impact_weight": 1.5,
        "track_symbols": ["SENSEX"]
    },
    {
        "username": "SEBI_India",
        "display_name": "SEBI",
        "account_type": "official",
        "follower_count": 300000,
        "verified": True,
        "credibility_score": 100.0,
        "impact_weight": 2.0,
        "track_symbols": None  # Track all
    },
    {
        "username": "Motilal_Oswal",
        "display_name": "Motilal Oswal",
        "account_type": "analyst",
        "follower_count": 150000,
        "verified": True,
        "credibility_score": 85.0,
        "impact_weight": 1.3,
        "track_symbols": None
    },
    {
        "username": "reliancejio",
        "display_name": "Reliance Jio Infocomm Limited",
        "account_type": "official",
        "follower_count": 800000,
        "verified": True,
        "credibility_score": 90.0,
        "impact_weight": 1.2,
        "track_symbols": ["RELIANCE"]
    },
    {
        "username": "ZerodhaOnline",
        "display_name": "Zerodha",
        "account_type": "media",
        "follower_count": 600000,
        "verified": True,
        "credibility_score": 80.0,
        "impact_weight": 1.1,
        "track_symbols": None
    },
    {
        "username": "NSEIndices",
        "display_name": "NSE Indices",
        "account_type": "official",
        "follower_count": 200000,
        "verified": True,
        "credibility_score": 95.0,
        "impact_weight": 1.4,
        "track_symbols": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYIT"]
    },
    {
        "username": "economictimes",
        "display_name": "The Economic Times",
        "account_type": "media",
        "follower_count": 2000000,
        "verified": True,
        "credibility_score": 85.0,
        "impact_weight": 1.2,
        "track_symbols": None
    },
    {
        "username": "moneycontrolcom",
        "display_name": "Moneycontrol",
        "account_type": "media",
        "follower_count": 1500000,
        "verified": True,
        "credibility_score": 82.0,
        "impact_weight": 1.1,
        "track_symbols": None
    },
    {
        "username": "BloombergQuint",
        "display_name": "BloombergQuint",
        "account_type": "media",
        "follower_count": 800000,
        "verified": True,
        "credibility_score": 88.0,
        "impact_weight": 1.3,
        "track_symbols": None
    },
    {
        "username": "CNBCTV18News",
        "display_name": "CNBC TV18",
        "account_type": "media",
        "follower_count": 1200000,
        "verified": True,
        "credibility_score": 84.0,
        "impact_weight": 1.2,
        "track_symbols": None
    },
    # Add popular market analysts/influencers (replace with actual usernames)
    {
        "username": "marketanalyst1",
        "display_name": "Market Analyst 1",
        "account_type": "analyst",
        "follower_count": 100000,
        "verified": False,
        "credibility_score": 70.0,
        "impact_weight": 1.0,
        "track_symbols": None
    },
    {
        "username": "tradingexpert",
        "display_name": "Trading Expert",
        "account_type": "influencer",
        "follower_count": 80000,
        "verified": False,
        "credibility_score": 65.0,
        "impact_weight": 0.9,
        "track_symbols": None
    },
]


def seed_twitter_accounts():
    """Add default Twitter accounts to database"""
    db = SessionLocal()
    
    try:
        added = 0
        skipped = 0
        
        for account_data in DEFAULT_ACCOUNTS:
            # Check if already exists
            existing = db.query(TwitterAccount).filter(
                TwitterAccount.username == account_data["username"]
            ).first()
            
            if existing:
                print(f"⏩ Skipping @{account_data['username']} (already exists)")
                skipped += 1
                continue
            
            # Create new account
            account = TwitterAccount(**account_data)
            db.add(account)
            added += 1
            print(f"✅ Added @{account_data['username']} ({account_data['account_type']})")
        
        db.commit()
        
        print(f"\n📊 Summary: {added} accounts added, {skipped} already existed")
        print(f"Total tracked accounts: {db.query(TwitterAccount).count()}")
        
        return True
    
    except Exception as e:
        print(f"❌ Error seeding Twitter accounts: {e}")
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding Twitter accounts for sentiment tracking...\n")
    success = seed_twitter_accounts()
    
    if success:
        print("\n✅ Twitter accounts seeded successfully!")
        print("💡 Tip: Update usernames in backend/seed_twitter_accounts.py with actual Indian market Twitter handles")
    else:
        print("\n❌ Failed to seed Twitter accounts")
        sys.exit(1)
