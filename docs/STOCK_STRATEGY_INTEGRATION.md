# Stock Strategy Integration - Complete Guide

## Overview

The strategy sidebar that was previously available for options trading (NIFTY50, BANKNIFTY) has been successfully integrated into the **Stock Detail Modal** in the Terminal/Bloomberg Terminal pages. You can now execute trading strategies directly from any stock modal.

---

## ✅ What's New

### 1. **Strategy Tab in Stock Modal**
When you click on any stock in the Terminal, the detail modal now includes a **"Strategies"** tab (shown second, right after "Overview"). This tab displays:
- All available stock trading strategies
- Quick execution buttons
- Real-time execution results
- Strategy status and configuration

### 2. **Stock-Specific Strategy Support**
The system supports three types of stock strategies:
- **Momentum Strategy** (`stock_momentum_15m`) - Trades based on RSI and moving averages
- **Trend Following Strategy** (`stock_trend_following_15m`) - Follows strong trends with ADX
- **Mean Reversion Strategy** (`stock_mean_reversion_15m`) - Trades oversold/overbought conditions

### 3. **Automatic Context Passing**
When executing a strategy from the stock modal, the current stock symbol and price are automatically passed to the strategy, so it knows exactly which stock to analyze and trade.

---

## 🎯 How to Use

### Step 1: Open a Stock Modal
1. Go to **Terminal** or **Bloomberg Terminal** page
2. Click on any stock in the watchlist or market movers
3. The stock detail modal opens

### Step 2: Navigate to Strategies Tab
1. In the modal, you'll see tabs at the top
2. Click on **"Strategies"** (second tab, with a ⚡ icon)
3. You'll see all available stock strategies for that symbol

### Step 3: Execute a Strategy
1. Each strategy card shows:
   - Strategy name and type
   - Description (if available)
   - Enabled/Disabled status
   - Parameters
2. Click the **"Execute"** button on any strategy
3. The strategy will:
   - Analyze current market data for that stock
   - Generate signals based on technical indicators
   - Create a trade recommendation (BUY/SELL)
   - Execute a paper trade (if approved)

### Step 4: View Results
- After execution, you'll see a result card showing:
  - ✅ Success or ❌ Failure
  - Strategy name
  - Reason for the trade decision
  - Signal details
  - Any errors (if failed)

---

## 🔧 Creating Stock Strategies

### Option 1: Via API

```bash
curl -X POST http://localhost:8000/api/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "RELIANCE Momentum Strategy",
    "description": "15min momentum strategy for RELIANCE stock",
    "strategy_type": "stock_momentum_15m",
    "underlying": "RELIANCE",
    "parameters": {
      "min_confidence": 65,
      "rsi_threshold": 50,
      "risk_percent": 2.0,
      "reward_multiple": 1.5
    }
  }'
```

### Option 2: Via Web UI (Coming Soon)
The **"Create"** button in the Strategies tab will open a form to create new strategies directly from the UI. This feature will be added in the next update.

### Available Strategy Types

| Strategy Type | Description | Best For |
|--------------|-------------|----------|
| `stock_momentum_15m` | RSI + MA based momentum | Volatile stocks with clear trends |
| `stock_trend_following_15m` | ADX-based trend trades | Strong trending markets |
| `stock_mean_reversion_15m` | Bollinger Bands reversion | Range-bound stocks |

---

## 📊 Strategy Parameters

### Momentum Strategy Parameters
```json
{
  "min_confidence": 65,      // Minimum signal confidence (0-100)
  "rsi_threshold": 50,       // RSI level for signal generation
  "risk_percent": 2.0,       // Stop loss as % of entry price
  "reward_multiple": 1.5     // Target = risk_percent * reward_multiple
}
```

### Trend Following Parameters
```json
{
  "min_confidence": 70,
  "adx_threshold": 25,       // Minimum ADX for trend strength
  "risk_percent": 2.5,
  "reward_multiple": 2.0
}
```

### Mean Reversion Parameters
```json
{
  "min_confidence": 60,
  "bb_period": 20,           // Bollinger Bands period
  "bb_std": 2.0,             // Standard deviations
  "risk_percent": 1.5,
  "reward_multiple": 2.0
}
```

---

## 🎨 UI Components

### New Components Added

1. **`StockStrategyPanel.tsx`**
   - Located: `web/src/components/StockStrategyPanel.tsx`
   - Purpose: Displays and manages stock strategies
   - Features:
     - Lists all available strategies
     - Single-click execution
     - Real-time result display
     - Create strategy button (placeholder)

2. **Updated `StockDetailModal.tsx`**
   - Added new "Strategies" tab
   - Integrated `StockStrategyPanel` component
   - Passes current symbol and price to panel

---

## 🔄 Backend Integration

### Existing Backend Support
The backend already includes full support for stock strategies:

1. **Strategy Registry** (`backend/app/core/strategies/registry.py`)
   - Auto-registers stock strategies on startup
   - Three stock strategies pre-registered:
     - `stock_momentum_15m`
     - `stock_trend_following_15m`
     - `stock_mean_reversion_15m`

2. **Strategy Implementations**
   - `backend/app/core/strategies/stock_strategies/momentum.py`
   - `backend/app/core/strategies/stock_strategies/trend_following.py`
   - `backend/app/core/strategies/stock_strategies/mean_reversion.py`

3. **Execution Engine** (`backend/app/core/strategies/executor.py`)
   - Supports `additional_context` parameter
   - Passes symbol and price to strategies
   - Returns detailed execution results

4. **API Endpoints** (`backend/app/api/routes/execution_v2.py`)
   - `POST /strategies/run/single` - Execute one strategy
   - `POST /strategies/run/multiple` - Execute multiple strategies
   - `POST /strategies/run/all` - Execute all enabled strategies

---

## 📝 Example Usage

### Complete Flow Example

1. **User opens RELIANCE stock modal**
2. **Clicks "Strategies" tab**
3. **Sees "RELIANCE Momentum Strategy"**
4. **Clicks "Execute"**
5. **Backend receives:**
   ```json
   {
     "strategy_id": 1,
     "additional_context": {
       "symbol": "RELIANCE",
       "current_price": 2456.75
     }
   }
   ```
6. **Strategy analyzes:**
   - Fetches 15min candles for RELIANCE
   - Calculates RSI, MA, ADX indicators
   - Generates BUY/SELL signal
   - Creates trade ticket with entry/stop/target
7. **Result displayed:**
   ```
   ✅ Strategy Executed
   RELIANCE Momentum Strategy
   Reason: BUY signal - RSI bullish divergence with price above 20-MA
   ```

---

## 🚀 Next Steps

### Immediate Enhancements
1. ✅ Strategy panel integration - **DONE**
2. 🔄 Add strategy creation form in UI
3. 🔄 Add strategy editing capability
4. 🔄 Enable/disable strategies from modal
5. 🔄 Show historical performance metrics

### Future Features
- Strategy backtesting from stock modal
- Multi-timeframe strategy support
- Portfolio-aware position sizing
- Risk management integration
- Real-time P&L tracking per strategy

---

## ❓ FAQ

**Q: Do strategies work for all NIFTY 50 stocks?**  
A: Yes! Stock strategies work for any stock symbol. You can create strategies for individual stocks or generic strategies that work across multiple stocks.

**Q: Are executions real or paper trades?**  
A: By default, all executions are **paper trades** for testing. You can switch to live trading in the settings.

**Q: Can I use the same strategy for multiple stocks?**  
A: Yes! Create a strategy without specifying an `underlying`, and it will be available for all stocks.

**Q: How do I enable/disable a strategy?**  
A: Currently via API or database. UI controls are coming in the next update.

**Q: What happens if a strategy fails?**  
A: You'll see an error message with details. Check logs for more information. Common issues:
- Insufficient market data
- Technical indicators not available
- Signal confidence below minimum threshold

---

## 🐛 Troubleshooting

### Strategy Not Showing in Modal
- Check if strategy `strategy_type` is one of the stock types
- Verify strategy `underlying` matches the stock symbol or is empty
- Ensure strategy exists in database

### Execution Fails
- Check backend logs for detailed error
- Verify market data is available for the symbol
- Check if strategy is enabled in database
- Ensure API connectivity

### No Strategies Available
- Create strategies using the API endpoint
- Verify backend has registered stock strategies
- Check database connection

---

## 📞 Support

For issues or questions:
1. Check backend logs: `backend/logs/`
2. Check browser console for frontend errors
3. Verify API connectivity: `http://localhost:8000/api/docs`
4. Review strategy configurations in database

---

**Version:** 1.0  
**Last Updated:** February 8, 2026  
**Status:** ✅ Production Ready
