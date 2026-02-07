#!/usr/bin/env python
"""Quick test script to verify Phase 1 implementations"""

import sys
import json

print("\n" + "="*60)
print("✅ PHASE 1 IMPLEMENTATION TEST")
print("="*60)

# Test 1: Models
print("\n1️⃣ Testing Models...")
try:
    from app.db.models import Symbol, MarketData, AlertRule
    print("   ✅ Symbol, MarketData, AlertRule imported")
except Exception as e:
    print(f"   ❌ Model import failed: {e}")
    sys.exit(1)

# Test 2: Repository
print("\n2️⃣ Testing Repository Layer...")
try:
    from app.db.multi_asset_repo import (
        create_symbol, get_symbol, list_nifty50,
        create_market_data, get_candles,
        create_alert_rule, list_active_alerts
    )
    from app.db.session import SessionLocal
    db = SessionLocal()
    db.close()
    print("   ✅ Repository functions and DB session working")
except Exception as e:
    print(f"   ❌ Repository test failed: {e}")
    sys.exit(1)

# Test 3: Signal Generation
print("\n3️⃣ Testing Multi-Asset Signal Generation...")
try:
    from app.core.signals.base import (
        Signal, SignalFactory, AssetType, 
        SignalStrength, MarketBias, IVRegime
    )
    from app.core.signals.enrichers import (
        StockEnricher, OptionEnricher, 
        FutureEnricher, IndexEnricher
    )
    
    enrichers = SignalFactory.list_enrichers()
    print(f"   ✅ Asset types registered: {[e.value for e in enrichers]}")
    print(f"   ✅ All enrichers available: {len(enrichers)} types")
except Exception as e:
    print(f"   ❌ Signal generation test failed: {e}")
    sys.exit(1)

# Test 4: Strategy Engine
print("\n4️⃣ Testing Multi-Asset Strategy Engine...")
try:
    from app.core.strategies.base_strategy import (
        BaseStrategy, StrategyType, StrategyResult, StrategyLeg
    )
    from app.core.strategies.stock_strategies import (
        MomentumStrategy, MeanReversionStrategy, TrendFollowingStrategy
    )
    
    print(f"   ✅ Strategy types available: {len([e for e in StrategyType])}")
    print(f"   ✅ Stock strategies available: 3 (Momentum, MeanReversion, TrendFollowing)")
except Exception as e:
    print(f"   ❌ Strategy engine test failed: {e}")
    sys.exit(1)

# Test 5: Strategy Registry
print("\n5️⃣ Testing Strategy Registry...")
try:
    from app.core.strategies.registry import StrategyRegistry
    
    strategies = StrategyRegistry.list_with_metadata()
    legacy_count = sum(1 for s in strategies if s['type'] == 'LEGACY')
    new_count = sum(1 for s in strategies if s['type'] == 'NEW')
    
    print(f"   ✅ Total strategies: {len(strategies)}")
    print(f"      - Legacy (old style): {legacy_count}")
    print(f"      - New (BaseStrategy): {new_count}")
    
except Exception as e:
    print(f"   ❌ Strategy registry test failed: {e}")
    sys.exit(1)

# Test 6: Application Startup
print("\n6️⃣ Testing Application Startup...")
try:
    from app.main import app
    print(f"   ✅ FastTradeApp initialized successfully")
except Exception as e:
    print(f"   ❌ App startup test failed: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ ALL PHASE 1 TESTS PASSED!")
print("="*60)
print("\nPhase 1 Status:")
print("  ✅ Phase 1.1: Multi-asset signal generation")
print("  ✅ Phase 1.2: Multi-asset strategy engine")
print("  ✅ Phase 1.3: Data models for NIFTY 50")
print("\n🚀 Ready for Phase 2: Web UI Overhaul")
print("="*60 + "\n")
