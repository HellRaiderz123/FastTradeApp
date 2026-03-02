import axios from 'axios';

// Default to Vite dev proxy (/api). Override via VITE_API_BASE if needed.
const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

const AUTH_TOKEN_KEY = 'fasttrade_auth_token';

export const authTokenStore = {
  get: () => localStorage.getItem(AUTH_TOKEN_KEY) || '',
  set: (token: string) => localStorage.setItem(AUTH_TOKEN_KEY, token),
  clear: () => localStorage.removeItem(AUTH_TOKEN_KEY),
};

api.interceptors.request.use((config) => {
  const token = authTokenStore.get();
  if (token) {
    config.headers = config.headers || {};
    (config.headers as any).Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Global Error Interceptor ───────────────────────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status;
      if (status === 503) {
        console.error('⚠️ Service unavailable (503) — backend may be overloaded or Zerodha API is down');
      } else if (status === 401) {
        console.error('🔒 Unauthorized (401) — authentication required');
      } else if (status >= 500) {
        console.error(`❌ Server error (${status}) on ${error.config?.url}`);
      }
    } else if (error.code === 'ECONNABORTED') {
      console.error('⏱️ Request timed out:', error.config?.url);
    } else if (!error.response) {
      console.error('🌐 Network error — cannot reach backend:', error.message);
    }
    return Promise.reject(error);
  }
);

// Account APIs
export const accountAPI = {
  getProfile: () =>
    api.get('/account/profile'),
  
  getCapital: () =>
    api.get('/account/capital'),
  
  getDailyCapital: (days: number = 30) =>
    api.get(`/account/daily-capital?days=${days}`),
  
  recordDailyCapital: (capital: number, date?: string) =>
    api.post('/account/daily-capital', { capital, date }),
};

// Strategy APIs (CRUD)
export const strategyAPI = {
  // Legacy - Run strategy directly
  runStrategy: (payload: any) =>
    api.post('/strategy/option-spread/15m/run', payload),
  
  // Phase 1 - Strategy Management
  listStrategies: (enabledOnly?: boolean) =>
    api.get('/strategies', { params: { enabled_only: enabledOnly } }),
  
  getStrategy: (id: number) =>
    api.get(`/strategies/${id}`),
  
  createStrategy: (data: any) =>
    api.post('/strategies', data),
  
  updateStrategy: (id: number, data: any) =>
    api.put(`/strategies/${id}`, data),
  
  deleteStrategy: (id: number) =>
    api.delete(`/strategies/${id}`),
  
  enableStrategy: (id: number) =>
    api.post(`/strategies/${id}/enable`),
  
  disableStrategy: (id: number) =>
    api.post(`/strategies/${id}/disable`),
  
  getStatus: (id: number) =>
    api.get(`/strategies/${id}/status`),
  
  createFromSuggestion: (data: any) =>
    api.post('/strategies/create-from-suggestion', data),
};

// Execution APIs
export const executionAPI = {
  // Legacy
  createIntent: (runId: number, capital?: number) =>
    api.post(
      '/intent/create',
      null,
      {
        params: {
          run_id: runId,
          ...(capital !== undefined ? { capital } : {}),
        },
      }
    ),

  executeIntent: (intentId: string, idempotencyKey: string) =>
    api.post(
      `/execute/paper/${intentId}`,
      null,
      {
        headers: { 'idempotency-key': idempotencyKey },
      }
    ),
  
  confirmIntent: (intentId: string) =>
    api.post(`/intent/confirm/${intentId}`, {}),
  
  // Phase 2 - Registry-based execution
  executeSingle: (strategyId: number, context?: any) =>
    api.post('/strategies/run/single', {
      strategy_id: strategyId,
      additional_context: context,
    }),
  
  executeMultiple: (strategyIds: number[], context?: any) =>
    api.post('/strategies/run/multiple', {
      strategy_ids: strategyIds,
      additional_context: context,
    }),
  
  executeAll: (context?: any) =>
    api.post('/strategies/run/all', {
      additional_context: context,
    }),
  
  getExecutionStatus: (strategyId: number) =>
    api.get(`/strategies/run/${strategyId}/status`),
};

// Exit APIs
export const exitAPI = {
  autoExit: () => api.post('/exit/auto', {}),
  manualExit: (intentId: string) =>
    api.post(`/exit/manual/${intentId}`, {}),
};

// Paper Trading APIs
export const paperAPI = {
  updateMtM: () => api.post('/paper/mtm/update', {}),
  getPositions: () => api.get('/paper/positions'),
};

// Journal APIs
export const journalAPI = {
  getStrategyRuns: (limit = 50) =>
    api.get(`/journal/strategy-runs?limit=${limit}`),
  getExecutionIntents: (limit = 50) =>
    api.get(`/journal/execution-intents?limit=${limit}`),
  getSpreadAnalysis: (limit = 50) =>
    api.get(`/journal/spread-analysis?limit=${limit}`),
  getSignalDiagnostics: (params?: { limit?: number; lookback_days?: number; underlying?: string; strategy?: string }) =>
    api.get('/journal/signal-diagnostics', { params }),
};

// Smart Position Suggestions API
export const smartSuggestionsAPI = {
  get: () => api.get('/positions/smart-suggestions'),
};

// Auto-Trader API
export const autoTraderAPI = {
  getConfig: () => api.get('/auto-trader/config'),
  updateConfig: (data: Record<string, any>) => api.put('/auto-trader/config', data),
  getStatus: () => api.get('/auto-trader/status'),
  start: () => api.post('/auto-trader/start'),
  stop: () => api.post('/auto-trader/stop'),
  pause: () => api.post('/auto-trader/pause'),
  resetDaily: () => api.post('/auto-trader/reset-daily'),
  getLogs: (params?: { limit?: number; action?: string; underlying?: string; severity?: string }) =>
    api.get('/auto-trader/logs', { params }),
  clearLogs: () => api.delete('/auto-trader/logs'),
};

// Market Data APIs
export const marketAPI = {
  getCandles: (symbol: string, interval: string = '15minute', from_date?: string, to_date?: string) =>
    api.get(`/market/candles/${symbol}`, { 
      params: { interval, from_date, to_date } 
    }),
  
  // Get candles from database (multi-timeframe support)
  getCandlesDB: (symbol: string, timeframe: '1m' | '5m' | '15m' | '1h' | 'daily', limit: number = 50) =>
    api.get(`/candles/${timeframe}/${symbol}`, {
      params: { limit }
    }),
  
  // Get live LTP (Last Traded Price) for spot price
  getLTP: (symbol: string = 'NIFTY') =>
    api.get(`/market/ltp/${symbol}`),
  
  // Get bulk quotes for multiple symbols
  getBulkQuotes: (symbols: string[]) =>
    api.get(`/market/bulk-quotes`, { 
      params: { symbols: symbols.join(',') } 
    }),
  
  // Get sector performance data
  getSectorPerformance: () =>
    api.get(`/market/sector-performance`),
  
  // Get option chain for a symbol and expiry
  getOptionChain: (symbol: string = 'NIFTY', expiry: string) =>
    api.get(`/market/option-chain/${symbol}`, { params: { expiry } }),
  
  // Get available expiry dates for options
  getAvailableExpiries: (symbol: string = 'NIFTY') =>
    api.get(`/market/expiries/${symbol}`),
  
  // Get premium for a specific strike
  getOptionPremium: (symbol: string, strike: number, option_type: 'CE' | 'PE', expiry: string) =>
    api.get(`/market/option-premium`, { 
      params: { symbol, strike, option_type, expiry } 
    }),
};

// Screener APIs
export const screenerAPI = {
  // Filter stocks based on criteria
  filterStocks: (filters: any) =>
    api.post(`/screener/filter`, filters),
  
  // Get predefined screener presets
  getPresets: () =>
    api.get(`/screener/presets`),
};

// Options Chain APIs
export const optionsAPI = {
  // Get full options chain with real market data from Zerodha
  // REAL DATA: Uses live premiums, volume, OI from Zerodha API
  getChain: (symbol: string, expiry?: string) =>
    api.get(`/options/real/chain/${symbol}`, { params: { expiry } }),
  
  // Get available expiry dates from actual Zerodha instruments
  getExpiries: (symbol: string) =>
    api.get(`/options/real/expiries/${symbol}`),
  
  // OLD STUB ENDPOINTS (simulated data):
  // getChain: (symbol: string, expiry?: string) =>
  //   api.get(`/options/chain/${symbol}`, { params: { expiry } }),
  // getExpiries: (symbol: string) =>
  //   api.get(`/options/expiries/${symbol}`),
};

// System Control APIs
export const systemAPI = {
  enable: () => api.post('/system/enable', {}),
  disable: () => api.post('/system/disable', {}),
  status: () => api.get('/system/status'),
};

// Alerts APIs
export const alertsAPI = {
  createAlert: (payload: {
    name?: string;
    ticker: string;
    alert_type?: string;
    condition: { operator: string; price: number };
    is_enabled?: boolean;
    is_recurring?: boolean;
    notify_via?: Record<string, any>;
    action_on_trigger?: string;
    created_by?: string;
  }) => api.post('/alerts/create', payload),

  listAlerts: (ticker?: string) =>
    api.get('/alerts/list', { params: ticker ? { ticker } : {} }),

  enableAlert: (id: number) => api.post(`/alerts/${id}/enable`, {}),
  disableAlert: (id: number) => api.post(`/alerts/${id}/disable`, {}),
  deleteAlert: (id: number) => api.delete(`/alerts/${id}`),
  evaluateAlerts: (ticker?: string) =>
    api.post('/alerts/evaluate', {}, { params: ticker ? { ticker } : {} }),
};

// Greeks Calculation APIs
export const greeksAPI = {
  calculate: (payload: any) =>
    api.post('/greeks/calculate', payload),
  
  calculateSingle: (leg: any) =>
    api.post('/greeks/single', leg),
};

// Backtest APIs
export const backtestAPI = {
  run: (payload: any) => api.post('/backtest/run', payload),
  getResult: (id: number) => api.get(`/backtest/results/${id}`),
  listForStrategy: (strategyId: number) => api.get(`/backtest/strategy/${strategyId}`),
  compare: (backtestIds: number[]) => api.post('/backtest/compare', { backtest_ids: backtestIds }),
};

// Suggestions APIs (AlgoRoom-like)
export const suggestionsAPI = {
  get: (payload: any) => api.post('/suggestions', payload),
};

// Stock Suggestions APIs
export const stockSuggestionsAPI = {
  get: (payload: any) => api.post('/suggestions/stocks', payload),
  getAvailableSymbols: () => api.get('/suggestions/stocks/available-symbols'),
};

// Settings APIs
export const settingsAPI = {
  getZerodhaSettings: () =>
    api.get('/settings/zerodha'),
  
  saveZerodhaCredentials: (credentials: { api_key: string; api_secret: string }) =>
    api.post('/settings/zerodha/credentials', credentials),
  
  saveZerodhaToken: (token: { access_token: string }) =>
    api.post('/settings/zerodha/token', token),
  
  generateZerodhaToken: (data: { request_token: string }) =>
    api.post('/settings/zerodha/generate-token', data),
  
  getZerodhaLoginUrl: (callbackUrl?: string) =>
    api.get('/settings/zerodha/login-url', { params: { callback_url: callbackUrl } }),
  
  handleZerodhaCallback: (requestToken: string) =>
    api.get('/settings/zerodha/callback', { params: { request_token: requestToken } }),
  
  getZerodhaSessionStatus: () =>
    api.get('/settings/zerodha/session-status'),
  
  logoutZerodha: () =>
    api.post('/settings/zerodha/logout'),
  
  setExecutionMode: (mode: string) =>
    api.post(`/settings/execution-mode`, {}, { params: { mode } }),

  // Trading settings
  getTradingSettings: () =>
    api.get('/settings/trading'),

  saveTradingSettings: (data: { risk_per_trade: number; max_trades_per_day: number }) =>
    api.post('/settings/trading', data),

  // Risk limits (DB-backed)
  getRiskLimits: () => api.get('/settings/risk'),

  saveRiskLimits: (data: {
    max_portfolio_loss_pct: number;
    max_trades_per_day: number;
    iv_regime_limits: Record<string, { min_atm_dist_pct: number; max_risk_pct_capital: number }>;
  }) => api.post('/settings/risk', data),

  // Notification settings (Gmail)
  getNotificationSettings: () =>
    api.get('/settings/notifications'),

  saveGmailSettings: (data: { gmail_user: string; gmail_app_password: string; alert_email: string }) =>
    api.post('/settings/notifications/gmail', data),

  setGmailEnabled: (enabled: boolean) =>
    api.post('/settings/notifications/gmail/enabled', { enabled }),

  sendTestEmail: (subject?: string, body?: string) =>
    api.post('/settings/notifications/gmail/test', null, { params: { subject, body } }),

  // ML Settings
  getMLSettings: () =>
    api.get('/settings/ml'),

  saveMLSettings: (data: { enabled: boolean; confidence_threshold: number; auto_train_enabled: boolean; retraining_frequency: string }) =>
    api.post('/settings/ml', data),
};

// ML APIs
export const mlAPI = {
  getMetrics: () => api.get('/ml/metrics'),
  train: () => api.post('/ml/train'),
  trainStock: (symbol: string) => api.post(`/ml/train-stock/${symbol}`),
  backfill: () => api.post('/ml/backfill'),
  getBackfillStatus: () => api.get('/ml/backfill-status'),
  getDataSummary: () => api.get('/ml/data-summary'),
  getModelInfo: () => api.get('/ml/model-info'),
  getPerformance: () => api.get('/ml/performance'),
  getTrainingHistory: () => api.get('/ml/training-history'),
  predict: (symbol: string) => api.get(`/ml/predict/${symbol}`),
  predictBulk: (symbols: string[]) => api.post('/ml/predict-bulk', { symbols }),
};

// Finance APIs
export const financeAPI = {
  // 🔹 Bulk insert transactions (CSV import)
  bulkCreateTransactions: (transactions: {
    tran_date: string;
    description: string;
    debit: number;
    credit: number;
    balance: number;
    category: string;
    source?: string;
  }[]) =>
    api.post('/finance/transactions', transactions),

  // 🔹 Fetch all finance transactions
  getTransactions: () =>
    api.get('/finance/transactions'),

  // 🔹 Update category for a single transaction
  updateTransactionCategory: (
    transactionId: number,
    category: string
  ) =>
    api.patch(
      `/finance/transactions/${transactionId}`,
      { category }
    ),

  // 🔹 Delete / clear all finance transactions
  clearAllTransactions: () =>
    api.delete('/finance/transactions'),

  deleteTransaction: (transactionId: number) =>
    api.delete(`/finance/transactions/${transactionId}`),

  // ========== RECURRING TRANSACTIONS ==========
  createRecurringTransaction: (payload: any) =>
    api.post('/finance/recurring', payload),

  getRecurringTransactions: () =>
    api.get('/finance/recurring'),

  updateRecurringTransaction: (recurringId: number, isActive: boolean) =>
    api.patch(`/finance/recurring/${recurringId}`, { is_active: isActive }),

  deleteRecurringTransaction: (recurringId: number) =>
    api.delete(`/finance/recurring/${recurringId}`),

  // ========== BUDGETS ==========
  createBudget: (payload: any) =>
    api.post('/finance/budgets', payload),

  getBudgets: (month?: string) =>
    api.get('/finance/budgets', { params: { month } }),

  getBudgetStatus: (category: string, month?: string) =>
    api.get(`/finance/budgets/status/${category}`, { params: { month } }),

  deleteBudget: (budgetId: number) =>
    api.delete(`/finance/budgets/${budgetId}`),

  // ========== SAVINGS GOALS ==========
  createSavingsGoal: (payload: any) =>
    api.post('/finance/goals', payload),

  getSavingsGoals: () =>
    api.get('/finance/goals'),

  updateSavingsGoalAmount: (goalId: number, amount: number) =>
    api.patch(`/finance/goals/${goalId}`, { amount }),

  deleteSavingsGoal: (goalId: number) =>
    api.delete(`/finance/goals/${goalId}`),

  // ========== BILL REMINDERS ==========
  createBillReminder: (payload: any) =>
    api.post('/finance/bills', payload),

  getBillReminders: () =>
    api.get('/finance/bills'),

  markBillPaid: (billId: number) =>
    api.patch(`/finance/bills/${billId}/pay`),

  deleteBillReminder: (billId: number) =>
    api.delete(`/finance/bills/${billId}`),

  // ========== EXPENSE FORECASTING ==========
  generateForecast: (category: string, monthsBack?: number) =>
    api.post(`/finance/forecast/${category}`, { months_back: monthsBack || 3 }),

  getExpenseForecasts: (month?: string) =>
    api.get('/finance/forecast', { params: { month } }),

  // ========== TRENDS ==========
  getTrends: (months: number = 6, top_n: number = 5) =>
    api.get('/finance/trends', { params: { months, top_n } }),

  // ========== CURRENCY EXCHANGE ==========
  setExchangeRate: (fromCurrency: string, toCurrency: string, rate: number) =>
    api.post(`/finance/currency/${fromCurrency}/${toCurrency}/${rate}`),

  getExchangeRate: (fromCurrency: string, toCurrency: string) =>
    api.get(`/finance/currency/${fromCurrency}/${toCurrency}`),

  getAllExchangeRates: () =>
    api.get('/finance/currency'),

  // ========== ZERODHA POSITIONS SECTION ==========
  getZerodhaPositions: () =>
    api.get('/zerodha/positions'),

  getZerodhaOrders: () =>
    api.get('/zerodha/orders'),

  getZerodhaHoldings: () =>
    api.get('/zerodha/holdings'),
};

// Trade Cost APIs
export const tradeCostAPI = {
  calculate: (trade: {
    symbol: string;
    trade_type: 'BUY' | 'SELL';
    segment: 'EQUITY' | 'FNO';
    product_type: 'DELIVERY' | 'INTRADAY' | 'OPTIONS' | 'FUTURES';
    quantity: number;
    price: number;
    intent_id?: string;
    order_id?: string;
  }) => api.post('/trade-costs/calculate', trade),
  
  getHistory: (limit?: number) =>
    api.get('/trade-costs/history', { params: { limit } }),
  
  getSummary: () =>
    api.get('/trade-costs/summary'),
  
  getConfig: () =>
    api.get('/trade-costs/config'),
  
  updateConfig: (config: any) =>
    api.post('/trade-costs/config', config),
};

// Watchlist APIs
export const watchlistAPI = {
  getAll: (includeInactive?: boolean) =>
    api.get('/watchlists', { params: { include_inactive: includeInactive } }),
  
  get: (id: number) =>
    api.get(`/watchlists/${id}`),
  
  create: (data: {
    name: string;
    description?: string;
    symbols?: string[];
    color?: string;
    icon?: string;
    is_default?: boolean;
  }) => api.post('/watchlists', data),
  
  update: (id: number, data: {
    name?: string;
    description?: string;
    symbols?: string[];
    color?: string;
    icon?: string;
    is_default?: boolean;
  }) => api.put(`/watchlists/${id}`, data),
  
  delete: (id: number, softDelete?: boolean) =>
    api.delete(`/watchlists/${id}`, { params: { soft_delete: softDelete } }),
  
  addSymbol: (id: number, symbol: string) =>
    api.post(`/watchlists/${id}/symbols/${symbol}`),
  
  removeSymbol: (id: number, symbol: string) =>
    api.delete(`/watchlists/${id}/symbols/${symbol}`),
  
  getQuotes: (id: number) =>
    api.get(`/watchlists/${id}/quotes`),
};

export default api;

// FIX: positionsAPI was previously declared BEFORE the `api` axios instance was
// created, causing a ReferenceError (Temporal Dead Zone) at runtime whenever
// updateTPSL was called. Moved here so `api` is guaranteed to exist.
export const positionsAPI = {
  updateTPSL: (intentId: string, { tp, sl, trailing_sl }: { tp?: number; sl?: number; trailing_sl?: number }) =>
    api.patch(`/intent/${intentId}/update_tp_sl`, { tp, sl, trailing_sl }),
};

// Authentication APIs
export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
  logout: () => {
    authTokenStore.clear();
  },
};