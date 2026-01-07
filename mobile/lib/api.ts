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
  createIntent: (runId: number, riskMode: string) =>
    api.post(`/intent/create?run_id=${runId}&risk_mode=${riskMode}`, {}),
  
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

// Settings APIs
export const settingsAPI = {
  getZerodhaSettings: () =>
    api.get('/settings/zerodha'),
  
  saveZerodhaCredentials: (credentials: { api_key: string; api_secret: string }) =>
    api.post('/settings/zerodha/credentials', credentials),
  
  saveZerodhaToken: (token: { access_token: string }) =>
    api.post('/settings/zerodha/token', token),
  
  generateZerodhaToken: (credentials: { api_key: string; api_secret: string }) =>
    api.post('/settings/zerodha/generate-token', credentials),
  
  setExecutionMode: (mode: string) =>
    api.post(`/settings/execution-mode?mode=${mode}`),
};

export default api;
