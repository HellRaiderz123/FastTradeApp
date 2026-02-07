# Production Trading Enhancements - Required for Real Trading

## Current Status
✅ Paper trading implemented
✅ Basic risk checks
✅ Strategy suggestions (3 strategies: Bull Put, Bear Call, Iron Condor)
⚠️ Missing critical production features

---

## 🚨 CRITICAL: Must-Have Before Live Trading

### 1. Position Monitoring & Alerts
**Status**: ⚠️ Partial (alerts exist but not real-time position monitoring)
**Priority**: HIGH

```python
# Required Features:
- Real-time position P&L tracking
- Price-based alerts (stop-loss, take-profit)
- Time-based alerts (approaching expiry, time decay warnings)
- Margin utilization alerts
- Position Greek monitoring (delta, theta decay)
- MTM (Mark-to-Market) updates every minute
```

**Implementation Needed**:
- WebSocket for live position updates
- Background worker for alert evaluation
- SMS/Email/Push notifications for critical alerts
- Position dashboard with live Greeks

---

### 2. Risk Management Enhancements
**Status**: ⚠️ Basic checks only
**Priority**: CRITICAL

#### Daily Loss Limits
```python
# Required:
- Max daily loss limit (e.g., 2% of capital)
- Max per-strategy loss
- Circuit breaker: auto-disable all strategies if daily loss exceeds threshold
- Cooling period after max loss
```

#### Position Limits
```python
# Required:
- Max positions per underlying (e.g., max 3 NIFTY positions)
- Max total positions across portfolio (e.g., max 10 open positions)
- Max capital allocation per strategy (e.g., 20% per strategy)
- Concentration limits (max 50% in one underlying)
```

#### Drawdown Management
```python
# Required:
- Track peak capital and current drawdown %
- Auto-reduce position sizes after drawdown exceeds threshold
- Pause trading if drawdown > 10%
```

**Implementation Path**:
```
backend/app/core/risk/
├── daily_limits.py           # NEW: Daily loss tracking
├── position_limits.py         # NEW: Portfolio-level limits
├── drawdown_tracker.py        # NEW: Drawdown monitoring
└── circuit_breaker.py         # NEW: Emergency stop system
```

---

### 3. Slippage & Commission Tracking
**Status**: ❌ Not implemented
**Priority**: HIGH

```python
# Zerodha Charges (as of 2024):
CHARGES = {
    "brokerage_per_order": 20,          # ₹20 per executed order (Flat fee)
    "stt_on_sell": 0.0625,              # 0.0625% on sell side (options)
    "transaction_charges": 0.05,         # 0.05% of turnover
    "gst": 0.18,                         # 18% on (brokerage + transaction charges)
    "sebi_charges": 0.0001,              # ₹10 per crore
    "stamp_duty": 0.003,                 # 0.003% on buy side
}

# Slippage Model:
- Market orders: 0.1% - 0.3% slippage
- Limit orders: 0% slippage but fill rate < 100%
- High volatility: increase slippage by 2x
- Near expiry: increase slippage by 1.5x
```

**Required Fields in Trade Record**:
```python
class TradeExecution:
    entry_price_expected: float
    entry_price_actual: float
    slippage_amount: float
    slippage_percent: float
    brokerage: float
    stt: float
    transaction_charges: float
    gst: float
    stamp_duty: float
    total_charges: float
    net_pnl_after_charges: float
```

---

### 4. Order Execution Improvements
**Status**: ⚠️ Basic execution only
**Priority**: HIGH

#### Order Types Support
```python
# Currently: Only MARKET orders
# Required:
- LIMIT orders with price
- STOP_LOSS orders (SL)
- STOP_LOSS_MARKET orders (SL-M)
- BRACKET orders (BO) - entry + SL + target in one
- COVER orders (CO) - market + compulsory SL
```

#### Smart Order Routing
```python
# Required:
- Try LIMIT order first (0.05% better than LTP)
- If not filled in 30 seconds, convert to MARKET
- For spreads: ensure both legs fill (leg risk management)
- Retry logic with exponential backoff
```

#### Order Status Tracking
```python
# Required:
- Poll order status every 2 seconds
- Handle partial fills
- Handle rejected orders
- Handle GTC (Good Till Cancelled) orders
- Handle GTD (Good Till Day) orders
```

---

### 5. Market Hours & Trading Windows
**Status**: ⚠️ Basic time checks
**Priority**: MEDIUM

```python
# NSE Hours:
MARKET_HOURS = {
    "pre_market": ("09:00", "09:15"),   # Pre-open session
    "regular": ("09:15", "15:30"),       # Regular trading
    "post_market": ("15:40", "16:00"),   # Closing session (equity only)
}

# Required Validations:
- Block orders outside market hours
- Pre-expiry day: warn if positions held overnight
- Weekly expiry: block new entries after 3:00 PM on expiry day
- Market holidays: fetch from NSE calendar API
- Trading halt detection (circuit breaker triggered)
```

---

### 6. Margin & Capital Management
**Status**: ⚠️ Basic calculation
**Priority**: HIGH

```python
# Required:
- Real-time margin calculation using Zerodha API
- SPAN + Exposure margins for options
- Margin benefit for hedged positions (spreads)
- Available margin vs used margin tracking
- Margin call alerts (if margin utilization > 80%)
- Auto-square-off prevention (maintain 30% buffer)
```

**Zerodha Margin Requirements**:
```python
# Example for NIFTY Bull Put Spread:
# Sell 24000 PE, Buy 23900 PE (100-point spread, 1 lot = 50 qty)
MARGIN_CALCULATION = {
    "naked_short_put_margin": 120000,  # Without hedge
    "spread_margin": 5000,              # With hedge (SPAN benefit)
    "margin_benefit": 115000,           # 96% reduction!
}
```

---

### 7. Strategy-Specific Enhancements

#### New Strategy Types to Add:

##### A. High IV Strategies (Sell Premium)
```python
1. SHORT_STRADDLE
   - Sell ATM Call + ATM Put
   - Use when: High IV + Range-bound market
   - Risk: Unlimited both sides
   - Margin: 2x single leg

2. SHORT_STRANGLE  
   - Sell OTM Call + OTM Put
   - Use when: High IV + Stable market
   - Risk: Unlimited both sides
   - Margin: ~1.8x single leg
```

##### B. Low IV Strategies (Buy Premium)
```python
3. LONG_STRADDLE
   - Buy ATM Call + ATM Put
   - Use when: Low IV + Expecting big move
   - Max Loss: Total premium paid
   - Margin: Zero (debit spread)

4. LONG_STRANGLE
   - Buy OTM Call + OTM Put  
   - Use when: Low IV + Expecting volatility spike
   - Max Loss: Total premium paid
   - Margin: Zero (debit spread)
```

##### C. Advanced Strategies
```python
5. BUTTERFLY_SPREAD (Call or Put)
   - Buy 1 ITM, Sell 2 ATM, Buy 1 OTM
   - Use when: Neutral market, expect low volatility
   - Max Risk: Net debit paid
   - Max Profit: (Middle strike - Lower strike) - Net debit

6. CALL_RATIO_BACKSPREAD
   - Sell 1 ITM Call, Buy 2 OTM Calls
   - Use when: Strongly bullish + expecting breakout
   - Max Loss: Limited (between strikes)
   - Max Profit: Unlimited upside

7. PUT_RATIO_BACKSPREAD
   - Sell 1 ITM Put, Buy 2 OTM Puts
   - Use when: Strongly bearish + expecting crash
   - Max Loss: Limited (between strikes)
   - Max Profit: Unlimited downside
```

---

### 8. Portfolio-Level Features
**Status**: ❌ Not implemented
**Priority**: MEDIUM

```python
# Required:
- Greeks aggregation across all positions
- Portfolio delta hedging (maintain delta-neutral)
- Correlation analysis (avoid over-concentration)
- Daily P&L tracking per strategy type
- Capital allocation optimizer
- Performance attribution (which strategy earned what)
```

---

### 9. Backtesting Enhancements
**Status**: ⚠️ Basic backtest exists
**Priority**: MEDIUM

```python
# Required Improvements:
- Include slippage in backtest results
- Include all commissions/charges
- Test with actual historical option prices (not Black-Scholes)
- Walk-forward optimization
- Monte Carlo simulation for strategy stress testing
- Max drawdown analysis
- Sharpe ratio, Sortino ratio calculations
```

---

### 10. Error Handling & Recovery
**Status**: ⚠️ Basic error handling
**Priority**: HIGH

```python
# Required:
- Order rejection handling (insufficient margin, RMS rejection)
- Network failure recovery (retry with backoff)
- Zerodha API rate limit handling (3 req/sec limit)
- Database connection loss recovery
- Graceful degradation (if market data fails, use cached LTP)
- Manual intervention UI (admin can force-close positions)
```

---

## Implementation Priority Matrix

### Phase 1: CRITICAL (Before any live trading)
1. ✅ Slippage & Commission tracking
2. ✅ Daily loss limits + circuit breaker
3. ✅ Real-time position monitoring
4. ✅ Order rejection handling
5. ✅ Market hours validation

### Phase 2: HIGH (First week of live trading)
1. ✅ Position limits (portfolio-level)
2. ✅ Margin monitoring + alerts
3. ✅ More strategy types (Straddle, Strangle)
4. ✅ Smart order routing (LIMIT → MARKET)
5. ✅ Drawdown tracking

### Phase 3: MEDIUM (First month)
1. ⚠️ Portfolio Greeks aggregation
2. ⚠️ Performance attribution
3. ⚠️ Advanced strategies (Butterfly, Ratio spreads)
4. ⚠️ Backtest with historical option prices
5. ⚠️ SMS/Email notifications

---

## Testing Checklist Before Live Trading

### Paper Trading Phase (Min 2 weeks)
- [ ] Run 100+ paper trades across all strategies
- [ ] Test all error scenarios (order rejection, network failure)
- [ ] Verify margin calculations match Zerodha's actual margins
- [ ] Test during high volatility days (VIX > 20)
- [ ] Test near expiry (last 2 hours of weekly expiry)
- [ ] Test circuit breaker triggers
- [ ] Test daily loss limit enforcement

### Small Capital Phase (₹50,000 for 1 month)
- [ ] Max 1 lot per trade
- [ ] Max 2 concurrent positions
- [ ] Daily loss limit: ₹1,000
- [ ] Monitor slippage vs paper trading
- [ ] Monitor actual commissions
- [ ] Track execution delays

### Scale-Up Phase (After 1 month + positive P&L)
- [ ] Increase to full capital gradually (10% per week)
- [ ] Increase position sizes gradually
- [ ] Review and tighten risk limits based on observed volatility

---

## Recommended Risk Parameters for Live Trading

```python
# Conservative Mode (Recommended for first 3 months):
RISK_PARAMS = {
    "max_daily_loss_pct": 1.0,           # 1% of capital
    "max_position_size_pct": 10,          # 10% per position
    "max_positions": 5,                    # Max 5 open positions
    "min_margin_buffer": 40,               # Keep 40% margin free
    "max_capital_deployed": 60,            # Use only 60% of capital
    "stop_loss_pct": 50,                   # 50% of credit received
    "profit_target_pct": 40,               # 40% of max profit
    "time_stop": "14:30",                  # Close all before 2:30 PM on expiry
}

# After 3 months with consistent profit:
RISK_PARAMS_AGGRESSIVE = {
    "max_daily_loss_pct": 2.0,
    "max_position_size_pct": 20,
    "max_positions": 10,
    "min_margin_buffer": 30,
    "max_capital_deployed": 80,
}
```

---

## Monitoring Dashboard (Real-Time Requirements)

### Must-Have Widgets:
1. **Today's P&L** (with % of capital)
2. **Open Positions** (with live Greeks and P&L)
3. **Margin Utilization** (% used vs available)
4. **Stop-Loss Status** (how close are we to SL?)
5. **Alerts Panel** (urgent: red, warning: yellow)
6. **Daily Loss Tracker** (% used of daily limit)
7. **Position Greeks** (portfolio delta, theta, vega)
8. **Last Trade Execution Status** (success/fail)

---

## Next Steps

1. **Immediate**: Implement slippage + commission tracking
2. **This Week**: Add daily loss limits + circuit breaker
3. **This Month**: Add 4 new strategy types (Straddle, Strangle, Butterfly, Ratio Spreads)
4. **Before Live**: Complete all Phase 1 items
5. **Paper Trading**: Run for minimum 2 weeks with full feature set

---

## Tools & Libraries to Consider

```python
# For Production:
- Celery: Background task queue (for alerts, monitoring)
- Redis: Caching market data, rate limiting
- Prometheus + Grafana: Metrics and monitoring
- Sentry: Error tracking and alerting
- Twilio: SMS alerts
- Firebase: Push notifications for mobile app
```

---

## Contact & Support During Live Trading

**Zerodha Support**:
- Trading Issues: 080-47181888
- Technical Support: support@zerodha.com
- Critical Issues: Use "Connect" app for instant support

**Market Data Issues**:
- NSE Status: https://www.nseindia.com/
- BSE Status: https://www.bseindia.com/

---

**REMEMBER**: Start small, test extensively, and scale gradually. Never risk more than you can afford to lose.
