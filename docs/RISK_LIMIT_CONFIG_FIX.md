# Risk Limit Configuration Issue - RESOLVED

## Problem

When you updated the risk limit to 12% in settings, the system was still showing 2% and rejecting trades like PUT_RATIO_BACKSPREAD.

Error message:
```
Risk 10.40% exceeds limit 2.0%
```

Even though the setting was changed to 12%, it was applying the default 2% limit from the NORMAL IV regime.

---

## Root Cause Analysis

There were **TWO separate issues**:

### Issue 1: JSON Column Updates Not Persisting

When updating the `iv_regime_limits` JSON column in the `risk_limits` table, SQLAlchemy wasn't detecting the nested dictionary changes. The update would appear to work but the database would retain the old value.

**File**: `backend/app/db/risk_repo.py`

```python
# WRONG: SQLAlchemy doesn't detect nested JSON changes
record.iv_regime_limits = new_limits
db.commit()  # Value gets lost!
```

**Why**: SQLAlchemy tracks changes at the ORM attribute level. When you replace `iv_regime_limits` with a new dict (which is the same object), SQLAlchemy can't detect the nested dictionary was modified.

### Issue 2: Risk Config Not Loading From Database

The engine.py calls `get_risk_limits()` without passing the database session.

**File**: `backend/app/core/strategies/option_spread_15m/engine.py` (line 233)

```python
# WRONG: No db parameter, creates new session
risk_config = get_risk_limits()
```

When `db=None`, `get_risk_limits()` creates a fresh session internally. This can lead to:
- Caching issues with different session contexts
- Missing updated data if the transaction hasn't been fully committed
- Redundant database connections

---

## Solutions Implemented

### Fix 1: Use `flag_modified` for JSON Column Updates

**File**: `backend/app/db/risk_repo.py`

```python
from sqlalchemy.orm.attributes import flag_modified

def update_risk_limits(
    db: Session,
    *,
    max_portfolio_loss_pct: float,
    max_trades_per_day: int,
    iv_regime_limits: dict | None = None,
) -> RiskLimitConfig:
    """Persist updated risk limits and return the saved record."""
    record = get_or_create_risk_limits(db)

    record.max_portfolio_loss_pct = max_portfolio_loss_pct
    record.max_trades_per_day = max_trades_per_day
    record.iv_regime_limits = iv_regime_limits or default_iv_limits()

    # ✅ Flag the JSON column as modified
    flag_modified(record, "iv_regime_limits")

    db.add(record)
    db.commit()
    db.refresh(record)
    return record
```

**Why this works**: `flag_modified()` tells SQLAlchemy that the attribute has changed and needs to be sent to the database on commit.

### Fix 2: Pass Database Session to `get_risk_limits()`

**File**: `backend/app/core/strategies/option_spread_15m/engine.py` (line 233)

```python
# ✅ BEFORE:
# risk_config = get_risk_limits()

# ✅ AFTER: Pass the active session
risk_config = get_risk_limits(db=db)
```

**Why this works**: 
- Uses the same session that's active in the request
- Ensures consistency with current transaction state
- Avoids creating unnecessary additional sessions
- Guarantees latest committed data is loaded

---

## Verification

Test Results:

```
✅ JSON updates now persist correctly
   - Risk limit changes are saved to database

✅ Risk config loads from database
   - Strategy engine reads your custom settings
   - No longer falls back to defaults

✅ End-to-end verification
   - NORMAL regime set to 12%
   - Engine loads 12% correctly
   - PUT_RATIO_BACKSPREAD and all strategies use 12% limit
```

---

## Files Changed

| File | Change | Reason |
|------|--------|--------|
| `backend/app/db/risk_repo.py` | Added `flag_modified()` on line ~42 | Fix JSON persistence |
| `backend/app/core/strategies/option_spread_15m/engine.py` | Pass `db=db` on line 233 | Fix config loading |

---

## How to Verify the Fix Works

1. **Go to Settings in the UI** (or use API endpoint `/api/settings/risk`)

2. **Update NORMAL IV regime risk limit** to your desired value (e.g., 12%)

3. **Save the settings**

4. **Generate a strategy suggestion** for NIFTY or BANKNIFTY

5. **Verify the new limit is used**: 
   - The error message should now say `exceeds limit 12.0%` instead of `exceeds limit 2.0%`
   - PUT_RATIO_BACKSPREAD with 10.4% risk will be APPROVED
   - You won't get false rejections

---

## API Endpoints Reference

**Get current risk limits:**
```
GET /api/settings/risk
```

Response:
```json
{
  "max_portfolio_loss_pct": 13.0,
  "max_trades_per_day": 5,
  "iv_regime_limits": {
    "LOW": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 4.0},
    "NORMAL": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 12.0},
    "HIGH": {"min_atm_dist_pct": 0.8, "max_risk_pct_capital": 5.0}
  }
}
```

**Update risk limits:**
```
POST /api/settings/risk
```

---

## Database Schema

The risk limits are stored in the `risk_limits` table with this structure:

```python
class RiskLimitConfig(Base):
    __tablename__ = "risk_limits"

    id = Column(Integer, primary_key=True)
    max_portfolio_loss_pct = Column(Float)  # e.g., 3.0
    max_trades_per_day = Column(Integer)   # e.g., 3
    iv_regime_limits = Column(JSON)        # Complex nested dict
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

The IV regime limits are stored as JSON:
```json
{
  "LOW": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 4.0},
  "NORMAL": {"min_atm_dist_pct": 0.6, "max_risk_pct_capital": 12.0},
  "HIGH": {"min_atm_dist_pct": 0.8, "max_risk_pct_capital": 5.0}
}
```

---

## Related Code Paths

When you generate strategy suggestions:

1. **API receives request** → `/api/suggestions` (suggestions.py)
2. **Engine runs** → `run_option_spread()` (engine.py)
3. **Risk config loads** → `get_risk_limits(db=db)` ← **FIXED**
4. **Strategy checked** → `check_ratio_backspread_risk()` (risk.py)
5. **Limits applied** → Uses your 12% limit ✅

---

## Testing

Run included tests to verify:

```bash
# Test 1: JSON persistence fix
python test_json_flag_modified.py

# Test 2: Complete end-to-end fix
python test_complete_risk_fix.py
```

---

## Issue Resolution Status

✅ **RESOLVED** - Both database persistence and configuration loading are now fixed.

Your updated risk limits will now be applied to all strategy checks immediately.
