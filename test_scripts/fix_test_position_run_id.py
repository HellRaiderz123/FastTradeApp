"""Fix the test position with invalid run_id"""

import sys
sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

db = SessionLocal()
try:
    # Find the test position with string run_id
    test_intent = (
        db.query(ExecutionIntent)
        .filter(ExecutionIntent.intent_id.like('test_%'))
        .filter(ExecutionIntent.run_id == 'manual_test')
        .first()
    )
    
    if test_intent:
        print(f"Found test position: {test_intent.intent_id}")
        print(f"  Current run_id: {test_intent.run_id} (type: {type(test_intent.run_id).__name__})")
        
        # Option 1: Delete it
        print(f"\nDeleting test position...")
        db.delete(test_intent)
        db.commit()
        print("  [DELETED]")
    else:
        print("No test position found with run_id='manual_test'")
        
        # Check for any other test positions
        all_test = db.query(ExecutionIntent).filter(
            ExecutionIntent.intent_id.like('test_%')
        ).all()
        
        if all_test:
            print(f"\nFound {len(all_test)} other test positions:")
            for intent in all_test:
                print(f"  {intent.intent_id[:12]}: run_id={intent.run_id}")
                if intent.run_id == 'manual_test' or not isinstance(intent.run_id, int):
                    print(f"    Deleting {intent.intent_id[:12]}...")
                    db.delete(intent)
            db.commit()
            print("  [DELETED ALL TEST POSITIONS]")

finally:
    db.close()

print("\n[DONE]")
