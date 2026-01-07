import axios from 'axios';

// Default to Vite dev proxy (/api). Override via VITE_API_BASE if needed.
const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
};

// Market Data APIs
export const marketAPI = {
  getCandles: (symbol: string, limit = 50) =>
    api.get(`/candles/15m/${symbol}?limit=${limit}`),
  
  // Get live LTP (Last Traded Price) for spot price
  getLTP: (symbol: string = 'NIFTY') =>
    api.get(`/market/ltp/${symbol}`),
  
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

// System Control APIs
export const systemAPI = {
  enable: () => api.post('/system/enable', {}),
  disable: () => api.post('/system/disable', {}),
  status: () => api.get('/system/status'),
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
};

// Suggestions APIs (AlgoRoom-like)
export const suggestionsAPI = {
  get: (payload: any) => api.post('/suggestions', payload),
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
  
  setExecutionMode: (mode: string) =>
    api.post(`/settings/execution-mode`, {}, { params: { mode } }),
};

export default api;
