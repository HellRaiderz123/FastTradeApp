# FastTradeApp — Documentation Index

## What is FastTradeApp?

FastTradeApp is a full-stack AI/ML-powered trading platform for Indian markets (NSE/BSE).
It combines automated signal generation, multi-broker execution, real-time monitoring,
backtesting, and personal finance tracking in a single application.

---

## Documentation

| Document                                  | Description                                      |
|-------------------------------------------|--------------------------------------------------|
| [ARCHITECTURE.md](./ARCHITECTURE.md)      | System design, tech stack, data flow diagrams    |
| [FEATURES.md](./FEATURES.md)              | Complete feature reference across all modules    |
| [FUNCTIONAL_SPEC.md](./FUNCTIONAL_SPEC.md)| API reference, user flows, data structures       |
| [ENHANCEMENTS.md](./ENHANCEMENTS.md)      | Suggested improvements and roadmap               |

---

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
# Configure .env (copy from .env.example and fill in Zerodha keys)
uvicorn app.main:app --reload --port 8000
```

### Frontend (Web)
```bash
cd web
npm install
npm run dev
# Opens at http://localhost:5173
```

### Mobile
```bash
cd mobile
npm install
npx expo start
```

### API Docs
Once backend is running: http://localhost:8000/docs

---

## Key Configuration

1. Set `EXECUTION_MODE=PAPER_TRADING` to start safely (no real orders)
2. Add Zerodha API keys to `backend/.env`
3. Set `AUTH_ENABLED=false` for local dev (change for production)
4. Set `RISK_PER_TRADE=2` and `MAX_TRADES_PER_DAY=5` as starting risk limits

---

## Feature Summary

| Category              | Key Features                                              |
|-----------------------|-----------------------------------------------------------|
| Trading               | Manual + automated, paper trading, multi-broker           |
| Signals               | TA (15+ indicators) + ML ensemble (XGBoost + LightGBM)   |
| Options               | Full chain, Greeks, spreads, IV Rank, PCR                 |
| Risk                  | Circuit breaker, kill switch, IV-regime limits, TP/SL     |
| Backtesting           | Historical simulation, options pricing, walk-forward      |
| Screening             | Swing scanner, condition scanner, stock screener          |
| Intelligence          | News sentiment, Twitter sentiment, SHAP explainability    |
| Monitoring            | Real-time WebSocket, alerts, email notifications          |
| Finance               | Transactions, budgets, savings goals, expense forecast    |
| Analytics             | P&L tracking, trade costs, peer comparison, heatmap       |

---

## Architecture at a Glance

```
React Web App  ──┐
                 ├──► FastAPI Backend ──► Zerodha / INDMoney
React Native  ──┘         │
                     SQLite DB
                     APScheduler
                     ML Engine (XGBoost + LightGBM)
                     WebSocket Server
```

---

## Broker Support

| Broker    | Orders | Positions | Live Quotes | Historic Data |
|-----------|--------|-----------|-------------|---------------|
| Zerodha   | ✅     | ✅        | ✅          | ✅            |
| INDMoney  | ✅     | ✅        | ❌          | ❌            |
| Paper     | ✅     | ✅        | via Zerodha | via Zerodha   |
