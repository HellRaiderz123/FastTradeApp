"""
Migration script to add watchlist tables
"""
from sqlalchemy import create_engine
from app.db.session import Base, DATABASE_URL
from app.db.models_watchlist import Watchlist, WatchlistAlert

def run_migration():
    """Create the watchlist tables"""
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    print("Creating watchlist tables...")
    print("- watchlists")
    print("- watchlist_alerts")
    
    # Create tables
    Base.metadata.create_all(bind=engine, tables=[
        Watchlist.__table__,
        WatchlistAlert.__table__,
    ])
    
    # Insert default watchlists
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    existing = session.query(Watchlist).filter(Watchlist.name == "NIFTY 50").first()
    
    if not existing:
        print("\nCreating default watchlists...")
        
        default_watchlists = [
            {
                "name": "NIFTY 50",
                "description": "Top 50 stocks by market cap",
                "symbols": ["NIFTY", "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL"],
                "color": "#3b82f6",
                "icon": "TrendingUp",
                "is_default": True,
            },
            {
                "name": "Indices",
                "description": "Major market indices",
                "symbols": ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"],
                "color": "#8b5cf6",
                "icon": "BarChart3",
                "is_default": False,
            },
            {
                "name": "IT Stocks",
                "description": "Information Technology sector",
                "symbols": ["INFY", "TCS", "WIPRO", "HCLTECH", "TECHM", "LTIM"],
                "color": "#10b981",
                "icon": "Cpu",
                "is_default": False,
            },
            {
                "name": "Bank NIFTY",
                "description": "Banking sector stocks",
                "symbols": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK"],
                "color": "#f59e0b",
                "icon": "Landmark",
                "is_default": False,
            },
        ]
        
        for wl_data in default_watchlists:
            watchlist = Watchlist(**wl_data)
            session.add(watchlist)
        
        session.commit()
        print("✅ Default watchlists created!")
    else:
        print("ℹ️  Watchlists already exist")
    
    session.close()
    
    print("\n✅ Migration complete!")
    print("\nNew tables created:")
    print("  • watchlists - Custom symbol watchlists")
    print("  • watchlist_alerts - Price alerts for symbols")
    print("\nDefault watchlists:")
    print("  • NIFTY 50")
    print("  • Indices")
    print("  • IT Stocks")
    print("  • Bank NIFTY")

if __name__ == "__main__":
    run_migration()
