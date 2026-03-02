#!/usr/bin/env python3
"""
Test to verify risk limit configuration is loaded correctly from DB.
"""

import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.db.session import SessionLocal
from app.db.risk_repo import get_or_create_risk_limits, update_risk_limits
from app.core.risk.risk_limits_config import get_risk_limits, DEFAULT_IV_REGIME_LIMITS

def test_risk_limits_loading():
    """Test that risk limits are loaded correctly from DB."""
    print("=" * 70)
    print("Risk Limits Configuration Test")
    print("=" * 70)
    print()
    
    db = SessionLocal()
    try:
        # 1. Get current DB settings
        print("1️⃣ Checking current DB settings...")
        current = get_or_create_risk_limits(db)
        print(f"   max_portfolio_loss_pct: {current.max_portfolio_loss_pct}%")
        print(f"   max_trades_per_day: {current.max_trades_per_day}")
        print(f"   IV Regime Limits:")
        for regime, limits in (current.iv_regime_limits or DEFAULT_IV_REGIME_LIMITS).items():
            print(f"     {regime}: max_risk={limits['max_risk_pct_capital']}%, min_atm_dist={limits['min_atm_dist_pct']}%")
        print()
        
        # 2. Update to 12% for NORMAL regime
        print("2️⃣ Updating NORMAL regime max_risk to 12%...")
        new_limits = current.iv_regime_limits or DEFAULT_IV_REGIME_LIMITS
        new_limits["NORMAL"]["max_risk_pct_capital"] = 12.0
        
        updated = update_risk_limits(
            db,
            max_portfolio_loss_pct=current.max_portfolio_loss_pct,
            max_trades_per_day=current.max_trades_per_day,
            iv_regime_limits=new_limits,
        )
        print(f"   ✅ Updated!")
        print(f"   NORMAL max_risk: {updated.iv_regime_limits['NORMAL']['max_risk_pct_capital']}%")
        print()
        
        # 3. Test loading with db parameter (CORRECT WAY)
        print("3️⃣ Loading with db parameter (passing session)...")
        config_with_db = get_risk_limits(db=db)
        limits_with_db = config_with_db.get_iv_regime_limits("NORMAL")
        print(f"   ✅ NORMAL max_risk: {limits_with_db['max_risk_pct_capital']}%")
        print()
        
        # 4. Test loading without db parameter (CREATES NEW SESSION)
        print("4️⃣ Loading without db parameter (creates new session)...")
        config_without_db = get_risk_limits()  # No db parameter
        limits_without_db = config_without_db.get_iv_regime_limits("NORMAL")
        print(f"   ✅ NORMAL max_risk: {limits_without_db['max_risk_pct_capital']}%")
        print()
        
        # 5. Summary
        print("=" * 70)
        print("Summary:")
        print("=" * 70)
        if limits_with_db['max_risk_pct_capital'] == 12.0:
            print("✅ With db parameter: CORRECT (12.0%)")
        else:
            print(f"❌ With db parameter: WRONG ({limits_with_db['max_risk_pct_capital']}%)")
        
        if limits_without_db['max_risk_pct_capital'] == 12.0:
            print("✅ Without db parameter: CORRECT (12.0%)")
        else:
            print(f"❌ Without db parameter: WRONG ({limits_without_db['max_risk_pct_capital']}%)")
        print()
        
    finally:
        db.close()

if __name__ == "__main__":
    test_risk_limits_loading()
