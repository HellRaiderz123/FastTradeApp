# FastTradeApp — Enhancements & Roadmap

> **Last audited:** 2026-04-08 — Full repo scan + focused trading-safety / auto-trader review
> **Legend:** ✅ Done · 🔧 Partial · ❌ Not started

---

## Infrastructure

| Item | Status | Evidence |
|------|--------|----------|
| PostgreSQL migration | ✅ | `DATABASE_URL` in `.env`, `session.py` full PG pool config |
| SQLite → Postgres migration script | ✅ | `backend/migrate_to_postgres.py` |
| Connection pooling | ✅ | `pool_size=5`, `max_overflow=10`, `pool_pre_ping`, `pool_recycle=300` |
| Docker (backend + frontend) | ✅ | `backend/Dockerfile`, `web/Dockerfile` |
| docker-compose (3 services) | ✅ | db + backend + frontend |
| Ollama (offline LLM) | ✅ | Added to `docker-compose.yml`, `ollama_data` volume |
| Rate limiter | ✅ | `core/rate_limiter.py` |
| Auth (Bearer token) | ✅ | `core/auth.py`, `AUTH_ENABLED` flag |
| Retry handler | ✅ | `core/retry_handler.py` |
| Structured JSON logging | ✅ | `JSON_LOGS` env var, `logging_config.py` |
| Circuit breaker | ✅ | `core/risk/circuit_breaker.py` |
| Kill switch | ✅ | `core/risk/kill_switch.py` |
| Nginx reverse proxy | ✅ | `web/nginx.conf` — API proxy, WebSocket upgrade, Swagger docs routes |
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
| Broker reconciliation | ✅ | `core/exit/broker_reconcile.py` |
| Broker reconciliation UI | ✅ | `BrokerReconciliation.tsx` |
| Multi-broker switching | ✅ | `ACTIVE_BROKER` env + Settings UI |
| Zerodha auto-login (daily 8 AM) | ✅ | `services/zerodha_auto_login.py` + scheduler |
| Zerodha WebSocket ticker (LTP mode) | ✅ | `services/zerodha_ticker.py` — LTP cache, symbol→token map |
| Zerodha GTT orders | ❌ | No `place_gtt()` anywhere — exits rely on polling every 10s |
| Idempotent order placement | ❌ | `routes/execute.py` accepts `idempotency_key` but does not persist/dedupe retries yet |
| Partial fill reconciliation | 🔧 | `services/order_monitor.py` stores partial fills, but `broker_reconcile.py` still mainly reconciles open/closed state |

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
| TP/SL auto-exit (10s polling) | ✅ | `core/exit/auto_exit.py` scheduler |
| Trailing stop loss | ✅ | `core/risk/tp_sl_calculator.py` |
| Expiry auto-exit | ✅ | `core/market/expiry_exit.py` scheduler |
| Manual override cooldown after manual exit | ❌ | `exit.py` sets `exit_reason="MANUAL"`, but `core/auto_trader.py` can re-enter immediately if the signal still persists |
| Strategy-specific TP/SL for ratio backspreads | 🔧 | `core/risk/tp_sl_calculator.py` special-cases `BULL_PUT` / `BEAR_CALL` / `IRON_CONDOR`; call/put ratio backspreads still use generic ₹ thresholds |
| Trade cost calculator | ✅ | `routes/trade_costs.py` + `TradeCostTracker.tsx` |
| Risk limits (DB-backed, IV regime) | ✅ | `core/risk/risk_limits_config.py` |
| Drawdown tracker | ✅ | `core/risk/drawdown_tracker.py` |
| Trade limit enforcement | ✅ | `core/risk/trade_limit.py` |
| Condition Scanner (Create Scanner) | ✅ | `CreateScanner.tsx` + `routes/condition_scanner.py` |
| Condition Strategy Lab | ✅ | `core/condition_strategy_lab.py` — 13 indicator families, 500 max candidates |
| Strategy Lab CLI script | ✅ | `backend/scripts/discover_condition_strategies.py` — parallel workers, exit sweep |
| Daily strategy discovery (auto 4:15 PM) | ✅ | `_strategy_discovery_job()` in `scheduler.py` |
| Strategy decay tracker (auto 4:30 PM) | ✅ | `core/strategy_decay.py` — HEALTHY/WARNING/DECAYED |
| Zerodha GTT orders | ❌ | Not implemented — missed exits possible when app is offline |
| Multi-timeframe signal confirmation | ❌ | Scanner uses single timeframe only |
| ATR-based position sizing | ❌ | Fixed % only, no volatility-adjusted sizing |

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
| 52-week high/low (live) | 🔧 | In schema, not live-fetched from broker API |
| Zerodha WebSocket FULL mode | ❌ | Currently `MODE_LTP` only — no volume, buy/sell qty per tick |

---

## AI & ML

| Item | Status | Evidence |
|------|--------|----------|
| GBM stock ML model | ✅ | `core/ml/stock_model.py` |
| Ensemble model | ✅ | `core/ml/ensemble.py` |
| SHAP explainability | ✅ | `core/ml/shap_explainer.py` |
| Walk-forward backtest | ✅ | `core/ml/walk_forward.py` |
| Signal backtest | ✅ | `core/ml/signal_backtest.py` |
| News sentiment (NLP) | ✅ | `core/ml/news_sentiment.py` |
| Twitter/X sentiment | ✅ | `services/twitter_service.py` + `TwitterAlerts.tsx` |
| Correlation matrix | ✅ | `core/ml/correlation.py` + ML Center tab |
| Signal diagnostics | ✅ | `core/learning/signal_diagnostics.py` + Journal UI |
| AI Chat — Ollama (offline LLM) | ✅ | `routes/ai_chat.py` — full context: positions, trades, strategies, scanner, finance, trade costs |
| AI Chat — multi-turn conversation | ✅ | `history` field in `ChatRequest`, last 10 turns passed to Ollama |
| AI Chat — OpenAI / Groq / custom fallback | ✅ | `LLM_PROVIDER`, `OPENAI_API_KEY`, `GROQ_API_KEY`, and `LLM_BASE_URL` are supported in `routes/ai_chat.py` |
| Reinforcement Learning agent | ❌ | No RL agent — needs 6-12 months live trade data first |

---

## Analytics & Reporting

| Item | Status | Evidence |
|------|--------|----------|
| Strategy P&L dashboard | ✅ | `StrategyPnL.tsx` — equity curve, drawdown, monthly heatmap |
| P&L analytics backend | ✅ | `routes/analytics.py` |
| Trade Journal | ✅ | `Journal.tsx` — app trades only, signal diagnostics, CSV export |
| Backtest engine | ✅ | `core/backtest/engine.py` + `Backtest.tsx` |
| Backtest comparison | ✅ | `BacktestComparison.tsx` |
| Heatmap | ✅ | `Heatmap.tsx` |
| Bloomberg Terminal | ✅ | `TerminalBloomberg.tsx` |
| Finance tracker | ✅ | `FinanceTracker.tsx` — budgets, goals, bills, forecasts, recurring |
| Trade calendar | ✅ | `TradeCalendar.tsx` — daily P&L heatmap calendar |
| Slippage modeling in backtest | ❌ | Assumes clean fills at signal price — overstates real returns |
| Walk-forward validation on discovered strategies | ❌ | No out-of-sample check after daily discovery |
| Audit trail / STCG/LTCG tax export | ❌ | No FIFO P&L, no capital gains report |
| Options Greeks portfolio dashboard | ❌ | `routes/greeks.py` exists per-leg, no portfolio aggregation |

---

## Screener

| Item | Status | Evidence |
|------|--------|----------|
| Basic filters (price, RSI, volume, MA) | ✅ | `routes/screener.py` + `Screener.tsx` |
| Fundamental filters (P/E, P/B, ROE, D/E) | ✅ | Backend + UI both implemented |
| 52-week high/low proximity | ✅ | `near_52w_high` / `near_52w_low` filters |
| Save/load custom presets | ✅ | localStorage persistence |
| Built-in presets (7) | ✅ | breakout, oversold, overbought, high_volume, trending_up, large_cap, IT sector |
| Relative strength vs NIFTY | ❌ | Not implemented |
| Earnings date proximity filter | ❌ | No earnings data source |
| Schedule screener runs | ❌ | No cron/scheduler for screener |

---

## Notifications

| Item | Status | Evidence |
|------|--------|----------|
| Gmail / SMTP alerts | ✅ | `services/notifications.py` |
| In-app notifications (DB-backed) | ✅ | `models_notification.py`, `routes/notifications.py` |
| Telegram notifications | ✅ | Trade entries, SL/TP hits, strategy discovery, decay alerts |
| WhatsApp notifications | ❌ | Not started |
| Push notifications (mobile) | ❌ | Expo Notifications not wired |
| Rate limit display in UI | ❌ | `rate_limiter.py` exists, not surfaced in Header |

---

## UI / UX

| Item | Status | Evidence |
|------|--------|----------|
| Dark mode (default) + light mode toggle | ✅ | CSS variables + Settings toggle |
| Favicon + PWA manifest | ✅ | `web/public/favicon.svg`, `manifest.json` |
| Sidebar (20+ items, collapsible, grouped) | ✅ | 5 collapsible sections, localStorage persistence |
| Keyboard shortcuts + Command Palette | ✅ | `useKeyboardShortcuts` + Ctrl+K |
| AI Assistant page | ✅ | `AIAssistant.tsx` — full Ollama integration with trade context |
| Positions — app trades only | ✅ | Zerodha holdings filtered out at both frontend and backend |
| Journal — app trades only | ✅ | Zerodha strategies filtered, auto-sync disabled |
| Mobile-responsive web layout | 🔧 | Tailwind responsive classes, tables/charts overflow on small screens |
| Options Greeks portfolio page | ❌ | Not built |
| Last signal timestamp per symbol | ❌ | Not surfaced in UI |

---

## Mobile App

| Item | Status | Evidence |
|------|--------|----------|
| Expo React Native app | 🔧 | `mobile/app/` — dashboard, journal, positions, strategies, backtest, settings, watchlists, options chain |
| Mobile feature parity with web | 🔧 | Missing: Auto Trader control, full Screener parity, ML Center, Finance Tracker, Condition Scanner; watchlists and options chain already exist |
| Mobile push notifications | ❌ | Not wired |

---

## Known Issues Fixed (This Session)

| Issue | Fix |
|-------|-----|
| Zerodha holdings auto-appearing in Positions/Journal | Removed `journalAPI.syncZerodha()` from `App.tsx` startup, disabled `/journal/sync-zerodha` endpoint, added frontend filters |
| `CreateScanner` crash on `timeframe` undefined | Guarded `runBacktest()` — checks `summary`/`all_trades` before `setBacktestResult` |
| AI Chat generic replies | Replaced keyword matching with full Ollama LLM — injects positions, trades, strategies, scanner, finance, trade costs as context |
| `/api/docs` not rendering via port 3000 | Added explicit Nginx routes for `/api/docs`, `/api/redoc`, `/api/openapi.json` |
| `discover_condition_strategies.py` not in Docker | Added `COPY scripts/ ./scripts/` to backend Dockerfile |
| `max_candidates` cap too low | Raised `StrategyDiscoveryRequest.max_candidates` from `le=250` to `le=500` |
| Watchlist `Change %` blank / missing | `watchlists.py` now computes `change_pct` from full quote + OHLC and the web UI accepts both `change_pct` / `change_percent` |
| Options Chain lacked actionable analytics | Added PCR, support/resistance, max pain, and buildup heuristics to `OptionsChain.tsx` |
| Jarvis interpreted `close my current position` as symbol `CURRENT` | `ai_chat.py` now resolves the latest/current open trade correctly and AI badges show failures clearly |

---

## Fresh Audit Additions — 2026-04-08

### 🟢 Highest-ROI Fixes Identified in the Latest Repo Scan

#### 1. Idempotent execution guard for trade placement
**Why:** `routes/execute.py` accepts an `idempotency_key` header, but retries are not yet deduplicated server-side. A timeout/retry path can still risk duplicate order placement.
**Files:** `backend/app/api/routes/execute.py`

#### 2. Manual-exit cooldown / human override lock
**Why:** After a manual close, `exit_reason="MANUAL"` is stored, but `core/auto_trader.py` can re-enter the same underlying immediately if the signal still says approved. A short cooldown (e.g. 15–30 min) would respect human override without disabling the whole engine.
**Files:** `backend/app/api/routes/exit.py`, `backend/app/core/auto_trader.py`

#### 3. Strategy-specific TP/SL for `CALL_RATIO_BACKSPREAD` and `PUT_RATIO_BACKSPREAD`
**Why:** Auto Trader TP/SL is functioning, but ratio backspreads still fall back to generic rupee-based thresholds in `tp_sl_calculator.py`. These structures deserve a more tailored exit model.
**Files:** `backend/app/core/risk/tp_sl_calculator.py`, `backend/app/core/strategies/option_spread_15m/engine.py`

#### 4. Partial fill + quantity drift reconciliation
**Why:** Partial fills are detected in `order_monitor.py`, but full quantity-aware recovery and broker/local drift handling are still incomplete. This is one of the highest leverage execution-safety improvements after GTT.
**Files:** `backend/app/services/order_monitor.py`, `backend/app/core/exit/broker_reconcile.py`

#### 5. Broker-side TP/SL protection using Zerodha GTT
**Why:** `auto_exit.py` still relies on polling. If the app or server is down, exits are not broker-native. GTT remains one of the most valuable safety upgrades.
**Files:** `backend/app/core/exit/auto_exit.py`, `backend/app/core/execution/zerodha.py`

---

## Next Steps — Prioritized

### 🟢 Quick Wins (< 2 hours each)

#### 1. Zerodha GTT Orders
**Why:** Current TP/SL relies on polling every 10s — if the app restarts or crashes, open positions have no protection. GTT orders sit on Zerodha's servers and fire even when your app is offline.
**What:** On trade entry, place a GTT on Zerodha for TP and SL. On exit, cancel the GTT.
**Files:** `core/execution/zerodha.py`, `core/exit/auto_exit.py`

#### 2. Multi-Timeframe Signal Confirmation
**Why:** Single-timeframe signals have more false positives. Requiring daily + hourly agreement significantly improves signal quality.
**What:** Before executing a scanner signal, check if the same condition holds on the next higher timeframe. Add `require_htf_confirm: bool` to `ConditionStrategy`.
**Files:** `core/condition_strategy_lab.py`, `routes/condition_scanner.py`, `CreateScanner.tsx`

#### 3. ATR-Based Position Sizing
**Why:** Fixed % position sizing ignores volatility. A 2% SL on a volatile stock is very different from a stable one. ATR-based sizing normalizes risk per trade.
**What:** Add `use_atr_sizing: bool` to scanner strategy config. Calculate position size as `risk_amount / (ATR × multiplier)` instead of fixed %.
**Files:** `core/backtest/engine.py`, `routes/condition_scanner.py`, `CreateScanner.tsx`

#### 4. Rate Limit Display in UI
**Why:** Users don't know when they're close to Zerodha API rate limits until they hit an error.
**What:** Expose `GET /system/rate-limit-status` → show a small badge in `Header.tsx`.
**Files:** `core/rate_limiter.py`, `api/system_control.py`, `components/Header.tsx`

---

### 🟡 Medium Effort (1–3 days each)

#### 5. Slippage Modeling in Backtest
**Why:** Current backtest assumes perfect fills at signal price. Real trades have 0.1–0.5% slippage on entry/exit, especially for mid-cap stocks. This overstates backtest returns.
**What:** Add `slippage_pct` param to `BacktestRequest`. Apply on entry (price × (1 + slippage)) and exit (price × (1 - slippage)).
**Files:** `core/backtest/engine.py`, `Backtest.tsx`, `CreateScanner.tsx`

#### 6. Walk-Forward Validation on Discovered Strategies
**Why:** Daily discovery backtests on the full period — no out-of-sample check. A strategy that looks great in-sample may be overfit.
**What:** After discovery, run a second backtest on the last 3 months (out-of-sample). Flag strategies where OOS return < 50% of in-sample return.
**Files:** `core/strategy_decay.py`, `scheduler.py`

#### 7. Audit Trail & Tax Export (STCG/LTCG)
**Why:** Indian traders need STCG/LTCG classification for ITR filing. Currently no way to export trade history in tax-ready format.
**What:** `GET /audit/trades` — FIFO P&L per symbol, holding period classification, STCG vs LTCG. CSV export with ITR-compatible columns.
**Files:** new `routes/audit.py`, new `AuditTrail.tsx`

#### 8. Options Greeks Portfolio Dashboard
**Why:** `routes/greeks.py` calculates per-leg Greeks but there's no portfolio-level view. Traders need to see net Delta, Gamma, Theta, Vega across all open positions.
**What:** New endpoint `GET /portfolio/greeks` aggregating across all open `ExecutionIntent` legs. New page `OptionsGreeks.tsx`.
**Files:** new `routes/portfolio_greeks.py`, new `OptionsGreeks.tsx`

#### 9. Trade Execution Safety — Idempotency + Audit Trail
**Why:** `execute.py` accepts `idempotency_key`, but retries are not deduped yet. Combined with limited end-to-end audit logging, this is one of the biggest operational safety gaps left in the project.
**What:** Persist `idempotency_key → intent_id`, return cached execution results on retry, and write a `trade_audit_log` entry for create / approve / execute / reject / exit transitions.
**Files:** `routes/execute.py`, `core/risk/circuit_breaker.py`, new `routes/audit.py`

#### 10. Condition Scanner — More Indicator Families
**Why:** Current lab has 13 families (EMA, SMA, RSI, MACD, BB, STOCH, WMA, DEMA/TEMA, Volume). Missing: Supertrend, Ichimoku, CCI, Williams %R, Parabolic SAR.
**What:** Add 5 new indicator families to `condition_strategy_lab.py`. Each adds ~30-50 new candidates.
**Files:** `core/condition_strategy_lab.py`, `core/indicators/technical.py`

---

### 🔴 Significant Effort (3–7 days each)

#### 11. Auto-Execution from Scanner Signals
**Why:** Scanner finds signals but you still manually execute. The biggest gap between the scanner and the auto-trader is that the auto-trader only uses the options engine, not condition scanner strategies.
**What:** Wire `ConditionStrategy` with `auto_scan_enabled=True` into the auto-trader loop. When a signal fires, auto-execute with configured `auto_amount`.
**Files:** `core/auto_trader.py`, `core/condition_scanner_scheduler.py`, `AutoTrader.tsx`

#### 12. Advanced Screener
**What:**
- Relative strength vs NIFTY (rolling 1m/3m/6m return comparison)
- Earnings date proximity (NSE corporate actions API)
- Schedule screener runs (cron + Telegram results)
- Promoter holding % filter
**Files:** `routes/screener.py`, `Screener.tsx`

#### 13. Mobile App Feature Parity
**What:** Add to Expo app: Screener, Auto Trader control, Finance Tracker, ML predictions, and Condition Scanner. Deepen parity for the existing Watchlists / Options Chain screens and wire Expo push notifications to backend trade alerts.
**Files:** `mobile/app/` (multiple new screens)

---

### ⚫ Long-term / Advanced

#### 14. CI/CD Pipeline
GitHub Actions: `tsc --noEmit` + `pytest` on PR, Docker build + deploy on merge to `main`.
**Files:** new `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`

#### 15. Monitoring & Observability
Prometheus `/metrics` endpoint, Grafana dashboard, Sentry SDK for frontend + backend errors.
**Files:** `backend/app/main.py`, new `routes/metrics.py`

#### 16. Secrets Management
Move from `.env` to AWS Secrets Manager or HashiCorp Vault. Auto-rotate Zerodha token daily.

#### 17. Reinforcement Learning Agent
Replace rule-based auto-trader signal with PPO/SAC RL agent (Stable Baselines3). Train on historical `ExecutionIntent` outcomes. Needs 6–12 months of live trade data first.
**Files:** new `core/ml/rl_agent.py`

#### 18. Multi-Account Support
Trade across multiple Zerodha sub-accounts. Consolidated P&L view. Per-account risk limits.

#### 19. Order Flow Analysis
Zerodha `MODE_FULL` WebSocket — volume per tick, buy/sell qty, large order detection, VWAP alerts, Time & Sales panel. **Note:** Limited value vs effort — Zerodha doesn't expose true Level 2 depth.

---

## What to Build Next

```
IMMEDIATE (highest ROI):
  1. Zerodha GTT orders          → protect positions when app is offline
  2. Multi-timeframe confirmation → reduce false signals from scanner
  3. ATR-based position sizing   → normalize risk per trade

NEXT SPRINT:
  4. Slippage modeling           → more realistic backtest returns
  5. Walk-forward validation     → catch overfit strategies before going live
  6. Auto-execute scanner signals → close the loop between scanner and execution
  7. Audit trail / tax export    → ITR filing support

LATER:
  8. Options Greeks portfolio    → net Delta/Theta/Vega across all positions
  9. Idempotent execution + audit trail → safer retries and clearer compliance history
 10. More indicator families     → Supertrend, Ichimoku, CCI, SAR
```

---

## Architecture Summary

```
FastTradeApp
├── Backend (FastAPI + PostgreSQL)
│   ├── Execution: Paper / Zerodha DryRun / Zerodha Live / INDMoney
│   ├── Scanner: Condition Strategy Lab → 13 indicator families → backtest → rank → save
│   ├── Auto Trader: TA signal → option spread engine → execute → monitor → exit
│   ├── ML: GBM + Ensemble + SHAP + Walk-Forward + News Sentiment + Twitter
│   ├── Risk: Circuit breaker, kill switch, drawdown tracker, trade limits, IV regime
│   ├── Scheduler: Candles (5m/1h/daily), VIX, strategy discovery, decay check, auto-login
│   └── AI Chat: Ollama llama3.2:3b with full DB context injection
├── Frontend (React + Vite + Tailwind)
│   ├── 25+ pages: Terminal, Scanner, Positions, Journal, Backtest, ML Center, Finance...
│   └── WebSocket: Live position MTM updates
├── Ollama (offline LLM)
│   └── llama3.2:3b — trading assistant with real data context
└── Docker Compose: db + backend + frontend + ollama
```
