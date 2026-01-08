# Position Status Flow - Debugging Guide

## Current Situation
Your data shows:
```json
Run 1: status="CONFIRMED", executed=false, closed_at=null
Run 2: status="CLOSED", executed=true  
Run 3: status="CLOSED", executed=true
```

## Why Positions Page is Empty

The Positions page filters for: **`status === 'EXECUTED' AND closed_at === null`**

- **Run 1**: Status is CONFIRMED (not EXECUTED yet) → Won't show ❌
- **Runs 2 & 3**: Status is CLOSED → Won't show ❌

## Status Lifecycle

```
1. CONFIRMED → Intent created, waiting for execution
   ↓
2. EXECUTED → Position is OPEN (shows in Positions page) ✅
   ↓
3. CLOSED → Position exited
```

## How to Fix

### Option 1: Execute the CONFIRMED Intent

Run this API call to execute intent from Run 1:

```powershell
# Get the intent_id from your run (from the JSON you showed)
$intentId = "37b67a27-d720-42ce-a743-8eb0d5433e67"
$idempotencyKey = [guid]::NewGuid().ToString()

Invoke-RestMethod `
  -Uri "http://localhost:8000/api/execute/paper/$intentId" `
  -Method Post `
  -Headers @{"idempotency-key" = $idempotencyKey}
```

### Option 2: Execute from UI

1. Go to **Strategies** page
2. Click **Execute** button on your strategy
3. System will:
   - Create strategy run
   - Create execution intent (CONFIRMED)
   - Execute paper trade (EXECUTED)
   - Now appears in Positions

### Option 3: Check Backend Logs

If execution is failing silently:

```powershell
# Check backend logs
Get-Content d:\FastTradeApp\backend\logs\app.log -Tail 50
```

Look for errors in `/execute/paper/{intent_id}` endpoint.

## Data Flow Diagram

```
┌─────────────────┐
│  Strategy Page  │
│  Click Execute  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│ POST /strategies/run/single │
│ Creates StrategyRun      │
│ Returns run_id           │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ POST /intent/create      │
│ Creates ExecutionIntent  │
│ status = "CONFIRMED"     │
│ Returns intent_id        │
└────────┬────────────────┘
         │
         ▼
┌──────────────────────────┐
│ POST /execute/paper/{id} │  ← **THIS STEP IS MISSING FOR RUN 1**
│ Executes paper trade     │
│ status = "EXECUTED"      │
└────────┬─────────────────┘
         │
         ▼
┌─────────────────┐
│ Positions Page  │  ← Shows only "EXECUTED" status
│ Shows position  │
└─────────────────┘
```

## Verification Query

Check execution_intents table:

```sql
SELECT id, intent_id, status, executed, closed_at 
FROM execution_intents 
ORDER BY created_at DESC 
LIMIT 5;
```

Expected for active position:
- status = "EXECUTED"
- executed = true
- closed_at = NULL

## Quick Test

Execute Run 1 intent manually:

```powershell
# Start backend if not running
cd d:\FastTradeApp\backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Execute intent
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/execute/paper/37b67a27-d720-42ce-a743-8eb0d5433e67" `
  -Method Post `
  -Headers @{"idempotency-key" = ([guid]::NewGuid().ToString())}

# Check positions
Invoke-RestMethod -Uri "http://localhost:8000/api/journal/execution-intents?limit=10" | ConvertTo-Json -Depth 5
```

Now check Positions page - Run 1 should appear!
