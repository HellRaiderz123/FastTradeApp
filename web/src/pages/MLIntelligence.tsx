import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain, Layers, BarChart3, Activity, TrendingUp, TrendingDown,
  Target, Zap, RefreshCw, Play, AlertTriangle, CheckCircle2,
  ArrowUpRight, ArrowDownRight, Newspaper, GitBranch, Grid,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, AreaChart, Area, Cell, ScatterChart, Scatter, ZAxis,
  ComposedChart, Legend,
} from 'recharts';
import { mlAPI } from '../lib/api';
import { useToast } from '../components/Toast';

// ========================= TAB DEFINITIONS ==============================
type Tab = 'ensemble' | 'shap' | 'signal-backtest' | 'news-sentiment' | 'correlation' | 'walk-forward';

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'ensemble', label: 'Model Ensemble', icon: Layers },
  { id: 'shap', label: 'Feature Importance', icon: BarChart3 },
  { id: 'signal-backtest', label: 'Signal Backtest', icon: Target },
  { id: 'news-sentiment', label: 'News Sentiment', icon: Newspaper },
  { id: 'correlation', label: 'Correlation Matrix', icon: Grid },
  { id: 'walk-forward', label: 'Walk-Forward', icon: GitBranch },
];

// ========================= MAIN component ================================
const MLIntelligence: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('ensemble');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <Brain className="w-8 h-8 text-purple-400" />
            ML Intelligence
          </h1>
          <p className="text-slate-400 mt-1">Tier 3 — Ensemble, SHAP, Signal Backtest, Sentiment, Correlation, Walk-Forward</p>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-slate-900 p-1 rounded-xl overflow-x-auto">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? 'bg-purple-600 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div>
        {activeTab === 'ensemble' && <EnsembleTab />}
        {activeTab === 'shap' && <ShapTab />}
        {activeTab === 'signal-backtest' && <SignalBacktestTab />}
        {activeTab === 'news-sentiment' && <NewsSentimentTab />}
        {activeTab === 'correlation' && <CorrelationTab />}
        {activeTab === 'walk-forward' && <WalkForwardTab />}
      </div>
    </div>
  );
};

// ========================= SHARED =================================
export const Card: React.FC<{ title: string; children: React.ReactNode; className?: string }> = ({ title, children, className = '' }) => (
  <div className={`bg-slate-900 border border-slate-800 rounded-xl p-5 ${className}`}>
    <h3 className="text-white font-semibold mb-4">{title}</h3>
    {children}
  </div>
);

export const Metric: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color = 'text-white' }) => (
  <div className="bg-slate-800 rounded-lg p-3">
    <p className="text-slate-400 text-xs mb-1">{label}</p>
    <p className={`text-lg font-bold ${color}`}>{value}</p>
  </div>
);

export const LoadingSpinner: React.FC<{ text?: string }> = ({ text = 'Loading…' }) => (
  <div className="flex flex-col items-center justify-center py-16 gap-3">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500" />
    <p className="text-slate-400 text-sm">{text}</p>
  </div>
);

// ========================= #15  ENSEMBLE TAB =============================
export const EnsembleTab: React.FC = () => {
  const { showToast } = useToast();
  const [info, setInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [training, setTraining] = useState(false);
  const [compareSymbol, setCompareSymbol] = useState('RELIANCE');
  const [comparison, setComparison] = useState<any>(null);
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState('');

  const loadInfo = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mlAPI.getEnsembleInfo();
      setInfo(res.data);
    } catch { setInfo(null); }
    setLoading(false);
  }, []);

  useEffect(() => { loadInfo(); }, [loadInfo]);

  const handleTrain = async () => {
    setTraining(true);
    try {
      await mlAPI.trainEnsemble();
      await loadInfo();
    } catch (e: any) { showToast('error', 'Training Failed', e?.response?.data?.detail || 'Training failed'); }
    setTraining(false);
  };

  const handleCompare = async () => {
    setComparing(true);
    setCompareError('');
    setComparison(null);
    try {
      const res = await mlAPI.ensembleCompare(compareSymbol);
      setComparison(res.data);
    } catch (e: any) {
      setCompareError(e?.response?.data?.detail || e?.message || 'Compare failed — check backend logs');
    }
    setComparing(false);
  };

  if (loading) return <LoadingSpinner />;

  const perModel = info?.per_model_accuracy || {};
  const chartData = Object.entries(perModel).map(([name, acc]: any) => ({ name: name.toUpperCase(), accuracy: +(acc * 100).toFixed(1) }));
  if (info?.accuracy) chartData.push({ name: 'ENSEMBLE', accuracy: +(info.accuracy * 100).toFixed(1) });

  return (
    <div className="space-y-6">
      {/* Train button */}
      <div className="flex items-center gap-4">
        <button onClick={handleTrain} disabled={training} className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg transition-colors">
          {training ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {training ? 'Training Ensemble…' : 'Train Ensemble'}
        </button>
        {info?.status === 'ready' && <span className="text-green-400 text-sm flex items-center gap-1"><CheckCircle2 className="w-4 h-4" /> Ensemble trained</span>}
        {info?.status === 'not_trained' && <span className="text-amber-400 text-sm flex items-center gap-1"><AlertTriangle className="w-4 h-4" /> Not trained yet</span>}
      </div>

      {info?.status === 'ready' && (
        <>
          {/* Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Metric label="Accuracy" value={`${(info.accuracy * 100).toFixed(1)}%`} color="text-green-400" />
            <Metric label="Precision" value={`${(info.precision * 100).toFixed(1)}%`} color="text-blue-400" />
            <Metric label="Recall" value={`${(info.recall * 100).toFixed(1)}%`} color="text-cyan-400" />
            <Metric label="F1 Score" value={`${(info.f1_score * 100).toFixed(1)}%`} color="text-purple-400" />
            <Metric label="ROC AUC" value={`${(info.roc_auc * 100).toFixed(1)}%`} color="text-amber-400" />
          </div>

          {/* Per-model comparison chart */}
          <Card title="Per-Model Accuracy vs Ensemble">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" domain={[0, 100]} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }} />
                <Bar dataKey="accuracy" radius={[6, 6, 0, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={i === chartData.length - 1 ? '#a855f7' : '#3b82f6'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Compare single vs ensemble */}
          <Card title="Single vs Ensemble — Compare Prediction">
            <div className="flex items-center gap-3 mb-4">
              <input value={compareSymbol} onChange={(e) => setCompareSymbol(e.target.value.toUpperCase())}
                className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-40" placeholder="Symbol" />
              <button onClick={handleCompare} disabled={comparing} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2">
                {comparing && <RefreshCw className="w-4 h-4 animate-spin" />}
                {comparing ? 'Comparing…' : 'Compare'}
              </button>
            </div>
            {compareError && <p className="text-red-400 text-sm mb-3">{compareError}</p>}
            {comparison && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-800 rounded-lg p-4">
                  <p className="text-slate-400 text-xs mb-1">Single GBM</p>
                  <p className={`text-xl font-bold ${comparison.single_model?.signal === 'BULLISH' ? 'text-green-400' : comparison.single_model?.signal === 'BEARISH' ? 'text-red-400' : 'text-slate-400'}`}>
                    {comparison.single_model?.signal} ({comparison.single_model?.confidence}%)
                  </p>
                </div>
                <div className="bg-slate-800 rounded-lg p-4">
                  <p className="text-slate-400 text-xs mb-1">Ensemble (3-model)</p>
                  <p className={`text-xl font-bold ${comparison.ensemble_model?.signal === 'BULLISH' ? 'text-green-400' : comparison.ensemble_model?.signal === 'BEARISH' ? 'text-red-400' : 'text-slate-400'}`}>
                    {comparison.ensemble_model?.signal} ({comparison.ensemble_model?.confidence}%)
                  </p>
                </div>
                <div className="bg-slate-800 rounded-lg p-4">
                  <p className="text-slate-400 text-xs mb-1">Agreement</p>
                  <p className={`text-xl font-bold ${comparison.agreement ? 'text-green-400' : 'text-amber-400'}`}>
                    {comparison.agreement ? 'Yes ✓' : 'No ✗'}
                  </p>
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
};

// ========================= #16  SHAP TAB ==================================
export const ShapTab: React.FC = () => {
  const [globalData, setGlobalData] = useState<any>(null);
  const [symbolShap, setSymbolShap] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState('');
  const [symbol, setSymbol] = useState('RELIANCE');
  const [modelType, setModelType] = useState('single');

  const loadGlobal = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mlAPI.getGlobalShap(modelType);
      setGlobalData(res.data);
    } catch { setGlobalData(null); }
    setLoading(false);
  }, [modelType]);

  useEffect(() => { loadGlobal(); }, [loadGlobal]);

  const handleSymbolShap = async () => {
    setExplaining(true);
    setExplainError('');
    setSymbolShap(null);
    try {
      const res = await mlAPI.getSymbolShap(symbol, modelType);
      if (res.data?.error) {
        setExplainError(res.data.error);
      } else {
        setSymbolShap(res.data);
      }
    } catch (e: any) {
      setExplainError(e?.response?.data?.detail || e?.message || 'SHAP explain failed');
    }
    setExplaining(false);
  };

  if (loading) return <LoadingSpinner text="Computing SHAP values…" />;

  const features = (globalData?.features || []).slice(0, 15);
  const chartData = features.map((f: any) => ({ feature: f.feature, importance: +(f.importance * 100).toFixed(2) }));

  return (
    <div className="space-y-6">
      {/* Model type selector */}
      <div className="flex items-center gap-3">
        <label className="text-slate-400 text-sm">Model:</label>
        <select value={modelType} onChange={(e) => setModelType(e.target.value)} title="Model type"
          className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700">
          <option value="single">Single GBM</option>
          <option value="ensemble">Ensemble</option>
        </select>
        <button onClick={loadGlobal} title="Refresh SHAP" className="p-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {globalData?.error && <p className="text-amber-400">{globalData.error}</p>}

      {/* Global SHAP bar chart */}
      {chartData.length > 0 && (
        <Card title={`Global Feature Importance (${globalData?.sample_count || 0} samples)`}>
          <ResponsiveContainer width="100%" height={400}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 100 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis type="number" stroke="#94a3b8" />
              <YAxis type="category" dataKey="feature" stroke="#94a3b8" width={95} tick={{ fontSize: 12 }} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }} />
              <Bar dataKey="importance" fill="#a855f7" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Per-symbol SHAP waterfall */}
      <Card title="Per-Symbol SHAP Waterfall">
        <div className="flex items-center gap-3 mb-4">
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-40" placeholder="Symbol" />
          <button onClick={handleSymbolShap} disabled={explaining} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg transition-colors flex items-center gap-2">
            {explaining && <RefreshCw className="w-4 h-4 animate-spin" />}
            {explaining ? 'Computing…' : 'Explain'}
          </button>
        </div>
        {explainError && <p className="text-red-400 text-sm mb-3">{explainError}</p>}
        {symbolShap?.waterfall && (
          <>
            <p className="text-slate-400 text-sm mb-3">
              Prediction: <span className="text-white font-bold">{(symbolShap.prediction_prob_up * 100).toFixed(1)}% bullish</span>
              {' | '}Base value: {symbolShap.base_value?.toFixed(4)}
            </p>
            <ResponsiveContainer width="100%" height={350}>
              <BarChart data={symbolShap.waterfall.slice(0, 12)} layout="vertical" margin={{ left: 110 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" stroke="#94a3b8" />
                <YAxis type="category" dataKey="feature" stroke="#94a3b8" width={105} tick={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                  formatter={(val: any) => [Number(val).toFixed(4), 'SHAP']} />
                <Bar dataKey="shap_value" radius={[0, 4, 4, 0]}>
                  {symbolShap.waterfall.slice(0, 12).map((d: any, i: number) => (
                    <Cell key={i} fill={d.shap_value >= 0 ? '#10b981' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
        {explaining && <LoadingSpinner text="Computing SHAP values for this symbol…" />}
        {symbolShap?.error && <p className="text-amber-400 text-sm">{symbolShap.error}</p>}
      </Card>
    </div>
  );
};

// ========================= MODULE CACHE (survives navigation) ==============
const _resultCache: Record<string, any> = {};

// Polling hook — polls a job until completed/failed, restores latest on mount
export function useAsyncJob(jobType: string) {
  const [result, setResult] = useState<any>(_resultCache[jobType] || null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'pending' | 'running' | 'completed' | 'failed'>('idle');
  const [error, setError] = useState('');
  const intervalRef = React.useRef<ReturnType<typeof setInterval> | null>(null);

  // On mount: check for cached result, or fetch latest from backend
  useEffect(() => {
    if (_resultCache[jobType]) {
      setResult(_resultCache[jobType]);
      setStatus('completed');
      return;
    }
    // Check backend for latest (running or completed)
    mlAPI.getLatestJob(jobType).then(res => {
      const data = res.data;
      if (data?.status === 'completed' && data.result) {
        _resultCache[jobType] = data.result;
        setResult(data.result);
        setStatus('completed');
      } else if (data?.status === 'running' || data?.status === 'pending') {
        setJobId(data.job_id);
        setStatus(data.status as any);
      }
    }).catch(() => {});
  }, [jobType]);

  // Poll when we have a job_id
  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') {
      if (intervalRef.current) clearInterval(intervalRef.current);
      return;
    }
    intervalRef.current = setInterval(async () => {
      try {
        const res = await mlAPI.getJobStatus(jobId);
        const data = res.data;
        if (data.status === 'completed') {
          _resultCache[jobType] = data.result;
          setResult(data.result);
          setStatus('completed');
          setJobId(null);
        } else if (data.status === 'failed') {
          setError(data.error || 'Job failed');
          setStatus('failed');
          setJobId(null);
        } else {
          setStatus(data.status as any);
        }
      } catch { }
    }, 3000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [jobId, status, jobType]);

  const start = (startFn: () => Promise<any>) => {
    setError('');
    setResult(null);
    setStatus('pending');
    startFn().then(res => {
      setJobId(res.data.job_id);
    }).catch((e: any) => {
      setError(e?.response?.data?.detail || e?.message || 'Failed to start job');
      setStatus('failed');
    });
  };

  const isRunning = status === 'pending' || status === 'running';

  return { result, status, error, isRunning, start };
}

// ========================= #17  SIGNAL BACKTEST TAB =======================
export const SignalBacktestTab: React.FC = () => {
  const { result, status, error, isRunning, start } = useAsyncJob('signal-backtest');
  const [symbol, setSymbol] = useState('RELIANCE');
  const [horizon, setHorizon] = useState(5);
  const [modelType, setModelType] = useState('single');

  const run = () => {
    start(() => mlAPI.startBacktestAsync({ symbol, horizon, model_type: modelType }));
  };

  const equityCurve = (result?.equity_curve || []).map((v: number, i: number) => ({ i, equity: v }));
  const confBuckets = result?.confidence_buckets ? Object.entries(result.confidence_buckets).map(([k, v]: any) => ({ bucket: k, accuracy: v.accuracy, count: v.count })) : [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-40" placeholder="Symbol" />
        <select value={modelType} onChange={(e) => setModelType(e.target.value)} title="Model type"
          className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700">
          <option value="single">Single GBM</option>
          <option value="ensemble">Ensemble</option>
        </select>
        <div className="flex items-center gap-2">
          <label className="text-slate-400 text-sm">Horizon:</label>
          <input type="number" value={horizon} onChange={(e) => setHorizon(+e.target.value)} min={1} max={20} title="Horizon days"
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-20" />
        </div>
        <button onClick={run} disabled={isRunning}
          className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg transition-colors">
          {isRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {isRunning ? 'Running Backtest…' : 'Run Backtest'}
        </button>
      </div>

      {isRunning && (
        <div className="flex items-center gap-3 bg-slate-800 rounded-lg p-4 border border-purple-500/30">
          <RefreshCw className="w-5 h-5 animate-spin text-purple-400" />
          <div>
            <p className="text-white font-medium">Backtest is running in the background</p>
            <p className="text-slate-400 text-sm">You can navigate away — results will be here when you return.</p>
          </div>
        </div>
      )}

      {error && <p className="text-red-400">{error}</p>}
      {result?.error && <p className="text-red-400">{result.error}</p>}

      {result && !result.error && (
        <>
          {/* Quick metrics */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
            <Metric label="Total Signals" value={result.total_signals} />
            <Metric label="Bullish Accuracy" value={`${result.bullish_accuracy}%`} color="text-green-400" />
            <Metric label="Bearish Accuracy" value={`${result.bearish_accuracy}%`} color="text-red-400" />
            <Metric label="Overall Accuracy" value={`${result.overall_accuracy}%`} color="text-purple-400" />
            <Metric label="Profit Factor" value={result.profit_factor ?? 'N/A'} color="text-amber-400" />
            <Metric label="Avg Bullish Return" value={`${result.avg_forward_return_bullish}%`} color="text-green-400" />
          </div>

          {/* Equity curve */}
          {equityCurve.length > 0 && (
            <Card title="Simulated Equity Curve (10% position sizing)">
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={equityCurve}>
                  <defs>
                    <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="i" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }} />
                  <Area type="monotone" dataKey="equity" stroke="#a855f7" fill="url(#eqGrad)" />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Confidence buckets */}
          {confBuckets.length > 0 && (
            <Card title="Accuracy by Confidence Bucket">
              <ResponsiveContainer width="100%" height={220}>
                <ComposedChart data={confBuckets}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="bucket" stroke="#94a3b8" />
                  <YAxis yAxisId="acc" stroke="#94a3b8" domain={[0, 100]} />
                  <YAxis yAxisId="cnt" orientation="right" stroke="#6b7280" />
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }} />
                  <Bar yAxisId="cnt" dataKey="count" fill="#3b82f6" opacity={0.5} radius={[4, 4, 0, 0]} />
                  <Line yAxisId="acc" type="monotone" dataKey="accuracy" stroke="#a855f7" strokeWidth={2} dot />
                </ComposedChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Recent events table */}
          <Card title={`Recent Signal Events (last ${Math.min(result.events?.length || 0, 30)})`}>
            <div className="overflow-x-auto max-h-[300px] overflow-y-auto custom-scrollbar">
              <table className="w-full text-sm">
                <thead className="text-slate-400 border-b border-slate-700 sticky top-0 bg-slate-900">
                  <tr>
                    <th className="py-2 px-3 text-left">Time</th>
                    <th className="py-2 px-3 text-left">Signal</th>
                    <th className="py-2 px-3 text-right">Confidence</th>
                    <th className="py-2 px-3 text-right">Fwd Return</th>
                    <th className="py-2 px-3 text-center">Hit?</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.events || []).slice(-30).map((ev: any, i: number) => (
                    <tr key={i} className="border-b border-slate-800 hover:bg-slate-800/50">
                      <td className="py-1.5 px-3 text-slate-400 text-xs">{ev.timestamp}</td>
                      <td className={`py-1.5 px-3 font-medium ${ev.signal === 'BULLISH' ? 'text-green-400' : ev.signal === 'BEARISH' ? 'text-red-400' : 'text-slate-500'}`}>
                        {ev.signal}
                      </td>
                      <td className="py-1.5 px-3 text-right text-white">{ev.confidence}%</td>
                      <td className={`py-1.5 px-3 text-right font-mono ${(ev.forward_return_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {ev.forward_return_pct !== null ? `${ev.forward_return_pct}%` : '-'}
                      </td>
                      <td className="py-1.5 px-3 text-center">
                        {ev.hit === true && <CheckCircle2 className="w-4 h-4 text-green-400 inline" />}
                        {ev.hit === false && <AlertTriangle className="w-4 h-4 text-red-400 inline" />}
                        {ev.hit === null && <span className="text-slate-600">-</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
};

// ========================= #18  NEWS SENTIMENT TAB ========================
export const NewsSentimentTab: React.FC = () => {
  const [symbol, setSymbol] = useState('RELIANCE');
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [manualHeadlines, setManualHeadlines] = useState('');
  const [manualResult, setManualResult] = useState<any>(null);

  const fetchSignalWithNews = async () => {
    setLoading(true);
    try {
      const res = await mlAPI.getSignalWithNews(symbol);
      setResult(res.data);
    } catch { setResult(null); }
    setLoading(false);
  };

  const scoreManual = async () => {
    const lines = manualHeadlines.split('\n').filter(Boolean);
    if (!lines.length) return;
    try {
      const res = await mlAPI.scoreNewsSentiment(lines);
      setManualResult(res.data);
    } catch { }
  };

  return (
    <div className="space-y-6">
      {/* Auto: Signal + News */}
      <Card title="ML Signal Enriched with News Sentiment">
        <div className="flex items-center gap-3 mb-4">
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-40" placeholder="Symbol" />
          <button onClick={fetchSignalWithNews} disabled={loading}
            className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg disabled:opacity-50 transition-colors">
            {loading ? 'Loading…' : 'Get Signal + News'}
          </button>
        </div>
        {result && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-slate-400 text-xs mb-1">Signal</p>
              <p className={`text-2xl font-bold ${result.signal === 'BULLISH' ? 'text-green-400' : result.signal === 'BEARISH' ? 'text-red-400' : 'text-slate-400'}`}>
                {result.signal}
              </p>
              <p className="text-slate-500 text-xs mt-1">{result.reason}</p>
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-slate-400 text-xs mb-1">Confidence (sentiment-adjusted)</p>
              <p className="text-2xl font-bold text-white">{result.confidence}%</p>
              {result.sentiment_adjustment !== 0 && (
                <p className={`text-xs mt-1 ${result.sentiment_adjustment > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {result.sentiment_adjustment > 0 ? '+' : ''}{result.sentiment_adjustment}% adjustment
                </p>
              )}
            </div>
            <div className="bg-slate-800 rounded-lg p-4">
              <p className="text-slate-400 text-xs mb-1">News Sentiment</p>
              <p className={`text-2xl font-bold ${
                result.news_sentiment?.label === 'POSITIVE' ? 'text-green-400' :
                result.news_sentiment?.label === 'NEGATIVE' ? 'text-red-400' : 'text-slate-400'
              }`}>
                {result.news_sentiment?.label || 'N/A'}
              </p>
              <p className="text-slate-500 text-xs mt-1">{result.news_sentiment?.headline_count || 0} headlines analyzed</p>
            </div>
          </div>
        )}
      </Card>

      {/* Manual headline scorer */}
      <Card title="Manual Headline Scorer">
        <textarea
          value={manualHeadlines}
          onChange={(e) => setManualHeadlines(e.target.value)}
          className="w-full bg-slate-800 text-white p-3 rounded-lg border border-slate-700 min-h-[120px] font-mono text-sm"
          placeholder={"Enter headlines, one per line:\nReliance profit surges 20% in Q3\nNifty crashes below 20000\nTCS wins $500M deal from major bank"}
        />
        <button onClick={scoreManual} className="mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
          Score Headlines
        </button>
        {manualResult && (
          <div className="mt-4 space-y-3">
            <div className="flex gap-4">
              <Metric label="Composite Score" value={manualResult.aggregate?.composite_score?.toFixed(3)} color={manualResult.aggregate?.composite_score > 0 ? 'text-green-400' : manualResult.aggregate?.composite_score < 0 ? 'text-red-400' : 'text-slate-400'} />
              <Metric label="Label" value={manualResult.aggregate?.label || 'N/A'} color="text-purple-400" />
              <Metric label="Positive" value={manualResult.aggregate?.positive_count || 0} color="text-green-400" />
              <Metric label="Negative" value={manualResult.aggregate?.negative_count || 0} color="text-red-400" />
            </div>
            <div className="space-y-2">
              {(manualResult.headlines || []).map((h: any, i: number) => (
                <div key={i} className="flex items-center justify-between bg-slate-800 rounded px-3 py-2 text-sm">
                  <span className="text-slate-300 truncate mr-4">{h.headline}</span>
                  <span className={`font-bold min-w-[60px] text-right ${h.score > 0 ? 'text-green-400' : h.score < 0 ? 'text-red-400' : 'text-slate-500'}`}>
                    {h.score > 0 ? '+' : ''}{h.score}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
};

// ========================= #19  CORRELATION TAB ===========================
export const CorrelationTab: React.FC = () => {
  const [symbols, setSymbols] = useState('RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK');
  const [days, setDays] = useState(90);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [rollingA, setRollingA] = useState('RELIANCE');
  const [rollingB, setRollingB] = useState('TCS');
  const [rollingResult, setRollingResult] = useState<any>(null);

  const computeMatrix = async () => {
    setLoading(true);
    try {
      const syms = symbols.split(',').map(s => s.trim()).filter(Boolean);
      const res = await mlAPI.getCorrelationMatrix({ symbols: syms, days });
      setResult(res.data);
    } catch { setResult(null); }
    setLoading(false);
  };

  const computeRolling = async () => {
    try {
      const res = await mlAPI.getRollingCorrelation({ symbol_a: rollingA, symbol_b: rollingB, days: 252 });
      setRollingResult(res.data);
    } catch { setRollingResult(null); }
  };

  // Color scale for heatmap
  const corrColor = (val: number) => {
    if (val >= 0.7) return '#10b981';
    if (val >= 0.3) return '#34d399';
    if (val >= -0.3) return '#6b7280';
    if (val >= -0.7) return '#f87171';
    return '#ef4444';
  };

  const matrixSyms = result?.symbols || [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <input value={symbols} onChange={(e) => setSymbols(e.target.value.toUpperCase())}
          className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 flex-1 min-w-[300px]" placeholder="RELIANCE,TCS,INFY,..." />
        <div className="flex items-center gap-2">
          <label className="text-slate-400 text-sm">Days:</label>
          <input type="number" value={days} onChange={(e) => setDays(+e.target.value)} title="Days"
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-20" />
        </div>
        <button onClick={computeMatrix} disabled={loading}
          className="px-5 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg transition-colors">
          {loading ? 'Computing…' : 'Compute Matrix'}
        </button>
      </div>

      {result?.error && <p className="text-amber-400">{result.error}</p>}

      {matrixSyms.length > 0 && (
        <>
          {/* Heatmap grid */}
          <Card title={`Correlation Heatmap (${result.data_points} data points, ${result.method})`}>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr>
                    <th className="p-2 text-slate-400" />
                    {matrixSyms.map((s: string) => (
                      <th key={s} className="p-2 text-white text-xs font-medium">{s}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrixSyms.map((rowSym: string) => (
                    <tr key={rowSym}>
                      <td className="p-2 text-white text-xs font-medium">{rowSym}</td>
                      {matrixSyms.map((colSym: string) => {
                        const val = result.matrix?.[rowSym]?.[colSym] ?? 0;
                        return (
                          <td key={colSym} className="p-1">
                            <div
                              className="w-14 h-10 rounded flex items-center justify-center text-xs font-bold text-white"
                              style={{ backgroundColor: corrColor(val), opacity: 0.7 + Math.abs(val) * 0.3 }}
                            >{val.toFixed(2)}</div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Risk metrics */}
          {result.risk_metrics && (
            <div className="grid grid-cols-3 gap-4">
              <Metric label="Avg Correlation" value={result.risk_metrics.average_correlation?.toFixed(4)} color={result.risk_metrics.average_correlation > 0.5 ? 'text-amber-400' : 'text-green-400'} />
              <Metric label="Effective Dimensionality" value={result.risk_metrics.effective_dimensionality?.toFixed(2)} color="text-blue-400" />
              <Metric label="Diversification Ratio" value={`${(result.risk_metrics.diversification_ratio * 100).toFixed(1)}%`} color="text-purple-400" />
            </div>
          )}

          {/* Highly correlated pairs */}
          {result.high_correlation_pairs?.length > 0 && (
            <Card title="Highly Correlated Pairs (|r| ≥ 0.7)">
              <div className="space-y-2">
                {result.high_correlation_pairs.map((p: any, i: number) => (
                  <div key={i} className="flex items-center justify-between bg-slate-800 rounded-lg px-4 py-2">
                    <span className="text-white font-medium">{p.pair.join(' ↔ ')}</span>
                    <span className={`font-bold ${p.correlation > 0 ? 'text-green-400' : 'text-red-400'}`}>{p.correlation.toFixed(4)}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      {/* Rolling correlation */}
      <Card title="Rolling Pairwise Correlation">
        <div className="flex items-center gap-3 mb-4">
          <input value={rollingA} onChange={(e) => setRollingA(e.target.value.toUpperCase())}
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-32" placeholder="Symbol A" />
          <span className="text-slate-500">↔</span>
          <input value={rollingB} onChange={(e) => setRollingB(e.target.value.toUpperCase())}
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-32" placeholder="Symbol B" />
          <button onClick={computeRolling} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">Compute</button>
        </div>
        {rollingResult?.series && (
          <>
            <p className="text-slate-400 text-sm mb-2">Current: <span className="text-white font-bold">{rollingResult.current_correlation}</span> | Avg: {rollingResult.avg_correlation}</p>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={rollingResult.series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 10 }} />
                <YAxis stroke="#94a3b8" domain={[-1, 1]} />
                <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }} />
                <Line type="monotone" dataKey="correlation" stroke="#a855f7" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </>
        )}
        {rollingResult?.error && <p className="text-amber-400 text-sm">{rollingResult.error}</p>}
      </Card>
    </div>
  );
};

// ========================= #20  WALK-FORWARD TAB ==========================
export const WalkForwardTab: React.FC = () => {
  const { result, status, error, isRunning, start } = useAsyncJob('walk-forward');
  const [modelName, setModelName] = useState('gbm');
  const [optimize, setOptimize] = useState(false);
  const [minTrain, setMinTrain] = useState(500);
  const [testSize, setTestSize] = useState(100);
  const [step, setStep] = useState(100);

  const run = () => {
    start(() => mlAPI.startWalkForwardAsync({
      model_name: modelName, min_train: minTrain,
      test_size: testSize, step, optimize,
    }));
  };

  const foldSeries = result?.fold_accuracy_series || [];

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <select value={modelName} onChange={(e) => setModelName(e.target.value)} title="Model"
          className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700">
          <option value="gbm">GradientBoosting</option>
          <option value="rf">RandomForest</option>
          <option value="xgb">XGBoost</option>
        </select>
        <div className="flex items-center gap-2">
          <label className="text-slate-400 text-sm">Min Train:</label>
          <input type="number" value={minTrain} onChange={(e) => setMinTrain(+e.target.value)} title="Minimum training rows"
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-24" />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-slate-400 text-sm">Test:</label>
          <input type="number" value={testSize} onChange={(e) => setTestSize(+e.target.value)} title="Test size"
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-20" />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-slate-400 text-sm">Step:</label>
          <input type="number" value={step} onChange={(e) => setStep(+e.target.value)} title="Step size"
            className="bg-slate-800 text-white px-3 py-2 rounded-lg border border-slate-700 w-20" />
        </div>
        <label className="flex items-center gap-2 text-slate-400 text-sm cursor-pointer">
          <input type="checkbox" checked={optimize} onChange={(e) => setOptimize(e.target.checked)}
            className="rounded bg-slate-800 border-slate-600" />
          Optuna Tuning
        </label>
        <button onClick={run} disabled={isRunning}
          className="flex items-center gap-2 px-5 py-2.5 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg transition-colors">
          {isRunning ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {isRunning ? 'Running…' : 'Run Walk-Forward'}
        </button>
      </div>

      {isRunning && (
        <div className="flex items-center gap-3 bg-slate-800 rounded-lg p-4 border border-purple-500/30">
          <RefreshCw className="w-5 h-5 animate-spin text-purple-400" />
          <div>
            <p className="text-white font-medium">Walk-forward is running in the background</p>
            <p className="text-slate-400 text-sm">You can navigate away — results will be here when you return.</p>
          </div>
        </div>
      )}

      {error && <p className="text-red-400">{error}</p>}
      {result?.error && <p className="text-red-400">{result.error}</p>}

      {result && !result.error && (
        <>
          {/* Aggregate OOS metrics */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Metric label="OOS Accuracy" value={`${(result.aggregate_oos?.accuracy * 100).toFixed(1)}%`} color="text-green-400" />
            <Metric label="OOS Precision" value={`${(result.aggregate_oos?.precision * 100).toFixed(1)}%`} color="text-blue-400" />
            <Metric label="OOS Recall" value={`${(result.aggregate_oos?.recall * 100).toFixed(1)}%`} color="text-cyan-400" />
            <Metric label="OOS F1" value={`${(result.aggregate_oos?.f1_score * 100).toFixed(1)}%`} color="text-purple-400" />
            <Metric label="OOS ROC AUC" value={`${(result.aggregate_oos?.roc_auc * 100).toFixed(1)}%`} color="text-amber-400" />
          </div>

          {/* Stability */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Metric label="Accuracy Mean ± Std" value={`${(result.stability?.accuracy_mean * 100).toFixed(1)}% ± ${(result.stability?.accuracy_std * 100).toFixed(1)}%`} />
            <Metric label="F1 Mean ± Std" value={`${(result.stability?.f1_mean * 100).toFixed(1)}% ± ${(result.stability?.f1_std * 100).toFixed(1)}%`} />
            <Metric label="Best Fold" value={`${(result.stability?.best_fold_accuracy * 100).toFixed(1)}%`} color="text-green-400" />
            <Metric label="Worst Fold" value={`${(result.stability?.worst_fold_accuracy * 100).toFixed(1)}%`} color="text-red-400" />
          </div>

          {/* Fold accuracy chart */}
          {foldSeries.length > 0 && (
            <Card title="Per-Fold Accuracy & F1 Over Time">
              <ResponsiveContainer width="100%" height={280}>
                <ComposedChart data={foldSeries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="fold" stroke="#94a3b8" label={{ value: 'Fold', position: 'insideBottom', offset: -5 }} />
                  <YAxis stroke="#94a3b8" domain={[0, 1]} />
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }}
                    formatter={(val: any) => `${(val * 100).toFixed(1)}%`} />
                  <Legend />
                  <Bar dataKey="accuracy" fill="#3b82f6" opacity={0.6} name="Accuracy" radius={[4, 4, 0, 0]} />
                  <Line type="monotone" dataKey="f1" stroke="#a855f7" strokeWidth={2} name="F1 Score" dot />
                </ComposedChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Fold details table */}
          <Card title="Fold Details">
            <div className="overflow-x-auto max-h-[300px] overflow-y-auto custom-scrollbar">
              <table className="w-full text-sm">
                <thead className="text-slate-400 border-b border-slate-700 sticky top-0 bg-slate-900">
                  <tr>
                    <th className="py-2 px-3 text-left">Fold</th>
                    <th className="py-2 px-3 text-right">Train</th>
                    <th className="py-2 px-3 text-right">Test</th>
                    <th className="py-2 px-3 text-right">Accuracy</th>
                    <th className="py-2 px-3 text-right">Precision</th>
                    <th className="py-2 px-3 text-right">Recall</th>
                    <th className="py-2 px-3 text-right">F1</th>
                    <th className="py-2 px-3 text-right">AUC</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.folds || []).map((f: any) => (
                    <tr key={f.fold} className="border-b border-slate-800 hover:bg-slate-800/50">
                      <td className="py-1.5 px-3 text-white">{f.fold}</td>
                      <td className="py-1.5 px-3 text-right text-slate-400">{f.train_rows}</td>
                      <td className="py-1.5 px-3 text-right text-slate-400">{f.test_rows}</td>
                      <td className="py-1.5 px-3 text-right text-green-400">{(f.accuracy * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-3 text-right text-blue-400">{(f.precision * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-3 text-right text-cyan-400">{(f.recall * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-3 text-right text-purple-400">{(f.f1_score * 100).toFixed(1)}%</td>
                      <td className="py-1.5 px-3 text-right text-amber-400">{(f.roc_auc * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
};

export default MLIntelligence;
