import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  MessageSquare,
  Brain,
  Sparkles,
  Bot,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Target,
  TrendingUp,
  TrendingDown,
  Minus,
  Radar,
} from 'lucide-react';
import { aiAPI, DebateRoundEntry, PipelineResult, type ReconciliationDeskSnapshot } from '../api/aiAPI';
import { journalAPI, mlAPI, watchlistAPI } from '../lib/api';

type Action = 'BUY' | 'SELL' | 'HOLD';

type SourceVote = {
  source: string;
  action: Action;
  confidence: number;
  detail: string;
  meta?: string;
  signalLabel?: string;
};

type MLSnapshot = {
  signal?: string;
  confidence?: number;
  reason?: string;
  bias?: string;
};

type WatchlistSuggestion = {
  symbol: string;
  score: number;
  recent_signal_count: number;
  bullish_count: number;
  bearish_count: number;
  latest_signal_at: string | null;
  latest_direction: string | null;
  latest_strategy: string | null;
  avg_change_pct: number | null;
};

type AIOutcome = {
  action: Action;
  confidence: number;
  rationale: string;
  analysed_at?: string;
};

type ReconciliationSnapshot = {
  savedAt: number;
  aiOutcome: AIOutcome | null;
  mlSingle: MLSnapshot | null;
  mlEnsemble: MLSnapshot | null;
  strategySuggestion: WatchlistSuggestion | null;
  diagnosticsSummary: any;
  diagnosticsScope: string;
  debateTranscript: DebateRoundEntry[];
  debateRoundsUsed: number | null;
};

const POPULAR_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'SBIN', 'INFY', 'HDFCBANK'];
const CACHE_TTL_MS = 5 * 60 * 1000;

function normalizeMlToAction(signal?: string): Action {
  const s = String(signal || '').toUpperCase();
  if (s.includes('BULL')) return 'BUY';
  if (s.includes('BEAR')) return 'SELL';
  return 'HOLD';
}

function normalizeConfidence01(value: unknown): number {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n) || n <= 0) return 0;
  // ML endpoints return confidence in 0-100, AI returns 0-1.
  return n > 1 ? Math.max(0, Math.min(1, n / 100)) : Math.max(0, Math.min(1, n));
}

function actionScore(action: Action): number {
  if (action === 'BUY') return 1;
  if (action === 'SELL') return -1;
  return 0;
}

function scoreToAction(v: number): Action {
  if (v > 0.2) return 'BUY';
  if (v < -0.2) return 'SELL';
  return 'HOLD';
}

function actionPill(action: Action): string {
  if (action === 'BUY') return 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
  if (action === 'SELL') return 'bg-rose-500/15 text-rose-300 border-rose-500/40';
  return 'bg-amber-500/15 text-amber-300 border-amber-500/40';
}

function actionIcon(action: Action) {
  if (action === 'BUY') return <TrendingUp className="w-4 h-4" />;
  if (action === 'SELL') return <TrendingDown className="w-4 h-4" />;
  return <Minus className="w-4 h-4" />;
}

const SignalReconciliation: React.FC = () => {
  const [symbol, setSymbol] = useState('RELIANCE');
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [aiOutcome, setAiOutcome] = useState<AIOutcome | null>(null);
  const [mlSingle, setMlSingle] = useState<MLSnapshot | null>(null);
  const [mlEnsemble, setMlEnsemble] = useState<MLSnapshot | null>(null);
  const [strategySuggestion, setStrategySuggestion] = useState<WatchlistSuggestion | null>(null);
  const [diagnosticsSummary, setDiagnosticsSummary] = useState<any>(null);
  const [diagnosticsScope, setDiagnosticsScope] = useState<string>('Symbol');

  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const [debateRounds, setDebateRounds] = useState(2);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [debateTranscript, setDebateTranscript] = useState<DebateRoundEntry[]>([]);
  const [debateRoundsUsed, setDebateRoundsUsed] = useState<number | null>(null);
  const cacheRef = useRef<Record<string, ReconciliationSnapshot>>({});
  const [deskSnapshot, setDeskSnapshot] = useState<ReconciliationDeskSnapshot | null>(null);
  const [deskLoading, setDeskLoading] = useState(false);
  const [deskError, setDeskError] = useState<string | null>(null);

  const cacheKey = (sym: string, rounds: number) => `${sym}:${rounds}`;

  const resetCurrentResults = () => {
    setError(null);
    setAiOutcome(null);
    setMlSingle(null);
    setMlEnsemble(null);
    setStrategySuggestion(null);
    setDiagnosticsSummary(null);
    setDiagnosticsScope('Symbol');
    setDebateTranscript([]);
    setDebateRoundsUsed(null);
    setLastRefreshedAt(null);
    setRunStatus(null);
  };

  const applySnapshot = (snapshot: ReconciliationSnapshot) => {
    setAiOutcome(snapshot.aiOutcome);
    setMlSingle(snapshot.mlSingle);
    setMlEnsemble(snapshot.mlEnsemble);
    setStrategySuggestion(snapshot.strategySuggestion);
    setDiagnosticsSummary(snapshot.diagnosticsSummary);
    setDiagnosticsScope(snapshot.diagnosticsScope || 'Symbol');
    setDebateTranscript(snapshot.debateTranscript || []);
    setDebateRoundsUsed(snapshot.debateRoundsUsed);
    setLastRefreshedAt(new Date(snapshot.savedAt).toLocaleTimeString('en-IN'));
  };

  const loadDeskSnapshot = async () => {
    setDeskLoading(true);
    setDeskError(null);
    try {
      const res = await aiAPI.getReconciliationDesk();
      setDeskSnapshot(res.data?.desk || null);
    } catch (e: any) {
      setDeskError(e?.response?.data?.detail || e?.message || 'Failed to load background desk');
    } finally {
      setDeskLoading(false);
    }
  };

  useEffect(() => {
    loadDeskSnapshot();
    const timer = setInterval(loadDeskSnapshot, 15000);
    return () => clearInterval(timer);
  }, []);

  const handleSymbolChange = (next: string) => {
    setSymbol(next.toUpperCase());
    resetCurrentResults();
  };

  const fetchStrategySuggestion = async (targetSymbol: string): Promise<WatchlistSuggestion | null> => {
    const wlRes = await watchlistAPI.getAll();
    const watchlists: Array<{ id: number }> = wlRes.data?.watchlists || [];
    if (!watchlists.length) return null;

    const calls = watchlists.slice(0, 8).map((wl) => watchlistAPI.getSuggestions(wl.id, 20, 14));
    const settled = await Promise.allSettled(calls);

    let best: WatchlistSuggestion | null = null;
    for (const row of settled) {
      if (row.status !== 'fulfilled') continue;
      const suggestions: WatchlistSuggestion[] = row.value.data?.suggestions || [];
      const match = suggestions.find((s) => s.symbol?.toUpperCase() === targetSymbol);
      if (!match) continue;
      if (!best || (match.score || 0) > (best.score || 0)) {
        best = match;
      }
    }

    return best;
  };

  const runAllSignals = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) return;

    const key = cacheKey(sym, debateRounds);
    const cached = cacheRef.current[key];
    if (cached && Date.now() - cached.savedAt < CACHE_TTL_MS) {
      applySnapshot(cached);
      const ageSec = Math.max(1, Math.round((Date.now() - cached.savedAt) / 1000));
      setRunStatus(`Loaded from cache (${ageSec}s old)`);
      return;
    }

    setRunning(true);
    setError(null);
    setRunStatus('Running full reconciliation...');
    resetCurrentResults();

    try {
      const [singleRes, ensembleRes, diagRes, suggestionRes] = await Promise.allSettled([
        mlAPI.predict(sym),
        mlAPI.ensemblePredict(sym),
        journalAPI.getSignalDiagnostics({ limit: 200, lookback_days: 45, underlying: sym }),
        fetchStrategySuggestion(sym),
      ]);

      const startRes = await aiAPI.analyze(sym, 'NSE', {
        debate_rounds: debateRounds,
      });
      const jobId = startRes.data?.job_id;
      if (!jobId) throw new Error('AI analysis did not return a job id');

      let completed = false;
      let finalResult: PipelineResult | null = null;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2500));
        const statusRes = await aiAPI.status(jobId);
        const status = statusRes.data?.status;
        const currentStep = statusRes.data?.current_step;
        finalResult = statusRes.data?.result || null;
        setRunStatus(status === 'RUNNING' && currentStep ? `Running: ${currentStep}` : `Status: ${status || 'UNKNOWN'}`);

        if (status === 'COMPLETED') {
          completed = true;
          break;
        }
        if (status === 'FAILED') {
          throw new Error('AI debate run failed');
        }
      }

      if (!completed) {
        throw new Error('Timed out waiting for AI debate run to complete');
      }

      const nextAiOutcome: AIOutcome | null = finalResult?.decision
        ? {
            action: finalResult.decision.action,
            confidence: normalizeConfidence01(finalResult.decision.confidence || 0),
            rationale: finalResult.decision.rationale || 'No AI rationale available.',
            analysed_at: finalResult.analysed_at,
          }
        : null;

      if (singleRes.status === 'fulfilled') {
        setMlSingle(singleRes.value.data || null);
      } else {
        setMlSingle(null);
      }

      if (ensembleRes.status === 'fulfilled') {
        setMlEnsemble(ensembleRes.value.data || null);
      } else {
        setMlEnsemble(null);
      }

      let nextDiagnosticsSummary: any = null;
      let nextDiagnosticsScope = `Symbol (${sym})`;

      if (diagRes.status === 'fulfilled') {
        const symbolSummary = diagRes.value.data?.summary || null;
        const symbolTrades = Number(symbolSummary?.total_trades || 0);
        if (symbolSummary && symbolTrades > 0) {
          nextDiagnosticsSummary = symbolSummary;
          nextDiagnosticsScope = `Symbol (${sym})`;
        } else {
          try {
            const portfolioDiag = await journalAPI.getSignalDiagnostics({ limit: 200, lookback_days: 45 });
            const portfolioSummary = portfolioDiag.data?.summary || null;
            nextDiagnosticsSummary = portfolioSummary;
            nextDiagnosticsScope = 'Portfolio (fallback)';
          } catch {
            nextDiagnosticsSummary = symbolSummary;
            nextDiagnosticsScope = `Symbol (${sym})`;
          }
        }
      } else {
        nextDiagnosticsSummary = null;
        nextDiagnosticsScope = `Symbol (${sym})`;
      }
      setDiagnosticsSummary(nextDiagnosticsSummary);
      setDiagnosticsScope(nextDiagnosticsScope);

      if (suggestionRes.status === 'fulfilled') {
        setStrategySuggestion(suggestionRes.value || null);
      } else {
        setStrategySuggestion(null);
      }

      setAiOutcome(nextAiOutcome);
      const transcript = finalResult?.debate_transcript || [];
      setDebateTranscript(Array.isArray(transcript) ? transcript : []);
      const rounds = Number(finalResult?.data_summary?.debate_rounds || 0);
      const nextRoundsUsed = Number.isFinite(rounds) && rounds > 0 ? rounds : null;
      setDebateRoundsUsed(nextRoundsUsed);

      const snapshot: ReconciliationSnapshot = {
        savedAt: Date.now(),
        aiOutcome: nextAiOutcome,
        mlSingle: singleRes.status === 'fulfilled' ? (singleRes.value.data || null) : null,
        mlEnsemble: ensembleRes.status === 'fulfilled' ? (ensembleRes.value.data || null) : null,
        strategySuggestion: suggestionRes.status === 'fulfilled' ? (suggestionRes.value || null) : null,
        diagnosticsSummary: nextDiagnosticsSummary,
        diagnosticsScope: nextDiagnosticsScope,
        debateTranscript: Array.isArray(transcript) ? transcript : [],
        debateRoundsUsed: nextRoundsUsed,
      };
      cacheRef.current[key] = snapshot;
      setRunStatus(`Completed with ${debateRounds} debate rounds`);

      setLastRefreshedAt(new Date().toLocaleTimeString('en-IN'));
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load reconciliation snapshot');
      setRunStatus('Run failed');
    } finally {
      setRunning(false);
    }
  };

  const runBackgroundDesk = async () => {
    setRunStatus('Queueing background Nifty100 and holdings review...');
    try {
      await Promise.allSettled([
        aiAPI.runNifty100Reconciliation(debateRounds),
        aiAPI.runHoldingsReconciliation(debateRounds),
      ]);
      await loadDeskSnapshot();
      setRunStatus('Background reconciliation queued');
    } catch (e: any) {
      setRunStatus(e?.message || 'Background reconciliation failed');
    }
  };

  const sourceVotes = useMemo<SourceVote[]>(() => {
    const votes: SourceVote[] = [];

    if (aiOutcome) {
      votes.push({
        source: 'AI Recommendation',
        action: aiOutcome.action || 'HOLD',
        confidence: Number(aiOutcome.confidence || 0),
        detail: aiOutcome.rationale || 'No AI rationale available.',
        meta: aiOutcome.analysed_at ? `Updated ${new Date(aiOutcome.analysed_at).toLocaleString('en-IN')}` : undefined,
      });
    }

    if (mlSingle) {
      const rawSignal = String(mlSingle.signal || 'NO_TRADE').toUpperCase();
      votes.push({
        source: 'ML Recommendation',
        action: normalizeMlToAction(rawSignal),
        confidence: normalizeConfidence01(mlSingle.confidence || 0),
        detail: mlSingle.reason || 'No ML explanation available.',
        meta: `Signal: ${rawSignal} | Bias: ${mlSingle.bias || 'NEUTRAL'}`,
        signalLabel: rawSignal,
      });
    }

    if (mlEnsemble) {
      const rawSignal = String(mlEnsemble.signal || 'NO_TRADE').toUpperCase();
      votes.push({
        source: 'ML Ensemble',
        action: normalizeMlToAction(rawSignal),
        confidence: normalizeConfidence01(mlEnsemble.confidence || 0),
        detail: mlEnsemble.reason || 'No ensemble explanation available.',
        meta: `Signal: ${rawSignal} | Bias: ${mlEnsemble.bias || 'NEUTRAL'}`,
        signalLabel: rawSignal,
      });
    }

    if (strategySuggestion) {
      const direction = String(strategySuggestion.latest_direction || '').toUpperCase();
      const action: Action = direction.includes('BULL') || direction.includes('BUY')
        ? 'BUY'
        : direction.includes('BEAR') || direction.includes('SELL')
          ? 'SELL'
          : 'HOLD';

      votes.push({
        source: 'Strategy Engine',
        action,
        confidence: Math.max(0, Math.min(1, Number(strategySuggestion.score || 0) / 100)),
        detail: strategySuggestion.latest_strategy || 'No recent strategy signal text available.',
        meta: `${strategySuggestion.recent_signal_count || 0} recent signals`,
      });
    }

    return votes;
  }, [aiOutcome, mlSingle, mlEnsemble, strategySuggestion]);

  const consensus = useMemo(() => {
    if (!sourceVotes.length) {
      return {
        action: 'HOLD' as Action,
        confidence: 0,
        conflict: 0,
      };
    }

    const weighted = sourceVotes.reduce((acc, row) => {
      const w = Math.max(0.15, Math.min(1, row.confidence || 0));
      return acc + actionScore(row.action) * w;
    }, 0);

    const denom = sourceVotes.reduce((acc, row) => acc + Math.max(0.15, Math.min(1, row.confidence || 0)), 0);
    const normalized = denom > 0 ? weighted / denom : 0;
    const action = scoreToAction(normalized);

    const first = sourceVotes[0]?.action;
    const disagreements = sourceVotes.filter((v) => v.action !== first).length;
    const conflict = sourceVotes.length > 1 ? disagreements / (sourceVotes.length - 1) : 0;

    return {
      action,
      confidence: Math.abs(normalized),
      conflict,
    };
  }, [sourceVotes]);

  const agreementText = consensus.conflict <= 0.2
    ? 'High agreement'
    : consensus.conflict <= 0.55
      ? 'Mixed signals'
      : 'Strong disagreement';

  const hasDiagnosticsTrades = Number(diagnosticsSummary?.total_trades || 0) > 0;

  return (
    <div className="space-y-6">
      <div className="rounded-2xl border border-slate-700 bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.12),transparent_45%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.12),transparent_40%),#0f172a] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <Radar className="w-8 h-8 text-cyan-300" />
              Signal Reconciliation
            </h1>
            <p className="mt-2 text-slate-300 max-w-3xl">
              One decision desk per stock across AI analysis, AI recommendation, ML recommendation, and strategy engine output.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              value={symbol}
              onChange={(e) => handleSymbolChange(e.target.value)}
              placeholder="RELIANCE"
              className="w-full sm:w-52 rounded-xl border border-slate-600 bg-slate-900/80 px-4 py-2.5 text-white placeholder-slate-500 focus:border-cyan-400 focus:outline-none"
            />
            <select
              value={debateRounds}
              onChange={(e) => setDebateRounds(Number(e.target.value))}
              className="w-full sm:w-36 rounded-xl border border-slate-600 bg-slate-900/80 px-3 py-2.5 text-white focus:border-cyan-400 focus:outline-none"
            >
              <option value={1}>Debate x1</option>
              <option value={2}>Debate x2</option>
              <option value={3}>Debate x3</option>
            </select>
            <button
              onClick={runAllSignals}
              disabled={running}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-500 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
            >
              {running ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Run Reconciliation
            </button>
            <button
              onClick={runBackgroundDesk}
              disabled={running || deskLoading}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-400/40 bg-emerald-500/10 px-4 py-2.5 font-semibold text-emerald-200 transition hover:bg-emerald-500/20 disabled:opacity-60"
            >
              <Radar className="w-4 h-4" />
              Queue Background Desk
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {POPULAR_SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => handleSymbolChange(s)}
              className={`rounded-lg border px-3 py-1.5 text-sm transition ${
                symbol === s
                  ? 'border-cyan-400 bg-cyan-500/20 text-cyan-200'
                  : 'border-slate-600 bg-slate-800/60 text-slate-300 hover:border-slate-500'
              }`}
            >
              {s}
            </button>
          ))}
        </div>

        {lastRefreshedAt && (
          <p className="mt-3 text-xs text-slate-400">Last refresh: {lastRefreshedAt}</p>
        )}
        {runStatus && (
          <p className="mt-1 text-xs text-violet-200">{runStatus}</p>
        )}
        {(deskLoading || deskError || deskSnapshot) && (
          <div className="mt-4 rounded-xl border border-slate-700 bg-slate-950/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-white font-semibold text-lg flex items-center gap-2">
                  <Bot className="w-5 h-5 text-emerald-300" />
                  Background Decision Desk
                </h2>
                <p className="text-xs text-slate-400">Nifty100 queue plus Zerodha holdings review, refreshed in the background.</p>
              </div>
              <button
                onClick={loadDeskSnapshot}
                className="rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-200 hover:border-cyan-400"
              >
                Refresh Desk
              </button>
            </div>
            {deskError && <p className="mt-2 text-xs text-rose-300">{deskError}</p>}
            {!deskError && deskLoading && <p className="mt-2 text-xs text-slate-400">Loading background desk...</p>}

            {deskSnapshot && (
              <div className="mt-4 grid grid-cols-1 xl:grid-cols-2 gap-4">
                <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Nifty100 Desk</p>
                      <h3 className="text-white font-semibold">Daily Buy Queue</h3>
                    </div>
                    <span className="text-xs text-slate-400">{deskSnapshot.nifty100.symbol_count} symbols</span>
                  </div>
                  <div className="mt-3 text-xs text-slate-400 flex flex-wrap gap-2">
                    <span className="rounded-full border border-slate-700 px-2 py-1">State: {deskSnapshot.nifty100.state.status || 'idle'}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Queued: {deskSnapshot.nifty100.state.queued || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Running: {deskSnapshot.nifty100.state.running || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Completed: {deskSnapshot.nifty100.state.completed || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Failed: {deskSnapshot.nifty100.state.failed || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Remaining: {deskSnapshot.nifty100.state.remaining || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Last run: {deskSnapshot.nifty100.state.last_run_at || '—'}</span>
                  </div>
                  <div className="mt-4 space-y-2 max-h-72 overflow-y-auto pr-1">
                    {(deskSnapshot.nifty100.buy_recommendations || []).slice(0, 8).map((row) => (
                      <div key={`${row.symbol}-${row.job_id}`} className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <div className="text-sm font-semibold text-white">{row.symbol}</div>
                            <div className="text-xs text-slate-400">{row.conviction || '—'} • {Math.round(Number(row.confidence || 0) * 100)}%</div>
                          </div>
                          <span className="rounded-full border border-emerald-400/40 px-2 py-1 text-xs text-emerald-200">BUY</span>
                        </div>
                        <p className="mt-2 text-xs text-slate-300 line-clamp-2">{row.rationale || 'No rationale available.'}</p>
                      </div>
                    ))}
                    {(deskSnapshot.nifty100.buy_recommendations || []).length === 0 && (
                      <p className="text-xs text-slate-500">No BUY recommendations available yet.</p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Zerodha Holdings</p>
                      <h3 className="text-white font-semibold">Hold / Sell Desk</h3>
                    </div>
                    <span className="text-xs text-slate-400">{deskSnapshot.holdings.rows.length} holdings</span>
                  </div>
                  <div className="mt-3 text-xs text-slate-400 flex flex-wrap gap-2">
                    <span className="rounded-full border border-slate-700 px-2 py-1">State: {deskSnapshot.holdings.state.status || 'idle'}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Queued: {deskSnapshot.holdings.state.queued || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Running: {deskSnapshot.holdings.state.running || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Completed: {deskSnapshot.holdings.state.completed || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Failed: {deskSnapshot.holdings.state.failed || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Remaining: {deskSnapshot.holdings.state.remaining || 0}</span>
                    <span className="rounded-full border border-slate-700 px-2 py-1">Last run: {deskSnapshot.holdings.state.last_run_at || '—'}</span>
                  </div>
                  <div className="mt-4 space-y-2 max-h-72 overflow-y-auto pr-1">
                    {deskSnapshot.holdings.rows.map((row) => {
                      const action = String(row.decision?.action || 'HOLD').toUpperCase();
                      const actionClass = action === 'BUY'
                        ? 'border-emerald-400/40 text-emerald-200 bg-emerald-500/10'
                        : action === 'SELL'
                          ? 'border-rose-400/40 text-rose-200 bg-rose-500/10'
                          : 'border-amber-400/40 text-amber-200 bg-amber-500/10';

                      return (
                        <div key={row.symbol} className="rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2">
                          <div className="flex items-center justify-between gap-2">
                            <div>
                              <div className="text-sm font-semibold text-white">{row.symbol}</div>
                              <div className="text-xs text-slate-400">Qty {row.quantity} • P&L ₹{Number(row.pnl || 0).toLocaleString('en-IN')}</div>
                            </div>
                            <span className={`rounded-full border px-2 py-1 text-xs font-semibold ${actionClass}`}>{action}</span>
                          </div>
                          <p className="mt-2 text-xs text-slate-300 line-clamp-2">
                            {row.decision?.rationale || 'No daily verdict yet for this holding.'}
                          </p>
                        </div>
                      );
                    })}
                    {deskSnapshot.holdings.rows.length === 0 && (
                      <p className="text-xs text-slate-500">No Zerodha holdings found or holdings API unavailable.</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-200 flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 rounded-xl border border-slate-700 bg-slate-900/80 p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-white font-semibold text-lg flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-cyan-300" />
              Reconciled View
            </h2>
            <span className={`inline-flex items-center gap-1 border rounded-full px-3 py-1 text-sm font-semibold ${actionPill(consensus.action)}`}>
              {actionIcon(consensus.action)}
              Consensus {consensus.action}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="rounded-lg border border-slate-700 bg-slate-800/80 p-3">
              <p className="text-xs text-slate-400">Consensus Confidence</p>
              <p className="text-2xl font-bold text-white mt-1">{Math.round(consensus.confidence * 100)}%</p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-800/80 p-3">
              <p className="text-xs text-slate-400">Signal Conflict</p>
              <p className="text-2xl font-bold text-white mt-1">{Math.round(consensus.conflict * 100)}%</p>
            </div>
            <div className="rounded-lg border border-slate-700 bg-slate-800/80 p-3">
              <p className="text-xs text-slate-400">Agreement State</p>
              <p className="text-xl font-semibold text-cyan-200 mt-1">{agreementText}</p>
            </div>
          </div>

          <div className="mt-4 h-2 rounded-full bg-slate-800 overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-emerald-400 via-cyan-400 to-rose-400"
              style={{ width: `${Math.max(8, Math.round((1 - consensus.conflict) * 100))}%` }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-5">
          <h2 className="text-white font-semibold text-lg flex items-center gap-2">
            <Target className="w-5 h-5 text-emerald-300" />
            Strategy Diagnostics
          </h2>
          <p className="mt-1 text-xs text-slate-400">Scope: {diagnosticsScope}</p>
          {diagnosticsSummary && hasDiagnosticsTrades ? (
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between text-slate-300">
                <span>Total Trades</span>
                <span className="text-white font-semibold">{diagnosticsSummary.total_trades ?? 0}</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>Win Rate</span>
                <span className="text-white font-semibold">{(diagnosticsSummary.win_rate_pct ?? 0).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>Net P&L</span>
                <span className={(diagnosticsSummary.net_pnl ?? 0) >= 0 ? 'text-emerald-300 font-semibold' : 'text-rose-300 font-semibold'}>
                  ₹{Number(diagnosticsSummary.net_pnl ?? 0).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="flex justify-between text-slate-300">
                <span>Avg Return</span>
                <span className="text-white font-semibold">{(diagnosticsSummary.avg_return_pct ?? 0).toFixed(2)}%</span>
              </div>
            </div>
          ) : (
            <div className="mt-4 space-y-2">
              <p className="text-sm text-slate-400">No closed-trade diagnostics yet for this symbol in current lookback.</p>
              {strategySuggestion ? (
                <p className="text-xs text-slate-500">
                  Recent strategy signals: {strategySuggestion.recent_signal_count || 0} | Latest strategy: {strategySuggestion.latest_strategy || 'N/A'}
                </p>
              ) : null}
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {sourceVotes.length === 0 && (
          <div className="col-span-full rounded-xl border border-slate-700 bg-slate-900/80 p-6 text-center text-slate-400">
            No signal sources loaded yet. Enter a symbol and click Refresh.
          </div>
        )}

        {sourceVotes.map((vote) => (
          <div key={vote.source} className="rounded-xl border border-slate-700 bg-slate-900/80 p-4 flex flex-col">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-white flex items-center gap-2">
                {vote.source.includes('AI') ? <Bot className="w-4 h-4 text-cyan-300" /> : null}
                {vote.source.includes('ML') ? <Brain className="w-4 h-4 text-violet-300" /> : null}
                {vote.source.includes('Strategy') ? <CheckCircle2 className="w-4 h-4 text-emerald-300" /> : null}
                {vote.source}
              </p>
              <span className={`inline-flex items-center gap-1 border rounded-full px-2.5 py-1 text-xs font-semibold ${actionPill(vote.action)}`}>
                {actionIcon(vote.action)}
                {vote.action}
              </span>
            </div>

            <p className="mt-3 text-2xl font-bold text-white">{Math.round(vote.confidence * 100)}%</p>
            <p className="text-xs text-slate-400">Confidence</p>
            {vote.signalLabel === 'NO_TRADE' ? (
              <p className="mt-1 text-xs text-amber-300">Model stance: NO_TRADE (abstain), shown as HOLD in consensus.</p>
            ) : null}

            <p className="mt-3 text-sm text-slate-300 line-clamp-4">{vote.detail}</p>
            {vote.meta && <p className="mt-2 text-xs text-slate-500">{vote.meta}</p>}
          </div>
        ))}
      </div>

      <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-white font-semibold text-lg flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-violet-300" />
            Debate Output
          </h2>
          {debateRoundsUsed ? (
            <span className="text-xs px-2.5 py-1 rounded-full bg-violet-500/20 border border-violet-500/40 text-violet-200">
              {debateRoundsUsed} rounds
            </span>
          ) : null}
        </div>

        {debateTranscript.length === 0 ? (
          <p className="mt-3 text-sm text-slate-400">
            Debate transcript will appear here after you click Run AI Debate and the job completes.
          </p>
        ) : (
          <div className="mt-4 space-y-3">
            {debateTranscript.map((round) => (
              <div key={round.round} className="rounded-lg border border-slate-700 bg-slate-800/70 p-3">
                <p className="text-xs font-semibold tracking-wide text-slate-300">ROUND {round.round}</p>
                <div className="mt-2 grid grid-cols-1 lg:grid-cols-2 gap-3">
                  <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3">
                    <p className="text-xs text-emerald-300 font-semibold">Bull Argument</p>
                    <p className="mt-1 text-sm text-slate-200">{round.bull?.thesis || 'No bull thesis available.'}</p>
                    <p className="mt-1 text-xs text-slate-400">Confidence: {Math.round(Number(round.bull?.confidence || 0) * 100)}%</p>
                  </div>
                  <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3">
                    <p className="text-xs text-rose-300 font-semibold">Bear Argument</p>
                    <p className="mt-1 text-sm text-slate-200">{round.bear?.thesis || 'No bear thesis available.'}</p>
                    <p className="mt-1 text-xs text-slate-400">Confidence: {Math.round(Number(round.bear?.confidence || 0) * 100)}%</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SignalReconciliation;
