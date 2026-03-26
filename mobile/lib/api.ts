import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Change this to your machine's IP when running on physical device
// For simulator: http://localhost:8000
// For physical device: http://YOUR_LOCAL_IP:8000
export const API_BASE = 'http://172.20.10.8:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15000,
});

// Auth interceptor
api.interceptors.request.use(async (config) => {
  const token = await AsyncStorage.getItem('fasttrade_auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

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
  scanStrategy: (id: number) => api.post(`/condition-scanner/scan/${id}`),
  getHistory: (params?: any) => api.get('/condition-scanner/history', { params }),
  executeSignal: (body: any) => api.post('/condition-scanner/execute-signal', body),
};

// ── Auto Trader ──────────────────────────────────────────────────────
export const autoTraderAPI = {
  getStatus: () => api.get('/auto-trader/status'),
  getConfig: () => api.get('/auto-trader/config'),
  start: () => api.post('/auto-trader/start'),
  stop: () => api.post('/auto-trader/stop'),
  pause: () => api.post('/auto-trader/pause'),
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

// ── AI Chat ──────────────────────────────────────────────────────────
export const aiAPI = {
  query: (message: string, history: any[] = []) =>
    api.post('/ai-chat/query', { message, history }),
};

// ── Finance ──────────────────────────────────────────────────────────
export const financeAPI = {
  getTransactions: () => api.get('/finance/transactions'),
  getBudgets: () => api.get('/finance/budgets'),
  getBudgetStatus: (category: string) =>
    api.get(`/finance/budgets/status/${category}`),
  getSavingsGoals: () => api.get('/finance/goals'),
  getBillReminders: () => api.get('/finance/bills'),
  getTrends: (months = 6, topN = 5) =>
    api.get(`/finance/trends?months=${months}&top_n=${topN}`),
};

// ── Analytics ────────────────────────────────────────────────────────
export const analyticsAPI = {
  getStrategyPnL: (params?: any) =>
    api.get('/analytics/strategy-pnl', { params }),
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
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password }),
  me: () => api.get('/auth/me'),
};

export default api;
