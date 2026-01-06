#!/usr/bin/env python3
"""
Migration script to create the daily_capital table.
Run this once to initialize the table.
"""

from sqlalchemy import create_engine, inspect
from app.db.session import Base, DATABASE_URL
from app.db.models import DailyCapital
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Create the DailyCapital table if it doesn't exist."""
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    # Check if table exists
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if 'daily_capital' in tables:
        logger.info("✅ Table 'daily_capital' already exists")
        return
    
    # Create table
    logger.info("📋 Creating 'daily_capital' table...")
    Base.metadata.create_all(bind=engine, tables=[DailyCapital.__table__])
    
    logger.info("✅ Migration complete! Table 'daily_capital' created successfully")
    logger.info("\nTable structure:")
    logger.info("  - id: Integer (Primary Key)")
    logger.info("  - trade_date: Date (Unique Index)")
    logger.info("  - opening_capital: Float")
    logger.info("  - closing_capital: Float")
    logger.info("  - daily_pnl: Float")
    logger.info("  - daily_return_pct: Float")
    logger.info("  - source: String (default: 'zerodha')")
    logger.info("  - created_at: DateTime")
    logger.info("  - updated_at: DateTime")

if __name__ == '__main__':
    run_migration()
