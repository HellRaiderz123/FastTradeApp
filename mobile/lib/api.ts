import axios from 'axios';

const API_BASE = 'http://192.168.31.244:8000'; // Android emulator localhost
// For iOS: use 'http://localhost:8000'
// For physical device: use your actual IP

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Strategy APIs
export const strategyAPI = {
  runStrategy: (payload: any) =>
    api.post('/strategy/option-spread/15m/run', payload),
};

// Execution APIs
export const executionAPI = {
  createIntent: (runId: number) =>
    api.post(`/intent/create`, { run_id: runId }),
  
  executeIntent: (intentId: string, idempotencyKey: string) =>
    api.post(`/execute/paper/${intentId}`, {}, {
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

// System Control APIs
export const systemAPI = {
  enable: () => api.post('/system/enable', {}),
  disable: () => api.post('/system/disable', {}),
  status: () => api.get('/system/status'),
};

export default api;
