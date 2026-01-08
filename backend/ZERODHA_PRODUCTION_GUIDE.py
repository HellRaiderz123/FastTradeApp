"""
===================================================================================
ZERODHA LIVE TRADING - PRODUCTION READINESS GUIDE
===================================================================================

USER CONCERNS ADDRESSED:
1. ✅ Margin display (not just premium)
2. ✅ TP/SL automatic monitoring
3. ✅ Trailing stops implementation
4. ⚠️  Zerodha GTT order placement (optional enhancement)

===================================================================================
WHAT'S NOW WORKING
===================================================================================

1. MARGIN TRACKING (✅ COMPLETE)
   - backend/app/db/models_intent.py: Added margin_required column
   - backend/app/core/execution/zerodha.py: Calls basket_order_margins() API
   - backend/app/api/routes/ws_positions.py: Sends margin in WebSocket
   - web/src/pages/Positions.tsx: Displays margin for Zerodha modes
   
   RESULT: You'll see BOTH premium AND margin (e.g., Premium: ₹3,227, Margin: ₹51,234)

2. AUTOMATIC TP/SL MONITORING (✅ COMPLETE)
   - backend/app/core/market/scheduler.py: Added auto_exit_check() job
   - Runs every 10 seconds during market hours (9:15 AM - 3:30 PM IST)
   - Monitors ALL execution modes: PAPER, ZERODHA_DRY_RUN, ZERODHA_LIVE
   - Auto-exits when TP or SL hit
   
   RESULT: Positions automatically close when targets hit (no manual intervention)

3. TRAILING STOPS (✅ COMPLETE)
   - backend/app/db/models_intent.py: Added max_unrealized_pnl column
   - backend/app/core/exit/auto_exit.py: Tracks peak profit, exits on 50% retracement
   - Example: Profit goes ₹2000 → ₹4000 (peak) → ₹2000 = Auto-exit (50% retracement)
   
   RESULT: Protects profits automatically if price reverses

===================================================================================
HOW IT WORKS IN ZERODHA LIVE TRADING
===================================================================================

STEP 1: Execute Strategy
-------------------------
POST /api/intent → Create intent with TP/SL
POST /api/execute/paper/{intent_id} → Execute trade

What happens:
1. Orders sent to Zerodha (SELL 25900 PE, BUY 25700 PE)
2. basket_order_margins() calculates margin (~₹50,000)
3. Orders placed, margin blocked by Zerodha
4. Database stores: entry_credit, margin_required, tp, sl
5. Status changes to EXECUTED

STEP 2: Automatic Monitoring (Background)
------------------------------------------
Auto-exit scheduler runs every 10 seconds:

```python
current_pnl = ₹1,500
tp = ₹2,000
sl = ₹-2,000
max_pnl = ₹1,800 (highest seen)

# Update max profit
if current_pnl > max_pnl:
    max_pnl = ₹1,500
    
# Check TP
if current_pnl >= tp:  # ₹1,500 >= ₹2,000? No
    exit("TP_HIT")
    
# Check SL
if current_pnl <= sl:  # ₹1,500 <= ₹-2,000? No
    exit("SL_HIT")
    
# Check trailing (50% retracement from peak)
if max_pnl > 0 and current_pnl < (max_pnl * 0.5):
    # Example: max was ₹3,000, now ₹1,400 → EXIT
    exit("TRAILING_SL_HIT")
```

STEP 3: Auto-Exit Execution
----------------------------
When TP/SL/Trailing hit:
1. executor.exit(intent) → Place reverse orders (BUY to close SELL, SELL to close BUY)
2. Status → CLOSED
3. Notification sent (Email/SMS if configured)
4. P&L finalized

===================================================================================
ZERODHA GTT ORDERS (OPTIONAL ENHANCEMENT - NOT YET IMPLEMENTED)
===================================================================================

PROBLEM: What if your server goes down?
- Current solution relies on our monitoring loop
- If server crashes, TP/SL won't trigger

SOLUTION: Zerodha GTT (Good-Till-Triggered) Orders
- Place TP/SL directly with Zerodha broker
- Broker monitors and exits automatically
- Works even if your server is offline

IMPLEMENTATION:
```python
# In zerodha.py execute() method, after placing orders:

# Place GTT for Take Profit
for leg in sold_legs:
    tp_price = leg["entry_price"] - (tp_amount / qty)
    kite.place_gtt(
        trigger_type=kite.GTT_TYPE_SINGLE,
        tradingsymbol=leg["symbol"],
        exchange="NFO",
        trigger_values=[tp_price],
        last_price=leg["entry_price"],
        orders=[{
            "transaction_type": "BUY",  # Close SELL position
            "quantity": leg["quantity"],
            "product": "NRML",
            "order_type": "LIMIT",
            "price": tp_price,
        }]
    )

# Similar for Stop Loss
```

LIMITATIONS:
- GTT does NOT support trailing stops (Zerodha limitation)
- GTT only works for static TP/SL
- For trailing, we MUST use our monitoring loop

===================================================================================
PRODUCTION DEPLOYMENT CHECKLIST
===================================================================================

BEFORE GOING LIVE:

1. VERIFY CREDENTIALS
   □ .env has valid ZERODHA_API_KEY, ZERODHA_API_SECRET, ZERODHA_ACCESS_TOKEN
   □ Test with: python backend/test_zerodha_creds.py
   □ Ensure sufficient margin in Zerodha account

2. TEST IN DRY-RUN MODE
   □ Set EXECUTION_MODE=ZERODHA_DRY_RUN in .env
   □ Execute a Bull Put spread
   □ Verify:
     - Premium calculated correctly
     - Margin displayed (~₹50K for NIFTY spreads)
     - TP/SL values shown
     - WebSocket updates P&L live
   □ Wait for TP/SL to trigger (or manual exit)
   □ Confirm auto-exit works

3. TEST TRAILING STOP (PAPER MODE)
   □ Execute position that goes into profit
   □ Watch max_unrealized_pnl increase
   □ Simulate price reversal
   □ Confirm exits at 50% retracement

4. VERIFY SCHEDULER IS RUNNING
   □ Check backend logs on startup:
     "🟢 Auto-exit scheduler started (every 10 seconds, market hours only)"
   □ Confirm no errors in logs
   □ Test during market hours (9:15 AM - 3:30 PM IST)

5. CONFIGURE NOTIFICATIONS
   □ Set up email/SMS in notifications.py
   □ Test TP_HIT notification
   □ Test SL_HIT notification
   □ Test TRAILING_SL_HIT notification

6. RISK MANAGEMENT SETTINGS
   □ Verify daily trade limit (default: 3 trades/day)
   □ Verify max portfolio loss (default: 5%)
   □ Adjust risk percentage per trade (default: 2%)
   □ Test kill switch activates when loss limit hit

7. SWITCH TO LIVE MODE
   □ Set EXECUTION_MODE=ZERODHA_LIVE in .env
   □ RESTART backend server (critical!)
   □ Execute small test trade (1 lot only)
   □ Monitor for 30 minutes
   □ Verify:
     - Orders placed successfully
     - Margin blocked correctly
     - TP/SL monitoring active
     - Manual exit works

8. MONITORING & LOGGING
   □ Monitor backend logs continuously
   □ Watch for "Auto-exited X position(s)" messages
   □ Check Zerodha order book matches our database
   □ Review P&L daily

===================================================================================
TROUBLESHOOTING
===================================================================================

ISSUE: "TP/SL not visible in UI"
SOLUTION: 
- Check intent.tp and intent.sl are not None in database
- Verify calculate_tp_sl_from_ticket() is called in intent.py
- Check WebSocket sends tp/sl in response

ISSUE: "Positions not auto-exiting"
SOLUTION:
- Verify scheduler is running: Check logs for "Auto-exit scheduler started"
- Confirm market hours (9:15 AM - 3:30 PM IST weekdays only)
- Check auto_exit.py logic for TP/SL thresholds
- Test manually: POST /api/exit/auto

ISSUE: "Margin not showing"
SOLUTION:
- Run migration: python migrate_add_margin_column.py
- Verify basket_order_margins() is called in zerodha.py
- Check WebSocket includes margin_required field
- Confirm UI checks isZerodhaMode before displaying

ISSUE: "Trailing stop not working"
SOLUTION:
- Run migration: python migrate_add_trailing_stop_column.py
- Verify max_unrealized_pnl is being updated in auto_exit.py
- Check retracement threshold (default: 50%)
- Position must go into profit first before trailing activates

===================================================================================
NEXT ENHANCEMENTS (FUTURE)
===================================================================================

1. Configurable trailing stop percentage (UI setting)
2. Zerodha GTT order placement (broker-side TP/SL)
3. Partial profit booking (close 50% at TP, trail remaining)
4. Multi-leg adjustment (roll strikes up/down)
5. Live Greeks monitoring (delta, theta decay)
6. Option chain analysis (OI, PCR for entry/exit signals)

===================================================================================
SUPPORT & DOCUMENTATION
===================================================================================

Files to review:
- TP_SL_TRAILING_GUIDE.py - Implementation details
- ZERODHA_SETTINGS_GUIDE.md - Zerodha configuration
- PHASE_5_QUICKSTART.md - Execution flow
- test_margin_calculation.py - Test margin API
- backend/app/core/exit/auto_exit.py - Exit logic
- backend/app/core/market/scheduler.py - Monitoring jobs

API endpoints:
- POST /api/intent - Create execution intent with TP/SL
- POST /api/execute/paper/{intent_id} - Execute trade
- POST /api/exit/auto - Manual TP/SL check (for testing)
- GET /api/exit/manual/{intent_id} - Manual position closure
- WS /api/ws/positions - Live P&L updates

===================================================================================
FINAL NOTES
===================================================================================

✅ PRODUCTION READY FOR:
- Automatic TP/SL monitoring
- Trailing stop (50% retracement)
- Margin display and tracking
- Live P&L updates
- Multi-mode execution (PAPER, DRY_RUN, LIVE)

⚠️  LIMITATIONS:
- Trailing stop requires our server running (not broker-side)
- GTT orders not yet implemented (optional enhancement)
- Retracement percentage is hardcoded (50%)

🚀 TO GO LIVE:
1. Test thoroughly in ZERODHA_DRY_RUN
2. Start with 1-lot positions
3. Monitor continuously for first week
4. Scale up gradually as confidence builds

Good luck with your trading! 🎯
"""

print(__doc__)
