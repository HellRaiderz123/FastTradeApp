"""
Test script to verify the expiry fix for ExecutionIntent
"""
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.intent_repo import create_execution_intent
from app.db.models_intent import ExecutionIntent

def test_expiry_fix():
    """Test that ExecutionIntent now has expiry attribute"""
    db: Session = SessionLocal()
    
    try:
        # Create a test intent with expiry
        test_ticket = {
            "strategy": "TEST",
            "underlying": "BANKNIFTY",
            "lot_size": 15,
            "lots": 1,
            "legs": [
                {"side": "SELL", "strike": 51000, "type": "CE"},
                {"side": "BUY", "strike": 51100, "type": "CE"},
            ]
        }
        
        intent = create_execution_intent(
            db=db,
            run_id=999999,
            strategy="TEST",
            underlying="BANKNIFTY",
            ticket=test_ticket,
            expiry="2026-01-15",
            tp=1000.0,
            sl=-500.0,
        )
        
        print(f"✅ Created ExecutionIntent with ID: {intent.intent_id}")
        print(f"✅ Expiry attribute exists: {hasattr(intent, 'expiry')}")
        print(f"✅ Expiry value: {intent.expiry}")
        
        # Verify we can access it
        assert hasattr(intent, 'expiry'), "ExecutionIntent should have expiry attribute"
        assert intent.expiry == "2026-01-15", f"Expected expiry '2026-01-15', got '{intent.expiry}'"
        
        # Clean up test data
        db.delete(intent)
        db.commit()
        
        print("\n🎉 All tests passed! The expiry fix is working correctly.")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_expiry_fix()
