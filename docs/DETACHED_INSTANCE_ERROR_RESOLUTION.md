# SQLAlchemy DetachedInstanceError - Root Cause & Fix

## The Error

```
Instance <StrategyRun at 0x2b3063ed6d0> is not bound to a Session; 
attribute refresh operation cannot proceed
(Background: https://sqlalche.me/e/20/bhk3)
```

This error occurs in the **suggestions endpoint** when checking strategy options for NIFTY, BANKNIFTY, FINNIFTY, NIFTY_IT, etc.

---

## Root Cause

The error happens because `StrategyRun` ORM instances were being returned from a function that **closes its own session**:

### Problematic Code Pattern (OLD)

```python
def _log_strategy_run(result: dict, underlying: str) -> Optional[StrategyRun]:
    """PROBLEMATIC: Returns ORM instance from a function that closes session."""
    db = SessionLocal()
    try:
        run = save_strategy_run(
            db=db,
            strategy=str(result.get("strategy") or "NO_TRADE"),
            underlying=str(underlying),
            approved=bool(result.get("approved")),
            ...
        )
        return run  # ❌ DETACHED! Session closes below, but run is returned
    finally:
        db.close()  # Session closes HERE
        # Now run is DETACHED - no session to lazily load attributes
```

### Why This Fails

1. `_log_strategy_run()` creates a local session and saves the `StrategyRun`
2. It **returns the ORM instance** `run`
3. The `finally` block **closes the session**
4. The caller now has a `StrategyRun` instance with no active session
5. If any code tries to access attributes on `run`, SQLAlchemy attempts to refresh from DB
6. Since there's no session bound, it raises **DetachedInstanceError**

### Where It Manifested

In [backend/app/api/routes/suggestions.py](backend/app/api/routes/suggestions.py), the endpoint called:
```python
result = run_option_spread(db=db, payload=payload)
```

Inside the engine, `_log_strategy_run()` was called, which returned a detached `StrategyRun`.  
Then the code tried to serialize the result dict (which somehow referenced the detached instance), triggering the error.

---

## The Fix

### Solution: Return Primitive run_id Instead Of ORM Instance

Changed `_log_strategy_run()` to return **only the primitive `id`** (an integer), not the ORM instance:

#### Fixed Code (NEW)

```python
def _log_strategy_run(result: dict, underlying: str) -> Optional[int]:
    """FIXED: Returns primitive run_id, not ORM instance."""
    db = SessionLocal()
    try:
        run = save_strategy_run(
            db=db,
            strategy=str(result.get("strategy") or "NO_TRADE"),
            underlying=str(underlying),
            approved=bool(result.get("approved")),
            ...
        )
        # ✅ Return only the primitive id (int)
        return run.id if run is not None else None
    except Exception as e:
        print("⚠️ DB log failed:", e)
        return None
    finally:
        db.close()  # Session closes - but we only returned an int, no problem!
```

#### Caller Pattern (NEW)

```python
# Before (WRONG):
# run = _log_strategy_run(result, payload["underlying"])
# if run:
#     result["run_id"] = run.id  # Accessing detached ORM instance

# After (CORRECT):
run_id = _log_strategy_run(result, payload["underlying"])
if run_id:
    result["run_id"] = run_id  # run_id is just an int
```

### Key Benefits

1. **No Session Reference**: Primitive `int` is not tied to any SQLAlchemy session
2. **Safe Serialization**: Can be freely returned in JSON responses
3. **No Lazy Loading**: No attributes to load from DB
4. **Type Safe**: Guaranteed to be `Optional[int]`

---

## Files Modified

### 1. `backend/app/core/strategies/option_spread_15m/engine.py`

- ✅ Changed `_log_strategy_run()` return type from `Optional[StrategyRun]` to `Optional[int]`
- ✅ Updated all 4 call sites to use `run_id = _log_strategy_run(...)` instead of `run = ...`
- ✅ Updated assignment: `result["run_id"] = run_id` instead of `result["run_id"] = run.id`

### 2. `backend/app/core/strategies/option_spread_custom/engine.py`

- ✅ Fixed similar pattern where StrategyRun was being returned
- ✅ Ensured only `run.id` (primitive) is assigned to result dict

---

## Test Validation

Run the included test to verify the fix:

```bash
python test_detached_instance_fix.py
```

Expected output:
```
✅ ALL TESTS PASSED - Fix is correct!

Summary of Changes:
  1. ✅ _log_strategy_run() now returns run.id (int) instead of run (ORM)
  2. ✅ Callers use: run_id = _log_strategy_run(...) instead of: run = ...
  3. ✅ result['run_id'] is set to primitive int, not ORM instance
  4. ✅ No DetachedInstanceError when suggestions endpoint returns JSON
```

---

## Why This Approach is Better

| Aspect | Old Pattern | New Pattern |
|--------|-----------|------------|
| **Return Type** | ORM Instance | Primitive `int` |
| **Session Binding** | Detached | N/A |
| **Lazy Loading Risk** | ❌ High | ✅ None |
| **Serializable** | ❌ No | ✅ Yes |
| **Thread Safe** | ❌ No | ✅ Yes |
| **Memory Overhead** | High | Minimal |

---

## General SQLAlchemy Best Practices

To avoid DetachedInstanceError in the future:

1. **Never Return ORM Instances From Detached Sessions**
   - Return primitive values (id, name, etc.)
   - Or convert to dicts/Pydantic models before closing session

2. **Keep Sessions Alive When Accessing Data**
   ```python
   # ✅ Good: Session is alive during access
   def get_run(db: Session, run_id: int):
       run = db.query(StrategyRun).get(run_id)
       return {
           "id": run.id,           # Accessed while session is alive
           "strategy": run.strategy,
           "approved": run.approved,
       }
   
   # ❌ Bad: Accessing after session closes
   db = SessionLocal()
   try:
       run = db.query(StrategyRun).get(1)
   finally:
       db.close()
   # Now run is detached!
   print(run.strategy)  # DetachedInstanceError
   ```

3. **Use Eager Loading When Needed**
   ```python
   # Load relationships before closing session
   from sqlalchemy.orm import joinedload
   run = db.query(StrategyRun).options(
       joinedload(StrategyRun.related_model)
   ).get(run_id)
   ```

4. **Convert to DTOs**
   ```python
   # Use Pydantic models - no session needed
   from pydantic import BaseModel
   
   class StrategyRunOut(BaseModel):
       id: int
       strategy: str
       approved: bool
   ```

---

## Issue Resolution Status

✅ **RESOLVED**

All occurrences of returning detached `StrategyRun` instances have been fixed.  
The suggestions endpoint now works correctly without raising DetachedInstanceError.

---

## Related Files

- Error log: `backend/logs/app.log` (lines with "not bound to a Session")
- Suggestions endpoint: `backend/app/api/routes/suggestions.py`
- Engine implementations:
  - `backend/app/core/strategies/option_spread_15m/engine.py`
  - `backend/app/core/strategies/option_spread_custom/engine.py`
