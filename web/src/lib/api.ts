import axios from 'axios';

const API_BASE = 'http://localhost:8000';

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
    api.post(`/intent/create`, { 
      run_id: runId,
      ...(capital && { capital })
    }),
  
  executeIntent: (intentId: string, idempotencyKey: string) =>
    api.post(`/execute/paper/${intentId}`, {
      headers: { 'idempotency-key': idempotencyKey }
    }),
  
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
};

// System Control APIs
export const systemAPI = {
  enable: () => api.post('/system/enable', {}),
  disable: () => api.post('/system/disable', {}),
  status: () => api.get('/system/status'),
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
