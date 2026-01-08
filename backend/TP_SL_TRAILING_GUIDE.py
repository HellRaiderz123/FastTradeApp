"""
TP/SL AND TRAILING STOP IMPLEMENTATION GUIDE
=============================================

CURRENT STATUS:
✅ TP/SL are calculated dynamically in intent.py
✅ TP/SL are stored in ExecutionIntent database
✅ TP/SL are displayed in UI (Positions page)
✅ auto_exit.py monitors and exits on TP/SL hit
❌ NO AUTOMATIC BACKGROUND MONITORING (manual API call only)
❌ NO TRAILING STOP IMPLEMENTATION
❌ NO ZERODHA GTT (Good-Till-Triggered) ORDER PLACEMENT

CRITICAL GAPS FOR PRODUCTION:
==============================

1. AUTO-EXIT IS MANUAL ONLY
----------------------------
Currently, TP/SL monitoring requires calling POST /api/exit/auto manually.
There is NO background scheduler running auto_exit().

Solution: Add auto_exit job to scheduler.py

2. TRAILING STOPS NOT IMPLEMENTED
----------------------------------
Code exists for trailing stops in backtesting (options_engine.py) but NOT in live trading.

For live trading, we need to track:
- max_unrealized_pnl (highest P&L reached)
- trailing_sl_percentage (e.g., if profit drops 50% from peak, exit)

3. ZERODHA DOES NOT SUPPORT TRAILING STOPS
-------------------------------------------
Zerodha's API limitations:
- No native trailing stop orders
- GTT (Good-Till-Triggered) supports only:
  * Single trigger (above/below price)
  * OCO (One-Cancels-Other) orders
  * NOT dynamic trailing

Solution for Zerodha live trading:
- Use GTT for static TP/SL (set once, forget)
- Implement manual trailing in our monitoring loop
- Poll every 5-10 seconds, adjust SL if profit increases

RECOMMENDED IMPLEMENTATION:
===========================

PHASE 1: Basic Auto-Exit (Immediate)
-------------------------------------
1. Add auto_exit to scheduler (every 10 seconds during market hours)
2. This handles static TP/SL automatically
3. Works for PAPER, ZERODHA_DRY_RUN, ZERODHA_LIVE

PHASE 2: Zerodha GTT Orders (Medium Priority)
----------------------------------------------
1. When executing in ZERODHA_LIVE:
   - Place orders
   - Create GTT triggers for TP/SL
   - GTT will auto-exit even if our server is down
2. Benefits:
   - Broker-side protection
   - No dependency on our monitoring
   - Market hours only concern

PHASE 3: Trailing Stops (Advanced)
-----------------------------------
1. Add max_unrealized_pnl to ExecutionIntent
2. In auto_exit loop:
   - Track highest P&L
   - If current P&L drops by X% from peak, exit
3. For Zerodha:
   - Cannot use GTT (not supported)
   - Must monitor continuously
   - Adjust SL dynamically via our code

ZERODHA GTT API EXAMPLE:
========================

# Place GTT order for TP
kite.place_gtt(
    trigger_type=kite.GTT_TYPE_SINGLE,
    tradingsymbol="NIFTY2501625900PE",
    exchange="NFO",
    trigger_values=[tp_price],  # Exit when price hits this
    last_price=current_ltp,
    orders=[{
        "transaction_type": "BUY",  # Close SELL position
        "quantity": 50,
        "product": "NRML",
        "order_type": "MARKET",
        "price": 0,
    }]
)

# Place GTT order for SL (similar)

TRAILING STOP LOGIC:
====================

max_pnl = getattr(intent, 'max_unrealized_pnl', 0) or 0
current_pnl = intent.pnl

# Update max if we hit new high
if current_pnl > max_pnl:
    intent.max_unrealized_pnl = current_pnl
    max_pnl = current_pnl

# Check trailing stop (e.g., 50% retracement from peak)
trailing_pct = 50.0  # User configurable
if max_pnl > 0:  # Only trail if in profit
    trailing_threshold = max_pnl * (trailing_pct / 100)
    if current_pnl < trailing_threshold:
        # Exit on trailing stop
        reason = "TRAILING_SL_HIT"
        executor.exit(intent)

IMPLEMENTATION FILES:
=====================
1. scheduler.py - Add start_auto_exit_scheduler()
2. auto_exit.py - Add trailing stop logic
3. models_intent.py - Add max_unrealized_pnl column
4. zerodha.py - Add place_gtt_orders() method (optional)
5. intent.py - Add trailing_sl_pct parameter

TESTING PLAN:
=============
1. Test static TP/SL with scheduler (PAPER mode)
2. Test Zerodha GTT placement (DRY_RUN mode)
3. Test trailing stop with simulated profit (PAPER mode)
4. Test full flow in ZERODHA_LIVE (small position)
"""
print(__doc__)
