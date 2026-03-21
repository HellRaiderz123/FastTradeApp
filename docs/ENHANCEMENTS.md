# FastTradeApp — Enhancements & Roadmap

> **Last audited:** Full live codebase scan — `backend/app/`, `web/src/`, `mobile/`, `.env`
> **Legend:** ✅ Done · 🔧 Partial · ❌ Not started

---

## Infrastructure

| Item | Status | Evidence |
|------|--------|----------|
| PostgreSQL (Neon) migration | ✅ | `DATABASE_URL` in `.env` points to Neon, `session.py` has full PG pool config |
| SQLite → Postgres migration script | ✅ | `backend/migrate_to_postgres.py` — full table-by-table copy |
| Connection pooling (PG) | ✅ | `session.py`: `pool_size=5`, `max_overflow=10`, `pool_pre_ping`, `pool_recycle=300` |
| Dockerfile (backend) | ✅ | `backend/Dockerfile` |
| Dockerfile (frontend) | ✅ | `web/Dockerfile` |
| docker-compose.yml | ✅ | Root `docker-compose.yml` |
| `.env` — all variables documented | ✅ | 60+ vars across 10 sections |
| Rate limiter | ✅ | `backend/app/core/rate_limiter.py` |
| Auth (Bearer token) | ✅ | `backend/app/core/auth.py`, `AUTH_ENABLED` flag |
| Retry handler | ✅ | `backend/app/core/retry_handler.py` |
| Structured JSON logging | ✅ | `JSON_LOGS` env var, `logging_config.py` |
| Circuit breaker | ✅ | `backend/app/core/risk/circuit_breaker.py` |
| Kill switch | ✅ | `backend/app/core/risk/kill_switch.py` |
| CI/CD pipeline | ❌ | No GitHub Actions |
| Secrets management (Vault/AWS SM) | ❌ | `.env` file only |
| Prometheus metrics endpoint | ❌ | No `/metrics` |
| Grafana / Sentry | ❌ | Not integrated |

---

## Broker Integration

| Item | Status | Evidence |
|------|--------|----------|
| Zerodha KiteConnect | ✅ | `core/broker/zerodha/` — client, instruments, OAuth |
| Zerodha OAuth login | ✅ | `oauth.py`, Settings UI with OAuth flow |
| Zerodha dry run / live / paper modes | ✅ | `execution/mode.py`, `EXECUTION_MODE` env |
| INDMoney / INDstocks | ✅ | `execution/indmoney.py`, `indmoney_broker.py` |
| Broker reconciliation backend | ✅ | `core/exit/broker_reconcile.py` |
| Broker reconciliation UI | ✅ | `web/src/pages/BrokerReconciliation.tsx` |
| Broker status indicator (header) | ✅ | Header shows active broker + execution mode |
| Multi-broker switching | ✅ | `ACTIVE_BROKER` env + Settings UI |
| Zerodha GTT orders | ❌ | No `place_gtt()` call anywhere in codebase |

---

## Trading Engine

| Item | Status | Evidence |
|------|--------|----------|
| Option spread strategies (15m) | ✅ | `core/strategies/option_spread_15m/` |
| Custom option spread engine | ✅ | `core/strategies/option_spread_custom/` |
| Stock strategies (momentum, mean reversion, trend) | ✅ | `core/strategies/stock_strategies/` |
| Strategy CRUD + enable/disable/deploy | ✅ | `routes/strategies.py`, `StrategyManager.tsx` |
| Strategy Builder (visual + payoff diagram) | ✅ | `StrategyBuilder.tsx` — SVG payoff chart, Greeks, PoP, breakevens |
| Strategy Marketplace (8 templates) | ✅ | `routes/marketplace.py` + `StrategyMarketplace.tsx` |
| Auto Trader | ✅ | `AutoTrader.tsx` + `core/auto_trader.py` — start/stop/pause/config/logs |
| Paper trading + MTM | ✅ | `execution/paper.py`, `execution/paper_mtm.py` |
| TP/SL auto-exit | ✅ | `core/exit/auto_exit.py` scheduler |
| Trailing stop loss | ✅ | `core/risk/tp_sl_calculator.py` |
| Expiry auto-exit | ✅ | `core/market/expiry_exit.py` scheduler |
| Trade cost calculator | ✅ | `routes/trade_costs.py` + `TradeCostTracker.tsx` |
| Risk limits (DB-backed, IV regime) | ✅ | `core/risk/risk_limits_config.py` |
| Drawdown tracker | ✅ | `core/risk/drawdown_tracker.py` |
| Trade limit enforcement | ✅ | `core/risk/trade_limit.py` |
| Zerodha GTT orders | ❌ | Not implemented |

---

## Market Data

| Item | Status | Evidence |
|------|--------|----------|
| Live LTP (Zerodha) | ✅ | `core/market/ltp.py` |
| Options chain (real Zerodha data) | ✅ | `routes/options_real.py` |
| Candle data (1m, 5m, 15m, 1h, daily) | ✅ | Scheduler + `models_candles.py` |
| Multi-timeframe view | ✅ | `MultiTimeframe.tsx` |
| VIX / IV Rank | ✅ | `core/market/vix_iv_api.py`, `iv_rank_calculator.py` |
| Sector performance | ✅ | `routes/market_dashboard.py` |
| Market depth | ✅ | `routes/market_depth.py` |
| Economic calendar | ✅ | `routes/economic_calendar.py` |
| Peer comparison | ✅ | `routes/peer_comparison.py` |
| WebSocket live positions | ✅ | `routes/ws_positions.py` |
| 52-week high/low (live) | 🔧 | In `Symbol` model schema, not live-fetched from broker API |

---

## ML & Signals

| Item | Status | Evidence |
|------|--------|----------|
| GBM stock ML model | ✅ | `core/ml/stock_model.py`, `STOCK_ML_ENABLED` flag |
| Ensemble model | ✅ | `core/ml/ensemble.py` |
| SHAP explainability | ✅ | `core/ml/shap_explainer.py` |
| Walk-forward backtest | ✅ | `core/ml/walk_forward.py` |
| Signal backtest | ✅ | `core/ml/signal_backtest.py` |
| News sentiment (NLP) | ✅ | `core/ml/news_sentiment.py` |
| Twitter/X sentiment | ✅ | `services/twitter_service.py` + `TwitterAlerts.tsx` |
| Correlation matrix UI | ✅ | `core/ml/correlation.py` + ML Center tab |
| ML Center UI (all tabs) | ✅ | `MLCenter.tsx` |
| Signal diagnostics | ✅ | `core/learning/signal_diagnostics.py` + Journal UI |
| Condition strategy lab | ✅ | `core/condition_strategy_lab.py` |
| Create Scanner | ✅ | `CreateScanner.tsx` + `routes/condition_scanner.py` |

---

## Analytics & Reporting

| Item | Status | Evidence |
|------|--------|----------|
| Strategy P&L dashboard | ✅ | `StrategyPnL.tsx` — equity curve, drawdown, monthly heatmap, per-strategy table, exit reasons |
| P&L analytics backend | ✅ | `routes/analytics.py` — full endpoint with filters |
| Trade Journal | ✅ | `Journal.tsx` — P&L filter, execution type filter, diagnostics, delete |
| Journal CSV export | ✅ | `exportCSV()` wired to Export button — downloads `filteredEntries` as CSV with all columns |
| Backtest engine | ✅ | `core/backtest/engine.py` + `Backtest.tsx` |
| Backtest comparison | ✅ | `BacktestComparison.tsx` |
| Heatmap | ✅ | `Heatmap.tsx` |
| Bloomberg Terminal | ✅ | `TerminalBloomberg.tsx` |
| Finance tracker | ✅ | `FinanceTracker.tsx` — budgets, goals, bills, forecasts, recurring |
| Audit trail / STCG/LTCG tax export | ❌ | No FIFO/LIFO P&L, no capital gains report |

---

## Screener

| Item | Status | Evidence |
|------|--------|----------|
| Basic filters (price, RSI, volume, MA) | ✅ | `routes/screener.py` + `Screener.tsx` |
| Fundamental filters (P/E, P/B, ROE, D/E, div yield) | ✅ | Backend + UI both implemented |
| 52-week high/low proximity | ✅ | `near_52w_high` / `near_52w_low` filters in backend + UI |
| Save/load custom presets (localStorage) | ✅ | `CUSTOM_PRESETS_KEY`, save/delete UI in `Screener.tsx` |
| Built-in presets (7) | ✅ | breakout, oversold, overbought, high_volume, trending_up, large_cap, IT sector |
| Earnings date proximity filter | ❌ | No earnings data source |
| Relative strength vs NIFTY | ❌ | Not implemented |
| Schedule screener runs | ❌ | No cron/scheduler |
| Promoter holding filter | ❌ | No data source |

---

## Notifications

| Item | Status | Evidence |
|------|--------|----------|
| Gmail / SMTP alerts | ✅ | `services/notifications.py` — trade executed, SL/TP hit, daily summary, system errors |
| In-app notifications (DB-backed) | ✅ | `models_notification.py`, `routes/notifications.py` |
| Telegram notifications | ✅ | `_send_telegram()` in `notifications.py` (stdlib urllib, no deps) · `settings.py` save/test endpoints · `Settings.tsx` Telegram card with bot token + chat ID + test button |
| WhatsApp notifications | ❌ | Not started |
| Push notifications (mobile) | ❌ | Expo Notifications not wired |
| Rate limit display in UI | ❌ | `rate_limiter.py` exists, not surfaced in Header or anywhere in UI |

---

## UI / UX

| Item | Status | Evidence |
|------|--------|----------|
| Dark mode (default) | ✅ | CSS variables + `html.light-mode` class |
| Light mode toggle | ✅ | Header button + Settings toggle, persisted to localStorage |
| Favicon + PWA manifest | ✅ | `web/public/favicon.svg`, `manifest.json` |
| API docs link in header | ✅ | `/api/docs` ExternalLink in `Header.tsx` |
| Sidebar (20+ items) | ✅ | All pages linked |
| Collapsible sidebar (icon-only) | ✅ | Collapses to `w-20` icon-only mode |
| Sidebar section grouping | ✅ | 5 collapsible sections (Market, Trading, Analytics, Intelligence, System) with localStorage persistence |
| Keyboard shortcuts | ✅ | `useKeyboardShortcuts` hook · `CommandPalette` modal (Ctrl+K) · single-key nav: T/D/S/J/P/A/M/B/F |
| Mobile-responsive web layout | 🔧 | Tailwind responsive classes used, but tables/charts overflow on small screens |
| Last signal timestamp per symbol | ❌ | Not surfaced anywhere in UI |
| Options Greeks dashboard (portfolio-level) | ❌ | `routes/greeks.py` exists for single-leg calc, no portfolio aggregation page |

---

## Mobile App

| Item | Status | Evidence |
|------|--------|----------|
| Expo React Native app | 🔧 | `mobile/app/` — dashboard, journal, positions, strategies, backtest, settings |
| Mobile feature parity with web | ❌ | Missing: screener, ML center, auto-trader, finance tracker, options chain, watchlists |
| Mobile push notifications | ❌ | Not wired |

---

## Pending Work — Prioritized

### 🟢 Quick Wins (< 2 hours each)

#### 1. Rate Limit Display in UI
Expose remaining quota from `rate_limiter.py` via `GET /system/rate-limit-status`.
Show a small badge in `Header.tsx` (e.g. "API 42/60").
**Files:** `backend/app/core/rate_limiter.py`, `backend/app/api/system_control.py`, `web/src/components/Header.tsx`.

#### 2. Last Signal Timestamp per Symbol
Add `last_signal_at` per underlying to the auto-trader status response.
Show "last scanned X mins ago" badge in `AutoTrader.tsx` dashboard tab.
**Files:** `backend/app/api/routes/auto_trader.py`, `web/src/pages/AutoTrader.tsx`.

---

### 🟡 Medium Effort (1–3 days each)

#### 3. Live Options Greeks Dashboard
New page showing portfolio-level Δ, Γ, Θ, Vega aggregated across all open `ExecutionIntent` positions.
`routes/greeks.py` already calculates per-leg — just needs a portfolio aggregation endpoint + page.
Delta-neutral suggestion: show lots needed to flatten delta.
**Files:** new `backend/app/api/routes/portfolio_greeks.py`, new `web/src/pages/OptionsGreeks.tsx`.

#### 4. Audit Trail & Tax Export (STCG/LTCG)
- New endpoint `GET /audit/trades` — all closed intents with holding period classification
- FIFO P&L per symbol, STCG (< 1 year) vs LTCG (≥ 1 year) for Indian tax
- CSV export with ITR-compatible columns
**Files:** new `backend/app/api/routes/audit.py`, new `web/src/pages/AuditTrail.tsx`.

---

### 🔴 Significant Effort (3–7 days each)

#### 5. Zerodha GTT Orders
On trade entry, place a GTT on Zerodha for TP and SL instead of polling every 30s.
Eliminates missed exits when the app is offline or restarting.
Requires `kite.place_gtt()` + GTT status polling + fallback to current polling on failure.
**Files:** `backend/app/core/execution/zerodha.py`, `backend/app/core/exit/auto_exit.py`.

#### 6. Mobile App Feature Parity
Add to Expo app: Screener, Auto Trader control, Finance Tracker, ML predictions, Watchlists.
Wire Expo push notifications to backend trade alerts.
**Files:** `mobile/app/` (multiple new screens).

#### 7. Advanced Screener — Remaining Filters
- Relative strength vs NIFTY (rolling return comparison)
- Earnings date proximity (NSE or external API)
- Schedule screener runs (cron + email results)
- Promoter holding % (BSE/NSE shareholding data)
**Files:** `backend/app/api/routes/screener.py`, `web/src/pages/Screener.tsx`.

---

### ⚫ Long-term / Advanced

#### 8. CI/CD Pipeline
GitHub Actions: `tsc --noEmit` + `pytest` on PR, Docker build + deploy on merge to `main`.
**Files:** new `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`.

#### 9. Monitoring & Observability
Prometheus `/metrics` endpoint, Grafana dashboard, Sentry SDK for frontend + backend.
**Files:** `backend/app/main.py`, new `backend/app/api/routes/metrics.py`.

#### 10. Secrets Management
Move from `.env` to AWS Secrets Manager or HashiCorp Vault. Auto-rotate Zerodha token daily.

#### 11. Reinforcement Learning Agent
Replace rule-based auto-trader signal with PPO/SAC RL agent (Stable Baselines3).
Train on historical `ExecutionIntent` outcomes. Paper trade before going live.
**Files:** new `backend/app/core/ml/rl_agent.py`.

#### 12. Multi-Account Support
Trade across multiple Zerodha sub-accounts. Consolidated P&L view. Per-account risk limits.

#### 13. AI Chat Assistant
Natural language: "Show me all losing trades this month."
SHAP explanations already exist — needs a chat UI + LLM backend.
**Files:** new `web/src/pages/AIAssistant.tsx`, new `backend/app/api/routes/ai_chat.py`.

#### 14. Paper Trading Competition Mode
Multiple paper portfolios running in parallel. Leaderboard comparing strategy performance.

#### 15. Order Flow Analysis
Tick-by-tick data via Zerodha WebSocket full mode. Large order detection, VWAP alerts, Time & Sales.

---

## What to Build Next

```
TODAY (< 2 hours):
  1. Rate limit display in UI    → Header.tsx + system_control.py
  2. Last signal timestamp       → auto_trader.py + AutoTrader.tsx

NEXT SPRINT:
  3. Options Greeks dashboard    → portfolio_greeks.py + OptionsGreeks.tsx
  4. Audit trail + tax export    → audit.py + AuditTrail.tsx
  5. Zerodha GTT orders          → execution/zerodha.py + auto_exit.py
```
