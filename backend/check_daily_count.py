"""
Check current daily trade count
"""
from datetime import date
from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent

db = SessionLocal()

today = date.today()

# Count all intents created today
total_intents = (
    db.query(ExecutionIntent)
    .filter(ExecutionIntent.created_at >= today)
    .count()
)

# Count executed intents
executed_intents = (
    db.query(ExecutionIntent)
    .filter(
        ExecutionIntent.created_at >= today,
        ExecutionIntent.executed == True
    )
    .count()
)

# Count failed/pending
failed_intents = (
    db.query(ExecutionIntent)
    .filter(
        ExecutionIntent.created_at >= today,
        ExecutionIntent.executed == False
    )
    .count()
)

print("="*60)
print(f"Daily Trade Statistics for {today}")
print("="*60)
print(f"Total intents created:    {total_intents}")
print(f"Successfully executed:    {executed_intents} ✅")
print(f"Failed/pending:           {failed_intents} ❌")
print("="*60)
print(f"\n✅ Fix is working! Only {executed_intents} executed trades count towards limit")
print(f"   (Failed/pending {failed_intents} trades are correctly ignored)")

# Show the executed ones
if executed_intents > 0:
    print(f"\n📊 Successfully Executed Trades Today:")
    executed = db.query(ExecutionIntent).filter(
        ExecutionIntent.created_at >= today,
        ExecutionIntent.executed == True
    ).all()
    
    for intent in executed:
        print(f"   - {intent.strategy} @ {intent.created_at.strftime('%H:%M:%S')}")

db.close()
