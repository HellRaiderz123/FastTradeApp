#!/usr/bin/env python3
"""
Test using flag_modified to update JSON columns properly.
"""

import sys
from pathlib import Path
from sqlalchemy import event
from sqlalchemy.orm import attributes

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.db.session import SessionLocal
from app.db.risk_repo import get_or_create_risk_limits
from app.db.models_risk import RiskLimitConfig

def test_json_update_with_flag_modified():
    """Test updating JSON column with flag_modified."""
    print("=" * 70)
    print("JSON Column Update Test with flag_modified")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    try:
        # Get current
        print("1️⃣ Getting current record...")
        current = get_or_create_risk_limits(db)
        print(f"   NORMAL max_risk before: {current.iv_regime_limits['NORMAL']['max_risk_pct_capital']}")
        
        # Update with flag_modified
        print("\n2️⃣ Updating with flag_modified...")
        new_limits = dict(current.iv_regime_limits)  # Create a copy
        new_limits["NORMAL"]["max_risk_pct_capital"] = 12.0
        
        current.iv_regime_limits = new_limits
        # Flag the JSON column as modified
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(current, "iv_regime_limits")
        
        db.commit()
        db.refresh(current)
        print(f"   NORMAL max_risk after commit: {current.iv_regime_limits['NORMAL']['max_risk_pct_capital']}")
        
        # Fetch fresh
        print("\n3️⃣ Fetching fresh from DB...")
        db.close()
        db = SessionLocal()
        
        fresh = db.query(RiskLimitConfig).filter(RiskLimitConfig.id == current.id).first()
        print(f"   NORMAL max_risk from fresh query: {fresh.iv_regime_limits['NORMAL']['max_risk_pct_capital']}")
        
        print()
        if fresh.iv_regime_limits['NORMAL']['max_risk_pct_capital'] == 12.0:
            print("✅ Update SUCCESSFUL with flag_modified!")
        else:
            print("❌ Update still FAILED")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_json_update_with_flag_modified()
