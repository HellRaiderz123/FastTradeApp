# FastTradeApp → Bloomberg Terminal: NEXT STEPS ROADMAP
**Date:** February 7, 2026  
**Status:** 60-65% Complete (Up from initial 60%)  
**Scanning Date:** Today's Full Workspace Scan  
**Recommendation:** Begin Phase 1 immediately (4-5 hours)

---

## 📊 CURRENT IMPLEMENTATION STATUS

### ✅ WHAT'S BEEN IMPLEMENTED

#### **Backend APIs** (28 Route Files)
1. **Market Data APIs** ✅
   - `/market/bulk-quotes` - Multi-symbol quotes
   - `/market/candles/{symbol}` - Historical candles with timeframes
   - `/market/sector-performance` - Sector metrics
   - `/market-dashboard/top-movers` - Gainers/Losers
   - `/market-dashboard/market-breadth` - Advancing/declining stocks
   - `/market/quote/{symbol}` - Single symbol quote

2. **Advanced Features** ✅
   - `/market-depth/get-depth` - Order book (5-level)
   - `/calendar/events` - Economic calendar (earnings, RBI, IPO, dividends)
   - `/swing-scanner/scan` - Pattern-based trading scanner
   - `/sentiment/market` - Fear & Greed index
   - `/screener/*` - Stock screening with filters
   - `/options/chain` - Options chain with Greeks
   - `/news/feed` - Live news with sentiment

3. **Real-time Updates** ✅
   - WebSocket `/ws/quotes` - Real-time price updates
   - `/health` - System health monitoring
   - Live Zerodha Kite Connect integration

4. **Trading Execution** ✅
   - `/execute/*` - Paper + Live trading (Phase 1 complete)
   - `/strategies/*` - Strategy management
   - `/positions/*` - Position tracking
   - Risk management (daily capital, trailing stops)

#### **Frontend Components** (14 Page Modules)
1. **TerminalBloomberg.tsx** ✅
   - Real-time watchlist (Bloomberg-style)
   - Market breadth display
   - Top movers panel
   - Sector performance heatmap
   - Swing trading opportunities
   - News feed integration
   - Economic calendar widget

2. **Supporting Pages** ✅
   - Dashboard.tsx - Main overview
   - OptionsChain.tsx - Greeks & analysis
   - Screener.tsx - Stock filtering
   - StrategyBuilder.tsx - Custom strategies
   - Positions.tsx - Trade tracking
   - Journal.tsx - Trade journal

#### **Data Infrastructure** ✅
- Zerodha Kite Connect (live market data)
- Historical candle database
- Multi-asset models (Symbol, MarketData, AlertRule)
- Tick data pipeline
- VIX & IV tracking

---

## 🔴 CRITICAL BLOCKERS (MUST FIX THIS WEEK)

### **BLOCKER #1: Universe Locked to NIFTY50** 🚨 SEVERITY: HIGH

**Current State:**
```typescript
// TerminalBloomberg.tsx - Hardcoded
<h1 className="terminal-title text-3xl text-white">NIFTY 50 Command Center</h1>
placeholder="Search NIFTY 50 stocks (e.g., TCS, RELIANCE)"
const movers = await marketDashboardAPI.getTopMovers(5);  // No universe param
const opportunities = await swingScannerAPI.scan('all', 60);  // NIFTY50 only
```

**Impact:**
- ❌ Cannot analyze BANKNIFTY (12 banking stocks)
- ❌ Cannot analyze FINNIFTY (15 financial services stocks)
- ❌ Cannot analyze NIFTY IT separately (9 IT stocks)
- ❌ Users stuck with single view despite backend supporting multiple universes
- ❌ Contradicts Bloomberg terminal's multi-index capability

**What Backend Already Has:**
```python
# backend/app/config/market_config.py (VERIFIED)
MARKET_SYMBOLS = {
    "NIFTY50": [...50 stocks...],
    "BANKNIFTY": [HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, AXISBANK, ...12 total],
    "NIFTY_IT": [TCS, INFY, WIPRO, HCLTECH, TECHM, ...9 total]
    # FINNIFTY: MISSING - 15 stocks needed
}

class MarketUniverse(str, Enum):
    NIFTY50 = "NIFTY50"
    BANKNIFTY = "BANKNIFTY"
    # FINNIFTY = "FINNIFTY"  ← NOT DEFINED
    NIFTY_IT = "NIFTY_IT"
```

**APIs Already Support Universe Parameter:**
```python
async def get_top_movers(limit: int = 10, universe: str = "NIFTY50")
async def get_market_breadth(universe: str = "NIFTY50")
async def scan(strategy: str, min_score: int = 50, universe: str = "NIFTY50")
```

**Fix Required:** 4-5 HOURS
1. Add FINNIFTY to config (5 min)
2. Update TerminalBloomberg.tsx with universe state (30 min)
3. Add universe dropdown UI (30 min)
4. Pass universe to all API calls (1 hour)
5. Update API interfaces (30 min)
6. Test all 4 universes (1 hour)

---

### **BLOCKER #2: No Keyboard Shortcuts** 🚨 SEVERITY: HIGH

**Why This Matters:**
Bloomberg Terminals are designed for keyboard-first users. The killer feature is:
```
Type stock symbol + Enter:   "TCS" → Load TCS chart
Command mode:                "GP" → Price graph, "MOV" → Moving averages
Quick timeframe toggle:       "1" → 1m, "2" → 5m, "3" → 15m, "4" → 1h, "5" → 1d
Command palette:             Ctrl+K → Fuzzy search all stocks
```

**Current State:** Mouse-only interface (not Bloomberg-like at all)

**Fix Required:** 6-8 HOURS
- Need `cmdk` library (^0.2.0)
- Keyboard event handling
- Command shortcuts map
- Command palette UI

---

### **BLOCKER #3: No Multi-Symbol Comparison Charts** 🚨 SEVERITY: MEDIUM

**Why This Matters:**
"Compare 4 stocks side-by-side" is essential for trading analysis:
- TCS vs INFY vs Wipro vs HCLTech (IT sector peers)
- RELIANCE vs RIL Futures (basis analysis)
- See correlations visually

**Current State:** Single symbol only, no comparison capability

**Fix Required:** 4-6 HOURS
- React-Query integration for data loading
- Recharts multi-line chart
- % returns calculation & normalization

---

## 🟡 HIGH PRIORITY (DO AFTER BLOCKERS)

### **Issue #4: Poor Loading States** 🟡

Every component shows generic "Loading..." text:
```typescript
{swingOpportunities.length > 0 ? (
  // render
) : (
  <p className="text-xs text-slate-500">Loading opportunities...</p>  // ← BAD
)}
```

**Fix:** Create skeleton loaders (need: react-loading-skeleton or DIY)
**Time:** 1-2 hours

---

### **Issue #5: No Error Boundaries** 🟡

One component crash kills entire Terminal page. Need:
```typescript
<ErrorBoundary>
  <SwingScanner />
</ErrorBoundary>
```

**Time:** 1 hour (need react-error-boundary package)

---

### **Issue #6: Backend Rate Limiting Missing** 🟡

Zerodha API = 3 requests/second max. No rate limiting = API ban risk.
- Need: `slowapi` package
- Apply to all external API calls

**Time:** 2-3 hours

---

### **Issue #7: No Caching Strategy** 🟡

Every request hits Zerodha (expensive, slow):
- Historical data never changes
- Quotes can cache 1-2 seconds
- Reduce API costs by 80%

**Fix:** Redis caching
**Time:** 3-4 hours

---

## 🟢 NICE TO HAVE (NEXT WEEKS)

### **Feature List:**
1. Heat map full-screen view (6 hours)
2. Peer comparison table by sector (4 hours)
3. Custom watchlists with drag-drop (6 hours)
4. Macro dashboard (USD/INR, gold, oil, DOW, Nifty) (8 hours)
5. Correlation matrix (6 hours)
6. Custom screener presets (4 hours)
7. Options OI analysis & max pain (6 hours)
8. Historical returns table (2 hours)
9. Corporate actions timeline (4 hours)
10. Earnings calendar with beat/miss tracking (6 hours)

---

## 📋 RECOMMENDED IMPLEMENTATION ROADMAP

### **PHASE 1: FIX CRITICAL BLOCKERS (Week 1 - 15-20 HOURS)**
**Goal:** Transform hardcoded NIFTY50-only terminal into flexible multi-universe platform

#### Week 1, Days 1-2 (8 hours):
1. Add FINNIFTY to backend ✅ (30 min)
2. Add universe state to TerminalBloomberg ✅ (30 min)
3. Create universe dropdown UI ✅ (1 hour)
4. Update all API calls for universe param ✅ (2-3 hours)
5. Test all 4 universes working ✅ (1 hour)
6. Add loading skeletons (1 hour)
7. Add error boundaries (1 hour)

**Expected Outcome:**
```
Before:
- Terminal hardcoded to NIFTY50
- Can't see BANKNIFTY stocks (HDFC Bank, ICICI, SBI)
- Can't compare with FIN NIFTY

After:
- Dropdown with all 4 universes
- Data updates when universe changes
- Can analyze any index independently
```

#### Week 1, Days 3-4 (4 hours):
8. Implement basic keyboard shortcuts (2 hours)
   - `Symbol + Enter` to load stock
   - `1-5` for timeframes
   - `Esc` to clear
   - `Ctrl+K` for command palette

9. Build command palette UI (2 hours)
   - Fuzzy search all symbols
   - Recent stocks history
   - Quick actions

**Expected Outcome:** Users can trade like pro Bloomberg operators

#### Week 1, Day 5 (4 hours):
10. Multi-symbol comparison chart (Basic version - 4 hours)
    - Add 2-4 symbols side-by-side
    - Normalized % returns
    - Volume comparison

**Expected Outcome:** Can compare RELIANCE vs TCS vs INFY in one view

---

### **PHASE 2: ADVANCED FEATURES (Week 2 - 20-25 HOURS)**

#### Week 2, Days 1-2 (8 hours):
11. Alert System (Backend + Frontend)
    - Price crosses threshold
    - RSI overbought/oversold
    - Volume spike
    - MACD crossover
    - Notifications (browser + email)

#### Week 2, Days 3-5 (12 hours):
12. Performance Optimizations
    - Redis caching (4 hours)
    - Rate limiting with slowapi (3 hours)
    - React Query integration (5 hours)

#### Week 2, Days 5+ (5 hours):
13. Heat Map & Peer Comparison
    - Full-screen treemap
    - Sector drill-down
    - Peer metrics table

---

### **PHASE 3: POLISH (Week 3-4 - 20-30 HOURS)**

14. Mobile responsive design
15. Custom watchlists (persistent)
16. Macro indicators dashboard
17. Correlation matrix
18. Advanced screener presets
19. Portfolio integration
20. Dark/Light theme toggle

---

## 🎯 IMMEDIATE ACTION PLAN (START TODAY)

### **Step 1: Add FINNIFTY** (5 minutes)
File: `backend/app/config/market_config.py`

Add after NIFTY_IT definition:
```python
"FINNIFTY": [
    "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
    "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "ICICIGI",
    "BAJAJHLDNG", "PFC", "RECLTD", "MUTHOOTFIN", "CHOLAFIN"
]

# In MarketUniverse enum:
FINNIFTY = "FINNIFTY"
```

### **Step 2: Create Universe State** (15 minutes)
File: `web/src/pages/TerminalBloomberg.tsx`

Around line 30, add:
```typescript
const [universe, setUniverse] = useState<string>('NIFTY50');
```

### **Step 3: Add Dropdown UI** (30 minutes)
Replace the hardcoded h1 title with:
```typescript
<div className="flex items-center gap-4">
  <h1 className="terminal-title text-3xl text-white">
    {universe === 'NIFTY50' ? 'NIFTY 50' : 
     universe === 'BANKNIFTY' ? 'BANK NIFTY' : 
     universe === 'FINNIFTY' ? 'FIN NIFTY' : 'NIFTY IT'} Command Center
  </h1>
  
  <select 
    value={universe}
    onChange={(e) => setUniverse(e.target.value)}
    className="bg-slate-900/80 border border-slate-700/50 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-emerald-400/50"
  >
    <option value="NIFTY50">NIFTY 50 (50 stocks)</option>
    <option value="BANKNIFTY">BANK NIFTY (12 stocks)</option>
    <option value="FINNIFTY">FIN NIFTY (15 stocks)</option>
    <option value="NIFTY_IT">NIFTY IT (9 stocks)</option>
  </select>
</div>
```

### **Step 4: Update API Calls** (1 hour)
Search for all API calls in TerminalBloomberg.tsx:
- Change `getTopMovers(5)` → `getTopMovers(5, universe)`
- Change `getMarketBreadth()` → `getMarketBreadth(universe)`
- Change `swingScannerAPI.scan()` → `swingScannerAPI.scan(..., universe)`

Update useEffect dependency:
```typescript
useEffect(() => {
  fetchMarketData();
}, [universe]);  // ← Add universe
```

### **Step 5: Install Missing Packages** (2 minutes)
```bash
npm install @tanstack/react-query cmdk react-error-boundary recharts
```

Backend:
```bash
pip install slowapi redis httpx
```

---

## 📊 CURRENT FEATURE COMPLETION CHECKLIST

### **Core Features** ✅ 90%
- ✅ Real-time watchlist with WebSocket
- ✅ Top movers (gainers/losers)
- ✅ Market breadth
- ✅ Sector performance heatmap
- ✅ Market sentiment (VIX, Fear & Greed)
- ✅ Advanced charting (TradingView-style)
- ✅ Technical indicators (RSI, MACD, Bollinger, ADX, ATR)
- ✅ Pattern recognition (swing scanner)
- ✅ News feed + sentiment analysis
- ✅ Economic calendar (earnings, RBI, IPO)
- ✅ Market depth/order book
- ✅ Stock screener with filters
- ✅ Options chain with Greeks
- ✅ Paper & live trading execution

### **Bloomberg Parity Features** 🟡 35%
- ❌ Multi-universe support (BLOCKER #1)
- ❌ Keyboard shortcuts (BLOCKER #2)
- ❌ Multi-symbol comparison (BLOCKER #3)
- ❌ Command palette
- ❌ Price alerts
- 🟡 Proper loading states
- 🟡 Error handling
- ❌ Heat map full-screen
- ❌ Peer comparison
- ❌ Custom watchlists
- ❌ Macro dashboard
- ❌ Correlation matrix
- ❌ Performance analytics

### **Performance & Reliability** 🟡 40%
- 🟡 Rate limiting (none)
- 🟡 Caching (none)
- 🟡 Error boundaries (none)
- 🟡 Loading states (basic)
- ✅ Real-time updates (excellent)
- ✅ Data integrity checks
- ✅ Kill switch & risk limits

---

## 💰 EFFORT ESTIMATION

| Phase | Component | Hours | Priority | Status |
|-------|-----------|-------|----------|--------|
| 1 | Fix universe support | 5 | CRITICAL | Ready |
| 1 | Keyboard shortcuts | 6 | CRITICAL | Ready |
| 1 | Multi-symbol comparison | 5 | HIGH | Ready |
| 1 | Loading skeletons | 2 | HIGH | Ready |
| 1 | Error boundaries | 1 | HIGH | Ready |
| 2 | Alert system | 10 | HIGH | Design |
| 2 | Redis caching | 4 | MEDIUM | Design |
| 2 | Rate limiting | 3 | MEDIUM | Design |
| 2 | React Query integration | 5 | MEDIUM | Design |
| 3 | Heat map full-screen | 6 | MEDIUM | Design |
| 3 | Peer comparison | 4 | MEDIUM | Design |
| 3 | Custom watchlists | 6 | LOW | Backlog |
| 3 | Macro dashboard | 8 | LOW | Backlog |

**Total to Bloomberg Parity:** ~65-75 hours (2-3 weeks with focus)

---

## 🚀 QUICK WINS (DO TODAY)

These can be completed in 2-3 hours:
1. Add FINNIFTY symbols ✅ (5 min)
2. Add universe dropdown ✅ (30 min)
3. Wire up API calls ✅ (1 hour)
4. Test all 4 universes ✅ (30 min)

**Expected Result:** Users can trade BANKNIFTY, FINNIFTY, and NIFTY IT immediately

---

## 📚 RELATED DOCUMENTATION

- ✅ BLOOMBERG_TERMINAL_ANALYSIS.md - Detailed feature analysis
- ✅ PHASE_1_FINAL_REPORT.md - Backend refactoring complete
- ✅ PHASE_2_2_SUMMARY.md - Terminal UI implementation
- ✅ SUMMARY.md - Overall scope (60% complete)

---

## ✨ SUCCESS CRITERIA

### After Phase 1 (This Week):
```
✅ User can switch between NIFTY50, BANKNIFTY, FINNIFTY, NIFTY_IT
✅ All data re-fetches when universe changes
✅ Can search stocks in selected universe
✅ Keyboard shortcuts working (TCS + Enter, 1-5 for timeframes)
✅ Command palette (Ctrl+K) opens
✅ Can compare 2 stocks side-by-side
✅ Loading states show properly
✅ Errors don't crash entire page
```

### After Phase 2 (Week 2):
```
✅ Price/technical alerts configured
✅ API calls rate-limited and cached
✅ Performance noticeably faster
✅ Heat map full-screen available
✅ Can see sector peers comparison
```

### After Phase 3 (Week 3-4):
```
✅ Custom watchlists (5+ created)
✅ Macro dashboard populated
✅ All features responsive on mobile
✅ Theme toggle working
✅ Portfolio linked to terminal
```

---

## 🎯 RECOMMENDATION

**START PHASE 1 IMMEDIATELY:**
- Fix universe support (4-5 hours)
- Add keyboard shortcuts (6 hours)
- Multi-symbol comparison (4 hours)
- Polish & testing (2-3 hours)

**Total: 16-18 hours** → Takes you from "trading app" → "Bloomberg-like terminal"

This unblocks everything else and gives users professional-grade trading platform.

---

*Generated by Full Workspace Scan - February 7, 2026*
