"""
migrate_multi_asset_tables.py
-----------------------------
Database migration script to add multi-asset support tables.

Creates:
- Symbol table (NIFTY 50 stocks metadata)
- MarketData table (candlestick data)
- AlertRule table (dynamic alerts)

Run with: python migrate_multi_asset_tables.py
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.db.models import Base, Symbol
from app.db import multi_asset_repo

logger = logging.getLogger(__name__)


def create_tables():
    """Create new tables in database"""
    logger.info("🔧 Creating multi-asset tables...")
    
    # Create all tables defined in models
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tables created successfully")


def seed_nifty50_symbols(db: Session):
    """Seed NIFTY 50 stocks into Symbol table"""
    
    # NIFTY 50 stocks (as of Feb 2026)
    nifty50_stocks = [
        # IT & Software
        {"ticker": "TCS", "name": "Tata Consultancy Services", "sector": "IT", "rank": 1},
        {"ticker": "INFY", "name": "Infosys Limited", "sector": "IT", "rank": 2},
        {"ticker": "WIPRO", "name": "Wipro Limited", "sector": "IT", "rank": 3},
        {"ticker": "TECHM", "name": "Tech Mahindra Limited", "sector": "IT", "rank": 4},
        {"ticker": "HCL", "name": "HCL Technologies Limited", "sector": "IT", "rank": 5},
        
        # Financials
        {"ticker": "RELIANCE", "name": "Reliance Industries Limited", "sector": "Finance", "rank": 6},
        {"ticker": "ICICIBANK", "name": "ICICI Bank Limited", "sector": "Finance", "rank": 7},
        {"ticker": "HDFC", "name": "HDFC Bank Limited", "sector": "Finance", "rank": 8},
        {"ticker": "SBIN", "name": "State Bank of India", "sector": "Finance", "rank": 9},
        {"ticker": "INDUSIND", "name": "IndusInd Bank Limited", "sector": "Finance", "rank": 10},
        
        # Pharma
        {"ticker": "SUNPHARMA", "name": "Sun Pharmaceutical Industries", "sector": "Pharma", "rank": 11},
        {"ticker": "JYOTHYLAB", "name": "Jyothy Labs Limited", "sector": "Pharma", "rank": 12},
        {"ticker": "CIPLA", "name": "Cipla Limited", "sector": "Pharma", "rank": 13},
        {"ticker": "BAJAJFINSV", "name": "Bajaj Finserv Limited", "sector": "Pharma", "rank": 14},
        {"ticker": "LUPIN", "name": "Lupin Limited", "sector": "Pharma", "rank": 15},
        
        # Automobiles & Engineering
        {"ticker": "MARUTI", "name": "Maruti Suzuki India Limited", "sector": "Automobile", "rank": 16},
        {"ticker": "TATAMOTORS", "name": "Tata Motors Limited", "sector": "Automobile", "rank": 17},
        {"ticker": "BAJAJAUTC", "name": "Bajaj Auto Limited", "sector": "Automobile", "rank": 18},
        {"ticker": "HEROMOTOCO", "name": "Hero MotoCorp Limited", "sector": "Automobile", "rank": 19},
        {"ticker": "LT", "name": "Larsen & Toubro Limited", "sector": "Engineering", "rank": 20},
        
        # Energy & Oil
        {"ticker": "NTPC", "name": "NTPC Limited", "sector": "Energy", "rank": 21},
        {"ticker": "POWERGRID", "name": "Power Grid Corporation of India", "sector": "Energy", "rank": 22},
        {"ticker": "JSWSTEEL", "name": "JSW Steel Limited", "sector": "Steel", "rank": 23},
        {"ticker": "TATASTEEL", "name": "Tata Steel Limited", "sector": "Steel", "rank": 24},
        {"ticker": "VEDL", "name": "Vedanta Limited", "sector": "Mining", "rank": 25},
        
        # Fast Moving Consumer Goods
        {"ticker": "HUL", "name": "Hindustan Unilever Limited", "sector": "FMCG", "rank": 26},
        {"ticker": "ITC", "name": "ITC Limited", "sector": "FMCG", "rank": 27},
        {"ticker": "NESTLEIND", "name": "Nestle India Limited", "sector": "FMCG", "rank": 28},
        {"ticker": "BRITANNIA", "name": "Britannia Industries Limited", "sector": "FMCG", "rank": 29},
        {"ticker": "MARICO", "name": "Marico Limited", "sector": "FMCG", "rank": 30},
        
        # Additional Sectors
        {"ticker": "KOTAK", "name": "Kotak Mahindra Bank Limited", "sector": "Finance", "rank": 31},
        {"ticker": "AXISBANK", "name": "Axis Bank Limited", "sector": "Finance", "rank": 32},
        {"ticker": "ULTRACEMCO", "name": "UltraTech Cement Limited", "sector": "Cement", "rank": 33},
        {"ticker": "BHARTIARTL", "name": "Bharti Airtel Limited", "sector": "Telecom", "rank": 34},
        {"ticker": "ASIANPAINT", "name": "Asian Paints (India) Limited", "sector": "Paints", "rank": 35},
        
        {"ticker": "DMART", "name": "Avenue Supermarts Limited", "sector": "Retail", "rank": 36},
        {"ticker": "BAJAJFINSV", "name": "Bajaj Finserv Limited", "sector": "Finance", "rank": 37},
        {"ticker": "DIVISLAB", "name": "Divi's Laboratories Limited", "sector": "Pharma", "rank": 38},
        {"ticker": "GSHIPPER", "name": "Gland Pharma (if included)", "sector": "Pharma", "rank": 39},
        {"ticker": "GMRINFRA", "name": "GMR Infrastructure Limited", "sector": "Infrastructure", "rank": 40},
        
        {"ticker": "M&MFIN", "name": "Mahindra & Mahindra Financial Services", "sector": "Finance", "rank": 41},
        {"ticker": "M&M", "name": "Mahindra & Mahindra Limited", "sector": "Automobile", "rank": 42},
        {"ticker": "MOTHERSUMI", "name": "Motherson Sumi Systems Limited", "sector": "Auto Components", "rank": 43},
        {"ticker": "MRF", "name": "MRF Limited", "sector": "Rubber", "rank": 44},
        {"ticker": "ONGC", "name": "Oil and Natural Gas Corporation Limited", "sector": "Energy", "rank": 45},
        
        {"ticker": "SAIL", "name": "Steel Authority of India Limited", "sector": "Steel", "rank": 46},
        {"ticker": "SBICARD", "name": "SBI Card and Payment Services Limited", "sector": "Finance", "rank": 47},
        {"ticker": "SIEMENS", "name": "Siemens Limited", "sector": "Engineering", "rank": 48},
        {"ticker": "TITAN", "name": "Titan Company Limited", "sector": "Consumer Durables", "rank": 49},
        {"ticker": "TORNTPHARMA", "name": "Torrent Pharmaceuticals Limited", "sector": "Pharma", "rank": 50},
    ]
    
    # Check if already seeded
    existing = db.query(Symbol).filter_by(is_nifty50=True).count()
    if existing >= 50:
        logger.info(f"✅ NIFTY 50 already seeded ({existing} symbols found)")
        return
    
    logger.info("🌱 Seeding NIFTY 50 symbols...")
    
    for stock in nifty50_stocks:
        try:
            symbol = multi_asset_repo.get_symbol(db, stock["ticker"])
            if symbol:
                # Update existing
                symbol.is_nifty50 = True
                symbol.nifty_50_rank = stock["rank"]
                symbol.sector = stock["sector"]
            else:
                # Create new
                symbol = multi_asset_repo.create_symbol(
                    db,
                    ticker=stock["ticker"],
                    name=stock["name"],
                    asset_type="STOCK",
                    sector=stock["sector"],
                    is_nifty50=True,
                    nifty_50_rank=stock["rank"],
                )
        except Exception as e:
            logger.warning(f"⚠️ Could not seed {stock['ticker']}: {e}")
    
    db.commit()
    logger.info(f"✅ Seeded {len(nifty50_stocks)} NIFTY 50 symbols")


def main():
    """Run migration"""
    logger.info("=" * 60)
    logger.info("🚀 MULTI-ASSET MIGRATION STARTING")
    logger.info("=" * 60)
    
    try:
        # Create tables
        create_tables()
        
        # Seed NIFTY 50
        db = SessionLocal()
        try:
            seed_nifty50_symbols(db)
        finally:
            db.close()
        
        logger.info("=" * 60)
        logger.info("✅ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ MIGRATION FAILED: {e}")
        logger.error("=" * 60)
        raise


if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/d/FastTradeApp/backend')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    main()
