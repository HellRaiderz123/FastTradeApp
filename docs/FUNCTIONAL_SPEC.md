# FastTradeApp — Functional Specification

## Application Identity

- Name: FastTradeApp
- Version: 2.0.0
- Domain: Indian equity and derivatives trading (NSE/BSE)
- Target Users: Retail traders and algo traders in India

---

## User Roles

| Role  | Access                                                        |
|-------|---------------------------------------------------------------|
| Admin | Full access to all features including system control          |
| User  | Trading, analysis, and monitoring (auth optional via env var) |

Authentication is JWT-based, toggled via `AUTH_ENABLED` env variable.
Default credentials: admin / admin123 (must be changed in production).

---

## Core User Flows

### Flow 1: Manual Trade Execution

1. User opens Terminal or Positions page
2. Selects symbol, asset type, quantity, order type
3. System validates against risk limits (daily trade count, capital %)
4. If approved: order sent to active broker adapter
5. StrategyRun record created in DB with signal snapshot
6. Position appears in live positions view
7. Auto-exit monitor begins watching TP/SL levels

### Flow 2: Automated Trading

1. Admin configures Auto-Trader (scan interval, max trades, strategy)
2. Auto-Trader starts scanning on schedule (APScheduler)
3. For each symbol in universe:
   a. Generate signal (TA + optional ML)
   b. Evaluate against risk limits
   c. If approved: execute via broker adapter
   d. Log to auto_trader_log table
4. On signal reversal: auto-exit or hedge based on config
5. Daily counters reset at market open

### Flow 3: Backtesting a Strategy

1. User navigates to Backtest page
2. Selects strategy, symbol, date range, capital
3. Backend runs simulation on stored OHLCV data
4. Results saved to backtest_results + backtest_trades tables
5. UI displays equity curve, metrics, trade list
6. User can compare multiple runs on Backtest Comparison page

### Flow 4: Options Analysis

1. User opens Options Chain page
2. Selects underlying (NIFTY, BANKNIFTY, or stock)
3. System fetches live chain from Zerodha
4. Displays strikes with OI, volume, IV, Delta, Gamma, Theta
5. User can select legs to build a spread
6. Greeks and payoff calculated in real time
7. User executes spread via Execute button

### Flow 5: Signal Generation

1. Triggered by: Auto-Trader scan, manual suggestion request, or API call
2. TA engine computes indicators on 15m candles
3. ML engine (if enabled) generates probability score
4. VIX/IV data fetched (cached, refreshed every 2 min)
5. Asset-specific enricher adds context (Greeks, sector, etc.)
6. Signal object returned with: strength, bias, IV regime, confidence
7. Signal stored in scanner_signal_history for diagnostics

### Flow 6: Alert Triggered

1. User creates alert rule (price threshold, technical condition)
2. Scheduler checks alert conditions periodically
3. On trigger: notification created in DB
4. Email sent if Gmail configured
5. In-app notification bell shows unread count
6. WebSocket pushes notification to connected clients

---

## API Reference Summary

### Authentication
| Method | Endpoint         | Description              |
|--------|------------------|--------------------------|
| POST   | /auth/login      | Get JWT token            |
| POST   | /auth/logout     | Invalidate token         |
| GET    | /auth/me         | Current user info        |

### Trading
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| POST   | /execute/order              | Place a trade order            |
| POST   | /strategy/spread            | Execute option spread          |
| GET    | /account/positions          | Get current positions          |
| GET    | /account/portfolio          | Portfolio summary              |
| POST   | /exit/position              | Exit a position                |
| POST   | /auto-exit/config           | Configure auto-exit rules      |

### Strategies
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | /strategies                 | List all strategies            |
| POST   | /strategies                 | Create strategy                |
| PUT    | /strategies/{id}            | Update strategy                |
| DELETE | /strategies/{id}            | Delete strategy                |
| POST   | /backtest/run               | Run backtest                   |
| GET    | /backtest/results           | List backtest results          |

### Market Data
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | /market/quote/{symbol}      | Get live quote                 |
| GET    | /market/candles             | Get OHLCV candles              |
| GET    | /market/option-chain        | Get options chain              |
| GET    | /market/sector-performance  | Sector heatmap data            |
| GET    | /market-dashboard/summary   | Dashboard aggregated data      |
| GET    | /market-depth/{symbol}      | Bid/ask depth                  |

### Signals & Suggestions
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | /suggestions/{symbol}       | Trade suggestions              |
| GET    | /stock-suggestions          | Stock-specific suggestions     |
| GET    | /position-suggestions       | Position recommendations       |
| GET    | /timeframe-suggestions      | Timeframe recommendations      |

### Screening
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| POST   | /screener/scan              | Run stock screener             |
| POST   | /swing-scanner/scan         | Run swing scanner              |
| POST   | /condition-scanner/scan     | Run condition-based scanner    |

### Options
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | /options/chain              | Options chain data             |
| GET    | /options-real/chain         | Live options chain             |
| POST   | /greeks/calculate           | Calculate Greeks               |

### ML
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| POST   | /ml/train                   | Train ML model                 |
| GET    | /ml/models                  | List trained models            |
| POST   | /ml/predict                 | Get ML prediction              |
| GET    | /ml/shap/{model_id}         | SHAP explanation               |

### Finance
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | /finance/transactions       | List transactions              |
| POST   | /finance/transactions       | Add transaction                |
| GET    | /finance/budgets            | Get budgets                    |
| POST   | /finance/budgets            | Create budget                  |
| GET    | /finance/savings-goals      | List savings goals             |
| GET    | /finance/bill-reminders     | List bill reminders            |
| GET    | /finance/forecast           | Expense forecast               |

### Monitoring
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | /health                     | System health check            |
| GET    | /notifications              | List notifications             |
| GET    | /alerts                     | List alert rules               |
| POST   | /alerts                     | Create alert rule              |
| WS     | /ws/positions               | Real-time position updates     |
| WS     | /ws/market                  | Real-time market data          |

### Broker
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| GET    | /zerodha/positions          | Zerodha live positions         |
| GET    | /zerodha/orders             | Zerodha order history          |
| GET    | /indmoney/positions         | INDMoney positions             |
| GET    | /paper-mtm                  | Paper trading MTM              |

### System
| Method | Endpoint                    | Description                    |
|--------|-----------------------------|--------------------------------|
| POST   | /system/start               | Start trading system           |
| POST   | /system/stop                | Stop trading system            |
| GET    | /system/status              | System status                  |
| GET    | /auto-trader/status         | Auto-trader status             |
| POST   | /auto-trader/start          | Start auto-trader              |
| POST   | /auto-trader/stop           | Stop auto-trader               |

---

## Signal Object Structure

```json
{
  "symbol": "NIFTY",
  "asset_type": "OPTION",
  "signal_strength": "STRONG_BUY",
  "market_bias": "BULLISH",
  "iv_regime": "NORMAL",
  "confidence": 0.72,
  "indicators": {
    "rsi": 58.4,
    "macd_signal": "BULLISH_CROSS",
    "adx": 28.1,
    "ema_trend": "ABOVE_50",
    "bollinger": "MIDDLE_BAND"
  },
  "ml_probability": 0.68,
  "vix": 14.2,
  "iv_rank": 42.0,
  "greeks": {
    "delta": 0.45,
    "gamma": 0.02,
    "theta": -12.5,
    "vega": 8.3
  },
  "generated_at": "2026-03-20T10:15:00+05:30"
}
```

---

## Risk Evaluation Flow

```
Signal Generated
      │
      ▼
Is kill switch active?  ──YES──► Reject
      │ NO
      ▼
Is circuit breaker tripped?  ──YES──► Reject
      │ NO
      ▼
Daily trade count < max?  ──NO──► Reject
      │ YES
      ▼
Capital available > risk %?  ──NO──► Reject
      │ YES
      ▼
IV regime limits satisfied?  ──NO──► Reject
      │ YES
      ▼
Market hours check  ──FAIL──► Reject
      │ PASS
      ▼
APPROVED → Execute
```

---

## Environment Configuration Reference

| Variable                    | Default          | Description                          |
|-----------------------------|------------------|--------------------------------------|
| EXECUTION_MODE              | PAPER_TRADING    | PAPER_TRADING / DRY_RUN / LIVE       |
| ACTIVE_BROKER               | ZERODHA          | ZERODHA / INDMONEY                   |
| ZERODHA_API_KEY             | —                | Kite Connect API key                 |
| ZERODHA_API_SECRET          | —                | Kite Connect API secret              |
| ZERODHA_ACCESS_TOKEN        | —                | Daily access token                   |
| RISK_PER_TRADE              | 2                | Risk % per trade                     |
| MAX_TRADES_PER_DAY          | 5                | Max daily trades                     |
| AUTH_ENABLED                | false            | Enable JWT authentication            |
| AUTH_USERNAME               | admin            | Login username                       |
| AUTH_PASSWORD               | admin123         | Login password (change this!)        |
| STOCK_ML_ENABLED            | false            | Enable ML signal generation          |
| NEWSDATA_API_KEY            | —                | NewsData.io API key                  |
| NOTIFY_GMAIL_ENABLED        | false            | Enable email notifications           |
| GMAIL_USER                  | —                | Gmail sender address                 |
| GMAIL_APP_PASSWORD          | —                | Gmail app password                   |
| DAILY_BACKFILL_DELAY_MINUTES| 5                | Delay before daily candle backfill   |
| DATABASE_URL                | sqlite:///...    | Database connection string           |
| LOG_LEVEL                   | INFO             | Logging level                        |
| JSON_LOGS                   | false            | Structured JSON logging              |
