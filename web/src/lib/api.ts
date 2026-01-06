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

// Strategy APIs
export const strategyAPI = {
  runStrategy: (payload: any) =>
    api.post('/strategy/option-spread/15m/run', payload),
};

// Execution APIs
export const executionAPI = {
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

export default api;
