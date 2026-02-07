# 🚀 NEXT STEPS - Strategy & Terminal Roadmap

**Date:** February 8, 2026  
**Current Status:** ✅ 10 Strategies Implemented | ⚠️ Terminal Hardcoded to NIFTY50  
**Priority:** Fix Terminal → Add Strategy Features → Production Trading

---

## 🎯 IMMEDIATE PRIORITY (This Week)

### **1. Fix Terminal Universe Selection** 🚨 CRITICAL
**Problem:** Terminal is hardcoded to NIFTY50, can't switch to BANKNIFTY/FINNIFTY/NIFTY_IT  
**Impact:** Users can't analyze other universes despite backend support

#### What Needs to Be Done:
```typescript
// Add Universe Selector to TerminalBloomberg
<UniverseSelector 
  current="NIFTY50"
  options={["NIFTY50", "BANKNIFTY", "FINNIFTY", "NIFTY_IT"]}
  onChange={(universe) => setUniverse(universe)}
/>

// Pass universe to all API calls
const movers = await marketDashboardAPI.getTopMovers(5, universe);
const sectorData = await marketDashboardAPI.getSectorPerformance(universe);
const opportunities = await swingScannerAPI.scan('all', 60, universe);
```

**Files to Modify:**
- `web/src/pages/TerminalBloomberg.tsx` - Add universe state + selector
- `web/src/api/marketDashboard.ts` - Add universe parameter to all APIs
- `web/src/api/swingScanner.ts` - Add universe parameter

**Estimated Time:** 2-3 hours

---

## 📊 STRATEGY ENHANCEMENTS (This Month)

### **2. Add Options Spread Visualizations** 📈 HIGH
Currently strategies show text-only tickets. Add visual payoff diagrams.

#### Implementation:
```typescript
// Create PayoffChart component
<PayoffChart 
  strategy={strategy}
  legs={ticket.legs}
  underlying={ticket.underlying}
  spot={currentPrice}
/>
```

**Features:**
- Show P&L curve at expiry
- Breakeven points highlighted
- Greeks curve (delta, theta, vega)
- Max profit/loss zones colored
- Current price marker

**Files to Create:**
- `web/src/components/StrategyManager/PayoffChart.tsx`
- `backend/app/api/routes/payoff.py` - Calculate payoff curves

**Estimated Time:** 1 day

---

### **3. Add Real-Time Strategy P&L Tracking** 💰 HIGH
Track open positions with live P&L updates.

#### Features:
- **Position Dashboard:**
  - Open strategies with live greeks
  - Current P&L (% and ₹)
  - Time decay visualization
  - Days to expiry countdown
  
- **P&L Alerts:**
  - Notify when P&L hits ±10%, ±25%, ±50%
  - Alert on stop-loss breach
  - Alert on take-profit hit
  - Alert 1 day before expiry

- **Auto Orders (Advanced):**
  - Auto-close at profit target (e.g., 40% of max profit)
  - Auto-close at stop-loss (e.g., 50% of max loss)
  - Auto-close at expiry (EOD)

**Files to Create:**
- `backend/app/core/positions/tracker.py` - Position monitoring
- `backend/app/core/positions/alerts.py` - Alert engine
- `web/src/pages/Positions.tsx` - Positions dashboard
- `web/src/components/Positions/LiveGreeks.tsx`

**Estimated Time:** 3-4 days

---

### **4. Add Strategy Performance Analytics** 📊 MEDIUM
Track which strategies perform best over time.

#### Features:
- **Performance Dashboard:**
  - Win rate by strategy type
  - Average return by strategy
  - Best/worst trades
  - Profit factor (gross win / gross loss)
  - Sharpe ratio per strategy

- **Strategy Comparison:**
  - Bull Put vs Bear Call performance
  - Credit spreads vs Debit spreads
  - Iron Condor vs Straddles
  - Filter by underlying (NIFTY vs BANKNIFTY)
  - Filter by IV regime (low/normal/high)

- **Optimization Insights:**
  - "Iron Condor works best when VIX > 20"
  - "Bull Put spreads have 78% win rate in low IV"
  - "BANKNIFTY strategies outperform NIFTY by 12%"

**Files to Create:**
- `backend/app/api/routes/analytics.py`
- `backend/app/core/analytics/performance.py`
- `web/src/pages/Analytics.tsx`

**Estimated Time:** 2-3 days

---

### **5. Add Position Sizing Calculator** 🎯 MEDIUM
Help users determine optimal lot sizes based on risk.

#### Features:
```
Input:
- Total capital: ₹500,000
- Risk per trade: 2% (₹10,000)
- Strategy: Bull Put Spread
- Max loss per lot: ₹5,200

Output:
- Recommended lots: 1 lot
- Capital used: ₹15,000 (3%)
- Max risk: ₹5,200 (1.04%)
- Remaining capital: ₹485,000
```

**Algorithm:**
```python
def calculate_position_size(capital, risk_pct, max_loss_per_lot):
    max_risk_amount = capital * (risk_pct / 100)
    recommended_lots = max_risk_amount / max_loss_per_lot
    return floor(recommended_lots)  # Conservative rounding
```

**Files to Create:**
- `backend/app/core/risk/position_sizer.py`
- `web/src/components/StrategyManager/PositionSizer.tsx`

**Estimated Time:** 1 day

---

## 🖥️ TERMINAL SCREEN ENHANCEMENTS (Next 2 Weeks)

### **6. Add Multi-Universe Support** ✅ IMMEDIATE
**Status:** Backend ready, frontend needs update

#### Current Backend Support:
```python
MARKET_SYMBOLS = {
    "NIFTY50": [50 stocks],         # Market leaders
    "BANKNIFTY": [12 banking stocks],  # Banking sector
    "FINNIFTY": [15 financial stocks], # Financial services
    "NIFTY_IT": [9 IT stocks]        # Technology sector
}
```

#### Frontend Changes Needed:
1. **Universe Selector Component**
   - Dropdown or tabs for universe selection
   - Show stock count per universe
   - Persist selection in localStorage

2. **Update All Components:**
   - Watchlist → filter by universe
   - Market Movers → top movers in selected universe
   - Sector Performance → sectors within universe
   - Screener → filter stocks by universe
   - Swing Scanner → scan selected universe only

3. **Add Universe Stats:**
   ```
   NIFTY50:     50 stocks | Market cap: ₹X.XX Lakh Cr
   BANKNIFTY:   12 stocks | Banks only
   FINNIFTY:    15 stocks | Financial services
   NIFTY_IT:     9 stocks | Technology sector
   ```

**Files to Modify:**
- `web/src/pages/TerminalBloomberg.tsx`
- `web/src/components/Watchlist.tsx`
- `web/src/components/MarketMovers.tsx`
- `web/src/components/SectorPerformance.tsx`
- `web/src/components/Screener.tsx`
- `web/src/api/*.ts` (add universe param to all calls)

**Estimated Time:** 4-5 hours

---

### **7. Add Favorites / Custom Watchlists** ⭐ HIGH
Let users create custom watchlists beyond default universes.

#### Features:
- **Create Watchlist:**
  - Name: "My Top 10", "Momentum Plays", "Dividend Kings"
  - Add/remove stocks from any universe
  - Color-code watchlists

- **Quick Actions:**
  - Pin favorite watchlist to sidebar
  - Toggle between multiple watchlists
  - Export watchlist to CSV

- **Smart Watchlists:**
  - Auto-populate based on screener results
  - "Bullish RSI" → auto-add stocks with RSI > 70
  - "High IV" → auto-add stocks with IV Rank > 80

**Files to Create:**
- `backend/app/db/models.py` - Add Watchlist, WatchlistItem models
- `backend/app/api/routes/watchlists.py`
- `web/src/pages/Watchlists.tsx`
- `web/src/components/WatchlistManager.tsx`

**Estimated Time:** 1-2 days

---

### **8. Add Advanced Screener Presets** 🔍 MEDIUM
Currently screener has basic filters. Add powerful presets.

#### Preset Templates:
1. **Momentum Breakout**
   - Price > 20-MA and 50-MA
   - RSI > 60
   - Volume > 1.5x avg
   - ADX > 25

2. **Oversold Value**
   - RSI < 30
   - Price < -10% from 52W high
   - P/E < sector average
   - Positive earnings growth

3. **High Dividend Yield**
   - Dividend yield > 3%
   - Payout ratio < 60%
   - 5Y dividend CAGR > 10%
   - Debt/Equity < 1.0

4. **Quality Growth**
   - ROE > 18%
   - Revenue growth > 15%
   - Profit margin > 10%
   - Debt/Equity < 0.5

5. **Options Premium Selling**
   - IV Rank > 70
   - ATM option premium > 2% of stock price
   - Low beta (< 1.2)
   - Liquid options (OI > 1000)

**Files to Modify:**
- `web/src/components/Screener/PresetTemplates.tsx`
- `backend/app/api/routes/screener.py` - Add preset logic

**Estimated Time:** 1 day

---

### **9. Add Heatmap Visualizations** 🌡️ MEDIUM
Visual representation of market/sector performance.

#### Features:
1. **Market Heatmap**
   - Grid of all stocks in universe
   - Size = Market cap or volume
   - Color = % change (green/red gradient)
   - Click to open quote panel

2. **Sector Heatmap**
   - Treemap showing sector weights
   - Drill down into sector stocks
   - Compare performance across sectors

3. **Correlation Heatmap**
   - Show correlation between stocks
   - Identify high-correlation pairs for spreads
   - Find uncorrelated stocks for diversification

**Libraries:** D3.js, Recharts Treemap, or custom canvas

**Files to Create:**
- `web/src/components/Heatmap/MarketHeatmap.tsx`
- `web/src/components/Heatmap/SectorHeatmap.tsx`
- `web/src/components/Heatmap/CorrelationMatrix.tsx`

**Estimated Time:** 2-3 days

---

### **10. Add Multi-Timeframe Analysis** ⏰ MEDIUM
Show same stock across multiple timeframes simultaneously.

#### Layout:
```
┌──────────────┬──────────────┐
│   15m Chart  │   1h Chart   │
├──────────────┼──────────────┤
│   4h Chart   │   Daily Chart│
└──────────────┴──────────────┘
```

#### Features:
- **Synchronized cursor:** Hover on one chart, show on all
- **Trend alignment:** Show if trends align across timeframes
- **Multi-timeframe signals:** 
  - "Bullish on 15m, 1h, 4h, daily" = Strong buy
  - "Mixed signals" = Wait
- **Quick toggle:** Switch between 2x2 grid and single chart

**Files to Create:**
- `web/src/components/Chart/MultiTimeframeChart.tsx`
- `web/src/components/Chart/TimeframeSelector.tsx`

**Estimated Time:** 2 days

---

## 🔧 PRODUCTION TRADING FEATURES (Month 2)

### **11. Add Order Confirmation Modal** ✅ CRITICAL
Never place orders without confirmation.

#### Modal Should Show:
```
┌─────────────────────────────────────┐
│  Confirm Order: Bull Put Spread     │
├─────────────────────────────────────┤
│  Underlying: NIFTY                  │
│  Legs:                              │
│    SELL 24000 PE x 65 qty           │
│    BUY  23900 PE x 65 qty           │
│                                     │
│  Max Profit: ₹1,300 (20%)          │
│  Max Loss:   ₹5,200 (80%)          │
│  Risk/Reward: 1:4                   │
│  Margin Required: ₹15,000           │
│                                     │
│  [Cancel]  [Confirm & Execute]     │
└─────────────────────────────────────┘
```

**Safety Checks:**
- ✅ Sufficient margin available
- ✅ Within daily loss limit
- ✅ Position limit not exceeded
- ✅ Market hours (09:15-15:30)
- ✅ Not expiry day after 15:00

**Files to Create:**
- `web/src/components/Orders/OrderConfirmModal.tsx`
- `backend/app/core/execution/pre_trade_checks.py`

**Estimated Time:** 1 day

---

### **12. Add Daily Loss Limit Enforcement** 🛑 CRITICAL
Prevent catastrophic losses.

#### Features:
```python
# Set daily loss limit
DAILY_LOSS_LIMIT_PCT = 2.0  # 2% of capital

# Monitor P&L
current_daily_pnl = calculate_today_pnl()
if current_daily_pnl < -1 * (capital * 0.02):
    # CIRCUIT BREAKER TRIGGERED
    disable_all_strategies()
    close_all_positions()  # Optional
    send_alert("Daily loss limit hit!")
    block_new_orders_for(hours=24)
```

#### UI Indicators:
- **Green Zone:** P&L > 0
- **Yellow Zone:** P&L -0.5% to -1%
- **Orange Zone:** P&L -1% to -2%
- **Red Zone:** P&L < -2% (circuit breaker)

**Display:**
```
Today's P&L: -₹8,500 (-1.7%) ⚠️ APPROACHING LIMIT
Daily Loss Limit: ₹10,000 (2%)
Remaining: ₹1,500
```

**Files to Create:**
- `backend/app/core/risk/daily_limits.py`
- `backend/app/core/risk/circuit_breaker.py`
- `web/src/components/Dashboard/RiskGauge.tsx`

**Estimated Time:** 2 days

---

### **13. Add Slippage & Commission Tracking** 💸 CRITICAL
Track real costs vs expected.

#### Data to Track:
```python
class TradeExecution:
    # Entry
    expected_fill_price: 23.50
    actual_fill_price: 23.65
    slippage: 0.15 (0.64%)
    
    # Costs
    brokerage: 40  # ₹20 per leg
    stt: 39        # 0.0625% on sell
    transaction_charges: 24
    gst: 11        # 18% on brokerage
    stamp_duty: 8
    total_charges: 122
    
    # Net P&L
    gross_pnl: 1300
    net_pnl: 1178  (-9.4% due to charges)
```

#### Display in UI:
```
Trade Summary:
Gross P&L:     ₹1,300
Charges:       -₹122
Net P&L:       ₹1,178

Breakdown:
- Brokerage:   ₹40
- STT:         ₹39
- Other:       ₹43
```

**Reports:**
- Daily commission report
- Monthly commission summary
- Slippage analysis by strategy
- Best/worst execution times

**Files to Create:**
- `backend/app/core/execution/slippage_tracker.py`
- `backend/app/core/execution/commission_calculator.py`
- `web/src/pages/CostAnalysis.tsx`

**Estimated Time:** 2-3 days

---

### **14. Add Position Monitoring Dashboard** 📊 HIGH
Real-time view of all open positions.

#### Dashboard Sections:
1. **Portfolio Summary**
   - Total P&L (today, this week, all-time)
   - Win rate, avg return, Sharpe ratio
   - Open positions count
   - Available margin

2. **Open Positions Table**
   ```
   Strategy       | Entry    | Current | P&L     | Greeks    | Days to Expiry
   Bull Put 24000 | 8:30 AM  | +₹850   | +65%   | Δ +0.73   | 3 days
   Iron Condor    | 10:15 AM | -₹1200  | -25%   | Δ -0.15   | 3 days
   Bear Call      | 1:45 PM  | +₹340   | +12%   | Δ -0.42   | 10 days
   ```

3. **P&L Chart**
   - Intraday P&L curve
   - Show against NIFTY movement
   - Mark entry/exit points

4. **Greeks Aggregation**
   - Portfolio Delta: +0.16 (slightly bullish)
   - Portfolio Theta: -₹1,250/day (time decay)
   - Portfolio Vega: +₹850/1% IV change
   - Suggest hedging if needed

5. **Risk Metrics**
   - Current risk: ₹28,000 (5.6% of capital)
   - Margin used: ₹75,000 (15%)
   - Correlation risk: Low (0.23)

**Files to Create:**
- `web/src/pages/PositionMonitor.tsx`
- `backend/app/api/routes/positions.py`
- `backend/app/core/positions/portfolio_greeks.py`

**Estimated Time:** 3-4 days

---

## 📋 IMPLEMENTATION PRIORITY

### **Week 1 (This Week)**
✅ **Day 1-2:** Fix universe selector in Terminal (CRITICAL)  
✅ **Day 3:** Add payoff chart visualization  
✅ **Day 4-5:** Add favorites/custom watchlists

### **Week 2**
✅ **Day 1-2:** Add position monitoring dashboard  
✅ **Day 3:** Add order confirmation modal  
✅ **Day 4-5:** Add daily loss limit enforcement

### **Week 3**
✅ **Day 1-2:** Add slippage & commission tracking  
✅ **Day 3:** Add position sizing calculator  
✅ **Day 4-5:** Add strategy performance analytics

### **Week 4**
✅ **Day 1-2:** Add heatmap visualizations  
✅ **Day 3:** Add screener presets  
✅ **Day 4-5:** Add multi-timeframe analysis

---

## 🎯 SUCCESS METRICS

### Strategy Module
- [ ] All 10 strategies generating suggestions
- [ ] Payoff charts render correctly
- [ ] Position P&L updates in real-time
- [ ] Daily loss limit enforcement working
- [ ] Commission tracking accurate to ±5%

### Terminal Module
- [ ] Can switch between 4 universes seamlessly
- [ ] Watchlists support 50+ stocks
- [ ] Screener finds opportunities in < 3 seconds
- [ ] Heatmap updates every 30 seconds
- [ ] Multi-timeframe analysis loads in < 2 seconds

### Production Trading
- [ ] Zero orders placed without confirmation
- [ ] Circuit breaker triggers at 2% loss
- [ ] Position monitor shows live P&L
- [ ] Slippage tracked on 100% of trades
- [ ] Greeks aggregation accurate to ±10%

---

## 💰 ESTIMATED TIMELINE & EFFORT

| Phase | Duration | Features | Team Size |
|-------|----------|----------|-----------|
| **Terminal Fixes** | 1 week | Universe selector, watchlists, presets | 1 developer |
| **Position Monitoring** | 1 week | Dashboard, live P&L, Greeks, alerts | 1 developer |
| **Risk Management** | 1 week | Daily limits, circuit breaker, commission | 1 developer |
| **Visualizations** | 1 week | Payoff charts, heatmaps, multi-timeframe | 1 developer |
| **Analytics** | 1 week | Performance tracking, optimization insights | 1 developer |
| **Testing & UAT** | 1 week | End-to-end testing, bug fixes | Full team |

**Total:** 6 weeks for complete implementation

---

## 🔥 QUICK WINS (Do These First!)

### 1. **Universe Selector** (2 hours)
   - Add dropdown to TerminalBloomberg
   - Pass universe to all API calls
   - Persist selection in localStorage

### 2. **Order Confirmation Modal** (4 hours)
   - Show trade details before execution
   - Add safety checks
   - Prevent accidental orders

### 3. **Daily P&L Tracker** (4 hours)
   - Calculate today's P&L
   - Show in dashboard header
   - Color-coded warning zones

### 4. **Position Count Badge** (1 hour)
   - Show "5 open positions" in header
   - Click to open positions page
   - Red badge if approaching limits

### 5. **Screener Presets** (3 hours)
   - Add 5 pre-built screener templates
   - One-click to run
   - Save results to watchlist

**Total Quick Wins:** 14 hours = ~2 days

---

## 📚 RESOURCES NEEDED

### Development
- [ ] React TypeScript developer (frontend)
- [ ] Python FastAPI developer (backend)
- [ ] DevOps for deployment
- [ ] QA for testing

### Tools & Services
- [ ] TradingView Charting Library ($50-200/month)
- [ ] WebSocket infrastructure (Redis)
- [ ] SMS provider for alerts (Twilio)
- [ ] Email service (SendGrid)
- [ ] Database backup solution

### Documentation
- [ ] API documentation (Swagger)
- [ ] User guide for terminal
- [ ] Strategy guide for traders
- [ ] Risk management guide

---

## ❓ QUESTIONS TO DECIDE

1. **Should we add paper trading mode?**
   - Yes → Add mock execution engine
   - No → Go straight to live trading (with confirmations)

2. **Should we support manual trades?**
   - Yes → Add order entry form
   - No → Only algo-generated strategies

3. **Should we add social features?**
   - Yes → Share strategies with community
   - No → Keep it personal

4. **Should we add mobile app?**
   - Yes → React Native version
   - No → Web-only for now

5. **Should we support futures trading?**
   - Yes → Add futures strategies
   - No → Options only for now

---

## 🚀 LET'S START!

**Recommended First Steps (This Weekend):**

1. ✅ Fix universe selector (2 hours)
2. ✅ Add order confirmation modal (4 hours)  
3. ✅ Add daily P&L tracker (4 hours)
4. ✅ Test with BANKNIFTY universe (1 hour)

**Total:** 11 hours = 1 weekend

**After that:** Follow the week-by-week plan above.

**Questions?** Let me know which area you want to tackle first! 🎯
