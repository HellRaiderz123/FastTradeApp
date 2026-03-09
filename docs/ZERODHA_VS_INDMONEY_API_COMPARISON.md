# Zerodha KiteConnect vs INDMoney/INDstocks API Comparison

**Analysis Date:** March 9, 2026  
**Purpose:** Determine if INDMoney can replace all Zerodha features in FastTradeApp

---

## Executive Summary

✅ **CAN MIGRATE:** Order execution, positions, holdings, portfolio funds  
⚠️ **PARTIAL SUPPORT:** Market data (quotes, historical candles)  
❌ **CANNOT MIGRATE:** Instruments master, WebSocket streaming (different format)  

**Recommendation:** **Hybrid approach** - Use INDMoney for order execution only, keep Zerodha for market data infrastructure.

---

## Detailed Feature Comparison

### 1. ✅ ORDER MANAGEMENT APIs (Full Parity)

| Feature | Zerodha KiteConnect | INDstocks API | Migration Status | Notes |
|---------|---------------------|---------------|------------------|-------|
| **Place Order** | `kite.place_order()` | `POST /order` | ✅ **YES** | Both support MARKET/LIMIT/SL/SL-M |
| **Modify Order** | `kite.modify_order()` | `POST /order/modify` | ✅ **YES** | Same parameters |
| **Cancel Order** | `kite.cancel_order()` | `POST /order/cancel` | ✅ **YES** | Same flow |
| **Order Book** | `kite.orders()` | `GET /order-book` | ✅ **YES** | Day's orders with status |
| **Order History** | `kite.order_history()` | `GET /order` | ✅ **YES** | Single order details |
| **Trade Book** | `kite.trades()` | `GET /trade-book` | ✅ **YES** | Executed trades |
| **Order Fills** | `kite.order_trades()` | `GET /trades/{order_id}` | ✅ **YES** | Per-order trade details |

**Migration Risk:** 🟢 **LOW** - Direct 1:1 mapping, already implemented

---

### 2. ✅ POSITIONS & HOLDINGS APIs (Full Parity)

| Feature | Zerodha KiteConnect | INDstocks API | Migration Status | Notes |
|---------|---------------------|---------------|------------------|-------|
| **Positions** | `kite.positions()` | `GET /portfolio/positions` | ✅ **YES** | Net/day positions |
| **Holdings** | `kite.holdings()` | `GET /portfolio/holdings` | ✅ **YES** | Demat stocks |
| **Funds/Margins** | `kite.margins()` | `GET /funds` | ✅ **YES** | Available balance, P&L |
| **Margin Calculator** | Not available | `GET /margin` | ✅ **BETTER** | Pre-trade margin check |

**Migration Risk:** 🟢 **LOW** - INDstocks has equal or better support

---

### 3. ⚠️ MARKET DATA APIs (Partial Parity)

| Feature | Zerodha KiteConnect | INDstocks API | Migration Status | Notes |
|---------|---------------------|---------------|------------------|-------|
| **LTP (Last Price)** | `kite.ltp()` | `GET /market/quotes/ltp` | ⚠️ **DIFFERENT** | Zerodha uses tokens, IND uses scrip codes |
| **Full Quote** | `kite.quote()` | `GET /market/quotes/full` | ⚠️ **DIFFERENT** | Different response schema |
| **OHLC Data** | `kite.ohlc()` | `GET /market/quotes/full` | ⚠️ **DIFFERENT** | IND includes in full quote |
| **Market Depth** | `kite.quote()` depth field | `GET /market/quotes/mkt` | ⚠️ **DIFFERENT** | Separate endpoint in IND |
| **Historical Candles** | `kite.historical_data()` | `GET /market/historical/{interval}` | ⚠️ **YES** | **MAJOR ISSUE: Different intervals** |

**Candle Interval Comparison:**

| Your App Uses | Zerodha | INDstocks | Status |
|---------------|---------|-----------|--------|
| 1 minute | ✅ `minute` | ✅ `1minute` | ✅ Available |
| 5 minute | ✅ `5minute` | ✅ `5minute` | ✅ Available |
| 15 minute | ✅ `15minute` | ✅ `15minute` | ✅ Available |
| 1 hour | ✅ `60minute` | ✅ `60minute` | ✅ Available |
| Daily | ✅ `day` | ✅ `1day` | ✅ Available |

**Migration Risk:** 🟡 **MEDIUM** - Requires adapter layer to normalize response formats

---

### 4. ❌ INSTRUMENTS MASTER (Critical Gap)

| Feature | Zerodha KiteConnect | INDstocks API | Migration Status | Notes |
|---------|---------------------|---------------|------------------|-------|
| **Instruments CSV** | `kite.instruments()` | `GET /market/instruments` | ❌ **DIFFERENT FORMAT** | **BLOCKING ISSUE** |
| **Search by Symbol** | In-memory search | CSV parsing required | ❌ **MORE WORK** | Need to cache/index CSV |
| **Token Mapping** | `instrument_token` | `security_id` | ❌ **INCOMPATIBLE** | All code uses tokens |

**Current Usage in Your App:**
```python
# backend/app/core/broker/zerodha/instruments.py
instruments = kite.instruments("NFO")  # Returns list of dicts
df = pd.DataFrame(instruments)
# Used in: options chain, symbol search, expiry lookups
```

**INDstocks Equivalent:**
```python
# Returns CSV file (not JSON)
response = requests.get("https://api.indstocks.com/market/instruments?source=fno")
csv_content = response.text  # Need to parse manually
```

**Migration Risk:** 🔴 **HIGH** - Requires complete rewrite of instruments caching layer

---

### 5. ❌ WEBSOCKET STREAMING (Format Incompatibility)

| Feature | Zerodha KiteTicker | INDstocks WebSocket | Migration Status | Notes |
|---------|---------------------|---------------------|------------------|-------|
| **Connection** | `wss://ws.kite.trade` | `wss://ws-prices.indstocks.com/api/v1/ws/prices` | ⚠️ **DIFFERENT** | Different hosts |
| **Auth Method** | Token in connect | Header in handshake | ⚠️ **DIFFERENT** | Different auth flow |
| **Subscribe Format** | Binary protocol | JSON messages | ❌ **INCOMPATIBLE** | Complete rewrite needed |
| **Data Format** | Binary packed | JSON | ❌ **INCOMPATIBLE** | Parser rewrite needed |
| **Modes** | LTP/Quote/Full | ltp/quote | ⚠️ **SIMILAR** | Conceptually same |

**Current Implementation:**
```python
# backend/app/services/zerodha_ticker.py - 200+ lines
from kiteconnect import KiteTicker
kws = KiteTicker(api_key, access_token)
kws.on_ticks = on_ticks  # Binary tick parsing
kws.connect()
```

**INDstocks Equivalent:**
```python
# Would need complete rewrite
import websocket
ws = websocket.create_connection("wss://ws-prices.indstocks.com/api/v1/ws/prices",
                                  header={"Authorization": token})
ws.send(json.dumps({"action": "subscribe", "mode": "ltp", "instruments": [...]}))
# Handle JSON messages instead of binary
```

**Migration Risk:** 🔴 **CRITICAL** - 200+ lines of WebSocket code needs replacement

---

### 6. ⚠️ USER PROFILE & SESSION APIs (Partial Parity)

| Feature | Zerodha KiteConnect | INDstocks API | Migration Status | Notes |
|---------|---------------------|---------------|------------------|-------|
| **User Profile** | `kite.profile()` | `GET /user/profile` | ✅ **YES** | User ID, email, name |
| **OAuth Login** | Custom OAuth flow | Not documented | ❌ **NO** | Only access token supported |
| **Session Management** | `kite.invalidate_token()` | Not documented | ❌ **NO** | Manual token management |

**Migration Risk:** 🟡 **MEDIUM** - OAuth features won't work with INDMoney

---

## Current Zerodha Usage in Your App

### Files Using Zerodha APIs (50+ matches found):

1. **Order Execution** (✅ Can migrate)
   - `app/core/execution/zerodha.py` - Order placement adapter
   - `app/core/exit/auto_exit.py` - Auto TP/SL exits
   - `app/api/routes/execute.py` - Manual execution

2. **Market Data** (⚠️ Hard to migrate)
   - `app/services/zerodha.py` - Main KiteConnect wrapper (300+ lines)
   - `app/api/routes/market.py` - Live quotes, LTP, bulk quotes
   - `app/api/routes/options.py` - Options chain with Greeks
   - `app/api/routes/market_depth.py` - Order book depth
   - `app/services/websocket_routes.py` - Real-time price feeds

3. **Instruments & Symbols** (❌ Cannot migrate easily)
   - `app/core/broker/zerodha/instruments.py` - Instruments caching
   - `app/core/broker/zerodha_symbols.py` - Option symbol builder

4. **Positions & Holdings** (✅ Can migrate)
   - `app/api/routes/zerodha_broker.py` - Positions/holdings/orders
   - `app/core/exit/broker_reconcile.py` - Position sync

5. **WebSocket Streaming** (❌ Complete rewrite needed)
   - `app/services/zerodha_ticker.py` - KiteTicker manager (200+ lines)

---

## Migration Strategy Recommendation

### ✅ **RECOMMENDED: Hybrid Approach** (Already Implemented!)

Your current implementation is **correct** - use each broker for what it does best:

| Feature | Use Broker | Reason |
|---------|-----------|--------|
| **Order Execution** | INDMoney | Lower costs, smart orders (GTT) |
| **Market Data** | Zerodha | Stable APIs, existing caching |
| **WebSocket Streaming** | Zerodha | Already implemented, battle-tested |
| **Instruments Master** | Zerodha | In-memory cache working |
| **Positions Check** | Both | Switch based on active broker |

### Implementation:

```python
# Market data - always Zerodha
from app.services.zerodha import KiteConnectService
kite = KiteConnectService()
quote = kite.get_quote("NIFTY")  # Always use Zerodha

# Order execution - switched dynamically
from app.core.execution.factory import get_execution_adapter
broker = os.getenv("ACTIVE_BROKER", "ZERODHA")
executor = get_execution_adapter(mode="LIVE", broker=broker)
executor.execute(strategy_legs)  # Uses INDMoney or Zerodha
```

---

## If You Want Full Migration (Not Recommended)

### Required Changes:

1. **Instruments Master Adapter** (~500 lines)
   - Parse INDstocks CSV format
   - Build token→symbol lookup cache
   - Replace all `instrument_token` with `security_id`

2. **Market Data Abstraction** (~800 lines)
   - Create broker-agnostic quote interface
   - Normalize Zerodha vs INDstocks response schemas
   - Handle different scrip code formats

3. **WebSocket Rewrite** (~300 lines)
   - Replace KiteTicker with INDstocks WebSocket
   - Convert binary parser to JSON parser
   - Update all tick handlers

4. **Historical Data Adapter** (~200 lines)
   - Map interval names (Zerodha `minute` → IND `1minute`)
   - Convert response formats
   - Handle epoch timestamp differences

**Total Effort:** ~1800 lines of code + testing  
**Risk:** High - breaking existing market data flows  
**Benefit:** Minimal - Zerodha market data works well

---

## Answer to Your Question

> "Can all Zerodha APIs be replaced by INDMoney?"

### Short Answer: **NO - Not Recommended**

### Detailed Answer:

✅ **Order APIs:** Yes, INDMoney can fully replace (already done)  
❌ **Market Data:** Technically possible, but requires massive rewrite  
❌ **WebSocket:** Complete incompatibility, full rewrite needed  
❌ **Instruments:** Different format, need new caching layer  

### Best Approach: **Keep Current Hybrid Model**

**What You Have Now is Optimal:**
- ✅ Market data from Zerodha (stable, cached, working)
- ✅ Order execution switches via `ACTIVE_BROKER` env var
- ✅ User can choose INDMoney for orders, Zerodha for data
- ✅ No breaking changes to existing features

---

## Next Steps

### Option 1: Keep Hybrid (Recommended) ✅
**Status:** Already implemented  
**Action:** None needed, just document the design  
**Benefit:** Best of both brokers

### Option 2: Add Dynamic Market Data Switching (Medium Effort)
**Effort:** ~800 lines  
**Benefit:** Users can choose market data source  
**Use case:** If INDMoney has better data quality/lower costs  
**Implementation:** Create `MarketDataFactory` similar to `ExecutionFactory`

### Option 3: Full Migration (Not Recommended) ❌
**Effort:** ~1800 lines + high risk  
**Benefit:** Single API dependency  
**Drawback:** Break existing features, no clear advantage

---

## Conclusion

Your **current implementation is correct** - using INDMoney for order execution while keeping Zerodha for market data infrastructure is the best approach. This gives you:

1. ✅ Lower execution costs (if INDMoney is cheaper)
2. ✅ Stable, tested market data pipeline
3. ✅ No breaking changes
4. ✅ Easy to switch brokers for orders

**No action needed** - your architecture is already optimal! 🎯
