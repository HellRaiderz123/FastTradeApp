import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Send,
  Loader2,
  CheckCircle2,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Newspaper,
  Zap,
  Target,
  ArrowUp,
  ArrowDown,
  ChevronDown,
  ChevronUp,
  Clock,
  Gauge,
} from 'lucide-react';
import { aiAPI, Decision, HistoryEntry, PipelineResult } from '../api/aiAPI';

// ─── Types ──────────────────────────────────────────────────────────────────

interface PipelineStep {
  key: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const PIPELINE_STEPS: PipelineStep[] = [
  { key: 'data_collection',  label: 'Collecting Data',        icon: () => <BarChart3 className="w-4 h-4" /> },
  { key: 'technical_analyst', label: 'Technical Analyst',      icon: () => <BarChart3 className="w-4 h-4" /> },
  { key: 'news_analyst',     label: 'News Analyst',            icon: () => <Newspaper className="w-4 h-4" /> },
  { key: 'sentiment_analyst', label: 'Sentiment Analyst',      icon: () => <Gauge className="w-4 h-4" /> },
  { key: 'bull_researcher',  label: 'Bull Researcher',         icon: () => <TrendingUp className="w-4 h-4" /> },
  { key: 'bear_researcher',  label: 'Bear Researcher',         icon: () => <TrendingDown className="w-4 h-4" /> },
  { key: 'fundamentals_analyst', label: 'Fundamentals Analyst', icon: () => <Target className="w-4 h-4" /> },
  { key: 'trader_decision',  label: 'Trader Decision',         icon: () => <Zap className="w-4 h-4" /> },
];

const POPULAR_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'SBIN', 'INFY', 'HDFC', 'ICICIBANK'];

const POLL_INTERVAL_MS = 3000;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function actionBgColor(action: string) {
  if (action === 'BUY')  return 'bg-green-500/10';
  if (action === 'SELL') return 'bg-red-500/10';
  return 'bg-amber-500/10';
}

function actionTextColor(action: string) {
  if (action === 'BUY')  return 'text-green-400';
  if (action === 'SELL') return 'text-red-400';
  return 'text-amber-400';
}

function actionBorderColor(action: string) {
  if (action === 'BUY')  return 'border-green-500/30';
  if (action === 'SELL') return 'border-red-500/30';
  return 'border-amber-500/30';
}

function confidenceLabel(c: number) {
  if (c >= 0.75) return 'HIGH';
  if (c >= 0.5)  return 'MEDIUM';
  return 'LOW';
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: '2-digit' });
  } catch { return iso; }
}

// ─── Main Component ─────────────────────────────────────────────────────────

const AIAnalysis: React.FC = () => {
  const [symbol, setSymbol] = useState('NIFTY');
  const [exchange] = useState('NSE');
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<'IDLE' | 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED'>('IDLE');
  const [stepsDone, setStepsDone] = useState<string[]>([]);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [dataSummary, setDataSummary] = useState<any>(null);
  const [reports, setReports] = useState<any>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [serviceReady, setServiceReady] = useState<boolean | null>(null);
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Check service health on mount ──────────────────────────────────
  useEffect(() => {
    aiAPI.health()
      .then((r) => setServiceReady(r.data?.ok === true))
      .catch(() => setServiceReady(false));
  }, []);

  // ── Load history when symbol changes ───────────────────────────────
  const loadHistory = useCallback(async (sym: string) => {
    setHistoryLoading(true);
    try {
      const r = await aiAPI.history(sym, 10);
      setHistory(r.data?.decisions ?? []);
    } catch {
      setHistory([]);
    }
    setHistoryLoading(false);
  }, []);

  useEffect(() => {
    if (symbol.length >= 2) loadHistory(symbol);
  }, [symbol, loadHistory]);

  // ── Stop polling ───────────────────────────────────────────────────
  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  // ── Poll status ────────────────────────────────────────────────────
  const pollStatus = useCallback(async (id: string) => {
    try {
      const r = await aiAPI.status(id);
      const job = r.data;
      setStepsDone(job.steps_done ?? []);
      setCurrentStep(job.current_step ?? null);
      setStatus(job.status as any);

      if (job.status === 'COMPLETED') {
        stopPolling();
        setDecision(job.result?.decision ?? null);
        setDataSummary(job.result?.data_summary ?? null);
        setReports(job.result?.reports ?? null);
        loadHistory(symbol);
        setAnalyzing(false);
      } else if (job.status === 'FAILED') {
        stopPolling();
        setAnalyzing(false);
      }
    } catch (err) {
      // network glitch — keep polling
    }
  }, [symbol, stopPolling, loadHistory]);

  useEffect(() => {
    if (jobId && (status === 'QUEUED' || status === 'RUNNING')) {
      pollRef.current = setInterval(() => pollStatus(jobId), POLL_INTERVAL_MS);
      return stopPolling;
    }
  }, [jobId, status, pollStatus, stopPolling]);

  // ── Start analysis ─────────────────────────────────────────────────
  const handleAnalyze = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) { alert('Enter a symbol (e.g. RELIANCE)'); return; }

    stopPolling();
    setJobId(null);
    setStatus('QUEUED');
    setStepsDone([]);
    setCurrentStep(null);
    setDecision(null);
    setDataSummary(null);
    setReports(null);
    setAnalyzing(true);

    try {
      const r = await aiAPI.analyze(sym, exchange);
      const id = r.data?.job_id;
      if (!id) throw new Error('No job_id');
      setJobId(id);
      setStatus('RUNNING');
    } catch (err: any) {
      setStatus('FAILED');
      setAnalyzing(false);
      alert(`Error: ${err?.response?.data?.detail ?? err?.message}`);
    }
  };

  const isRunning = status === 'QUEUED' || status === 'RUNNING';
  const conf = decision ? Math.round((decision.confidence || 0) * 100) : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Zap className="w-8 h-8 text-blue-400" />
            AI Agents
          </h1>
          <p className="text-slate-400 mt-1">Multi-agent market analysis pipeline</p>
        </div>
      </div>

      {/* Service warning */}
      {serviceReady === false && (
        <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg">
          <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-semibold text-amber-400">LLM Service Not Configured</p>
            <p className="text-sm text-amber-300/80 mt-1">
              Set LLM_API_KEY in backend .env to enable AI analysis (Groq, OpenAI, or NVIDIA)
            </p>
          </div>
        </div>
      )}

      {/* Symbol input card */}
      <div className="p-6 bg-slate-800 border border-slate-700 rounded-xl">
        <label className="block text-sm font-semibold text-slate-300 mb-3">NSE / BSE Symbol</label>
        <div className="flex gap-3 mb-4">
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            placeholder="e.g. RELIANCE"
            disabled={isRunning}
            className="flex-1 px-4 py-3 bg-slate-900 border border-slate-600 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
          <button
            onClick={handleAnalyze}
            disabled={isRunning || !serviceReady}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg flex items-center gap-2 transition-colors"
          >
            {analyzing ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                Analyse
              </>
            )}
          </button>
        </div>

        {/* Quick-pick chips */}
        <div className="flex flex-wrap gap-2">
          {POPULAR_SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              disabled={isRunning}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                symbol === s
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-700 text-slate-300 hover:bg-slate-600 disabled:opacity-50'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline progress */}
      {status !== 'IDLE' && (
        <div className="p-6 bg-slate-800 border border-slate-700 rounded-xl">
          <h3 className="font-semibold text-white mb-4">Agent Pipeline</h3>
          <div className="space-y-2">
            {PIPELINE_STEPS.map((step, idx) => {
              const isDone = stepsDone.includes(step.key);
              const isCurrent = currentStep === step.key;
              return (
                <div key={step.key} className="flex items-center gap-3 p-2">
                  <div className="w-6 h-6 flex items-center justify-center">
                    {isDone ? (
                      <CheckCircle2 className="w-5 h-5 text-green-400" />
                    ) : isCurrent ? (
                      <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />
                    ) : (
                      <div className="w-2 h-2 rounded-full bg-slate-600" />
                    )}
                  </div>
                  <span className={`text-sm ${isCurrent ? 'font-semibold text-white' : isDone ? 'text-slate-400' : 'text-slate-500'}`}>
                    {step.label}
                  </span>
                </div>
              );
            })}
          </div>
          {status === 'FAILED' && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-300 text-sm">
              Pipeline failed. Check LLM configuration.
            </div>
          )}
        </div>
      )}

      {/* Decision result */}
      {decision && (
        <div className={`p-6 border rounded-xl ${actionBgColor(decision.action)} ${actionBorderColor(decision.action)}`}>
          {/* Action badge */}
          <div className="flex items-center justify-between mb-4">
            <div className={`inline-block px-6 py-2 text-2xl font-bold rounded-lg ${actionTextColor(decision.action)} ${actionBgColor(decision.action)} border ${actionBorderColor(decision.action)}`}>
              {decision.action}
            </div>
          </div>

          {/* Confidence */}
          <div className="mb-4">
            <div className="flex justify-between items-center mb-2">
              <span className="text-slate-300 text-sm font-medium">Confidence</span>
              <span className={`text-lg font-bold ${actionTextColor(decision.action)}`}>{conf}%</span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden">
              <div
                className={`h-full rounded-full ${decision.action === 'BUY' ? 'bg-green-500' : decision.action === 'SELL' ? 'bg-red-500' : 'bg-amber-500'}`}
                style={{ width: `${conf}%` }}
              />
            </div>
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-2 mb-4">
            {decision.conviction && (
              <span className="px-3 py-1 text-xs font-medium bg-slate-700 text-slate-300 rounded-full">
                {decision.conviction}
              </span>
            )}
            {decision.time_horizon && (
              <span className="px-3 py-1 text-xs font-medium bg-slate-700 text-slate-300 rounded-full">
                {decision.time_horizon}
              </span>
            )}
            {decision.risk_level && (
              <span className="px-3 py-1 text-xs font-medium bg-slate-700 text-slate-300 rounded-full">
                Risk: {decision.risk_level}
              </span>
            )}
          </div>

          {/* Levels */}
          {(decision.suggested_stop_loss_pct != null || decision.suggested_target_pct != null) && (
            <div className="grid grid-cols-2 gap-3 mb-4">
              {decision.suggested_stop_loss_pct != null && (
                <div className="p-3 bg-slate-700/50 rounded-lg">
                  <p className="text-xs text-slate-400">Stop Loss</p>
                  <p className="text-lg font-bold text-red-400">-{decision.suggested_stop_loss_pct}%</p>
                </div>
              )}
              {decision.suggested_target_pct != null && (
                <div className="p-3 bg-slate-700/50 rounded-lg">
                  <p className="text-xs text-slate-400">Target</p>
                  <p className="text-lg font-bold text-green-400">+{decision.suggested_target_pct}%</p>
                </div>
              )}
            </div>
          )}

          {/* Rationale */}
          <p className="text-slate-300 text-sm mb-3">{decision.rationale}</p>

          {/* Key factors */}
          {decision.key_factors?.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Key Factors</p>
              <ul className="space-y-1">
                {decision.key_factors.map((f, i) => (
                  <li key={i} className="text-sm text-slate-400">
                    • {f}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Data summary */}
          {dataSummary && (
            <p className="text-xs text-slate-500 border-t border-slate-700/50 pt-3 mt-3">
              {dataSummary.candles_used} candles ({dataSummary.candle_timeframe}) · {dataSummary.news_items_used} news ·{' '}
              {dataSummary.vix?.toFixed(1) ?? '–'} VIX · {dataSummary.history_decisions_used ?? 0} past decisions used
            </p>
          )}

          <p className="text-xs text-slate-600 italic mt-3">
            ⚠️ Research simulation only. Not financial advice.
          </p>
        </div>
      )}

      {/* Agent reports */}
      {reports && (
        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          {Object.entries(reports).map(([key, report]: [string, any]) => {
            const isExpanded = expandedReport === key;
            const reportLabel = key
              .replace(/_report$/, '')
              .replace(/_/g, ' ')
              .split(' ')
              .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
              .join(' ');

            return (
              <div key={key} className="border-b border-slate-700 last:border-b-0">
                <button
                  onClick={() => setExpandedReport(isExpanded ? null : key)}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-slate-700/50 transition-colors text-left"
                >
                  <span className="font-semibold text-slate-200">{reportLabel}</span>
                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </button>
                {isExpanded && (
                  <div className="px-6 pb-4 pt-0 text-slate-300 text-sm space-y-2 border-t border-slate-700">
                    {report?.summary && <p>{report.summary}</p>}
                    {report?.bull_thesis && <p>{report.bull_thesis}</p>}
                    {report?.bear_thesis && <p>{report.bear_thesis}</p>}
                    {report?.key_points && (
                      <ul className="list-disc list-inside space-y-1">
                        {report.key_points.map((p: string, i: number) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* History */}
      {(history.length > 0 || historyLoading) && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Decision History — {symbol}</h3>
            {historyLoading && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
          </div>

          {history.length === 0 ? (
            <p className="text-slate-400 text-center py-6">No past decisions for {symbol}</p>
          ) : (
            <div className="space-y-2">
              {history.map((entry) => {
                const outcomeColor =
                  entry.outcome_correct === 1
                    ? 'text-green-400'
                    : entry.outcome_correct === 0
                      ? 'text-red-400'
                      : 'text-slate-400';

                return (
                  <div
                    key={entry.id}
                    className={`p-4 bg-slate-800 border border-slate-700 rounded-lg ${actionBgColor(entry.action)}`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <span className={`px-3 py-1 text-xs font-bold rounded ${actionTextColor(entry.action)} ${actionBgColor(entry.action)} border ${actionBorderColor(entry.action)}`}>
                          {entry.action}
                        </span>
                        <span className="text-sm text-slate-400">{formatDate(entry.analysed_at)}</span>
                        {entry.outcome_correct != null && (
                          <span className={`text-xs font-semibold ${outcomeColor}`}>
                            {entry.outcome_correct === 1 ? '✓ Correct' : '✗ Wrong'}
                            {entry.actual_return_pct != null && ` (${entry.actual_return_pct > 0 ? '+' : ''}${entry.actual_return_pct.toFixed(1)}%)`}
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-slate-300 mb-2">{entry.rationale}</p>
                    {entry.reflection && (
                      <p className="text-xs text-slate-400 italic">💡 {entry.reflection}</p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default AIAnalysis;
