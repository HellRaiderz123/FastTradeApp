# Bloomberg Terminal - Next Steps (Updated Feb 8, 2026)
**Current State Analysis & Action Plan**

---

## ✅ WHAT'S CURRENTLY WORKING

### **Core Bloomberg Features ✅**
- ✅ **Bloomberg Terminal UI** (`TerminalBloomberg.tsx`) - Full-screen terminal interface
- ✅ **Universe Switcher** - NIFTY50 / BANKNIFTY / FINNIFTY / NIFTY_IT dropdown
- ✅ **Real-time Watchlist** - WebSocket streaming quotes for selected universe
- ✅ **Top Movers** - Gainers, Losers, Most Active (universe-aware)
- ✅ **Market Breadth** - Advancing/Declining, A/D Ratio, 52W Highs/Lows
- ✅ **Sector Performance** - Heat visualization with industry breakdown
- ✅ **Market Sentiment** - Fear & Greed, VIX, Put/Call Ratio
- ✅ **Stock Detail Modal** - News, Technicals, Timeframes, Overview (with newsdata.io + 30min caching)
- ✅ **Keyboard Shortcuts** - Ctrl+K (command palette), ESC, 1-5 (timeframes)
- ✅ **Economic Calendar** - Earnings, RBI, IPOs, Dividends, Corporate Actions
- ✅ **Market Depth** - 5-level bid/ask order book with imbalance
- ✅ **Swing Scanner** - 6+ strategies (Momentum, Oversold, Trend, Volume, Squeeze)
- ✅ **Stock Screener** - Technical + Fundamental filters (47 NIFTY50 stocks)
- ✅ **Heatmap Page** - Grid visualization by sector, color by % change
- ✅ **News Feed** - Live news with sentiment analysis
- ✅ **Technical Charts** - Multiple timeframes (1m, 5m, 15m, 1h, 1d)
- ✅ **Options Chain** - Greeks (Delta, Gamma, Theta, Vega, Rho)
- ✅ **Alerts Backend** - Price/indicator alerts API ready

### **Backend APIs Ready ✅**
```python
# All registered routes in main.py:
- /market-dashboard/*      # Top movers, breadth, sectors, heatmap
- /swing-scanner/*          # Swing trading opportunities
- /sentiment/*              # Market sentiment, Fear & Greed
- /stock-news/{symbol}      # Stock-specific news (newsdata.io)
- /timeframe-suggestions/*  # Volatility-based timeframe suggestion
- /economic-calendar/*      # Calendar events
- /market-depth/{symbol}    # Order book depth
- /alerts/*                 # Create/manage alerts
- /screener/*               # Stock screening
- /options/*                # Options chain
- /ws/quotes                # Real-time quote WebSocket
```

---

## 🚀 HIGH PRIORITY - BLOOMBERG ESSENTIALS

### **1. Multi-Symbol Comparison Chart** 📊 (4-6 hours)
**Impact:** ⭐⭐⭐⭐⭐ (Bloomberg's most-used feature)

Compare 2-4 stocks side-by-side with normalized returns.

**Implementation:**
```tsx
// Create: web/src/components/ComparisonChart.tsx
<ComparisonChart 
  symbols={['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']}
  timeframe="1d"
  baseline="percentage" // or "absolute"
/>
```

**Features:**
- Normalized % returns from common start date
- Correlation matrix below chart
- Volume comparison bars
- Sync zoom/pan across all symbols
- Symbol picker with color codes

**Backend:** Already exists (`/market-dashboard/stock-candles/{symbol}`)

**Files to Create:**
- `web/src/components/ComparisonChart.tsx`
- Add to TerminalBloomberg as new panel

---

### **2. Alert System UI** 🔔 (6-8 hours)
**Impact:** ⭐⭐⭐⭐⭐ (Critical for active traders)

Backend alert API exists, needs frontend UI.

**Implementation:**
```tsx
// Create: web/src/components/AlertManager.tsx
<AlertManager 
  symbol={selectedSymbol}
  currentPrice={quote.ltp}
  technicals={indicators}
/>
```

**Features:**
- **Price Alerts:** Above/below threshold, % change
- **Technical Alerts:** RSI > 80, MACD crossover, Bollinger squeeze
- **Volume Alerts:** 2x daily average spike
- **News Alerts:** Sentiment change for symbol
- **Alert List:** Active alerts panel with edit/delete
- **Notifications:** Toast notifications when triggered

**Backend API (Ready):**
```python
POST   /alerts              # Create alert
GET    /alerts              # List user alerts
DELETE /alerts/{alert_id}   # Delete alert
GET    /alerts/triggered    # Recently triggered
```

**Files to Create:**
- `web/src/components/AlertManager.tsx`
- `web/src/components/AlertList.tsx`
- `web/src/components/AlertNotification.tsx`
- Add alert icon to stock quote panels

---

### **3. Historical Performance Quick View** 📈 (2-3 hours)
**Impact:** ⭐⭐⭐⭐

Quick returns lookup table (Bloomberg staple).

**Display:**
```
RELIANCE
1D: +1.2%   1W: +3.5%   1M: +8.2%
3M: +15.3%  6M: +22.1%  1Y: +45.6%
```

**Implementation:**
```tsx
// Add to QuotePanel.tsx
<HistoricalReturns 
  symbol={symbol}
  periods={['1D', '1W', '1M', '3M', '6M', '1Y']}
/>
```

**Backend:**
- Use existing `/market-dashboard/stock-candles/{symbol}` 
- Calculate returns client-side from historical data
- Cache results for 1 hour

**Files to Modify:**
- `web/src/components/QuotePanel.tsx` (add returns section)
- Create utility: `utils/calculateReturns.ts`

---

### **4. Peer Comparison Table** 📊 (4-5 hours)
**Impact:** ⭐⭐⭐⭐

When viewing a stock, show sector peers side-by-side.

**Example (viewing HDFCBANK):**
```
           HDFCBANK  ICICIBANK  SBIN    Sector Avg
P/E Ratio    18.5      22.3     12.1      17.6
P/B Ratio     2.1       3.2      1.4       2.2
ROE %        14.2      18.5      9.8      14.2
Div Yield %   1.2       1.5      2.3       1.7
RSI(14)      65        48       72         62
```

**Implementation:**
```tsx
// Create: web/src/components/PeerComparison.tsx
<PeerComparison 
  symbol="HDFCBANK"
  sector="Banking"
  metrics={['pe', 'pb', 'roe', 'div_yield', 'rsi']}
/>
```

**Backend:**
- Use existing `/screener/search` to find sector peers
- Add sector mapping to stock metadata
- Return top 3-4 peers by market cap

**Files to Create:**
- `web/src/components/PeerComparison.tsx`
- Add to Stock Detail Modal as new tab

---

### **5. Treemap Heatmap Visualization** 🗺️ (3-4 hours)
**Impact:** ⭐⭐⭐⭐

Upgrade current grid heatmap to Bloomberg-style treemap.

**Current:** Grid layout with cells
**Target:** Hierarchical treemap (sector → stocks)

**Implementation:**
```tsx
// Use Recharts Treemap component
import { Treemap } from 'recharts';

<Treemap
  data={hierarchicalData}
  dataKey="market_cap"
  colorKey="change_percent"
  colorRange={['#ef4444', '#22c55e']}
/>
```

**Features:**
- Size rectangles by market cap
- Color by % change (red/green gradient)
- Sector grouping with drill-down
- Click to open stock detail
- Hover shows full metrics

**Files to Modify:**
- `web/src/pages/Heatmap.tsx` (upgrade to treemap)

---

### **6. Macro Dashboard Panel** 🌍 (4-5 hours)
**Impact:** ⭐⭐⭐

Quick view of macro indicators Bloomberg-style.

**Display:**
```
USD/INR: 83.25 (+0.12%)
Gold:    ₹62,450 (-0.35%)
Crude:   $78.50 (+1.2%)
10Y:     7.15% (+2 bps)
```

**Implementation:**
```tsx
// Create: web/src/components/MacroDashboard.tsx
<MacroDashboard 
  metrics={['usd_inr', 'gold', 'crude', '10y_yield']}
/>
```

**Backend Options:**
1. Use existing Zerodha API for commodities (MCX symbols)
2. Add external API (Alpha Vantage, Yahoo Finance)
3. Manual daily update from admin panel

**Files to Create:**
- `backend/app/api/routes/macro.py` (new API)
- `web/src/components/MacroDashboard.tsx`
- Add to TerminalBloomberg header bar

---

## 🎨 UI/UX ENHANCEMENTS

### **7. Custom Watchlists** 📋 (6-8 hours)
**Impact:** ⭐⭐⭐⭐

User-defined watchlists instead of hardcoded universe lists.

**Current:** Hardcoded watchlist per universe
**Target:** Multiple custom watchlists per user

**Implementation:**
```python
# Backend: app/db/models.py
class Watchlist:
    id: int
    user_id: str
    name: str  # "Day Trading", "Long Term", etc.
    symbols: List[str]  # JSON array
    created_at: datetime
```

**Features:**
- Create unlimited watchlists
- Drag-and-drop to reorder
- Quick switch dropdown
- Import/export CSV
- Set default watchlist

**Files to Create:**
- `backend/app/api/routes/watchlists.py`
- `web/src/components/WatchlistManager.tsx`
- `web/src/components/WatchlistDropdown.tsx`

---

### **8. Enhanced Keyboard Shortcuts** ⌨️ (3-4 hours)
**Impact:** ⭐⭐⭐⭐

Complete Bloomberg-style keyboard navigation.

**Current:** Partial (Ctrl+K, ESC, 1-5)
**Target:** Full shortcuts like real Bloomberg

**Shortcuts to Add:**
```
TCS <GO>          → Load TCS chart
GP                → Show price graph panel
CT                → Show chart panel
NEWS              → Show news panel
DES               → Show description/fundamentals
MON               → Show monitor (alerts)
HDS               → Show holders
DVD               → Show dividends
G                 → Next timeframe
Shift+G           → Previous timeframe
/                 → Focus search
?                 → Show shortcuts help
```

**Implementation:**
- Extend existing keyboard handler in TerminalBloomberg.tsx
- Add shortcuts help modal (`?` key)
- Visual shortcuts hints on hover

**Files to Modify:**
- `web/src/pages/TerminalBloomberg.tsx` (extend handleKeyDown)
- Create `web/src/components/ShortcutsHelp.tsx`

---

### **9. Chart Drawing Tools** ✏️ (8-10 hours)
**Impact:** ⭐⭐⭐

Add TradingView-style drawing tools to charts.

**Tools:**
- Trendlines
- Horizontal support/resistance
- Fibonacci retracement
- Text annotations
- Arrows/shapes

**Implementation:**
- Upgrade to TradingView Lightweight Charts (currently using Recharts)
- Or use Plotly with drawing mode
- Save drawings to localStorage per symbol

**Files to Create:**
- `web/src/components/AdvancedChart.tsx` (TradingView integration)
- `web/src/hooks/useChartDrawings.ts`

---

## 📊 ADVANCED ANALYTICS

### **10. Volume Profile** 📊 (6-7 hours)
**Impact:** ⭐⭐⭐

Show volume distribution at price levels.

**Display:**
```
Price    Volume Bars
1580  ▓▓▓▓▓▓▓▓░░
1575  ▓▓▓▓▓▓▓▓▓▓▓▓  ← High volume node
1570  ▓▓▓▓▓░░
1565  ▓▓░
```

**Implementation:**
- Calculate volume-at-price from historical candles
- Display as horizontal bars on chart
- Identify high-volume nodes (support/resistance)

**Files to Create:**
- `web/src/components/VolumeProfile.tsx`
- Add to chart panel as overlay

---

### **11. Portfolio Analytics Dashboard** 💼 (10-12 hours)
**Impact:** ⭐⭐⭐⭐

Aggregate view of all positions with risk metrics.

**Features:**
- **Total P&L:** Current, Today, All-time
- **Asset Allocation:** Pie chart (stocks%, options%, cash%)
- **Sector Allocation:** Exposure by sector
- **Greeks Summary:** Portfolio delta, gamma, theta, vega
- **Risk Metrics:** Sharpe ratio, max drawdown, VaR
- **Top Performers:** Best/worst holdings
- **Performance Chart:** Equity curve over time

**Backend:**
- Use existing positions API
- Calculate aggregations
- Store historical snapshots for equity curve

**Files to Create:**
- `web/src/pages/PortfolioAnalytics.tsx`
- `backend/app/api/routes/portfolio_analytics.py`

---

### **12. Backtest Integration into Terminal** 🔬 (8-10 hours)
**Impact:** ⭐⭐⭐

Quick-backtest from terminal without leaving page.

**Implementation:**
```tsx
// Add to Stock Detail Modal
<QuickBacktest 
  symbol={symbol}
  strategy={selectedStrategy}
  dateRange="3M"
/>
```

**Features:**
- Select pre-built strategy
- Set parameters (entry/exit conditions)
- Run on 1-click
- Show: win%, avg return, drawdown, equity curve
- Compare multiple strategies

**Backend:** Use existing `/backtest/*` APIs

---

## 🔧 INFRASTRUCTURE

### **13. Redis Caching Layer** ⚡ (4-5 hours)
**Impact:** ⭐⭐⭐⭐ (Performance critical)

Add Redis for market data caching.

**Current:** In-memory Python cache (lost on restart)
**Target:** Persistent Redis cache

**What to Cache:**
- Quote data (1-5 sec TTL)
- Candle data (1-5 min TTL)
- Option chains (1 min TTL)
- News articles (30 min TTL) ← Already implemented in-memory
- Screener results (5 min TTL)

**Implementation:**
```python
# backend/requirements.txt
redis==5.0.1

# backend/app/core/cache.py
import redis
r = redis.Redis(host='localhost', port=6379, db=0)

def cache_quote(symbol: str, data: dict, ttl: int = 5):
    r.setex(f"quote:{symbol}", ttl, json.dumps(data))
```

---

### **14. User Preferences & Settings** ⚙️ (6-8 hours)
**Impact:** ⭐⭐⭐

Save user preferences (theme, layout, watchlists).

**Features:**
- **Layout:** Save panel positions/sizes
- **Theme:** Light/Dark mode
- **Default Universe:** NIFTY50 vs BANKNIFTY
- **Default Timeframe:** 15m vs 1h
- **Watchlist Order:** Custom sort
- **Alerts Preferences:** Email, SMS, Push

**Backend:**
```python
class UserPreference:
    user_id: str
    key: str  # "theme", "default_universe", etc.
    value: str
    updated_at: datetime
```

**Files to Create:**
- `backend/app/api/routes/user_preferences.py`
- `web/src/contexts/PreferencesContext.tsx`

---

## 📱 MOBILE & ACCESSIBILITY

### **15. Mobile-Responsive Terminal** 📱 (12-15 hours)
**Impact:** ⭐⭐⭐

Make terminal usable on tablets/phones.

**Current:** Desktop-only layout
**Target:** Adaptive responsive layout

**Mobile Features:**
- Collapsible panels (accordion)
- Bottom nav for quick access
- Swipe gestures for charts
- Simplified quote cards
- Pull-to-refresh

---

## 🎯 RECOMMENDED PRIORITY ORDER

### **THIS WEEK (HIGH IMPACT):**
1. ✅ **Alert System UI** (6-8h) - Critical trader feature
2. ✅ **Multi-Symbol Comparison** (4-6h) - Bloomberg essential
3. ✅ **Historical Performance View** (2-3h) - Quick win
4. ✅ **Peer Comparison Table** (4-5h) - Adds depth

**Total: ~18-22 hours**

### **NEXT WEEK (POLISH):**
5. ✅ **Treemap Heatmap** (3-4h)
6. ✅ **Macro Dashboard** (4-5h)
7. ✅ **Custom Watchlists** (6-8h)
8. ✅ **Enhanced Keyboard Shortcuts** (3-4h)

**Total: ~16-21 hours**

### **WEEK 3-4 (ADVANCED):**
9. ✅ **Chart Drawing Tools** (8-10h)
10. ✅ **Volume Profile** (6-7h)
11. ✅ **Portfolio Analytics** (10-12h)
12. ✅ **Redis Caching** (4-5h)

---

## 💡 QUICK WINS (< 2 HOURS EACH)

1. **Add "Last Updated" timestamp** to all panels (30 min)
2. **Add "Refresh" button** to each panel (30 min)
3. **Loading skeletons** for all data panels (1-2h)
4. **Error retry logic** with exponential backoff (1h)
5. **Tooltips** on all technical indicators (1h)
6. **Export CSV** from screener/scanner results (1h)
7. **Share button** for charts (copy URL with params) (1h)
8. **Dark/Light theme toggle** (1-2h)

---

## 🐛 KNOWN ISSUES TO FIX

1. **WebSocket reconnection** - Sometimes fails silently
2. **Chart lag** - Recharts performance with large datasets
3. **Memory leaks** - Component unmount cleanup needed
4. **Mobile layout breaks** - Not responsive currently
5. **Search autocomplete** - Needs debounce & better UX
6. **News API rate limits** - Need better error handling (status 429)

---

## 📝 NOTES

- **Current Stack:** React + TypeScript + Vite + FastAPI + Python
- **Real-time:** WebSocket for quotes, 30s polling for rest
- **Caching:** In-memory (news 30min), no Redis yet
- **Database:** SQLite (dev), ready for PostgreSQL (prod)
- **News:** newsdata.io (200 credits/day = 20 articles, cached 30min)

**Last Updated:** February 8, 2026
**Status:** Bloomberg Terminal UI functional with most core features. Focus now on polish & advanced analytics.
