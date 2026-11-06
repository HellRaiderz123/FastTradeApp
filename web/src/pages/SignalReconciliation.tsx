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
  FileText,
  BarChart2,
  Activity,
} from 'lucide-react';
import { aiAPI, DebateRoundEntry, PipelineResult, type ReconciliationDeskRow, type ReconciliationDeskSnapshot } from '../api/aiAPI';
import { journalAPI, mlAPI, watchlistAPI } from '../lib/api';
import api from '../lib/api';

type Action = 'BUY' | 'SELL' | 'HOLD';

type SourceVote = {
  source: string;
  action: Action;
  confidence: number;
  detail: string;
  meta?: string;
  signalLabel?: string;
  icon?: React.ReactNode;
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

type QuantSnapshot = {
  orb_breakout?: string;
  price_vs_vwap?: string;
  rvol?: number;
  rvol_signal?: string;
  regime?: string;
  hurst_exponent?: number;
  zscore_20?: number;
  rs_vs_nifty_5d?: number;
  atr_14?: number;
};

type FilingSnapshot = {
  sentiment?: string;
  sentiment_score?: number;
  summary?: string;
  signal_tags?: string[];
  published_at?: string;
};

type SentimentSnapshot = {
  sentiment_score?: number;
  sentiment?: string;
  components?: {
    vix?: { level: number; score: number; interpretation: string };
    pcr?: { value: number; score: number; interpretation: string };
    advance_decline?: { ratio: number; score: number; strength: string };
  };
};

type ReconciliationSnapshot = {
  savedAt: number;
  aiOutcome: AIOutcome | null;
  mlSingle: MLSnapshot | null;
  mlEnsemble: MLSnapshot | null;
  mlLSTM: MLSnapshot | null;
  strategySuggestion: WatchlistSuggestion | null;
  diagnosticsSummary: any;
  diagnosticsScope: string;
  debateTranscript: DebateRoundEntry[];
  debateRoundsUsed: number | null;
  filing: FilingSnapshot | null;
  quant: QuantSnapshot | null;
  sentiment: SentimentSnapshot | null;
};

const POPULAR_SYMBOLS = ['NIFTY', 'BANKNIFTY', 'RELIANCE', 'TCS', 'SBIN', 'INFY', 'HDFCBANK'];
const CACHE_TTL_MS = 5 * 60 * 1000;

// Source weights for final consensus (must sum to 1.0)
const SOURCE_WEIGHTS: Record<string, number> = {
  'AI Debate':       0.25,
  'ML Ensemble':     0.18,
  'ML Single':       0.12,
  'ML LSTM':         0.10,
  'Quant Bot':       0.15,
  'NSE Filing':      0.10,
  'Market Sentiment':0.05,
  'Strategy Engine': 0.05,
};

function normalizeMlToAction(signal?: string): Action {
  const s = String(signal || '').toUpperCase();
  if (s.includes('BULL')) return 'BUY';
  if (s.includes('BEAR')) return 'SELL';
  return 'HOLD';
}

function normalizeDeskAction(action?: string | null): Action {
  const s = String(action || '').toUpperCase();
  if (s === 'BUY') return 'BUY';
  if (s === 'SELL') return 'SELL';
  return 'HOLD';
}

function normalizeConfidence01(value: unknown): number {
  const n = Number(value ?? 0);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return n > 1 ? Math.max(0, Math.min(1, n / 100)) : Math.max(0, Math.min(1, n));
}

function actionScore(action: Action): number {
  if (action === 'BUY') return 1;
  if (action === 'SELL') return -1;
  return 0;
}

function scoreToAction(v: number): Action {
  if (v > 0.15) return 'BUY';
  if (v < -0.15) return 'SELL';
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
  const [mlLSTM, setMlLSTM] = useState<MLSnapshot | null>(null);
  const [strategySuggestion, setStrategySuggestion] = useState<WatchlistSuggestion | null>(null);
  const [diagnosticsSummary, setDiagnosticsSummary] = useState<any>(null);
  const [diagnosticsScope, setDiagnosticsScope] = useState<string>('Symbol');
  const [filing, setFiling] = useState<FilingSnapshot | null>(null);
  const [quant, setQuant] = useState<QuantSnapshot | null>(null);
  const [sentiment, setSentiment] = useState<SentimentSnapshot | null>(null);

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
    setMlLSTM(null);
    setStrategySuggestion(null);
    setDiagnosticsSummary(null);
    setDiagnosticsScope('Symbol');
    setDebateTranscript([]);
    setDebateRoundsUsed(null);
    setLastRefreshedAt(null);
    setRunStatus(null);
    setFiling(null);
    setQuant(null);
    setSentiment(null);
  };

  const applySnapshot = (snapshot: ReconciliationSnapshot) => {
    setAiOutcome(snapshot.aiOutcome);
    setMlSingle(snapshot.mlSingle);
    setMlEnsemble(snapshot.mlEnsemble);
    setMlLSTM(snapshot.mlLSTM);
    setStrategySuggestion(snapshot.strategySuggestion);
    setDiagnosticsSummary(snapshot.diagnosticsSummary);
    setDiagnosticsScope(snapshot.diagnosticsScope || 'Symbol');
    setDebateTranscript(snapshot.debateTranscript || []);
    setDebateRoundsUsed(snapshot.debateRoundsUsed);
    setFiling(snapshot.filing);
    setQuant(snapshot.quant);
    setSentiment(snapshot.sentiment);
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
      if (!best || (match.score || 0) > (best.score || 0)) best = match;
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
    setRunStatus('Running full 6-source reconciliation...');
    resetCurrentResults();

    try {
      // Fire all non-AI calls in parallel
      setRunStatus('Fetching ML, Quant, Filing, Sentiment signals...');
      const [
        singleRes,
        ensembleRes,
        lstmRes,
        diagRes,
        suggestionRes,
        filingRes,
        quantRes,
        sentimentRes,
      ] = await Promise.allSettled([
        mlAPI.predict(sym),
        mlAPI.ensemblePredict(sym),
        mlAPI.lstmPredict(sym),
        journalAPI.getSignalDiagnostics({ limit: 200, lookback_days: 45, underlying: sym }),
        fetchStrategySuggestion(sym),
        api.get(`/nse/filing-analysis?symbol=${sym}&limit=1&passed_only=true`),
        api.get(`/quant/cash/${sym}`),
        api.get(`/sentiment/overall`),
      ]);

      // Start AI debate
      setRunStatus('Starting AI debate...');
      const startRes = await aiAPI.analyze(sym, 'NSE', { debate_rounds: debateRounds });
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
        setRunStatus(status === 'RUNNING' && currentStep ? `AI: ${currentStep}` : `AI status: ${status || 'UNKNOWN'}`);
        if (status === 'COMPLETED') { completed = true; break; }
        if (status === 'FAILED') throw new Error('AI debate run failed');
      }
      if (!completed) throw new Error('Timed out waiting for AI debate');

      // --- AI outcome ---
      const nextAiOutcome: AIOutcome | null = finalResult?.decision
        ? {
            action: finalResult.decision.action,
            confidence: normalizeConfidence01(finalResult.decision.confidence || 0),
            rationale: finalResult.decision.rationale || 'No AI rationale available.',
            analysed_at: finalResult.analysed_at,
          }
        : null;

      // --- ML Single ---
      const nextMlSingle = singleRes.status === 'fulfilled' ? (singleRes.value.data || null) : null;
      setMlSingle(nextMlSingle);

      // --- ML Ensemble ---
      const nextMlEnsemble = ensembleRes.status === 'fulfilled' ? (ensembleRes.value.data || null) : null;
      setMlEnsemble(nextMlEnsemble);

      // --- ML LSTM ---
      const nextMlLSTM = lstmRes.status === 'fulfilled' ? (lstmRes.value.data || null) : null;
      setMlLSTM(nextMlLSTM);

      // --- Filing ---
      let nextFiling: FilingSnapshot | null = null;
      if (filingRes.status === 'fulfilled') {
        const row = filingRes.value.data?.data?.[0];
        if (row) {
          nextFiling = {
            sentiment: row.sentiment,
            sentiment_score: row.sentiment_score,
            summary: row.summary,
            signal_tags: (row.signal_tags || []),
            published_at: row.published_at,
          };
        }
      }
      setFiling(nextFiling);

      // --- Quant ---
      let nextQuant: QuantSnapshot | null = null;
      if (quantRes.status === 'fulfilled') {
        nextQuant = quantRes.value.data || null;
      }
      setQuant(nextQuant);

      // --- Sentiment ---
      let nextSentiment: SentimentSnapshot | null = null;
      if (sentimentRes.status === 'fulfilled') {
        nextSentiment = sentimentRes.value.data || null;
      }
      setSentiment(nextSentiment);

      // --- Diagnostics ---
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
            nextDiagnosticsSummary = portfolioDiag.data?.summary || null;
            nextDiagnosticsScope = 'Portfolio (fallback)';
          } catch {
            nextDiagnosticsSummary = symbolSummary;
          }
        }
      }
      setDiagnosticsSummary(nextDiagnosticsSummary);
      setDiagnosticsScope(nextDiagnosticsScope);

      // --- Strategy ---
      const nextStrategy = suggestionRes.status === 'fulfilled' ? (suggestionRes.value || null) : null;
      setStrategySuggestion(nextStrategy);

      setAiOutcome(nextAiOutcome);
      const transcript = finalResult?.debate_transcript || [];
      setDebateTranscript(Array.isArray(transcript) ? transcript : []);
      const rounds = Number(finalResult?.data_summary?.debate_rounds || 0);
      const nextRoundsUsed = Number.isFinite(rounds) && rounds > 0 ? rounds : null;
      setDebateRoundsUsed(nextRoundsUsed);

      const snapshot: ReconciliationSnapshot = {
        savedAt: Date.now(),
        aiOutcome: nextAiOutcome,
        mlSingle: nextMlSingle,
        mlEnsemble: nextMlEnsemble,
        mlLSTM: nextMlLSTM,
        strategySuggestion: nextStrategy,
        diagnosticsSummary: nextDiagnosticsSummary,
        diagnosticsScope: nextDiagnosticsScope,
        debateTranscript: Array.isArray(transcript) ? transcript : [],
        debateRoundsUsed: nextRoundsUsed,
        filing: nextFiling,
        quant: nextQuant,
        sentiment: nextSentiment,
      };
      cacheRef.current[key] = snapshot;
      setRunStatus(`Completed — ${debateRounds} debate rounds, 6 sources reconciled`);
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

    // 1. AI Debate
    if (aiOutcome) {
      votes.push({
        source: 'AI Debate',
        action: aiOutcome.action || 'HOLD',
        confidence: Number(aiOutcome.confidence || 0),
        detail: aiOutcome.rationale || 'No AI rationale available.',
        meta: aiOutcome.analysed_at ? `Updated ${new Date(aiOutcome.analysed_at).toLocaleString('en-IN')}` : undefined,
        icon: <Bot className="w-4 h-4 text-cyan-300" />,
      });
    }

    // 2. ML Ensemble
    if (mlEnsemble) {
      const rawSignal = String(mlEnsemble.signal || 'NO_TRADE').toUpperCase();
      votes.push({
        source: 'ML Ensemble',
        action: normalizeMlToAction(rawSignal),
        confidence: normalizeConfidence01(mlEnsemble.confidence || 0),
        detail: mlEnsemble.reason || 'No ensemble explanation available.',
        meta: `Signal: ${rawSignal} | Bias: ${mlEnsemble.bias || 'NEUTRAL'}`,
        signalLabel: rawSignal,
        icon: <Brain className="w-4 h-4 text-violet-300" />,
      });
    }

    // 3. ML Single
    if (mlSingle) {
      const rawSignal = String(mlSingle.signal || 'NO_TRADE').toUpperCase();
      votes.push({
        source: 'ML Single',
        action: normalizeMlToAction(rawSignal),
        confidence: normalizeConfidence01(mlSingle.confidence || 0),
        detail: mlSingle.reason || 'No ML explanation available.',
        meta: `Signal: ${rawSignal} | Bias: ${mlSingle.bias || 'NEUTRAL'}`,
        signalLabel: rawSignal,
        icon: <Brain className="w-4 h-4 text-purple-300" />,
      });
    }

    // 4. ML LSTM
    if (mlLSTM && String(mlLSTM.signal || '').toUpperCase() !== 'N/A') {
      const rawSignal = String(mlLSTM.signal || 'NO_TRADE').toUpperCase();
      votes.push({
        source: 'ML LSTM',
        action: normalizeMlToAction(rawSignal),
        confidence: normalizeConfidence01(mlLSTM.confidence || 0),
        detail: mlLSTM.reason || 'No LSTM explanation available.',
        meta: `Signal: ${rawSignal} | Bias: ${mlLSTM.bias || 'NEUTRAL'}`,
        signalLabel: rawSignal,
        icon: <Activity className="w-4 h-4 text-pink-300" />,
      });
    }

    // 5. Quant Bot
    if (quant) {
      const orbUp = quant.orb_breakout === 'UP';
      const orbDown = quant.orb_breakout === 'DOWN';
      const aboveVwap = quant.price_vs_vwap === 'ABOVE';
      const belowVwap = quant.price_vs_vwap === 'BELOW';
      const highRvol = (quant.rvol || 0) > 1.2;
      const bullish = orbUp && aboveVwap && highRvol;
      const bearish = orbDown && belowVwap;
      const quantAction: Action = bullish ? 'BUY' : bearish ? 'SELL' : 'HOLD';
      const quantConf = Math.min(1, (quant.rvol || 1) / 3);
      votes.push({
        source: 'Quant Bot',
        action: quantAction,
        confidence: quantConf,
        detail: `ORB: ${quant.orb_breakout || 'N/A'} | VWAP: ${quant.price_vs_vwap || 'N/A'} | RVOL: ${(quant.rvol || 0).toFixed(2)} | RS vs Nifty: ${(quant.rs_vs_nifty_5d || 0).toFixed(2)}%`,
        meta: `Regime: ${quant.regime || 'N/A'} | Hurst: ${(quant.hurst_exponent || 0).toFixed(2)} | Z-Score: ${(quant.zscore_20 || 0).toFixed(2)}`,
        icon: <BarChart2 className="w-4 h-4 text-orange-300" />,
      });
    }

    // 6. NSE Filing
    if (filing) {
      const score = filing.sentiment_score ?? 0;
      const filingAction: Action = score > 0.1 ? 'BUY' : score < -0.1 ? 'SELL' : 'HOLD';
      votes.push({
        source: 'NSE Filing',
        action: filingAction,
        confidence: Math.min(1, Math.abs(score)),
        detail: filing.summary || `Signals: ${(filing.signal_tags || []).join(', ') || 'None'}`,
        meta: `Tags: ${(filing.signal_tags || []).join(', ') || 'None'} | ${filing.published_at ? new Date(filing.published_at).toLocaleDateString('en-IN') : ''}`,
        icon: <FileText className="w-4 h-4 text-yellow-300" />,
      });
    }

    // 7. Market Sentiment
    if (sentiment) {
      const score = Number(sentiment.sentiment_score || 50);
      // Convert 0-100 scale to action
      const sentAction: Action = score >= 60 ? 'BUY' : score <= 40 ? 'SELL' : 'HOLD';
      const sentConf = Math.abs(score - 50) / 50;
      const vix = sentiment.components?.vix;
      const pcr = sentiment.components?.pcr;
      votes.push({
        source: 'Market Sentiment',
        action: sentAction,
        confidence: sentConf,
        detail: `Overall: ${sentiment.sentiment || 'NEUTRAL'} (${score}/100) | VIX: ${vix?.interpretation || 'N/A'} | PCR: ${pcr?.interpretation || 'N/A'}`,
        meta: `VIX: ${vix?.level?.toFixed(1) || 'N/A'} | PCR: ${pcr?.value?.toFixed(2) || 'N/A'}`,
        icon: <Radar className="w-4 h-4 text-teal-300" />,
      });
    }

    // 8. Strategy Engine
    if (strategySuggestion) {
      const direction = String(strategySuggestion.latest_direction || '').toUpperCase();
      const stratAction: Action =
        direction.includes('BULL') || direction.includes('BUY') ? 'BUY'
        : direction.includes('BEAR') || direction.includes('SELL') ? 'SELL'
        : 'HOLD';
      votes.push({
        source: 'Strategy Engine',
        action: stratAction,
        confidence: Math.max(0, Math.min(1, Number(strategySuggestion.score || 0) / 100)),
        detail: strategySuggestion.latest_strategy || 'No recent strategy signal text available.',
        meta: `${strategySuggestion.recent_signal_count || 0} recent signals`,
        icon: <CheckCircle2 className="w-4 h-4 text-emerald-300" />,
      });
    }

    return votes;
  }, [aiOutcome, mlSingle, mlEnsemble, mlLSTM, strategySuggestion, filing, quant, sentiment]);

  const consensus = useMemo(() => {
    if (!sourceVotes.length) return { action: 'HOLD' as Action, confidence: 0, conflict: 0, weightedScore: 0 };

    let weightedSum = 0;
    let totalWeight = 0;

    for (const vote of sourceVotes) {
      const w = SOURCE_WEIGHTS[vote.source] ?? 0.05;
      const conf = Math.max(0.1, Math.min(1, vote.confidence || 0));
      const effectiveWeight = w * conf;
      weightedSum += actionScore(vote.action) * effectiveWeight;
      totalWeight += effectiveWeight;
    }

    const normalized = totalWeight > 0 ? weightedSum / totalWeight : 0;
    const action = scoreToAction(normalized);

    const first = sourceVotes[0]?.action;
    const disagreements = sourceVotes.filter((v) => v.action !== first).length;
    const conflict = sourceVotes.length > 1 ? disagreements / (sourceVotes.length - 1) : 0;

    return { action, confidence: Math.abs(normalized), conflict, weightedScore: normalized };
  }, [sourceVotes]);

  const agreementText =
    consensus.conflict <= 0.2 ? 'High agreement'
    : consensus.conflict <= 0.55 ? 'Mixed signals'
    : 'Strong disagreement';

  const hasDiagnosticsTrades = Number(diagnosticsSummary?.total_trades || 0) > 0;

  const latestNiftyRows = useMemo(
    () => (deskSnapshot?.nifty100.latest || []).slice(0, 12),
    [deskSnapshot]
  );

  const niftyActionCounts = useMemo(() => {
    const counts: Record<Action, number> = { BUY: 0, SELL: 0, HOLD: 0 };
    const apiCounts = deskSnapshot?.nifty100.action_counts;
    if (apiCounts) {
      counts.BUY = Number(apiCounts.BUY || 0);
      counts.SELL = Number(apiCounts.SELL || 0);
      counts.HOLD = Number(apiCounts.HOLD || 0);
      return counts;
    }
    for (const row of deskSnapshot?.nifty100.latest || []) {
      counts[normalizeDeskAction(row.recommendation_action || row.action)] += 1;
    }
    return counts;
  }, [deskSnapshot]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-slate-700 bg-[radial-gradient(circle_at_top_left,_rgba(34,197,94,0.12),transparent_45%),radial-gradient(circle_at_top_right,_rgba(14,165,233,0.12),transparent_40%),#0f172a] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white flex items-center gap-3">
              <Radar className="w-8 h-8 text-cyan-300" />
              Signal Reconciliation
            </h1>
            <p className="mt-2 text-slate-300 max-w-3xl">
              8-source quant decision desk — AI Debate, ML Ensemble, ML Single, ML LSTM, Quant Bot, NSE Filing, Market Sentiment, and Strategy Engine.
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

        {lastRefreshedAt && <p className="mt-3 text-xs text-slate-400">Last refresh: {lastRefreshedAt}</p>}
        {runStatus && <p className="mt-1 text-xs text-violet-200">{runStatus}</p>}

        {/* Signal source weight legend */}
        <div className="mt-4 flex flex-wrap gap-2">
          {Object.entries(SOURCE_WEIGHTS).map(([src, w]) => (
            <span key={src} className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-xs text-slate-400">
              {src} <span className="text-slate-500">{Math.round(w * 100)}%</span>
            </span>
          ))}
        </div>

        {/* Background Decision Desk */}
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
                {/* Nifty100 Desk */}
                <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Nifty100 Desk</p>
                      <h3 className="text-white font-semibold">Daily Decision Queue</h3>
                    </div>
                    <span className="text-xs text-slate-400">{deskSnapshot.nifty100.symbol_count} symbols</span>
                  </div>
                  <div className="mt-3 text-xs text-slate-400 flex flex-wrap gap-2">
                    {(['status','queued','running','completed','failed','remaining'] as const).map((k) => (
                      <span key={k} className="rounded-full border border-slate-700 px-2 py-1">
                        {k.charAt(0).toUpperCase() + k.slice(1)}: {(deskSnapshot.nifty100.state as any)[k] ?? (k === 'status' ? 'idle' : 0)}
                      </span>
                    ))}
                    <span className="rounded-full border border-slate-700 px-2 py-1">Last run: {deskSnapshot.nifty100.state.last_run_at || '—'}</span>
                  </div>
                  <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    {(['BUY', 'SELL', 'HOLD'] as Action[]).map((action) => (
                      <div key={action} className={`rounded-lg border px-3 py-2 ${actionPill(action)}`}>
                        <div className="flex items-center justify-between gap-2">
                          <span className="inline-flex items-center gap-1 font-semibold">{actionIcon(action)}{action}</span>
                          <span>{niftyActionCounts[action]}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 space-y-2 max-h-80 overflow-y-auto pr-1">
                    {(deskSnapshot.nifty100.buy_recommendations || []).slice(0, 8).map((row) => (
                      <div key={`${row.symbol}-${row.job_id}`} className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 px-3 py-2">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <div className="text-sm font-semibold text-white">{row.symbol}</div>
                            <div className="text-xs text-slate-400">
                              {row.conviction || 'N/A'} | {Math.round(Number(row.confidence || 0) * 100)}% | {row.execution_allowed ? 'Allowed' : 'Blocked'}
                            </div>
                          </div>
                          <span className="rounded-full border border-emerald-400/40 px-2 py-1 text-xs text-emerald-200">BUY</span>
                        </div>
                        <p className="mt-2 text-xs text-slate-300 line-clamp-2">{row.manager_block_reason || row.rationale || 'No rationale available.'}</p>
                      </div>
                    ))}
                    {(deskSnapshot.nifty100.buy_recommendations || []).length === 0 && (
                      <p className="text-xs text-slate-500">No BUY recommendations in the latest completed batch.</p>
                    )}
                    {latestNiftyRows.length > 0 && (
                      <div className="pt-2">
                        <div className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Latest Decisions</div>
                        <div className="space-y-2">
                          {latestNiftyRows.map((row: ReconciliationDeskRow) => {
                            const action = normalizeDeskAction(row.recommendation_action || row.action);
                            return (
                              <div key={`latest-${row.symbol}-${row.job_id}`} className="rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2">
                                <div className="flex items-center justify-between gap-2">
                                  <div>
                                    <div className="text-sm font-semibold text-white">{row.symbol}</div>
                                    <div className="text-xs text-slate-400">
                                      {row.conviction || 'N/A'} | {Math.round(Number(row.confidence || 0) * 100)}% | {row.execution_allowed ? 'Allowed' : 'Blocked'}
                                    </div>
                                  </div>
                                  <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-xs font-semibold ${actionPill(action)}`}>
                                    {actionIcon(action)}{action}
                                  </span>
                                </div>
                                <p className="mt-2 text-xs text-slate-300 line-clamp-2">{row.manager_block_reason || row.rationale || 'No rationale available.'}</p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Holdings Desk */}
                <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Zerodha Holdings</p>
                      <h3 className="text-white font-semibold">Hold / Sell Desk</h3>
                    </div>
                    <span className="text-xs text-slate-400">{deskSnapshot.holdings.rows.length} holdings</span>
                  </div>
                  <div className="mt-3 text-xs text-slate-400 flex flex-wrap gap-2">
                    {(['status','queued','running','completed','failed','remaining'] as const).map((k) => (
                      <span key={k} className="rounded-full border border-slate-700 px-2 py-1">
                        {k.charAt(0).toUpperCase() + k.slice(1)}: {(deskSnapshot.holdings.state as any)[k] ?? (k === 'status' ? 'idle' : 0)}
                      </span>
                    ))}
                    <span className="rounded-full border border-slate-700 px-2 py-1">Last run: {deskSnapshot.holdings.state.last_run_at || '—'}</span>
                  </div>
                  <div className="mt-4 space-y-2 max-h-72 overflow-y-auto pr-1">
                    {deskSnapshot.holdings.rows.map((row) => {
                      const action = String(row.decision?.action || 'HOLD').toUpperCase();
                      const actionClass =
                        action === 'BUY' ? 'border-emerald-400/40 text-emerald-200 bg-emerald-500/10'
                        : action === 'SELL' ? 'border-rose-400/40 text-rose-200 bg-rose-500/10'
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
                          <p className="mt-2 text-xs text-slate-300 line-clamp-2">{row.decision?.rationale || 'No daily verdict yet for this holding.'}</p>
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

      {/* Error */}
      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 p-4 text-rose-200 flex items-start gap-2">
          <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Consensus + Diagnostics row */}
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

          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
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
            <div className="rounded-lg border border-slate-700 bg-slate-800/80 p-3">
              <p className="text-xs text-slate-400">Sources Active</p>
              <p className="text-2xl font-bold text-white mt-1">{sourceVotes.length} / 8</p>
            </div>
          </div>

          {/* Weighted score bar */}
          <div className="mt-4">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>SELL</span>
              <span>NEUTRAL</span>
              <span>BUY</span>
            </div>
            <div className="relative h-3 rounded-full bg-slate-800 overflow-hidden">
              <div className="absolute inset-0 flex">
                <div className="w-1/2 bg-rose-500/20" />
                <div className="w-1/2 bg-emerald-500/20" />
              </div>
              <div
                className={`absolute top-0 h-full w-1 rounded-full transition-all duration-500 ${consensus.action === 'BUY' ? 'bg-emerald-400' : consensus.action === 'SELL' ? 'bg-rose-400' : 'bg-amber-400'}`}
                style={{ left: `${Math.max(2, Math.min(98, 50 + consensus.weightedScore * 50))}%` }}
              />
            </div>
          </div>

          {/* Per-source weight bars */}
          {sourceVotes.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {sourceVotes.map((v) => {
                const w = SOURCE_WEIGHTS[v.source] ?? 0.05;
                const barColor = v.action === 'BUY' ? 'bg-emerald-500' : v.action === 'SELL' ? 'bg-rose-500' : 'bg-amber-500';
                return (
                  <div key={v.source} className="flex items-center gap-3 text-xs">
                    <span className="w-32 text-slate-400 truncate">{v.source}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
                      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.round(v.confidence * 100)}%` }} />
                    </div>
                    <span className={`w-10 text-right font-semibold ${v.action === 'BUY' ? 'text-emerald-300' : v.action === 'SELL' ? 'text-rose-300' : 'text-amber-300'}`}>
                      {v.action}
                    </span>
                    <span className="w-8 text-right text-slate-500">{Math.round(w * 100)}%</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Strategy Diagnostics */}
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
              {strategySuggestion && (
                <p className="text-xs text-slate-500">
                  Recent signals: {strategySuggestion.recent_signal_count || 0} | Latest: {strategySuggestion.latest_strategy || 'N/A'}
                </p>
              )}
            </div>
          )}

          {/* Quant quick stats */}
          {quant && (
            <div className="mt-4 pt-4 border-t border-slate-700 space-y-1.5 text-xs">
              <p className="text-slate-400 font-semibold uppercase tracking-wide">Quant Signals</p>
              {[
                ['ORB', quant.orb_breakout || 'N/A'],
                ['VWAP', quant.price_vs_vwap || 'N/A'],
                ['RVOL', (quant.rvol || 0).toFixed(2)],
                ['Regime', quant.regime || 'N/A'],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between text-slate-300">
                  <span>{label}</span>
                  <span className="text-white font-semibold">{val}</span>
                </div>
              ))}
            </div>
          )}

          {/* Filing quick stats */}
          {filing && (
            <div className="mt-4 pt-4 border-t border-slate-700 space-y-1.5 text-xs">
              <p className="text-slate-400 font-semibold uppercase tracking-wide">Latest Filing</p>
              <div className="flex justify-between text-slate-300">
                <span>Sentiment</span>
                <span className={`font-semibold ${filing.sentiment === 'BULLISH' ? 'text-emerald-300' : filing.sentiment === 'BEARISH' ? 'text-rose-300' : 'text-amber-300'}`}>
                  {filing.sentiment || 'N/A'}
                </span>
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {(filing.signal_tags || []).map((tag) => (
                  <span key={tag} className="rounded-full border border-slate-600 bg-slate-800 px-2 py-0.5 text-slate-300">{tag}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Source Vote Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {sourceVotes.length === 0 && (
          <div className="col-span-full rounded-xl border border-slate-700 bg-slate-900/80 p-6 text-center text-slate-400">
            No signal sources loaded yet. Enter a symbol and click Run Reconciliation.
          </div>
        )}

        {sourceVotes.map((vote) => (
          <div key={vote.source} className="rounded-xl border border-slate-700 bg-slate-900/80 p-4 flex flex-col">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-white flex items-center gap-2">
                {vote.icon}
                {vote.source}
              </p>
              <span className={`inline-flex items-center gap-1 border rounded-full px-2.5 py-1 text-xs font-semibold ${actionPill(vote.action)}`}>
                {actionIcon(vote.action)}
                {vote.action}
              </span>
            </div>

            <div className="mt-3 flex items-end gap-2">
              <p className="text-2xl font-bold text-white">{Math.round(vote.confidence * 100)}%</p>
              <p className="text-xs text-slate-400 mb-1">confidence</p>
              <p className="text-xs text-slate-500 mb-1 ml-auto">wt {Math.round((SOURCE_WEIGHTS[vote.source] ?? 0.05) * 100)}%</p>
            </div>

            {vote.signalLabel === 'NO_TRADE' && (
              <p className="mt-1 text-xs text-amber-300">Model stance: NO_TRADE (abstain), shown as HOLD in consensus.</p>
            )}

            <p className="mt-3 text-sm text-slate-300 line-clamp-4 flex-1">{vote.detail}</p>
            {vote.meta && <p className="mt-2 text-xs text-slate-500">{vote.meta}</p>}
          </div>
        ))}
      </div>

      {/* Debate Transcript */}
      <div className="rounded-xl border border-slate-700 bg-slate-900/80 p-5">
        <div className="flex items-center justify-between">
          <h2 className="text-white font-semibold text-lg flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-violet-300" />
            Debate Output
          </h2>
          {debateRoundsUsed && (
            <span className="text-xs px-2.5 py-1 rounded-full bg-violet-500/20 border border-violet-500/40 text-violet-200">
              {debateRoundsUsed} rounds
            </span>
          )}
        </div>

        {debateTranscript.length === 0 ? (
          <p className="mt-3 text-sm text-slate-400">
            Debate transcript will appear here after you click Run Reconciliation and the job completes.
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
