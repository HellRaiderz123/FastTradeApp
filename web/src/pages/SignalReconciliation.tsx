import React, { useMemo, useState } from 'react';
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
import { aiAPI, DebateRoundEntry, HistoryEntry, PipelineResult } from '../api/aiAPI';
import { journalAPI, mlAPI, watchlistAPI } from '../lib/api';

type Action = 'BUY' | 'SELL' | 'HOLD';

type SourceVote = {
  source: string;
  action: Action;
  confidence: number;
  detail: string;
  meta?: string;
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

const POPULAR_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'SBIN', 'INFY', 'HDFCBANK'];

function normalizeMlToAction(signal?: string): Action {
  const s = String(signal || '').toUpperCase();
  if (s.includes('BULL')) return 'BUY';
  if (s.includes('BEAR')) return 'SELL';
  return 'HOLD';
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [aiLatest, setAiLatest] = useState<HistoryEntry | null>(null);
  const [mlSingle, setMlSingle] = useState<MLSnapshot | null>(null);
  const [mlEnsemble, setMlEnsemble] = useState<MLSnapshot | null>(null);
  const [strategySuggestion, setStrategySuggestion] = useState<WatchlistSuggestion | null>(null);
  const [diagnosticsSummary, setDiagnosticsSummary] = useState<any>(null);

  const [lastRefreshedAt, setLastRefreshedAt] = useState<string | null>(null);
  const [debateRounds, setDebateRounds] = useState(2);
  const [aiRunLoading, setAiRunLoading] = useState(false);
  const [aiRunStatus, setAiRunStatus] = useState<string | null>(null);
  const [debateTranscript, setDebateTranscript] = useState<DebateRoundEntry[]>([]);
  const [debateRoundsUsed, setDebateRoundsUsed] = useState<number | null>(null);

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

  const loadSnapshot = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) return;

    setLoading(true);
    setError(null);

    try {
      const [aiRes, singleRes, ensembleRes, diagRes, suggestionRes] = await Promise.allSettled([
        aiAPI.history(sym, 5),
        mlAPI.predict(sym),
        mlAPI.ensemblePredict(sym),
        journalAPI.getSignalDiagnostics({ limit: 200, lookback_days: 45, underlying: sym }),
        fetchStrategySuggestion(sym),
      ]);

      if (aiRes.status === 'fulfilled') {
        const decisions: HistoryEntry[] = aiRes.value.data?.decisions || [];
        setAiLatest(decisions[0] || null);
      } else {
        setAiLatest(null);
      }

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

      if (diagRes.status === 'fulfilled') {
        setDiagnosticsSummary(diagRes.value.data?.summary || null);
      } else {
        setDiagnosticsSummary(null);
      }

      if (suggestionRes.status === 'fulfilled') {
        setStrategySuggestion(suggestionRes.value || null);
      } else {
        setStrategySuggestion(null);
      }

      setLastRefreshedAt(new Date().toLocaleTimeString('en-IN'));
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load reconciliation snapshot');
    } finally {
      setLoading(false);
    }
  };

  const runFreshAIDebate = async () => {
    const sym = symbol.trim().toUpperCase();
    if (!sym) return;

    setAiRunLoading(true);
    setAiRunStatus('Starting AI debate run...');
    setError(null);

    try {
      const startRes = await aiAPI.analyze(sym, 'NSE', {
        debate_rounds: debateRounds,
      });
      const jobId = startRes.data?.job_id;
      if (!jobId) throw new Error('AI analysis did not return a job id');

      let completed = false;
      let finalResult: PipelineResult | null = null;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        // Poll every 2.5s up to ~5 minutes for completion.
        await new Promise((resolve) => setTimeout(resolve, 2500));
        const statusRes = await aiAPI.status(jobId);
        const status = statusRes.data?.status;
        const currentStep = statusRes.data?.current_step;
        finalResult = statusRes.data?.result || null;
        setAiRunStatus(status === 'RUNNING' && currentStep ? `Running: ${currentStep}` : `Status: ${status || 'UNKNOWN'}`);

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

      const historyRes = await aiAPI.history(sym, 5);
      const decisions: HistoryEntry[] = historyRes.data?.decisions || [];
      setAiLatest(decisions[0] || null);
      const transcript = finalResult?.debate_transcript || [];
      setDebateTranscript(Array.isArray(transcript) ? transcript : []);
      const rounds = Number(finalResult?.data_summary?.debate_rounds || 0);
      setDebateRoundsUsed(Number.isFinite(rounds) && rounds > 0 ? rounds : null);
      setAiRunStatus(`Completed with ${debateRounds} debate rounds`);
      setLastRefreshedAt(new Date().toLocaleTimeString('en-IN'));
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Failed to run AI debate analysis';
      setError(msg);
      setAiRunStatus('Run failed');
    } finally {
      setAiRunLoading(false);
    }
  };

  const sourceVotes = useMemo<SourceVote[]>(() => {
    const votes: SourceVote[] = [];

    if (aiLatest) {
      votes.push({
        source: 'AI Recommendation',
        action: (aiLatest.action as Action) || 'HOLD',
        confidence: Number(aiLatest.confidence || 0),
        detail: aiLatest.rationale || 'No AI rationale available.',
        meta: aiLatest.analysed_at ? `Updated ${new Date(aiLatest.analysed_at).toLocaleString('en-IN')}` : undefined,
      });
    }

    if (mlSingle) {
      votes.push({
        source: 'ML Recommendation',
        action: normalizeMlToAction(mlSingle.signal),
        confidence: Number(mlSingle.confidence || 0),
        detail: mlSingle.reason || 'No ML explanation available.',
        meta: `Signal: ${mlSingle.signal || 'NO_TRADE'} | Bias: ${mlSingle.bias || 'NEUTRAL'}`,
      });
    }

    if (mlEnsemble) {
      votes.push({
        source: 'ML Ensemble',
        action: normalizeMlToAction(mlEnsemble.signal),
        confidence: Number(mlEnsemble.confidence || 0),
        detail: mlEnsemble.reason || 'No ensemble explanation available.',
        meta: `Signal: ${mlEnsemble.signal || 'NO_TRADE'} | Bias: ${mlEnsemble.bias || 'NEUTRAL'}`,
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
  }, [aiLatest, mlSingle, mlEnsemble, strategySuggestion]);

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
              onChange={(e) => setSymbol(e.target.value.toUpperCase())}
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
              onClick={loadSnapshot}
              disabled={loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-500 px-4 py-2.5 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Refresh
            </button>
            <button
              onClick={runFreshAIDebate}
              disabled={aiRunLoading}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-violet-500 px-4 py-2.5 font-semibold text-white transition hover:bg-violet-400 disabled:opacity-60"
            >
              {aiRunLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
              Run AI Debate
            </button>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {POPULAR_SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
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
        {aiRunStatus && (
          <p className="mt-1 text-xs text-violet-200">{aiRunStatus}</p>
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
          {diagnosticsSummary ? (
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
            <p className="mt-4 text-sm text-slate-400">No diagnostics yet for this symbol in current lookback.</p>
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
