"""
Migration script: Create StrategyConfig table
Run this once to set up the database for multi-strategy support
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text, inspect
from app.db.session import engine, Base
from app.db.models import StrategyConfig
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def table_exists(table_name: str) -> bool:
    """Check if table exists"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def migrate_strategy_config():
    """Create StrategyConfig table"""
    
    if table_exists("strategy_configs"):
        logger.info("✅ strategy_configs table already exists")
        return True
    
    try:
        logger.info("🔨 Creating strategy_configs table...")
        
        # Create all tables defined in models
        Base.metadata.create_all(engine)
        
        logger.info("✅ strategy_configs table created successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = migrate_strategy_config()
    exit(0 if success else 1)
