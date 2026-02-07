# Bloomberg Terminal - Comprehensive Analysis & Roadmap
**Date: February 7, 2026**

---

## ✅ WHAT'S WORKING (Current Features)

### 1. **Core Market Data** ✅
- ✅ Real-time watchlist with live Zerodha prices (WebSocket)
- ✅ Top Movers (Gainers, Losers, Most Active)
- ✅ Market Breadth (Advancing/Declining, A/D Ratio, 52W Highs/Lows)
- ✅ Sector Performance with industry heat visualization
- ✅ Market Sentiment (Fear & Greed Index, VIX, P/C Ratio)

### 2. **Technical Analysis** ✅
- ✅ Advanced charting with TradingView-style interface
- ✅ Multiple timeframes (1m, 5m, 15m, 1h, 1d)
- ✅ Technical indicators (RSI, MACD, Bollinger Bands, ADX, ATR)
- ✅ Pattern recognition in swing scanner

### 3. **News & Events** ✅
- ✅ Live news feed with sentiment analysis
- ✅ **Economic Calendar (NEW - just built today)**
  - ✅ Earnings announcements
  - ✅ RBI monetary policy
  - ✅ Economic data releases (inflation, GDP, etc.)
  - ✅ IPO listings
  - ✅ Dividend announcements
  - ✅ Corporate actions
  - ✅ Global events

### 4. **Market Depth & Liquidity** ✅
- ✅ **Market Depth/Order Book (NEW - just built today)**
  - ✅ 5-level bid/ask ladder visualization
  - ✅ Order imbalance calculation (-100 to +100)
  - ✅ Support/resistance levels from depth
  - ✅ Spread analysis
  - ✅ Auto-refresh every 3 seconds

### 5. **Scanning & Screening** ✅
- ✅ Swing Trading Scanner with 6+ strategies:
  - Momentum Breakout
  - Oversold Bounce
  - Trend Following
  - Volume Surge
  - Bollinger Squeeze
  - Custom patterns
- ✅ **Stock Screener (UPDATED - expanded today)**
  - Technical filters: MACD, Bollinger Squeeze, ATR, ADX
  - Fundamental filters: P/E, P/B, ROE, Dividend Yield, Debt/Equity
  - Pattern recognition
  - 47 NIFTY50 stocks with full fundamental data

### 6. **Options Analytics** ✅
- ✅ Options Chain with Greeks (Delta, Gamma, Theta, Vega, Rho)
- ✅ Put/Call Ratio analysis
- ✅ IV Rank calculation
- ⚠️ **NOTE:** Using Black-Scholes calculated Greeks (documented)

---

## 🔴 CRITICAL ISSUES TO FIX IMMEDIATELY

### **Issue #1: Hardcoded NIFTY50 Universe** 🚨 BLOCKING
**Problem:** Terminal is completely hardcoded to NIFTY50
```typescript
// Line 109 - TerminalBloomberg.tsx
<h1>NIFTY 50 Command Center</h1>  // ← Hardcoded title

// Line 148 - Search placeholder
placeholder="Search NIFTY 50 stocks (e.g., TCS, RELIANCE)"  // ← Hardcoded

// Line 54-58 - API calls with no universe parameter
const movers = await marketDashboardAPI.getTopMovers(5);  // ← Defaults to NIFTY50
const sectorData = await marketDashboardAPI.getSectorPerformance();  // ← All sectors
const opportunities = await swingScannerAPI.scan('all', 60);  // ← NIFTY50 only
```

**Impact:** 
- ❌ Cannot analyze BANKNIFTY stocks (12 banking stocks like HDFC, ICICI, SBI, Kotak)
- ❌ Cannot analyze FINNIFTY stocks (15 financial services stocks)
- ❌ Cannot analyze NIFTY IT separately (9 IT stocks)
- ❌ Users are locked into one universe despite backend supporting multiple

**What Backend Already Supports:**
```python
# backend/app/config/market_config.py - Line 22-47
MARKET_SYMBOLS = {
    "NIFTY50": [50 stocks],
    "BANKNIFTY": [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
        "INDUSINDBK", "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "PNB",
        "BANKBARODA", "AUBANK"
    ],
    "NIFTY_IT": [
        "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM",
        "LTIM", "COFORGE", "PERSISTENT", "MPHASIS"
    ]
}
```

**BUT:** FINNIFTY is NOT defined yet!

**REQUIRED FIXES:**

1. **Add FINNIFTY to market_config.py** (5 minutes):
```python
MARKET_SYMBOLS = {
    # ... existing ...
    "FINNIFTY": [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
        "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "ICICIGI",
        "BAJAJHLDNG", "PFC", "RECLTD", "MUTHOOTFIN", "CHOLAFIN"
    ]
}

class MarketUniverse(str, Enum):
    NIFTY50 = "NIFTY50"
    BANKNIFTY = "BANKNIFTY"
    FINNIFTY = "FINNIFTY"  # ADD THIS
    NIFTY_IT = "NIFTY_IT"
    NIFTY100 = "NIFTY100"
    CUSTOM = "CUSTOM"
```

2. **Add Universe Switcher to Terminal UI** (30 minutes):
```typescript
// web/src/pages/TerminalBloomberg.tsx
const [universe, setUniverse] = useState<string>('NIFTY50');

// Add to header (after line 109)
<div className="flex items-center gap-4">
  <h1 className="terminal-title text-3xl text-white">
    {universe === 'NIFTY50' ? 'NIFTY 50' : 
     universe === 'BANKNIFTY' ? 'BANK NIFTY' : 
     universe === 'FINNIFTY' ? 'FIN NIFTY' : 'NIFTY IT'} Command Center
  </h1>
  
  <select 
    value={universe}
    onChange={(e) => setUniverse(e.target.value)}
    className="bg-slate-900/80 border border-slate-700/50 rounded-lg px-4 py-2 text-sm text-white"
  >
    <option value="NIFTY50">NIFTY 50</option>
    <option value="BANKNIFTY">BANK NIFTY (12)</option>
    <option value="FINNIFTY">FIN NIFTY (15)</option>
    <option value="NIFTY_IT">NIFTY IT (9)</option>
  </select>
</div>
```

3. **Make All API Calls Universe-Aware** (1 hour):
```typescript
// Update fetchMarketData function
useEffect(() => {
  const fetchMarketData = async () => {
    try {
      // Pass universe to all API calls
      const movers = await marketDashboardAPI.getTopMovers(5, universe);
      const sectorData = await marketDashboardAPI.getSectorPerformance();  // Keep as-is
      const breadth = await marketDashboardAPI.getMarketBreadth(universe);
      const opportunities = await swingScannerAPI.scan('all', 60, universe);
      
      // ... set state
    } catch (error) {
      console.error('Failed to fetch market data:', error);
    }
  };

  fetchMarketData();
  const interval = setInterval(fetchMarketData, 30000);
  return () => clearInterval(interval);
}, [universe]);  // ← Add universe dependency
```

4. **Update API Interfaces** (30 minutes):
```typescript
// web/src/lib/marketDashboardAPI.ts
export const marketDashboardAPI = {
  async getTopMovers(limit: number = 10, universe: string = 'NIFTY50') {
    const response = await api.get('/market-dashboard/top-movers', {
      params: { limit, universe }
    });
    return response.data;
  },
  
  async getMarketBreadth(universe: string = 'NIFTY50') {
    const response = await api.get('/market-dashboard/market-breadth', {
      params: { universe }
    });
    return response.data;
  }
};

export const swingScannerAPI = {
  async scan(strategy: string = 'all', min_score: number = 50, universe: string = 'NIFTY50') {
    const response = await api.get('/swing-scanner/scan', {
      params: { strategy, min_score, universe }
    });
    return response.data;
  }
};
```

**Total Time:** ~2 hours to fully fix universe support

---

### **Issue #2: No Loading States** 🟡
**Problem:** Components show generic "Loading..." text
```typescript
// Line 293 - Swing opportunities
{swingOpportunities.length > 0 ? (
  // ... render opportunities
) : (
  <p className="text-xs text-slate-500">Loading opportunities...</p>  // ← Bad UX
)}
```

**Fix:** Add proper loading skeletons
```typescript
import { Skeleton } from './Skeleton';  // Create this component

{loading ? (
  <div className="space-y-3">
    {[1,2,3,4,5].map(i => (
      <Skeleton key={i} className="h-20 w-full rounded-xl" />
    ))}
  </div>
) : swingOpportunities.length > 0 ? (
  // ... render opportunities
) : (
  <div className="text-center py-8">
    <AlertTriangle className="mx-auto mb-2 text-slate-500" />
    <p className="text-sm text-slate-400">No opportunities match your criteria</p>
    <button onClick={retry} className="mt-2 text-xs text-blue-400">Retry</button>
  </div>
)}
```

---

### **Issue #3: No Error Boundaries** 🟡
**Problem:** One component crash kills entire terminal
**Fix:** Wrap in error boundary
```typescript
// web/src/components/ErrorBoundary.tsx
import React from 'react';

export class ErrorBoundary extends React.Component {
  state = { hasError: false };
  
  static getDerivedStateFromError(error) {
    return { hasError: true };
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div className="terminal-panel p-8 text-center">
          <AlertTriangle className="mx-auto mb-4 text-red-400" size={48} />
          <h3 className="text-lg font-semibold text-white mb-2">Component Error</h3>
          <p className="text-sm text-slate-400">This component crashed. Try refreshing.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

// Wrap terminal sections
<ErrorBoundary>
  <SwingScanner />
</ErrorBoundary>
```

---

## 📊 MISSING BLOOMBERG FEATURES

### **Priority 1: MUST IMPLEMENT THIS WEEK**

#### 1. **Multi-Symbol Comparison Charts** 🚧 (YOUR TODO #6)
Real Bloomberg terminals show side-by-side stock comparison:

**Features:**
- Compare 2-4 stocks in one chart
- Normalized % returns from baseline
- Correlation coefficient display
- Volume comparison bars
- Sync timeframes across charts

**Component Structure:**
```typescript
<MultiSymbolComparison 
  symbols={['RELIANCE', 'TCS', 'INFY', 'HDFCBANK']}
  timeframe="1d"
  metric="returns"  // or "price", "volume"
/>
```

**Implementation Plan:**
- Create `ComparisonChart.tsx` using Recharts
- Add symbol selector with multi-select
- Fetch data for all symbols
- Calculate % returns from baseline date
- Show correlation matrix below chart

**Time:** 4-6 hours

---

#### 2. **Keyboard Shortcuts & Command Palette** 🚧 (YOUR TODO #7)
Bloomberg's killer feature - keyboard-first navigation:

**Essential Shortcuts:**
```
TCS <Enter>          → Load TCS chart
RELIANCE GO          → Load RELIANCE with default view
GP                   → Show price graph
MOV                  → Show moving averages
ESC                  → Clear selection
1-5                  → Set timeframe (1m/5m/15m/1h/1d)
Ctrl+K               → Open command palette
```

**Implementation:**
```typescript
// Add to TerminalBloomberg.tsx
useEffect(() => {
  const handleKeyPress = (e: KeyboardEvent) => {
    // Ignore if typing in input
    if (e.target instanceof HTMLInputElement) return;
    
    // Command mode: Stock symbol loading
    if (e.key === 'Enter' && searchInput.match(/^[A-Z]+( GO)?$/)) {
      const symbol = searchInput.replace(' GO', '');
      setSelectedSymbol(symbol);
      setSearchInput('');
      return;
    }
    
    // Quick timeframe switching
    const timeframeKeys: Record<string, typeof timeframe> = {
      '1': '1m', '2': '5m', '3': '15m', '4': '1h', '5': '1d'
    };
    if (timeframeKeys[e.key]) {
      setTimeframe(timeframeKeys[e.key]);
      return;
    }
    
    // ESC to clear
    if (e.key === 'Escape') {
      setSearchInput('');
      setSelectedSymbol('RELIANCE');
    }
    
    // Ctrl+K for command palette
    if (e.ctrlKey && e.key === 'k') {
      e.preventDefault();
      setShowCommandPalette(true);
    }
  };
  
  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, [searchInput]);
```

**Command Palette:**
- Use `cmdk` library
- Fuzzy search all stocks
- Recent stocks history
- Quick actions (screener, heatmap, alerts)

**Time:** 6-8 hours

---

#### 3. **Alert System** 🔔
**Bloomberg-style price/indicator alerts:**

**Features:**
- Price crosses threshold (above/below)
- RSI overbought/oversold
- Volume spike (2x average)
- MACD crossover
- News sentiment trigger
- Earnings announcement

**Implementation:**
```typescript
// New route: backend/app/api/routes/alerts.py
@router.post("/alerts")
async def create_alert(
    symbol: str,
    condition: str,  # "price_above", "rsi_below", etc.
    threshold: float,
    user_id: str
):
    # Store in database
    # Schedule background check
    pass

// Frontend component
<AlertManager 
  symbol={selectedSymbol}
  currentPrice={quote.ltp}
  onCreateAlert={(alert) => saveAlert(alert)}
/>
```

**Time:** 8-10 hours (backend + frontend + notifications)

---

### **Priority 2: SHOULD HAVE (NEXT WEEK)**

#### 4. **Heat Map Full-Screen View**
Treemap visualization like Bloomberg:
- Color-coded by % change (red/green)
- Size by market cap
- Click to drill down to stock
- Sector grouping

#### 5. **Peer Comparison Table**
When viewing stock, show sector peers:
- Side-by-side metrics (P/E, P/B, ROE, etc.)
- Relative valuation
- Technical indicators comparison

#### 6. **Custom Watchlists**
User-defined watchlists:
- Create unlimited watchlists
- Drag-and-drop to reorder
- Quick switch between watchlists
- Import/export watchlist

#### 7. **Historical Performance Table**
Quick returns lookup:
```
RELIANCE
1D: +1.2%   1W: +3.5%   1M: +8.2%
3M: +15.3%  6M: +22.1%  1Y: +45.6%
```

#### 8. **Macro Dashboard**
Quick view of macro indicators:
- USD/INR exchange rate
- Gold/Silver prices
- Crude oil
- Global indices (DOW, NASDAQ, FTSE, HSI)
- Interest rates

---

### **Priority 3: NICE TO HAVE (FUTURE)**

9. **Correlation Matrix** - Show stock/sector correlations
10. **Earnings Calendar** - With analyst estimates
11. **FII/DII Activity** - Track institutional flows
12. **Options OI Analysis** - Max pain calculator
13. **Custom Screener Presets** - Save filter combinations
14. **Portfolio Integration** - Link terminal to positions
15. **Dividend Calendar** - Upcoming ex-dates
16. **Corporate Actions Timeline** - Splits, bonus issues
17. **Technical Pattern Scanner** - Head & shoulders, triangles
18. **Volatility Analysis** - IV rank trends

---

## 🐛 CODE QUALITY & PERFORMANCE ISSUES

### Backend Issues:

#### 1. **No Rate Limiting** 🔴 CRITICAL
**Problem:** Zerodha API has strict limits (3 req/sec)
- Unlimited requests = API ban
- Bulk endpoints help but not enough

**Fix:**
```python
# backend/app/core/rate_limiter.py
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Apply to routes
@router.get("/top-movers")
@limiter.limit("10/minute")  # Max 10 requests per minute
async def get_top_movers():
    pass
```

#### 2. **No Caching** 🟡
**Problem:** Every request hits Zerodha
- Historical data doesn't change
- Quotes can be cached for 1-2 seconds

**Fix:**
```python
# Add Redis caching
from redis import Redis
import json

redis_client = Redis(host='localhost', port=6379, db=0)

def get_cached_or_fetch(key: str, fetch_fn, ttl=60):
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    
    data = fetch_fn()
    redis_client.setex(key, ttl, json.dumps(data))
    return data

# Usage
quotes = get_cached_or_fetch(
    f"quotes:{symbol}", 
    lambda: kite.quote([symbol]),
    ttl=2  # Cache for 2 seconds
)
```

#### 3. **No Request Timeout** 🟡
**Problem:** Zerodha calls can hang indefinitely

**Fix:**
```python
# In zerodha.py
import httpx

async def get_quote(symbol: str, timeout=10):
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{ZERODHA_API}/quote/{symbol}")
            return response.json()
    except httpx.TimeoutException:
        logger.error(f"Timeout fetching {symbol}")
        raise HTTPException(status_code=504, detail="Request timeout")
```

#### 4. **Inconsistent Error Handling** 🟡
**Problem:** Mix of 503, 500, 404 errors

**Fix:** Standardize error responses
```python
class MarketDataError(HTTPException):
    def __init__(self, message: str, code: str = "MARKET_DATA_ERROR"):
        super().__init__(
            status_code=503,
            detail={"message": message, "code": code}
        )

# Usage
if not quotes:
    raise MarketDataError("Unable to fetch quotes from Zerodha")
```

---

### Frontend Issues:

#### 1. **No Loading Skeletons** 🔴
**Problem:** Generic "Loading..." text everywhere

**Fix:** Create reusable skeleton component
```typescript
export const StockCardSkeleton = () => (
  <div className="terminal-panel rounded-xl px-4 py-3 animate-pulse">
    <div className="h-4 bg-slate-700/50 rounded w-1/3 mb-2" />
    <div className="h-6 bg-slate-700/50 rounded w-2/3" />
  </div>
);
```

#### 2. **No Error Boundaries** 🟡
**Problem:** Component crashes kill entire page
**Fix:** Wrap each major section in ErrorBoundary

#### 3. **Performance: Excessive Re-renders** 🟡
**Problem:** Quote updates trigger re-render of entire terminal

**Fix:** Memoize components
```typescript
const QuoteCard = React.memo(({ symbol, quote }: Props) => {
  // Component only re-renders if symbol or quote changes
  return <div>...</div>;
});

// Also memoize quote selectors
const selectQuote = useCallback((symbol) => quotes[symbol], [quotes]);
```

#### 4. **Hardcoded Watchlist** 🟡
**Problem:** Always shows same 6 stocks

**Fix:** Make watchlist user-configurable
```typescript
const [watchlist, setWatchlist] = useState(() => {
  const saved = localStorage.getItem('watchlist');
  return saved ? JSON.parse(saved) : DEFAULT_WATCHLIST;
});

// Add watchlist editor
<WatchlistEditor 
  symbols={watchlist}
  onChange={(newList) => {
    setWatchlist(newList);
    localStorage.setItem('watchlist', JSON.stringify(newList));
  }}
/>
```

#### 5. **Universe Not Reactive** 🔴
**Problem:** Changing universe doesn't refresh data

**Fix:** Add universe to useEffect dependency
```typescript
useEffect(() => {
  fetchMarketData();
}, [universe]);  // ← Must include universe
```

---

## 🎯 RECOMMENDED IMPLEMENTATION ORDER

### **PHASE 1: CRITICAL FIXES (THIS WEEK - 8-10 hours)**
1. ✅ Remove mock data fallbacks (DONE TODAY)
2. 🔄 Add FINNIFTY to market_config.py (5 min)
3. 🔄 Add universe switcher dropdown (30 min)
4. 🔄 Make all APIs universe-aware (2 hours)
5. 🔄 Add loading skeletons (1 hour)
6. 🔄 Add error boundaries (1 hour)
7. 🔄 Fix universe reactivity (30 min)
8. 🔄 Add "No results" empty states (1 hour)

### **PHASE 2: CORE BLOOMBERG FEATURES (NEXT WEEK - 20-25 hours)**
9. ⬜ Multi-symbol comparison charts (6 hours)
10. ⬜ Keyboard shortcuts (4 hours)
11. ⬜ Command palette (4 hours)
12. ⬜ Alert system backend (6 hours)
13. ⬜ Alert system frontend (4 hours)
14. ⬜ Historical performance table (2 hours)

### **PHASE 3: ADVANCED FEATURES (WEEK 3-4 - 30-40 hours)**
15. ⬜ Heat map full-screen view (6 hours)
16. ⬜ Peer comparison table (4 hours)
17. ⬜ Custom watchlists (6 hours)
18. ⬜ Macro dashboard (8 hours)
19. ⬜ Correlation matrix (6 hours)
20. ⬜ Custom screener presets (4 hours)

### **PHASE 4: POLISH & PERFORMANCE (ONGOING)**
21. ⬜ Rate limiting (4 hours)
22. ⬜ Redis caching (6 hours)
23. ⬜ Performance optimization (8 hours)
24. ⬜ Mobile responsive (12 hours)
25. ⬜ Dark/Light theme (4 hours)

---

## 📝 IMMEDIATE ACTION ITEMS (START NOW)

### **Task 1: Add Universe Switcher (30 minutes)**

**Step 1:** Add FINNIFTY to backend
```python
# File: backend/app/config/market_config.py
# Add after line 40
"FINNIFTY": [
    "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
    "BAJFINANCE", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "ICICIGI",
    "BAJAJHLDNG", "PFC", "RECLTD", "MUTHOOTFIN", "CHOLAFIN"
]
```

**Step 2:** Add universe state to terminal
```typescript
// File: web/src/pages/TerminalBloomberg.tsx
// Add after line 30
const [universe, setUniverse] = useState<string>('NIFTY50');
```

**Step 3:** Add dropdown in header
```typescript
// File: web/src/pages/TerminalBloomberg.tsx
// Replace line 109 with:
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

**Step 4:** Update API calls
```typescript
// File: web/src/pages/TerminalBloomberg.tsx
// Update fetchMarketData function (line 54)
const fetchMarketData = async () => {
  try {
    const movers = await marketDashboardAPI.getTopMovers(5, universe);
    const breadth = await marketDashboardAPI.getMarketBreadth(universe);
    const opportunities = await swingScannerAPI.scan('all', 60, universe);
    // ... rest
  } catch (error) {
    console.error('Failed to fetch market data:', error);
  }
};

// Update useEffect dependency (line 87)
}, [universe]);  // Add universe
```

**Step 5:** Update API interfaces
```typescript
// File: web/src/lib/marketDashboardAPI.ts
// Update function signatures
async getTopMovers(limit: number = 10, universe: string = 'NIFTY50')
async getMarketBreadth(universe: string = 'NIFTY50')

// File: web/src/lib/swingScannerAPI.ts (or similar)
async scan(strategy: string, min_score: number, universe: string = 'NIFTY50')
```

---

## 🚀 QUICK TEXT REPLACEMENTS

Run these find-and-replace operations:

1. **Terminal Title:**
   - Find: `<h1 className="terminal-title text-3xl text-white">NIFTY 50 Command Center</h1>`
   - Replace with universe-aware version

2. **Search Placeholder:**
   - Find: `placeholder="Search NIFTY 50 stocks`
   - Replace: `placeholder="Search {universe} stocks`

3. **Hardcoded Universe in API calls:**
   - Find: `await marketDashboardAPI.getTopMovers(5)`
   - Replace: `await marketDashboardAPI.getTopMovers(5, universe)`

---

## 📊 EXPECTED OUTCOMES

### After Phase 1 (This Week):
- ✅ Can switch between NIFTY50/BANKNIFTY/FINNIFTY/NIFTY_IT
- ✅ All data updates when universe changes
- ✅ Proper loading states (no more "Loading...")
- ✅ Error boundaries prevent crashes
- ✅ Clear "No results" messages

### After Phase 2 (Next Week):
- ✅ Compare multiple stocks side-by-side
- ✅ Bloomberg-style keyboard navigation (TCS GO, etc.)
- ✅ Command palette (Ctrl+K)
- ✅ Price/indicator alerts with notifications
- ✅ Historical returns table

### After Phase 3 (Week 3-4):
- ✅ Full-screen heat map
- ✅ Peer comparison tables
- ✅ Custom watchlists
- ✅ Macro indicators dashboard
- ✅ Correlation analysis

### After Phase 4 (Ongoing):
- ✅ Production-ready performance
- ✅ Rate limiting prevents API bans
- ✅ Redis caching reduces costs
- ✅ Mobile responsive design
- ✅ Theme customization

---

## 💡 ARCHITECTURE IMPROVEMENTS

### 1. **Create Market Context**
Avoid prop drilling for universe selection:
```typescript
// contexts/MarketContext.tsx
export const MarketContext = createContext({
  universe: 'NIFTY50',
  setUniverse: (u: string) => {},
  symbols: [] as string[]
});

export const MarketProvider = ({ children }) => {
  const [universe, setUniverse] = useState('NIFTY50');
  const [symbols, setSymbols] = useState([]);
  
  useEffect(() => {
    // Fetch symbols for universe
    configAPI.getSymbols(universe).then(setSymbols);
  }, [universe]);
  
  return (
    <MarketContext.Provider value={{ universe, setUniverse, symbols }}>
      {children}
    </MarketContext.Provider>
  );
};

// Usage
const { universe, setUniverse } = useContext(MarketContext);
```

### 2. **Use React Query for API Calls**
Better caching, automatic retries, loading states:
```typescript
import { useQuery } from '@tanstack/react-query';

const { data: topMovers, isLoading, error } = useQuery({
  queryKey: ['topMovers', universe],
  queryFn: () => marketDashboardAPI.getTopMovers(5, universe),
  refetchInterval: 30000,  // Auto-refresh every 30s
  staleTime: 10000,  // Consider fresh for 10s
  retry: 3  // Retry 3 times on failure
});

if (isLoading) return <Skeleton />;
if (error) return <ErrorMessage error={error} retry={refetch} />;
return <TopMoversTable data={topMovers} />;
```

### 3. **WebSocket Multiplexing**
Optimize WebSocket usage:
```typescript
class QuoteManager {
  private subscriptions = new Map<string, Set<Function>>();
  
  subscribe(symbol: string, callback: Function) {
    if (!this.subscriptions.has(symbol)) {
      this.subscriptions.set(symbol, new Set());
      this.ws.send({ type: 'subscribe', symbol });
    }
    this.subscriptions.get(symbol).add(callback);
  }
  
  unsubscribe(symbol: string, callback: Function) {
    const subs = this.subscriptions.get(symbol);
    subs?.delete(callback);
    if (subs?.size === 0) {
      this.ws.send({ type: 'unsubscribe', symbol });
      this.subscriptions.delete(symbol);
    }
  }
}
```

---

## 📚 RECOMMENDED LIBRARIES

### New Packages to Add:

**Frontend:**
```json
{
  "@tanstack/react-query": "^5.0.0",  // Data fetching & caching
  "cmdk": "^0.2.0",  // Command palette component
  "react-hot-keys": "^2.7.0",  // Keyboard shortcuts
  "recharts": "^2.10.0",  // Comparison charts
  "react-error-boundary": "^4.0.0",  // Error handling
  "zustand": "^4.4.0"  // Global state (lighter than Redux)
}
```

**Backend:**
```python
# requirements.txt
slowapi==0.1.9  # Rate limiting
redis==5.0.0  # Caching
httpx==0.25.0  # Async HTTP client with timeout
```

---

## ✨ SUMMARY

### **Current Status:**
- ✅ Excellent real-time data integration with Zerodha
- ✅ Professional Bloomberg-style UI
- ✅ Comprehensive market data (breadth, sentiment, sectors)
- ✅ Advanced screening & scanning tools
- ✅ Economic calendar & market depth (NEW)
- ✅ No mock data (removed today)

### **Critical Blockers:**
- ❌ **Universe locked to NIFTY50** (can't view BANKNIFTY/FINNIFTY)
- ❌ **No keyboard shortcuts** (Bloomberg's signature feature)
- ❌ **No multi-symbol comparison** (from your todo list)
- ⚠️ **Missing loading states** (bad UX)
- ⚠️ **No error boundaries** (crashes possible)

### **Quick Wins Today (4-5 hours):**
1. Add FINNIFTY symbols (5 min) ✅
2. Add universe dropdown (30 min) ✅
3. Make APIs universe-aware (2 hours) ✅
4. Add loading skeletons (1 hour) ✅
5. Basic keyboard shortcuts (1 hour) ✅

### **Next Steps:**
1. **TODAY:** Fix universe support (2-3 hours)
2. **TOMORROW:** Multi-symbol comparison (6 hours)
3. **THIS WEEK:** Keyboard shortcuts & command palette (8 hours)
4. **NEXT WEEK:** Alert system (10 hours)

---

## 🎯 START WITH THIS COMMAND

Find all hardcoded NIFTY50 references:
```powershell
grep -r "NIFTY50\|NIFTY 50" web/src/ --include="*.tsx" --include="*.ts" -n
```

Then replace systematically with universe-aware code.

**First file to edit:** `web/src/pages/TerminalBloomberg.tsx` (lines 30, 54, 87, 109, 148)

