import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';

const API_BASE_STORAGE_KEY = 'fasttrade_api_base_url';
const AI_API_BASE_STORAGE_KEY = 'fasttrade_ai_api_base_url';
export const AUTH_TOKEN_STORAGE_KEY = 'fasttrade_auth_token';

let unauthorizedHandler: (() => void | Promise<void>) | null = null;
export const setUnauthorizedHandler = (handler: (() => void | Promise<void>) | null) => {
  unauthorizedHandler = handler;
};

const trimTrailingSlash = (url: string) => url.replace(/\/+$/, '');
const DEFAULT_BACKEND_PORT = '8000';

const extractExpoHost = (): string | null => {
  const candidates = [
    (Constants.expoConfig as { hostUri?: string } | undefined)?.hostUri,
    (Constants as any)?.expoGoConfig?.debuggerHost,
    (Constants as any)?.manifest2?.extra?.expoClient?.hostUri,
    (Constants as any)?.manifest?.debuggerHost,
  ];

  for (const candidate of candidates) {
    if (typeof candidate !== 'string' || !candidate.trim()) continue;
    const host = candidate.split(',')[0].trim().split(':')[0]?.trim();
    if (host) {
      return host;
    }
  }

  return null;
};

const isLegacyDevApiBase = (url: string) => {
  const normalized = trimTrailingSlash(url);
  return (
    /:[\/]?11434\b/i.test(normalized) ||
    /^https?:\/\/192\.168\.1\.(101|103):8000$/i.test(normalized) ||
    (Platform.OS === 'android' && /^https?:\/\/(localhost|127\.0\.0\.1):8000$/i.test(normalized))
  );
};

const getDefaultApiBaseUrl = () => {
  const expoHost = extractExpoHost();

  if (expoHost && expoHost !== 'localhost' && expoHost !== '127.0.0.1') {
    return `http://${expoHost}:${DEFAULT_BACKEND_PORT}`;
  }

  if (Platform.OS === 'web') {
    return `http://localhost:${DEFAULT_BACKEND_PORT}`;
  }
  if (Platform.OS === 'android') {
    return `http://10.0.2.2:${DEFAULT_BACKEND_PORT}`;
  }
  return `http://127.0.0.1:${DEFAULT_BACKEND_PORT}`;
};

const getDefaultAiApiBaseUrl = () => getDefaultApiBaseUrl();

const envApiBase = process.env.EXPO_PUBLIC_API_BASE_URL;
const envAiApiBase = process.env.EXPO_PUBLIC_AI_API_BASE_URL;
const extraApiBase = (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl;
const extraAiApiBase = (Constants.expoConfig?.extra as { aiApiBaseUrl?: string } | undefined)?.aiApiBaseUrl;

let API_BASE = trimTrailingSlash(envApiBase || extraApiBase || getDefaultApiBaseUrl());
let AI_API_BASE = trimTrailingSlash(envAiApiBase || extraAiApiBase || getDefaultAiApiBaseUrl());

export const getApiBaseUrl = () => API_BASE;
export const getAiApiBaseUrl = () => AI_API_BASE;
export { getDefaultApiBaseUrl, getDefaultAiApiBaseUrl };

export const setApiBaseUrl = (nextUrl: string) => {
  const normalized = trimTrailingSlash(nextUrl.trim());
  API_BASE = normalized;
  api.defaults.baseURL = normalized;
};

export const setAiApiBaseUrl = (nextUrl: string) => {
  const normalized = trimTrailingSlash(nextUrl.trim());
  AI_API_BASE = normalized;
  aiApi.defaults.baseURL = normalized;
};

export const persistApiBaseUrl = async (nextUrl: string) => {
  setApiBaseUrl(nextUrl);
  await AsyncStorage.setItem(API_BASE_STORAGE_KEY, getApiBaseUrl());
};

export const persistAiApiBaseUrl = async (nextUrl: string) => {
  setAiApiBaseUrl(nextUrl);
  await AsyncStorage.setItem(AI_API_BASE_STORAGE_KEY, getAiApiBaseUrl());
};

export const syncApiBaseUrlFromStorage = async () => {
  const stored = await AsyncStorage.getItem(API_BASE_STORAGE_KEY);
  if (stored?.trim()) {
    const normalizedStored = trimTrailingSlash(stored);
    if (isLegacyDevApiBase(normalizedStored)) {
      const migrated = getDefaultApiBaseUrl();
      setApiBaseUrl(migrated);
      await AsyncStorage.setItem(API_BASE_STORAGE_KEY, migrated);
    } else {
      setApiBaseUrl(normalizedStored);
    }
  }
  return getApiBaseUrl();
};

export const syncAiApiBaseUrlFromStorage = async () => {
  const stored = await AsyncStorage.getItem(AI_API_BASE_STORAGE_KEY);
  if (stored?.trim()) {
    const normalizedStored = trimTrailingSlash(stored);
    // Migration: older versions stored direct Ollama URL (:11434), but mobile
    // AI client calls /ai-chat/query which is served by FastTrade backend.
    // Move stale Ollama base or legacy LAN IP to backend base to avoid connection issues.
    if (isLegacyDevApiBase(normalizedStored)) {
      setAiApiBaseUrl(getApiBaseUrl());
      await AsyncStorage.setItem(AI_API_BASE_STORAGE_KEY, getAiApiBaseUrl());
    } else {
      setAiApiBaseUrl(normalizedStored);
    }
  }
  return getAiApiBaseUrl();
};

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

const aiApi = axios.create({
  baseURL: AI_API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 120000, // LLM inference can take 60–90s
});

syncApiBaseUrlFromStorage().catch(() => {
  // no-op: app continues with default/env base URL
});

syncAiApiBaseUrlFromStorage().catch(() => {
  // no-op: app continues with default/env AI base URL
});

// Auth interceptor
api.interceptors.request.use(async (config) => {
  config.baseURL = getApiBaseUrl();
  const token = await authTokenStore.get();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

aiApi.interceptors.request.use(async (config) => {
  config.baseURL = getAiApiBaseUrl();
  const token = await authTokenStore.get();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    const url = String(error?.config?.url || '');
    if (status === 401 && !url.includes('/auth/login')) {
      await authTokenStore.clear();
      if (unauthorizedHandler) {
        await unauthorizedHandler();
      }
    }
    return Promise.reject(error);
  }
);

aiApi.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status;
    if (status === 401) {
      await authTokenStore.clear();
      if (unauthorizedHandler) {
        await unauthorizedHandler();
      }
    }
    return Promise.reject(error);
  }
);

const isConnectivityError = (error: any) => {
  if (error?.response) return false;
  const details = `${error?.code || ''} ${error?.message || ''}`;
  return /ECONNABORTED|timeout|Network Error|network request failed/i.test(details);
};

const attachConnectionHelp = (error: any, baseUrl: string) => {
  if (error && !error?.response) {
    error.message = `Could not reach FastTrade backend at ${baseUrl}. If you're on the Android emulator, use http://10.0.2.2:8000. On a real phone, use your PC's LAN IP.`;
  }
  return error;
};

// ── Journal / Positions ──────────────────────────────────────────────
export const journalAPI = {
  getExecutionIntents: (limit = 50) =>
    api.get(`/journal/execution-intents?limit=${limit}`),
  getSignalDiagnostics: (params?: any) =>
    api.get('/journal/signal-diagnostics', { params }),
  deleteExecutionIntent: (intentId: string) =>
    api.delete(`/journal/execution-intents/${intentId}`),
  clearClosedTrades: () =>
    api.delete('/journal/execution-intents/closed'),
};

// ── Exit ─────────────────────────────────────────────────────────────
export const exitAPI = {
  manualExit: (intentId: string) =>
    api.post(`/exit/manual/${intentId}`, {}),
};

// ── Intent (TP/SL) ──────────────────────────────────────────────────
export const intentAPI = {
  updateTpSl: (intentId: string, payload: { tp?: number; sl?: number; tp_pct?: number; sl_pct?: number; trailing_sl?: number }) =>
    api.patch(`/intent/${intentId}/update_tp_sl`, payload),
};

// ── System ───────────────────────────────────────────────────────────
export const systemAPI = {
  status: () => api.get('/system/status'),
  enable: () => api.post('/system/enable', {}),
  disable: () => api.post('/system/disable', {}),
};

// ── Condition Scanner ────────────────────────────────────────────────
export const scannerAPI = {
  listStrategies: () => api.get('/condition-scanner/strategies'),
  getStrategy: (id: number) => api.get(`/condition-scanner/strategies/${id}`),
  explainStrategy: (id: number) => api.get(`/condition-scanner/strategies/${id}/explain`),
  deleteStrategy: (id: number) => api.delete(`/condition-scanner/strategies/${id}`),
  scanStrategy: (id: number) => api.post(`/condition-scanner/scan/${id}`),
  runBacktest: (id: number, payload?: any) => api.post(`/condition-scanner/backtest/${id}`, payload || {}),
  getCandleRange: (timeframe: string, universe = 'NIFTY50') =>
    api.get(`/condition-scanner/candle-range/${encodeURIComponent(timeframe)}`, { params: { universe } }),
  getHistory: (params?: any, timeout = 30000) =>
    api.get('/condition-scanner/history', { params, timeout }),
  executeSignal: (body: any) => api.post('/condition-scanner/execute-signal', body),
  startAutoScan: (id: number) => api.post(`/condition-scanner/scheduler/start/${id}`),
  stopAutoScan: (id: number) => api.post(`/condition-scanner/scheduler/stop/${id}`),
  setAutoAmount: (id: number, amount: number) => api.put(`/condition-scanner/scheduler/amount/${id}`, null, { params: { amount } }),
};

// ── Auto Trader ──────────────────────────────────────────────────────
export const autoTraderAPI = {
  getStatus: () => api.get('/auto-trader/status'),
  getConfig: () => api.get('/auto-trader/config'),
  updateConfig: (payload: any) => api.put('/auto-trader/config', payload),
  start: () => api.post('/auto-trader/start'),
  stop: () => api.post('/auto-trader/stop'),
  pause: () => api.post('/auto-trader/pause'),
  resetDaily: () => api.post('/auto-trader/reset-daily'),
  getLogs: (params?: any) => api.get('/auto-trader/logs', { params }),
};

// ── Market ───────────────────────────────────────────────────────────
export const marketAPI = {
  getLTP: (symbol = 'NIFTY') => api.get(`/market/ltp/${symbol}`),
  getSectorPerformance: () => api.get('/market/sector-performance'),
  getAvailableExpiries: (symbol = 'NIFTY') => api.get(`/market/expiries/${symbol}`),
  getOptionPremium: (symbol: string, strike: number, optionType: string, expiry: string) =>
    api.get('/market/option-premium', { params: { symbol, strike, option_type: optionType, expiry } }),
};

export const marketDashboardAPI = {
  getTopMovers: (params?: { limit?: number; universe?: string }) =>
    api.get('/market-dashboard/top-movers', { params }),
  getMarketBreadth: (params?: { universe?: string }) =>
    api.get('/market-dashboard/market-breadth', { params }),
  getHeatmap: () => api.get('/market-dashboard/heatmap'),
  getSectorPerformance: () => api.get('/market-dashboard/sector-performance'),
  getStockTechnicals: (symbol: string) => api.get(`/market-dashboard/stock-technicals/${symbol}`),
};

export const screenerAPI = {
  filterStocks: (filters: any) => api.post('/screener/filter', filters),
  getPresets: () => api.get('/screener/presets'),
};

export const reconcileAPI = {
  getStatus: () => api.get('/reconcile/status'),
  run: () => api.post('/reconcile/run'),
};

export const calendarAPI = {
  getEvents: (params?: { days_ahead?: number; event_type?: string }) =>
    api.get('/calendar/events', { params }),
  getToday: () => api.get('/calendar/today'),
  getWeek: () => api.get('/calendar/week'),
  getEarnings: (days_ahead = 30) => api.get('/calendar/earnings', { params: { days_ahead } }),
  getIpo: (days_ahead = 30) => api.get('/calendar/ipo', { params: { days_ahead } }),
};

// ── AI Chat ──────────────────────────────────────────────────────────
const AI_TIMEOUT = 120000; // 2 min — LLM inference is slow

const hasChatAnswerShape = (data: any): boolean => {
  if (!data) return false;
  if (typeof data === 'string') return false;
  return Boolean(data.answer || data.response || data.message);
};

export const aiAPI = {
  query: async (
    message: string,
    history: any[] = [],
    options: { voice_mode?: boolean; assistant_style?: string } = {},
  ) => {
    const payload = { message, history, ...options };
    try {
      const primary = await aiApi.post('/ai-chat/query', payload, { timeout: AI_TIMEOUT });
      // AI base can be reachable but mispointed (health/html payload). In that case,
      // retry through main API base which is typically user-configured and verified.
      if (hasChatAnswerShape(primary?.data)) {
        return primary;
      }
      return api.post('/ai-chat/query', payload, { timeout: AI_TIMEOUT });
    } catch (error: any) {
      const status = error?.response?.status;
      // Fallback to main backend when AI backend is down/unreachable/misconfigured.
      // Keep 4xx (except 404) as-is because they are usually request/auth issues.
      if (!status || status >= 500 || status === 404) {
        return api.post('/ai-chat/query', payload, { timeout: AI_TIMEOUT });
      }
      throw error;
    }
  },
};

// ── Finance ──────────────────────────────────────────────────────────
export const financeAPI = {
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
  getTransactions: () => api.get('/finance/transactions'),
  updateTransactionCategory: (transactionId: number, category: string) =>
    api.patch(`/finance/transactions/${transactionId}`, { category }),
  clearAllTransactions: () => api.delete('/finance/transactions'),
  deleteTransaction: (transactionId: number) =>
    api.delete(`/finance/transactions/${transactionId}`),

  createRecurringTransaction: (payload: any) =>
    api.post('/finance/recurring', payload),
  getRecurringTransactions: () => api.get('/finance/recurring'),
  updateRecurringTransaction: (recurringId: number, isActive: boolean) =>
    api.patch(`/finance/recurring/${recurringId}`, { is_active: isActive }),
  deleteRecurringTransaction: (recurringId: number) =>
    api.delete(`/finance/recurring/${recurringId}`),

  createBudget: (payload: any) =>
    api.post('/finance/budgets', payload),
  getBudgets: (month?: string) => api.get('/finance/budgets', { params: { month } }),
  getBudgetStatus: (category: string, month?: string) =>
    api.get(`/finance/budgets/status/${category}`, { params: { month } }),
  getAllBudgetStatuses: (month?: string) =>
    api.get('/finance/budgets/status', { params: { month } }),
  deleteBudget: (budgetId: number) =>
    api.delete(`/finance/budgets/${budgetId}`),

  createSavingsGoal: (payload: any) =>
    api.post('/finance/goals', payload),
  getSavingsGoals: () => api.get('/finance/goals'),

  createBillReminder: (payload: any) =>
    api.post('/finance/bills', payload),
  getBillReminders: () => api.get('/finance/bills'),

  getExpenseForecasts: (month?: string) =>
    api.get('/finance/forecast', { params: { month } }),
  getTrends: (months = 6, topN = 5) =>
    api.get('/finance/trends', { params: { months, top_n: topN } }),
};

// ── Analytics ────────────────────────────────────────────────────────
export const analyticsAPI = {
  getStrategyPnL: (params?: any) =>
    api.get('/analytics/pnl', { params }).catch(() => api.get('/analytics/strategy-pnl', { params })),
};

// ── Legacy Compatibility APIs ───────────────────────────────────────
export const strategyAPI = {
  runStrategy: (payload: any) => api.post('/strategy/option-spread/15m/run', payload),
};

export const executionAPI = {
  createIntent: (runId: number, riskMode: string) =>
    api.post(`/intent/create?run_id=${runId}&risk_mode=${riskMode}`, {}),
  executeIntent: (intentId: string, idempotencyKey: string) =>
    api.post(`/execute/paper/${intentId}`, {}, { headers: { 'idempotency-key': idempotencyKey } }),
  confirmIntent: (intentId: string) => api.post(`/intent/confirm/${intentId}`, {}),
};

export const paperAPI = {
  updateMtM: () => api.post('/paper/mtm/update', {}),
  getPositions: () => api.get('/paper/positions'),
};

export const greeksAPI = {
  calculate: (payload: any) => api.post('/greeks/calculate', payload),
};

export const backtestAPI = {
  runBacktest: (payload: any) => api.post('/backtest/run', payload),
};

export const optionsAPI = {
  getChain: (symbol: string, expiry?: string) =>
    api.get(`/options/chain/${symbol}`, { params: expiry ? { expiry } : {} }),
};

// ── Watchlists ──────────────────────────────────────────────────────
export const watchlistAPI = {
  list: () => api.get('/watchlists'),
  get: (id: number) => api.get(`/watchlists/${id}`),
  create: (payload: { name: string; description?: string; symbols?: string[]; color?: string }) =>
    api.post('/watchlists', payload),
  update: (id: number, payload: any) => api.put(`/watchlists/${id}`, payload),
  remove: (id: number) => api.delete(`/watchlists/${id}`),
  addSymbol: (id: number, symbol: string) => api.post(`/watchlists/${id}/symbols/${symbol}`),
  removeSymbol: (id: number, symbol: string) => api.delete(`/watchlists/${id}/symbols/${symbol}`),
  getQuotes: (id: number) => api.get(`/watchlists/${id}/quotes`),
};

// ── Price Alerts ─────────────────────────────────────────────────────
export const alertsAPI = {
  list: (ticker?: string) => api.get('/alerts/list', ticker ? { params: { ticker } } : {}),
  create: (payload: { ticker: string; condition: { operator: string; price: number }; name?: string; alert_type?: string }) =>
    api.post('/alerts/create', { alert_type: 'PRICE', is_enabled: true, notify_via: [], ...payload }),
  enable: (id: number) => api.post(`/alerts/${id}/enable`),
  disable: (id: number) => api.post(`/alerts/${id}/disable`),
  remove: (id: number) => api.delete(`/alerts/${id}`),
};

// ── Trade Costs ──────────────────────────────────────────────────────
export const tradeCostAPI = {
  calculate: (payload: any) => api.post('/trade-costs/calculate', payload),
  getHistory: (params?: any) => api.get('/trade-costs/history', { params }),
  getSummary: () => api.get('/trade-costs/summary'),
  getConfig: () => api.get('/trade-costs/config'),
};

export const mlAPI = {
  getMetrics: () => api.get('/ml/metrics'),
  train: () => api.post('/ml/train'),
  backfill: () => api.post('/ml/backfill'),
  getBackfillStatus: () => api.get('/ml/backfill-status'),
  getDataSummary: () => api.get('/ml/data-summary'),
  getModelInfo: () => api.get('/ml/model-info'),
  getPerformance: () => api.get('/ml/performance'),
  getTrainingHistory: () => api.get('/ml/training-history'),
  predict: (symbol: string) => api.get(`/ml/predict/${symbol}`),
  predictBulk: (symbols: string[]) => api.post('/ml/predict-bulk', { symbols }),
};

// ── AI Agents (Multi-Agent Analysis Pipeline) ────────────────────────
export const aiAgentsAPI = {
  health: () =>
    api.get('/ai-analysis/health'),
  analyze: (symbol: string, exchange = 'NSE') =>
    api.post('/ai-analysis/analyze', { symbol, exchange }, { timeout: 10000 }),
  status: (jobId: string) =>
    api.get(`/ai-analysis/status/${jobId}`),
  history: (symbol: string, limit = 10) =>
    api.get(`/ai-analysis/history/${symbol}`, { params: { limit } }),
  evaluateOutcomes: (symbol?: string) =>
    api.post('/ai-analysis/evaluate-outcomes', symbol ? { symbol } : {}),
};

export const newsAPI = {
  getFeed: (params?: { limit?: number; category?: string; sentiment?: string }) =>
    api.get('/news/feed', { params }),
  getTrending: () => api.get('/news/trending'),
  getAlerts: () => api.get('/news/alerts'),
};

export const accountAPI = {
  getProfile: () => api.get('/account/profile'),
  getCapital: () => api.get('/account/capital'),
  getDailyCapitalHistory: (days = 30) => api.get('/account/daily-capital', { params: { days } }),
};

export const safetyAPI = {
  getStatus: (underlying?: string) =>
    api.get('/safety/status', underlying ? { params: { underlying } } : {}),
  getDrawdown: () => api.get('/safety/drawdown'),
  getCircuitBreaker: (underlying?: string) =>
    api.get('/safety/circuit-breaker', underlying ? { params: { underlying } } : {}),
  getExpiryWarnings: () => api.get('/safety/expiry-warnings'),
};

export const settingsAPI = {
  getZerodhaSettings: () => api.get('/settings/zerodha').then((res) => res.data),
  saveZerodhaCredentials: (credentials: { api_key: string; api_secret: string }) =>
    api.post('/settings/zerodha/credentials', credentials),
  saveZerodhaToken: (token: { access_token: string }) =>
    api.post('/settings/zerodha/token', token),
  generateZerodhaToken: (credentials: { api_key: string; api_secret: string }) =>
    api.post('/settings/zerodha/generate-token', credentials),
  setExecutionMode: (mode: string) =>
    api.post(`/settings/execution-mode?mode=${mode}`),
};

// ── Auth ─────────────────────────────────────────────────────────────
export const authAPI = {
  login: async (username: string, password: string) => {
    try {
      return await api.post('/auth/login', { username, password });
    } catch (error: any) {
      const currentBase = getApiBaseUrl();
      const fallbackBase = getDefaultApiBaseUrl();

      if (isConnectivityError(error) && fallbackBase !== currentBase) {
        try {
          const response = await axios.post(
            `${fallbackBase}/auth/login`,
            { username, password },
            {
              headers: { 'Content-Type': 'application/json' },
              timeout: 15000,
            }
          );
          await persistApiBaseUrl(fallbackBase);
          return response;
        } catch (retryError: any) {
          throw attachConnectionHelp(retryError, fallbackBase);
        }
      }

      throw attachConnectionHelp(error, currentBase);
    }
  },
  me: () => api.get('/auth/me'),
};

export const authTokenStore = {
  get: async () => {
    if (Platform.OS === 'web') {
      return AsyncStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
    }

    const secureToken = await SecureStore.getItemAsync(AUTH_TOKEN_STORAGE_KEY);
    if (secureToken) {
      return secureToken;
    }

    // Migration path from older AsyncStorage-backed auth token.
    const legacyToken = await AsyncStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
    if (legacyToken) {
      await SecureStore.setItemAsync(AUTH_TOKEN_STORAGE_KEY, legacyToken);
      await AsyncStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      return legacyToken;
    }
    return null;
  },
  set: async (token: string) => {
    if (Platform.OS === 'web') {
      await AsyncStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
      return;
    }
    await SecureStore.setItemAsync(AUTH_TOKEN_STORAGE_KEY, token);
    await AsyncStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  },
  clear: async () => {
    if (Platform.OS === 'web') {
      await AsyncStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      return;
    }
    await Promise.all([
      SecureStore.deleteItemAsync(AUTH_TOKEN_STORAGE_KEY),
      AsyncStorage.removeItem(AUTH_TOKEN_STORAGE_KEY),
    ]);
  },
};

export default api;
