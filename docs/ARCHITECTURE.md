# FastTradeApp — Architecture Document

## Overview

FastTradeApp is a full-stack AI/ML-powered trading platform for Indian markets (NSE/BSE).
It supports automated and manual trading across stocks, options, futures, and indices,
with multi-broker support, real-time monitoring, backtesting, and personal finance tracking.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                                  │
│                                                                      │
│   ┌──────────────────┐   ┌──────────────────┐                       │
│   │  Web App (React) │   │ Mobile (React     │                       │
│   │  Vite + TS       │   │ Native / Expo)    │                       │
│   │  Tailwind CSS    │   │ TypeScript        │                       │
│   │  Zustand         │   │ Zustand           │                       │
│   └────────┬─────────┘   └────────┬──────────┘                      │
└────────────┼────────────────────────┼───────────────────────────────┘
             │  REST + WebSocket      │
┌────────────▼────────────────────────▼───────────────────────────────┐
│                        API LAYER (FastAPI)                           │
│                                                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │  45+ REST Routers  │  WebSocket Server  │  Auth Middleware   │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────────┐
│                        CORE ENGINE                                   │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Signals  │ │   ML     │ │  Risk    │ │Execution │ │Backtest  │  │
│  │ Engine   │ │ Engine   │ │ Manager  │ │ Adapter  │ │ Engine   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ Market   │ │ Auto     │ │ Exit     │ │Scheduler │               │
│  │ Data     │ │ Trader   │ │ Manager  │ │(APSched) │               │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘               │
└─────────────────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────────┐
│                     BROKER / DATA LAYER                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │   Zerodha    │  │  INDMoney    │  │  External Data Sources   │  │
│  │  Kite API    │  │  API         │  │  (NSE, NewsData, Twitter) │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────────┐
│                     PERSISTENCE LAYER                                │
│                                                                      │
│              SQLite (SQLAlchemy ORM)  ─  trading.db                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer       | Technology                                      |
|-------------|--------------------------------------------------|
| Backend     | Python 3.11+, FastAPI 0.110, Uvicorn             |
| ORM/DB      | SQLAlchemy 2.0, SQLite (PostgreSQL-ready)        |
| Frontend    | React 18, TypeScript, Vite, Tailwind CSS         |
| Mobile      | React Native (Expo 50), TypeScript               |
| State Mgmt  | Zustand (web + mobile)                           |
| Charts      | Lightweight Charts, Recharts, react-native-chart-kit |
| ML          | XGBoost, LightGBM, Scikit-learn, SHAP, Optuna   |
| Scheduling  | APScheduler 3.10                                 |
| Real-time   | WebSockets (websockets 12.0)                     |
| Broker APIs | Kite Connect 5.0 (Zerodha), INDMoney REST API    |
| Data        | Pandas, NumPy, SciPy, TA-Lib (ta 0.11)          |
| Monitoring  | Psutil, custom performance tracker              |

---

## Directory Structure

```
FastTradeApp/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entry point, lifespan, router registration
│   │   ├── api/
│   │   │   ├── option_spread.py     # Option spread strategy API
│   │   │   ├── system_control.py    # System on/off control
│   │   │   ├── schemas/             # Pydantic request/response models
│   │   │   └── routes/              # 45+ route modules (see API section)
│   │   ├── config/
│   │   │   └── market_config.py     # Symbols, strategies, sector config
│   │   ├── core/
│   │   │   ├── auto_trader.py       # Automated trading orchestrator
│   │   │   ├── signals/             # Signal generation (TA + ML + enrichers)
│   │   │   ├── ml/                  # ML models, features, ensemble, SHAP
│   │   │   ├── risk/                # Risk limits, circuit breaker, kill switch
│   │   │   ├── execution/           # Broker adapters (Zerodha, INDMoney, Paper)
│   │   │   ├── broker/              # Broker clients and OAuth
│   │   │   ├── backtest/            # Backtest engine + options pricing
│   │   │   ├── market/              # Market data, candles, LTP, VIX, expiry
│   │   │   ├── indicators/          # Technical indicators + Greeks
│   │   │   ├── exit/                # Auto-exit and broker reconciliation
│   │   │   ├── learning/            # Signal history and diagnostics
│   │   │   └── data/                # Candle data helpers
│   │   ├── db/
│   │   │   ├── session.py           # DB engine and session factory
│   │   │   ├── models.py            # Core ORM models
│   │   │   ├── models_finance.py    # Finance tracking models
│   │   │   └── models_*.py          # Domain-specific models
│   │   └── services/
│   │       ├── websocket.py         # WebSocket server + MTM broadcast
│   │       ├── zerodha_ticker.py    # Live quote WebSocket from Zerodha
│   │       ├── notifications.py     # Email/in-app notifications
│   │       ├── health_monitor.py    # System health + performance tracking
│   │       └── ...                  # Other service modules
│   ├── .env                         # Environment configuration
│   └── requirements.txt
├── web/
│   ├── src/
│   │   ├── main.tsx                 # React entry point
│   │   ├── pages/                   # 24 page components
│   │   ├── components/              # Reusable UI components
│   │   ├── lib/                     # API client, store, utilities
│   │   ├── api/                     # API endpoint wrappers
│   │   └── hooks/                   # Custom React hooks
│   └── package.json
└── mobile/
    ├── App.tsx                      # Expo entry point
    ├── app/                         # Expo Router screens
    ├── lib/                         # Shared utilities
    └── package.json
```

---

## Core Module Interactions

```
User Action / Scheduler Tick
         │
         ▼
  Signal Generation
  ┌─────────────────────────────────────────┐
  │  ta_engine.py  →  TA indicators         │
  │  ml_engine.py  →  XGBoost/LightGBM      │
  │  vix_iv_api.py →  VIX + IV Rank         │
  │  enrichers/    →  Asset-specific data   │
  └──────────────────┬──────────────────────┘
                     │ Signal object
                     ▼
           Risk Evaluation
  ┌─────────────────────────────────────────┐
  │  risk_limits_config.py  (IV-regime)     │
  │  circuit_breaker.py     (daily limits)  │
  │  kill_switch.py         (portfolio)     │
  │  tp_sl_calculator.py    (TP/SL levels)  │
  └──────────────────┬──────────────────────┘
                     │ Approved / Rejected
                     ▼
           Execution Adapter (factory.py)
  ┌─────────────────────────────────────────┐
  │  PaperExecutionAdapter  (paper trading) │
  │  ZerodhaExecutionAdapter (live/dry-run) │
  │  INDMoneyExecutionAdapter               │
  └──────────────────┬──────────────────────┘
                     │ Order placed
                     ▼
           StrategyRun saved to DB
                     │
                     ▼
           Auto-Exit Monitor (APScheduler)
  ┌─────────────────────────────────────────┐
  │  auto_exit.py  →  TP/SL/trailing check  │
  │  expiry_exit.py → Near-expiry exit      │
  │  broker_reconcile.py → Sync positions   │
  └─────────────────────────────────────────┘
```

---

## Database Schema (Key Tables)

| Table                  | Purpose                                      |
|------------------------|----------------------------------------------|
| strategy_runs          | All executed trades with P&L, signal, ticket |
| daily_capital          | Daily portfolio capital snapshots            |
| vix_historic           | Historic VIX + IV Rank data                  |
| strategy_configs       | User-defined strategy configurations         |
| backtest_results       | Backtest run summaries                       |
| backtest_trades        | Individual trades from backtests             |
| symbols                | Stock/index metadata and fundamentals        |
| market_data            | OHLCV candle data                            |
| alert_rules            | Dynamic price/technical alerts               |
| auto_trader_config     | Auto-trader settings                         |
| auto_trader_log        | Auto-trader execution log                    |
| risk_limit_config      | Configurable risk limits                     |
| signal_outcomes        | Signal performance tracking                  |
| scanner_signal_history | Historical scanner signals                   |
| finance_transactions   | Personal finance transactions                |
| budgets                | Monthly budget categories                    |
| savings_goals          | Savings targets                              |
| bill_reminders         | Bill payment reminders                       |
| notifications          | In-app notification records                  |
| watchlists             | Custom symbol watchlists                     |
| zerodha_sessions       | Zerodha OAuth session storage                |

---

## Execution Modes

| Mode          | Description                                      |
|---------------|--------------------------------------------------|
| PAPER_TRADING | Simulated trades, no real orders placed          |
| DRY_RUN       | Real broker API called but orders not submitted  |
| LIVE          | Real orders placed with the active broker        |

Controlled via `EXECUTION_MODE` env variable. Broker selected via `ACTIVE_BROKER`.

---

## Scheduler Jobs (APScheduler)

| Job                          | Frequency       | Purpose                              |
|------------------------------|-----------------|--------------------------------------|
| start_candle_scheduler       | Every 5 min     | Fetch intraday candles               |
| start_daily_candles_scheduler| Daily (delayed) | Backfill daily OHLCV data            |
| start_intraday_candles_scheduler | Every 3 min | 5m + 1h candle updates               |
| start_vix_scheduler          | Daily (delayed) | Update VIX + IV Rank                 |
| start_auto_exit_scheduler    | Continuous      | Monitor TP/SL/trailing stops         |
| start_expiry_exit_scheduler  | Daily           | Auto-exit options near expiry        |
| start_twitter_sentiment_scheduler | Periodic  | Fetch Twitter market sentiment       |
