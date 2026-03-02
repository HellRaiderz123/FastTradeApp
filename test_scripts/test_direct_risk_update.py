#!/usr/bin/env python3
"""
Test to debug why risk limit updates aren't persisting.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.db.session import SessionLocal
from app.db.risk_repo import get_or_create_risk_limits, update_risk_limits
from app.db.models_risk import RiskLimitConfig, default_iv_limits

def test_direct_update():
    """Test direct update to the database."""
    print("=" * 70)
    print("Direct Risk Limits Update Test")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    try:
        # Get current
        print("1️⃣ Getting current record...")
        current = get_or_create_risk_limits(db)
        print(f"   ID: {current.id}")
        print(f"   NORMAL max_risk before: {current.iv_regime_limits['NORMAL']['max_risk_pct_capital']}")
        
        # Direct update
        print("\n2️⃣ Direct update to DB...")
        new_limits = current.iv_regime_limits.copy()
        new_limits["NORMAL"]["max_risk_pct_capital"] = 12.0
        print(f"   Setting NORMAL max_risk to: 12.0")
        
        current.iv_regime_limits = new_limits
        db.add(current)
        db.commit()
        db.refresh(current)
        print(f"   NORMAL max_risk after commit: {current.iv_regime_limits['NORMAL']['max_risk_pct_capital']}")
        
        # Fetch fresh
        print("\n3️⃣ Fetching fresh from DB...")
        fresh = db.query(RiskLimitConfig).filter(RiskLimitConfig.id == current.id).first()
        print(f"   NORMAL max_risk from fresh query: {fresh.iv_regime_limits['NORMAL']['max_risk_pct_capital']}")
        
        # Close and reopen session
        print("\n4️⃣ Closing session and reopening...")
        db.close()
        db = SessionLocal()
        
        fresh2 = db.query(RiskLimitConfig).filter(RiskLimitConfig.id == current.id).first()
        print(f"   NORMAL max_risk from new session: {fresh2.iv_regime_limits['NORMAL']['max_risk_pct_capital']}")
        
        print()
        if fresh2.iv_regime_limits['NORMAL']['max_risk_pct_capital'] == 12.0:
            print("✅ Update SUCCESSFUL!")
        else:
            print("❌ Update FAILED - value not persisted")
        
    finally:
        db.close()

if __name__ == "__main__":
    test_direct_update()
