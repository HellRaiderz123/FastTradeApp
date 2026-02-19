# Zerodha Direct Positions - Duplicate & Stale Values Fix

## Issue Identified

When viewing positions, users saw the **same positions displayed twice** with **different P&L values**:

### Example from Screenshots:
**Zerodha Live Positions Widget** (Correct) ✅
```
NIFTY26FEB25650PE: ₹786.50 (Q: -65)
NIFTY26FEB25450PE: ₹-328.25 (Q: 65)
Total: ₹458.25
```

**Open Positions Section** (Wrong) ❌
```
NIFTY26FEB25650PE: ₹12.1 (same symbol, different P&L)
NIFTY26FEB25450PE: ₹-4.95 (same symbol, different P&L)
```

**Journal** (Wrong) ❌
```
Same positions showing stale values
```

## Root Cause

1. **Zerodha positions were being synced** from the Zerodha API as ZERODHA_LIVE_DIRECT entries
2. **Both the ZerodhaPositionsWidget AND the Open Positions section** displayed these same positions
3. **ZerodhaPositionsWidget** gets fresh data directly from Zerodha API (correct)
4. **Open Positions** got stale synced journal entries with old P&L values (incorrect)
5. **Journal** had improper deduplication logic that didn't prioritize ZERODHA_LIVE over ZERODHA_LIVE_DIRECT

## Root Causes Analysis

### Why Values Were Different:
- ZerodhaPositionsWidget: Updates every 30 seconds from Zerodha REST API → Fresh rates → Accurate P&L
- Open Positions: Gets WebSocket updates (if initialized) from synced entries → Slower initialization → Stale values
- Journal: Kept whichever entry was most recent (could be the stale direct sync instead of the live app entry)

### Why Duplicates Appeared:
- Positions executed via app (ZERODHA_LIVE) were synced again from Zerodha API (creating ZERODHA_LIVE_DIRECT)
- Same position now existed in two forms
- Both were shown separately in Open Positions

## Fixes Applied

### Fix 1: Exclude ZERODHA_LIVE_DIRECT from Open Positions Page
**File:** `web/src/pages/Positions.tsx` (Line 123-131)

**Changed:**
```typescript
// OLD: Showed all EXECUTED positions including ZERODHA_LIVE_DIRECT
const openPositions = displayTrades.filter((t) => t?.status === 'EXECUTED');
```

**To:**
```typescript
// NEW: Exclude Zerodha direct positions (already shown in ZerodhaPositionsWidget)
const openPositions = displayTrades.filter((t) => {
  if (t?.status !== 'EXECUTED') return false;
  const mode = typeof t.execution_result === 'object' ? t.execution_result?.mode : null;
  return mode !== 'ZERODHA_LIVE_DIRECT';
});
```

**Result:**
- Open Positions section now only shows app-managed positions (PAPER, ZERODHA_DRY_RUN, ZERODHA_LIVE)
- Avoids duplication with ZerodhaPositionsWidget
- Shows positions with correct WebSocket-updated P&L values

### Fix 2: Prefer ZERODHA_LIVE Over ZERODHA_LIVE_DIRECT in Journal
**File:** `web/src/pages/Journal.tsx` (Line 68-99)

**Changed Deduplication Logic:**

**Old Logic:**
```typescript
// Kept whichever was most recent by created_at (could pick the wrong one)
if (!existing || new Date(entry.created_at) > new Date(existing.created_at)) {
  zerodhaLiveMap.set(key, entry);
}
```

**New Logic:**
```typescript
if (!existing) {
  zerodhaLiveMap.set(key, entry);
} else {
  // Prefer ZERODHA_LIVE (app-executed) over ZERODHA_LIVE_DIRECT (synced)
  const existingIsLiveDirect = existing.execution_mode?.includes('ZERODHA_LIVE_DIRECT');
  const currentIsLiveDirect = entry.execution_mode?.includes('ZERODHA_LIVE_DIRECT');
  
  if (currentIsLiveDirect && !existingIsLiveDirect) {
    // Keep existing (app-executed) over direct
    return;
  } else if (!currentIsLiveDirect && existingIsLiveDirect) {
    // Replace with app-executed (current)
    zerodhaLiveMap.set(key, entry);
  } else {
    // Both same type: keep most recent
    if (new Date(entry.created_at) > new Date(existing.created_at)) {
      zerodhaLiveMap.set(key, entry);
    }
  }
}
```

**Result:**
- Journal shows ZERODHA_LIVE entries (which have correct WebSocket updates)
- Avoids showing stale ZERODHA_LIVE_DIRECT synced values
- For the same strategy/underlying, app-executed position is preferred
- Correct P&L values displayed in Journal

## Intended Behavior After Fix

### Position Widget Layout:
```
┌─────────────────────────────────────────────┐
│ Zerodha Live Positions (Widget)             │ ← Fresh from Zerodha API
│ NIFTY26FEB25650PE: ₹786.50 ✅              │
│ NIFTY26FEB25450PE: ₹-328.25 ✅             │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Open Positions (App-Managed)                │ ← Only app-executed, correct P&L
│ [ZERODHA_LIVE and PAPER positions only]     │
│ (No ZERODHA_LIVE_DIRECT duplicates)         │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Journal (Trade History)                     │ ← Shows correct entries
│ Duplicates resolved: ZERODHA_LIVE preferred │
└─────────────────────────────────────────────┘
```

## Testing

### Verify Fix Works:

1. **Open Positions Page:**
   - Should NOT show duplicate Zerodha positions
   - Open Positions count should be lower
   - P&L values should match the ZerodhaPositionsWidget
   - Positions update every 1-2 seconds via WebSocket

2. **Journal Page:**
   - Same positions should appear only once
   - Should show ZERODHA_LIVE entries with correct P&L
   - Should NOT show stale ZERODHA_LIVE_DIRECT duplicates

3. **Try This Scenario:**
   - Execute a position via Strategy Manager
   - Check Open Positions: should show correct live P&L
   - Check Journal: should show as ZERODHA_LIVE with correct P&L
   - Check ZerodhaPositionsWidget: values should match Journal
   - All three should show the same P&L ✅

## Files Modified

1. **web/src/pages/Positions.tsx**
   - Line 123-131: Filter out ZERODHA_LIVE_DIRECT from openPositions
   
2. **web/src/pages/Journal.tsx**
   - Line 68-99: Improved deduplication logic to prefer ZERODHA_LIVE over ZERODHA_LIVE_DIRECT

## Impact

✅ **Eliminates visual duplication** of the same position in different sections  
✅ **Shows accurate P&L values** across all views  
✅ **Preferred entries are maintained** (app-executed over synced)  
✅ **Cleaner UI** with no confusing duplicate entries  
✅ **Consistent data** across Positions, Journal, and Zerodha Live Positions Widget  

## Edge Cases Handled

1. **Only ZERODHA_LIVE_DIRECT exists:** Shows in Zerodha Live Positions Widget only (correct)
2. **Both ZERODHA_LIVE and ZERODHA_LIVE_DIRECT exist:** Journal shows ZERODHA_LIVE (correct P&L)
3. **Multiple positions with same strategy/underlying:** Keeps only the most recent by created_at
4. **Paper and ZERODHA_DRY_RUN positions:** Unaffected, show in Open Positions normally

## Related Components

- **ZerodhaPositionsWidget:** `web/src/components/ZerodhaPositionsWidget.tsx` (displays Zerodha positions)
- **Positions Page:** `web/src/pages/Positions.tsx` (displays app-managed positions)
- **Journal Page:** `web/src/pages/Journal.tsx` (shows all trades with deduplication)
- **WebSocket Handler:** `backend/app/api/routes/ws_positions.py` (now includes ZERODHA_LIVE updates)
- **Position Sync:** `backend/app/api/routes/journal.py` (syncs Zerodha positions as ZERODHA_LIVE_DIRECT)
