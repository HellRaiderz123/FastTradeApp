# FastTradeApp — How to Use This App

> Internal guide. Not financial advice. Always start in paper-trading mode.

---

## 1. First-Time Setup

### Start the backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Start the web app
```bash
cd web
npm install
npm run dev                    # opens http://localhost:5173
```

### Start the mobile app (optional)
```bash
cd mobile
npm install
npx expo start
```

Or use the one-shot script at the project root:
```
setup.bat
```

### Required `.env` keys (backend/.env)
| Key | What it does |
|-----|-------------|
| `DATABASE_URL` | PostgreSQL URL — leave blank to use local SQLite |
| `ZERODHA_API_KEY` / `ZERODHA_API_SECRET` | Live/paper broker |
| `NEWSDATA_API_KEY` | News feed for AI analysis |
| `JWT_SECRET` | Auth token signing — set a strong random string |
| `SCHEDULERS_ENABLED` | Set `false` during dev to stop background jobs |

Copy `backend/.env.example` → `backend/.env` and fill in the blanks.

---

## 2. Daily Workflow

### Morning (pre-market)
1. Open the web app → **Watchlists** page
2. Click **Run Pre-Market Analysis** — the scheduler enriches each symbol with AI signals
3. Check **NSE Flash Alerts** (top-right overlay) for HIGH-impact filings
4. Review **AI Analysis** page for any overnight signals

### During market hours
1. **Scanner** → pick a built-in strategy or create one → **Run Scan**
2. Hits appear in **Scanner Execution** — review each signal
3. For options: go to **Options Chain** → check live Greeks before entering
4. Place trades via **Auto Trader** (paper mode first) or manually from **Positions**

### End of day
1. **Journal** → log your trades and notes
2. **Strategy P&L** → check how each strategy performed
3. **Trade Cost Tracker** → review brokerage and slippage
4. **Backtest** → if you tweaked a strategy, run a quick backtest to validate

---

## 3. Key Pages and What They Do

### AI Features
| Page | URL | Use it for |
|------|-----|-----------|
| AI Analysis | `/ai-analysis` | Full 9-agent pipeline — technical + sentiment + fundamentals + bull/bear research for any symbol |
| AI Assistant | `/ai-assistant` | Chat with the AI; it has persistent memory across sessions. Clear memory with the 🧹 button |
| Simple AI | `/simple-ai` | Bare LLM chat, no tools, fastest response |

**AI Assistant memory**: stored per `fasttrade_user_id` in localStorage. The assistant remembers your last 20 conversation turns across browser sessions. Hit **🧹 Clear Memory** to reset.

### Trading
| Page | Use it for |
|------|-----------|
| Auto Trader | Set rules for automated entry/exit; always test in paper mode first |
| Positions | Live position overview with broker reconciliation |
| Options Chain | Real-time chain with Delta/Gamma/Theta/Vega; click any strike to trade |
| Quant Bot | Multi-agent bots running predefined quant strategies |
| Scalp Trading | Fast intraday scalp engine with tight stop-loss rules |

### Analysis
| Page | Use it for |
|------|-----------|
| Scanner | Create condition-based scans (RSI, MACD, volume, etc.) |
| Screener | Filter the full market by fundamentals + technicals |
| Backtest | Replay a strategy on historical candles |
| ML Center | Train/retrain XGBoost/LightGBM models; view SHAP explanations |
| Multi-Timeframe | Compare 5m / 15m / 1h / 1D candles side by side |
| Heatmap | Sector-level heat map of price change |
| FII/DII | Institutional flow data |

### Portfolio
| Page | Use it for |
|------|-----------|
| Strategy P&L | Per-strategy profit/loss breakdown |
| Finance Tracker | Overall portfolio value over time |
| Trade Cost Tracker | Brokerage, STT, slippage per trade |
| Broker Reconciliation | Diff between app positions and broker positions |

---

## 4. NSE Flash Alerts

A live overlay appears in the top-right corner when HIGH or MEDIUM impact NSE filings are detected.

- **RED badge** = HIGH impact (board meeting, merger, order win, FIR, rights issue, etc.)
- **YELLOW badge** = MEDIUM impact (analyst meet, investor presentation, etc.)
- Each card shows: symbol, LTP, % change, volume, headline, link to PDF
- Cards auto-dismiss after 14 seconds; click ✕ to dismiss early
- Powered by SSE stream at `GET /nse/flash-alerts`; falls back to REST poll every 35s

---

## 5. Scanner — Quick Start

1. Go to **Scanner** → **Create Scanner**
2. Add conditions (e.g. RSI < 30, Volume > 1.5× avg)
3. Save and click **Run**
4. Results appear in **Scanner Execution** with signal strength
5. Click a result → opens AI Analysis for that symbol

Built-in strategies are in `backend/scripts/discover_condition_strategies.py` — run it to auto-populate the strategy library.

---

## 6. Backtest — Quick Start

1. Go to **Backtest**
2. Select a strategy and symbol
3. Set date range and capital
4. Click **Run Backtest**
5. Review: Sharpe ratio, Max Drawdown, Win Rate, P&L curve
6. Use **Backtest Comparison** to compare two strategies side by side

Data sources: Zerodha historical → Yahoo Finance fallback → mock data. See `docs/BACKTEST_DATA_SOURCES_GUIDE.md` for details.

---

## 7. ML Center — Quick Start

1. Go to **ML Center**
2. Pre-trained models are already loaded (`ensemble_model.joblib`, `stock_daily_model.joblib`)
3. Click **Retrain** to update with recent data
4. **ML Intelligence** page shows SHAP feature importance and signal confidence
5. Signals from ML feed into the Scanner and Auto Trader automatically

To retrain from CLI:
```bash
cd backend
python scripts/backfill_candles.py   # ensure data is fresh
# then retrain via ML Center UI or add a script call here
```

---

## 8. Broker Setup

### Zerodha
Follow `docs/ZERODHA_SETUP_GUIDE.md`. Key steps:
1. Create a Kite Connect app at `developers.kite.trade`
2. Set `ZERODHA_API_KEY` and `ZERODHA_API_SECRET` in `.env`
3. On first login, complete the OAuth flow — the app stores the access token
4. Token expires daily at 6 AM IST; re-login or automate via `docs/ZERODHA_SETTINGS_GUIDE.md`

### INDMoney
Set `INDMONEY_*` keys in `.env`. See `docs/ZERODHA_VS_INDMONEY_API_COMPARISON.md` for capability differences.

### Paper trading (no broker needed)
Leave broker keys blank. All trades execute in paper mode with real-time MTM via WebSocket.

---

## 9. Alexa Skill

Voice queries like "Alexa, ask FastTrade what is the price of Reliance":
1. Deploy the skill using `backend/examples/alexa_fasttrade_interaction_model.json`
2. Set `ALEXA_SKILL_ID` in `.env`
3. See `docs/ALEXA_NVIDIA_SETUP.md` for full setup

---

## 10. Scheduled Jobs

Background jobs run automatically when `SCHEDULERS_ENABLED=true`:

| Job | Frequency | What it does |
|-----|-----------|-------------|
| Candle backfill | Every 15 min | Fetches and stores 15m candles |
| VIX tracker | Every 5 min | Updates India VIX |
| Pre-market analysis | 8:45 AM IST | Runs AI analysis on all watchlist symbols |
| Auto-exit | Configurable | Exits positions at set time or on expiry |
| NSE flash alerts | Every 30s | Polls NSE announcements, pushes SSE events |

View and manage jobs on the **Scheduled Jobs** page.

---

## 11. Authentication

- JWT-based auth; set a strong `JWT_SECRET` in `.env`
- Default first-run: no auth (dev mode)
- Enable auth: `AUTH_ENABLED=true` in `.env`
- See `docs/AUTHENTICATION_DEPLOYMENT_GUIDE.md` for production hardening

---

## 12. What's Still Pending

See `redmes/PENDING_WORK.txt` for the full list. Short version:

| Feature | Status |
|---------|--------|
| Strategy Builder UI (drag & drop legs, payoff diagram) | 🔴 Not started |
| Portfolio Greeks aggregation dashboard | 🔴 Not started |
| Live Zerodha order execution (tested end-to-end) | 🟡 Partial |
| Advanced backtesting (Monte Carlo, walk-forward) | 🟢 Low priority |
| ML real models (beyond pre-trained joblibs) | 🟢 Low priority |

---

## 13. Useful API Endpoints (dev reference)

Interactive docs: `http://localhost:8000/docs`

| Endpoint | What it returns |
|----------|----------------|
| `GET /ai-analysis/{symbol}` | Full 9-agent AI report |
| `POST /ai-chat` | Chat turn with tool-calling AI |
| `DELETE /ai-chat/memory` | Clear persistent memory for user |
| `GET /nse/flash-alerts` | SSE stream of HIGH/MEDIUM NSE filings |
| `GET /scanner/run/{id}` | Run a saved scanner |
| `GET /options/chain/{symbol}` | Live options chain with Greeks |
| `GET /positions` | Current open positions |
| `POST /trade/paper` | Place a paper trade |

---

## 14. Troubleshooting

**Backend won't start**
- Check `backend/.env` exists and `DATABASE_URL` is valid
- Run `pip install -r requirements.txt` again
- Check `backend/logs/app.log` for the error

**No candle data**
- Run `python scripts/backfill_candles.py` manually
- Ensure Zerodha token is fresh (re-login if expired)

**AI Analysis returns empty**
- Check `NEWSDATA_API_KEY` is set
- Verify the LLM provider key (OpenAI / Groq / etc.) in `.env`

**NSE Flash Alerts not showing**
- Open browser console — check for SSE connection errors
- Fallback REST poll fires every 35s; alerts will appear with a short delay

**TypeScript errors in web**
```bash
cd web
npx tsc --noEmit --skipLibCheck
```
