"""
Test that daily trade limit only counts successful executions
"""
from datetime import date
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.risk.trade_limit import check_daily_trade_limit
from app.core.risk.risk_limits_config import RiskLimits

def test_trade_limit_logic():
    """Test that only executed trades count towards daily limit"""
    db: Session = SessionLocal()
    
    try:
        # Clean up test data first
        today = date.today()
        db.query(ExecutionIntent).filter(
            ExecutionIntent.created_at >= today,
            ExecutionIntent.run_id == 999999
        ).delete()
        db.commit()
        
        print("="*60)
        print("Testing Daily Trade Limit Logic")
        print("="*60)
        
        # Create test risk config with limit of 3
        test_config = RiskLimits(
            max_trades_per_day=3,
            max_portfolio_loss_pct=5.0
        )
        
        # Test 1: No trades yet
        print("\n1️⃣ Test: No trades executed yet")
        limit_exceeded = check_daily_trade_limit(db, test_config)
        print(f"   Limit exceeded: {limit_exceeded}")
        assert limit_exceeded == False, "Should allow trades when none executed"
        print("   ✅ PASSED")
        
        # Test 2: Create 3 FAILED execution attempts (executed=False)
        print("\n2️⃣ Test: Create 3 failed execution attempts")
        for i in range(3):
            intent = ExecutionIntent(
                run_id=999999,
                intent_id=f"test-failed-{i}",
                strategy="TEST",
                underlying="NIFTY",
                ticket={},
                executed=False,  # Failed/pending
            )
            db.add(intent)
        db.commit()
        
        # Check limit - should still allow because executed=False
        limit_exceeded = check_daily_trade_limit(db, test_config)
        print(f"   Limit exceeded: {limit_exceeded}")
        assert limit_exceeded == False, "Failed trades should NOT count towards limit"
        print("   ✅ PASSED - Failed trades don't count!")
        
        # Test 3: Execute 2 successful trades (executed=True)
        print("\n3️⃣ Test: Execute 2 successful trades")
        for i in range(2):
            intent = ExecutionIntent(
                run_id=999999,
                intent_id=f"test-success-{i}",
                strategy="TEST",
                underlying="NIFTY",
                ticket={},
                executed=True,  # Successfully executed
            )
            db.add(intent)
        db.commit()
        
        # Check limit - should still allow (2/3)
        limit_exceeded = check_daily_trade_limit(db, test_config)
        print(f"   Limit exceeded: {limit_exceeded}")
        assert limit_exceeded == False, "Should allow when 2/3 trades executed"
        print("   ✅ PASSED - 2/3 trades allowed")
        
        # Test 4: Execute one more successful trade (3rd)
        print("\n4️⃣ Test: Execute 3rd successful trade")
        intent = ExecutionIntent(
            run_id=999999,
            intent_id="test-success-3",
            strategy="TEST",
            underlying="NIFTY",
            ticket={},
            executed=True,
        )
        db.add(intent)
        db.commit()
        
        # Check limit - should now be exceeded (3/3)
        limit_exceeded = check_daily_trade_limit(db, test_config)
        print(f"   Limit exceeded: {limit_exceeded}")
        assert limit_exceeded == True, "Should block when limit reached"
        print("   ✅ PASSED - Limit correctly enforced at 3/3")
        
        # Test 5: Verify failed trades still don't count
        print("\n5️⃣ Test: Add more failed trades")
        for i in range(5):
            intent = ExecutionIntent(
                run_id=999999,
                intent_id=f"test-failed-extra-{i}",
                strategy="TEST",
                underlying="NIFTY",
                ticket={},
                executed=False,
            )
            db.add(intent)
        db.commit()
        
        # Should still be at 3 successful trades
        limit_exceeded = check_daily_trade_limit(db, test_config)
        print(f"   Limit exceeded: {limit_exceeded}")
        assert limit_exceeded == True, "Failed trades should still not count"
        print("   ✅ PASSED - Failed trades ignored")
        
        # Clean up
        print("\n6️⃣ Cleaning up test data...")
        db.query(ExecutionIntent).filter(
            ExecutionIntent.run_id == 999999
        ).delete()
        db.commit()
        print("   ✅ Cleanup complete")
        
        print("\n" + "="*60)
        print("✅ All trade limit tests passed!")
        print("="*60)
        print("\n📝 Summary:")
        print("   - Failed trades (executed=False) do NOT count")
        print("   - Successful trades (executed=True) DO count")
        print("   - Limit is enforced only on successful executions")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        # Ensure cleanup
        try:
            db.query(ExecutionIntent).filter(
                ExecutionIntent.run_id == 999999
            ).delete()
            db.commit()
        except:
            pass
        db.close()

if __name__ == "__main__":
    test_trade_limit_logic()
