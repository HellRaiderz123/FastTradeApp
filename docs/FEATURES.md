# FastTradeApp — Feature Reference

## 1. Trading Execution

### Manual Trade Execution
- Place buy/sell orders for stocks, options, and futures
- Support for NRML, MIS, and CNC product types
- Market and limit order types
- Real-time order status tracking

### Automated Trading (Auto-Trader)
- Signal-based automated entry and exit
- Configurable scan interval (default 30 seconds)
- Daily trade counter with configurable max trades
- Auto-resume after server restart (persists state in DB)
- Reversal handling: auto-exit or hedge on signal flip
- Market hours filtering (no trades outside NSE hours)

### Paper Trading
- Full simulation with no real capital at risk
- Mark-to-market (MTM) calculations in real time
- Tracks unrealized P&L per position
- Identical flow to live trading for testing strategies

### Multi-Broker Support
- Zerodha (Kite Connect 5.0): full order, position, and live data
- INDMoney: order placement and position tracking
- Factory pattern — swap brokers via single env variable
- Dry-run mode: calls broker API without submitting orders

### Option Spread Strategies
- Bull Call Spread, Bear Put Spread
- Iron Condor, Iron Butterfly
- Credit spread P&L and Greeks calculation
- Spread grouping view in UI

---

## 2. Signal Generation

### Technical Analysis Engine
Indicators computed on 15-minute candles by default:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ADX + DI+/DI- (trend strength)
- EMA 20/50/200
- SMA
- ATR (Average True Range)
- Stochastic Oscillator
- Volume analysis

### ML Signal Engine
- Ensemble model: XGBoost + LightGBM + Random Forest (soft voting)
- Weights: 35% XGBoost, 30% RF, 35% LightGBM
- Feature engineering: 20+ technical features
- Walk-forward validation to prevent lookahead bias
- SHAP explainability for each prediction
- Configurable confidence thresholds
- Optuna hyperparameter optimization
- Model versioning and registry

### Signal Enrichers (per asset type)
- Stock Enricher: fundamentals, sector, peer comparison
- Option Enricher: Greeks, IV, moneyness, days-to-expiry
- Future Enricher: basis, rollover data
- Index Enricher: breadth, advance/decline

### VIX & IV Regime
- India VIX fetched and stored daily
- 52-week IV Rank calculation
- IV Regime classification: LOW / NORMAL / HIGH
- Regime-aware risk limits (different sizing per regime)

---

## 3. Risk Management

### Trade-Level Controls
- Configurable risk % per trade (default 2%)
- TP/SL calculator with ATR-based levels
- Trailing stop-loss support
- Cost-adjusted P&L (brokerage, STT, exchange fees)

### Portfolio-Level Controls
- Max trades per day (configurable, default 3–5)
- Max portfolio loss % per day
- Circuit breaker: halts trading after threshold breach
- Kill switch: immediate halt of all new trades
- Drawdown tracker with alerts

### IV-Regime Risk Limits
| Regime | Min ATM Distance | Max Risk % Capital |
|--------|------------------|--------------------|
| LOW    | 0.5%             | 4.0%               |
| NORMAL | 0.6%             | 2.0%               |
| HIGH   | 0.8%             | 5.0%               |

### System Guard
- Validates system state before each trade
- Checks market hours, broker connectivity, daily limits

---

## 4. Backtesting

### Core Backtest Engine
- Historical simulation on OHLCV data
- Configurable date range, capital, and strategy parameters
- Trade-by-trade P&L tracking

### Options Backtest Engine
- Black-Scholes pricing for historical options
- Greeks simulation over time
- Expiry handling and assignment simulation

### Performance Metrics
- Total return, CAGR
- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- Maximum Drawdown (absolute and %)
- Win rate, average win/loss
- Profit factor

### Backtest Comparison
- Side-by-side comparison of multiple backtest runs
- Visual equity curve overlay

### Walk-Forward Validation
- Out-of-sample testing to validate ML models
- Prevents overfitting on historical data

---

## 5. Market Data & Analysis

### Live Data
- Real-time LTP (Last Traded Price) via Zerodha WebSocket ticker
- Option chain with live Greeks
- Market depth (bid/ask ladder)
- Sector performance heatmap

### Historical Data
- Daily OHLCV candles (up to 900 days)
- Intraday candles: 1m, 5m, 15m, 1h
- Automatic backfill on startup (configurable delay)
- Zerodha historic data fetcher

### Market Calendar
- NSE trading holidays
- Market open/close hours
- Options expiry dates (weekly + monthly)

### Economic Calendar
- Upcoming economic events (RBI policy, GDP, CPI, etc.)
- Impact classification (high/medium/low)

---

## 6. Screening & Scanning

### Stock Screener
- Filter by RSI, MACD, ADX, volume, price range
- Sector and index filters
- Fundamental filters (P/E, market cap)

### Swing Scanner
- Momentum Breakout: ADX > 25, volume surge, RSI > 50
- Oversold Bounce: RSI < 35, MACD crossover
- Trend Following: ADX > 25, consistent direction
- Volume Surge: 2x average volume with breakout
- Mean Reversion: price deviation from moving average

### Condition-Based Scanner
- User-defined multi-condition strategies
- Auto-scan on schedule
- Signal history tracking and diagnostics

### Multi-Timeframe Analysis
- Simultaneous view of 1m, 5m, 15m, 1h, daily, weekly
- Timeframe confluence scoring

---

## 7. Options Tools

### Options Chain Viewer
- Full chain with strikes, OI, volume, IV, Greeks
- PCR (Put/Call Ratio) per strike and total
- Max pain calculation
- OI change visualization

### Greeks Calculator
- Delta, Gamma, Theta, Vega, Rho
- Black-Scholes model
- Portfolio-level Greeks aggregation

### IV Tools
- IV Rank (52-week percentile)
- IV Percentile
- IV Regime classification
- Historical IV chart

---

## 8. Intelligence & Sentiment

### News Feed
- NewsData API integration
- Stock-specific news filtering
- RSS feed parsing for financial news
- Trending topics detection

### Twitter Sentiment
- Twitter API v2 integration
- Market sentiment scoring per symbol
- Scheduled sentiment updates
- Sentiment alerts

### ML Intelligence Center
- Model training and retraining UI
- Feature importance visualization (SHAP)
- Signal performance diagnostics
- Correlation analysis across symbols
- News sentiment model

---

## 9. Monitoring & Alerts

### Alert System
- Price alerts (above/below threshold)
- Technical alerts (RSI overbought/oversold, MACD cross)
- Fundamental alerts
- Custom condition alerts
- Email notifications (Gmail SMTP)

### Real-Time Position Monitoring
- WebSocket-based live P&L updates
- Zerodha positions widget
- INDMoney positions widget
- Paper trading MTM widget

### System Health
- API response time tracking
- Scheduler status monitoring
- Broker connectivity checks
- Psutil-based resource monitoring

### Notifications
- In-app notification center
- Email alerts (configurable recipients)
- Trade execution confirmations
- Risk limit breach alerts

---

## 10. Trade Journal

- Log every trade with entry/exit, rationale, and outcome
- Signal snapshot at time of trade
- P&L tracking per journal entry
- Signal diagnostics and outcome analysis
- Export capability

---

## 11. Personal Finance Tracker

### Transaction Management
- Bank transaction import and categorization
- Recurring transaction tracking
- Currency exchange rate tracking

### Budgeting
- Monthly budgets by category
- Actual vs. budget comparison
- Overspend alerts

### Savings Goals
- Target amount and deadline
- Progress tracking
- Contribution scheduling

### Bill Reminders
- Due date tracking
- Payment status
- Recurring bill management

### Expense Forecasting
- ML-based expense prediction
- Historical trend analysis

---

## 12. Portfolio Analytics

### Daily Capital Tracking
- Opening and closing capital per day
- Daily return %
- Portfolio growth curve

### Trade Cost Analysis
- Brokerage fees (Zerodha slab-based)
- STT, exchange fees, GST
- Cost-adjusted P&L
- Cost breakdown per trade

### Peer Comparison
- Compare stock performance vs. sector peers
- Relative strength analysis

### Watchlists
- Multiple custom watchlists
- Quick quote view
- Alert integration

---

## 13. Configuration & Settings

### Execution Settings
- Switch between PAPER / DRY_RUN / LIVE
- Switch active broker (Zerodha / INDMoney)
- Product type (NRML / MIS / CNC)

### Risk Settings
- Risk per trade %
- Max trades per day
- IV-regime specific limits
- Circuit breaker thresholds

### ML Settings
- Enable/disable ML signals
- Model directory and name
- Feature parameters (RSI period, EMA windows, etc.)
- Confidence thresholds

### Notification Settings
- Gmail SMTP configuration
- Alert email recipients
- Notification types to enable

### Market Universe
- Select from NIFTY50, NIFTY100, BANKNIFTY, FINNIFTY, NIFTY_IT
- Custom symbol lists

---

## 14. UI Features (Web)

| Page                  | Description                                      |
|-----------------------|--------------------------------------------------|
| Dashboard             | Overview widgets, market summary                 |
| Draggable Dashboard   | Fully customizable widget layout                 |
| Positions             | Live position monitoring                         |
| Strategies            | Strategy list and management                     |
| Strategy Builder      | Visual strategy creation                         |
| Backtest              | Run and view backtest results                    |
| Backtest Comparison   | Compare multiple backtest runs                   |
| Terminal              | Trading terminal                                 |
| Terminal (Bloomberg)  | Bloomberg-style professional terminal            |
| Options Chain         | Full options chain viewer                        |
| Screener              | Stock screener with filters                      |
| Journal               | Trade journal                                    |
| Auto-Trader           | Auto-trader control panel                        |
| ML Center             | ML model management and training                 |
| ML Intelligence       | Signal analysis and SHAP explanations            |
| Finance Tracker       | Personal finance dashboard                       |
| Trade Cost Tracker    | Brokerage cost analysis                          |
| Calendar              | Economic events calendar                         |
| Heatmap               | Sector/stock performance heatmap                 |
| Multi-Timeframe       | Multi-timeframe chart analysis                   |
| Custom Watchlists     | Watchlist management                             |
| Create Scanner        | Custom scanner builder                           |
| Settings              | App configuration                                |
| Login                 | Authentication                                   |
