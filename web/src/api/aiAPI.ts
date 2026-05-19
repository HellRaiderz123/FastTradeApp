import axios from 'axios';

const AI_API = axios.create({
  baseURL: (import.meta as any).env?.VITE_API_BASE ? `${(import.meta as any).env?.VITE_API_BASE}/ai-analysis` : '/api/ai-analysis',
  timeout: 120000, // Long timeout for LLM processing
});

// ── Types ────────────────────────────────────────────────────────────────────

export interface Decision {
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number;
  conviction: string;
  rationale: string;
  key_factors: string[];
  time_horizon: string;
  risk_level: string;
  suggested_stop_loss_pct: number | null;
  suggested_target_pct: number | null;
}

export interface AgentReport {
  summary?: string;
  bull_thesis?: string;
  bear_thesis?: string;
  key_points?: string[];
  score?: number;
  [key: string]: unknown;
}

export interface DebateRoundEntry {
  round: number;
  bull?: {
    thesis?: string;
    confidence?: number;
  };
  bear?: {
    thesis?: string;
    confidence?: number;
  };
}

export interface PipelineResult {
  job_id: string;
  symbol: string;
  exchange: string;
  status: 'COMPLETED' | 'FAILED';
  decision: Decision | null;
  reports: {
    technical_report?: AgentReport;
    news_report?: AgentReport;
    sentiment_report?: AgentReport;
    bull_report?: AgentReport;
    bear_report?: AgentReport;
    fundamentals_report?: AgentReport;
  };
  data_summary: {
    candles_used: number;
    candle_timeframe: string;
    news_items_used: number;
    vix?: number;
    history_decisions_used?: number;
    fundamentals_used?: string[];
    debate_rounds?: number;
  };
  debate_transcript?: DebateRoundEntry[];
  error?: string;
  analysed_at: string;
}

export interface JobStatus {
  job_id: string;
  symbol: string;
  status: 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  current_step: string | null;
  steps_done: string[];
  result: PipelineResult | null;
}

export interface HistoryEntry {
  id: number;
  job_id: string;
  symbol: string;
  exchange: string;
  action: string;
  confidence: number;
  conviction: string;
  rationale: string;
  price_at_decision: number | null;
  suggested_stop_loss_pct: number | null;
  suggested_target_pct: number | null;
  outcome_correct: number | null;
  actual_return_pct: number | null;
  reflection: string | null;
  analysed_at: string;
}

export interface HistoryResponse {
  symbol: string;
  decisions: HistoryEntry[];
  accuracy_pct: number;
  total_decisions: number;
}

export interface HealthResponse {
  ok: boolean;
  llm_available: boolean;
  llm_provider?: string;
  message?: string;
}

export interface AnalyzeOptions {
  debate_rounds?: number;
  clear_checkpoint?: boolean;
}

export interface ReconciliationDeskRow {
  job_id: string;
  symbol: string;
  exchange: string;
  action: 'BUY' | 'SELL' | 'HOLD';
  confidence: number | null;
  conviction?: string | null;
  time_horizon?: string | null;
  risk_level?: string | null;
  rationale?: string | null;
  execution_allowed?: boolean | null;
  manager_block_reason?: string | null;
  analysed_at?: string | null;
}

export interface ReconciliationDeskSnapshot {
  nifty100: {
    state: {
      status?: string;
      last_run_at?: string | null;
      queued?: number;
      running?: number;
      completed?: number;
      failed?: number;
      remaining?: number;
      processed?: number;
      last_error?: string | null;
      symbol_count?: number;
    };
    latest: ReconciliationDeskRow[];
    buy_recommendations: ReconciliationDeskRow[];
    sell_recommendations: ReconciliationDeskRow[];
    symbol_count: number;
  };
  holdings: {
    state: {
      status?: string;
      last_run_at?: string | null;
      queued?: number;
      running?: number;
      completed?: number;
      failed?: number;
      remaining?: number;
      processed?: number;
      last_error?: string | null;
      symbol_count?: number;
    };
    rows: Array<{
      symbol: string;
      quantity: number;
      average_price: number;
      last_price: number;
      pnl: number;
      decision: ReconciliationDeskRow | null;
    }>;
  };
}

// ── API Client ───────────────────────────────────────────────────────────────

export const aiAPI = {
  // Check service & LLM availability
  health: () =>
    AI_API.get<HealthResponse>('/health'),

  // Start new analysis
  analyze: (symbol: string, exchange: string = 'NSE', options?: AnalyzeOptions) =>
    AI_API.post<{ job_id: string; status: string }>('/analyze', {
      symbol,
      exchange,
      ...(options || {}),
    }),

  // Poll job status & result
  status: (jobId: string) =>
    AI_API.get<JobStatus>(`/status/${jobId}`),

  // Get decision history for a symbol
  history: (symbol: string, limit: number = 10) =>
    AI_API.get<HistoryResponse>('/history/' + symbol, { params: { limit } }),

  // Trigger outcome evaluation
  evaluateOutcomes: (evaluationDays: number = 3) =>
    AI_API.post('/evaluate-outcomes', { evaluation_days: evaluationDays }),

  // Cleanup expired jobs
  cleanupJobs: () =>
    AI_API.delete('/jobs/cleanup'),

  // Background reconciliation desk
  getReconciliationDesk: () =>
    AI_API.get<{ ok: boolean; desk: ReconciliationDeskSnapshot }>('/reconciliation/desk'),

  runNifty100Reconciliation: (debateRounds: number = 2) =>
    AI_API.post('/reconciliation/run-nifty100', {}, { params: { debate_rounds: debateRounds } }),

  runHoldingsReconciliation: (debateRounds: number = 2) =>
    AI_API.post('/reconciliation/run-holdings', {}, { params: { debate_rounds: debateRounds } }),
};
