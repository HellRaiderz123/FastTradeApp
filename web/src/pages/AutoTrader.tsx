import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Bot, Play, Square, Pause, RefreshCw, Settings2, Activity,
  TrendingUp, TrendingDown, AlertTriangle, CheckCircle, XCircle,
  Clock, Zap, Shield, Eye, DollarSign, BarChart3, Trash2,
  ChevronDown, ChevronUp, Info, ArrowUpDown, Brain
} from 'lucide-react';
import { autoTraderAPI } from '../lib/api';

// ─── Types ──────────────────────────────────────────────────────────

interface AutoTraderConfig {
  id: number;
  underlyings: string[];
  capital: number;
  lots: number;
  risk_mode: string;
  min_confidence: number;
  max_open_positions: number;
  max_daily_loss: number;
  default_tp: number | null;
  default_sl: number | null;
  trailing_sl_pct: number;
  mode: string;
  enabled: boolean;
  auto_exit_on_reversal: boolean;
  auto_hedge_on_reversal: boolean;
  reversal_confidence_threshold: number;
  scan_interval_sec: number;
  market_hours_only: boolean;
  entry_start_time: string;
  entry_end_time: string;
  use_ai_gate: boolean;
  ai_gate_min_confidence: number;
  trade_stocks: boolean;
  stock_symbols: string[];
  status: string;
  last_scan_at: string | null;
  error_message: string | null;
  daily_pnl: number;
  daily_trades: number;
}

interface AutoTraderStatus {
  status: string;
  mode: string;
  enabled: boolean;
  last_scan_at: string | null;
  error_message: string | null;
  daily_pnl: number;
  daily_trades: number;
  open_positions: number;
  max_positions: number;
  today_entries: number;
  today_exits: number;
  underlyings: string[];
  capital: number;
  scan_interval_sec: number;
  entry_start_time: string;
  entry_end_time: string;
}

interface LogEntry {
  id: number;
  action: string;
  underlying: string | null;
  strategy: string | null;
  reason: string | null;
  details: Record<string, any> | null;
  intent_id: string | null;
  run_id: number | null;
  pnl_impact: number | null;
  severity: string;
  created_at: string;
}

// ─── Constants ──────────────────────────────────────────────────────

const UNDERLYING_OPTIONS = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];
const RISK_MODES = ['CONSERVATIVE', 'BALANCED', 'AGGRESSIVE'];
const TRADE_MODES = [
  { value: 'PAPER', label: 'Paper Trade', color: 'text-green-400', bg: 'bg-green-500/20', border: 'border-green-500/30' },
  { value: 'DRY_RUN', label: 'Dry Run', color: 'text-yellow-400', bg: 'bg-yellow-500/20', border: 'border-yellow-500/30' },
  { value: 'LIVE', label: 'Live Trading', color: 'text-red-400', bg: 'bg-red-500/20', border: 'border-red-500/30' },
];

const ACTION_COLORS: Record<string, string> = {
  ENTRY: 'text-green-400',
  EXIT: 'text-red-400',
  REVERSAL_EXIT: 'text-orange-400',
  HEDGE: 'text-blue-400',
  SCAN: 'text-slate-400',
  SKIP: 'text-yellow-400',
  ERROR: 'text-red-500',
  START: 'text-green-300',
  STOP: 'text-slate-300',
};

const SEVERITY_BADGES: Record<string, string> = {
  SUCCESS: 'bg-green-500/20 text-green-400 border-green-500/30',
  INFO: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  WARNING: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  ERROR: 'bg-red-500/20 text-red-400 border-red-500/30',
};

// ─── Main Component ─────────────────────────────────────────────────

const AutoTrader: React.FC = () => {
  const [config, setConfig] = useState<AutoTraderConfig | null>(null);
  const [status, setStatus] = useState<AutoTraderStatus | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'config' | 'logs'>('dashboard');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [logFilter, setLogFilter] = useState<string>('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Data fetching ─────────────────────────────────────────────
  const fetchAll = useCallback(async () => {
    try {
      const [cfgRes, statusRes, logsRes] = await Promise.all([
        autoTraderAPI.getConfig(),
        autoTraderAPI.getStatus(),
        autoTraderAPI.getLogs({ limit: 100 }),
      ]);
      setConfig(cfgRes.data || cfgRes);
      setStatus(statusRes.data || statusRes);
      setLogs((logsRes.data || logsRes).logs || []);
    } catch (err) {
      console.error('Auto-trader fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    pollRef.current = setInterval(fetchAll, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchAll]);

  // ── Actions ───────────────────────────────────────────────────
  const handleStart = async () => {
    setActionLoading(true);
    try {
      await autoTraderAPI.start();
      await fetchAll();
    } catch (err) { console.error(err); }
    setActionLoading(false);
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      await autoTraderAPI.stop();
      await fetchAll();
    } catch (err) { console.error(err); }
    setActionLoading(false);
  };

  const handlePause = async () => {
    setActionLoading(true);
    try {
      await autoTraderAPI.pause();
      await fetchAll();
    } catch (err) { console.error(err); }
    setActionLoading(false);
  };

  const handleResetDaily = async () => {
    try {
      await autoTraderAPI.resetDaily();
      await fetchAll();
    } catch (err) { console.error(err); }
  };

  const handleClearLogs = async () => {
    try {
      await autoTraderAPI.clearLogs();
      setLogs([]);
    } catch (err) { console.error(err); }
  };

  const handleConfigUpdate = async (updates: Record<string, any>) => {
    try {
      await autoTraderAPI.updateConfig(updates);
      await fetchAll();
    } catch (err) { console.error(err); }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  const isRunning = status?.status === 'RUNNING';
  const isPaused = status?.status === 'PAUSED';
  const isError = status?.status === 'ERROR';
  const modeInfo = TRADE_MODES.find(m => m.value === config?.mode) || TRADE_MODES[0];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-blue-600 rounded-xl flex items-center justify-center">
            <Bot className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Auto Trader</h1>
            <p className="text-sm text-slate-400">
              AI-powered automated trading with TA signals
            </p>
          </div>
        </div>

        {/* Control buttons */}
        <div className="flex items-center gap-3">
          {/* Mode badge */}
          <span className={`px-3 py-1.5 rounded-full text-xs font-bold border ${modeInfo.bg} ${modeInfo.color} ${modeInfo.border}`}>
            {modeInfo.label}
          </span>

          {/* Status indicator */}
          <span className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold ${
            isRunning ? 'bg-green-500/20 text-green-400 border border-green-500/30' :
            isPaused ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
            isError ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
            'bg-slate-500/20 text-slate-400 border border-slate-500/30'
          }`}>
            <span className={`w-2 h-2 rounded-full ${
              isRunning ? 'bg-green-400 animate-pulse' :
              isPaused ? 'bg-yellow-400' :
              isError ? 'bg-red-400' : 'bg-slate-400'
            }`} />
            {status?.status || 'STOPPED'}
          </span>

          {!isRunning && !isPaused ? (
            <button
              onClick={handleStart}
              disabled={actionLoading}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium transition disabled:opacity-50"
            >
              <Play className="w-4 h-4" /> Start
            </button>
          ) : (
            <>
              {isRunning && (
                <button
                  onClick={handlePause}
                  disabled={actionLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white rounded-lg font-medium transition disabled:opacity-50"
                >
                  <Pause className="w-4 h-4" /> Pause
                </button>
              )}
              <button
                onClick={handleStop}
                disabled={actionLoading}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg font-medium transition disabled:opacity-50"
              >
                <Square className="w-4 h-4" /> Stop
              </button>
            </>
          )}
        </div>
      </div>

      {/* Error banner */}
      {isError && status?.error_message && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-red-400 font-medium">Engine Error</p>
            <p className="text-red-300/80 text-sm mt-1">{status.error_message}</p>
          </div>
        </div>
      )}

      {/* ── Tabs ───────────────────────────────────────────────── */}
      <div className="flex gap-1 bg-slate-900/50 p-1 rounded-xl border border-slate-800">
        {(['dashboard', 'config', 'logs'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition capitalize ${
              activeTab === tab
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            {tab === 'dashboard' && <Activity className="w-4 h-4 inline-block mr-2" />}
            {tab === 'config' && <Settings2 className="w-4 h-4 inline-block mr-2" />}
            {tab === 'logs' && <BarChart3 className="w-4 h-4 inline-block mr-2" />}
            {tab}
          </button>
        ))}
      </div>

      {/* ── Dashboard Tab ──────────────────────────────────────── */}
      {activeTab === 'dashboard' && status && (
        <DashboardView
          status={status}
          config={config}
          logs={logs}
          onResetDaily={handleResetDaily}
        />
      )}

      {/* ── Config Tab ─────────────────────────────────────────── */}
      {activeTab === 'config' && config && (
        <ConfigPanel
          config={config}
          onUpdate={handleConfigUpdate}
          isRunning={isRunning}
        />
      )}

      {/* ── Logs Tab ───────────────────────────────────────────── */}
      {activeTab === 'logs' && (
        <LogsPanel
          logs={logs}
          filter={logFilter}
          onFilterChange={setLogFilter}
          onClear={handleClearLogs}
        />
      )}
    </div>
  );
};

// ─── Dashboard Sub-component ────────────────────────────────────────

const DashboardView: React.FC<{
  status: AutoTraderStatus;
  config: AutoTraderConfig | null;
  logs: LogEntry[];
  onResetDaily: () => void;
}> = ({ status, config, logs, onResetDaily }) => {
  const recentLogs = logs.slice(0, 8);
  const pnlPositive = (status.daily_pnl || 0) >= 0;

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Daily P&L"
          value={`₹${(status.daily_pnl || 0).toFixed(0)}`}
          icon={pnlPositive ? TrendingUp : TrendingDown}
          color={pnlPositive ? 'text-green-400' : 'text-red-400'}
          bg={pnlPositive ? 'bg-green-500/10' : 'bg-red-500/10'}
        />
        <StatCard
          label="Open Positions"
          value={`${status.open_positions} / ${status.max_positions}`}
          icon={Zap}
          color="text-blue-400"
          bg="bg-blue-500/10"
        />
        <StatCard
          label="Today's Trades"
          value={`${status.today_entries} entries, ${status.today_exits} exits`}
          icon={Activity}
          color="text-purple-400"
          bg="bg-purple-500/10"
        />
        <StatCard
          label="Capital"
          value={`₹${((status.capital || 0) / 1000).toFixed(0)}K`}
          icon={DollarSign}
          color="text-amber-400"
          bg="bg-amber-500/10"
        />
      </div>

      {/* Active underlyings */}
      <div className="card-glass p-5 rounded-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Eye className="w-4 h-4 text-slate-400" />
            Monitoring
          </h3>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Clock className="w-3.5 h-3.5" />
            {status.last_scan_at
              ? `Last scan: ${new Date(status.last_scan_at).toLocaleTimeString()}`
              : 'No scan yet'
            }
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {(status.underlyings || []).map((u) => (
            <span key={u} className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white font-medium">
              {u}
            </span>
          ))}
        </div>
        <div className="mt-3 text-xs text-slate-500 space-y-1">
          <div>
            Scanning every {status.scan_interval_sec}s &middot; {config?.market_hours_only ? 'Market hours only' : 'All hours'}
          </div>
          <div>
            Fresh entry window: {config?.entry_start_time || '10:00'} - {config?.entry_end_time || '15:15'} IST
          </div>
        </div>
      </div>

      {/* Quick Config Overview */}
      {config && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MiniStat label="Risk Mode" value={config.risk_mode} />
          <MiniStat label="Min Confidence" value={`${config.min_confidence}%`} />
          <MiniStat label="Max Daily Loss" value={`₹${config.max_daily_loss}`} />
          <MiniStat label="Reversal Action" value={
            config.auto_exit_on_reversal ? 'Auto Exit' :
            config.auto_hedge_on_reversal ? 'Auto Hedge' : 'Manual'
          } />
        </div>
      )}

      {/* Per-underlying performance breakdown (Tier 2) */}
      {config && (status.underlyings || []).length > 0 && (
        <UnderlyingBreakdown logs={logs} underlyings={status.underlyings} />
      )}

      {/* Recent Activity */}
      <div className="card-glass p-5 rounded-xl">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-white font-semibold">Recent Activity</h3>
          <button onClick={onResetDaily} className="text-xs text-slate-400 hover:text-white transition">
            Reset Daily
          </button>
        </div>
        {recentLogs.length === 0 ? (
          <p className="text-slate-500 text-sm py-4 text-center">No activity yet. Start the auto-trader to begin.</p>
        ) : (
          <div className="space-y-2">
            {recentLogs.map((log) => (
              <LogRow key={log.id} log={log} compact />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

// ─── Config Panel ───────────────────────────────────────────────────

const ConfigPanel: React.FC<{
  config: AutoTraderConfig;
  onUpdate: (data: Record<string, any>) => void;
  isRunning: boolean;
}> = ({ config, onUpdate, isRunning }) => {
  const [form, setForm] = useState({ ...config });
  const [dirty, setDirty] = useState(false);

  const update = (key: string, value: any) => {
    setForm(prev => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const save = () => {
    const diff: Record<string, any> = {};
    for (const key of Object.keys(form) as (keyof typeof form)[]) {
      if (JSON.stringify(form[key]) !== JSON.stringify(config[key])) {
        diff[key] = form[key];
      }
    }
    if (Object.keys(diff).length) {
      onUpdate(diff);
      setDirty(false);
    }
  };

  return (
    <div className="space-y-6">
      {isRunning && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-3 flex items-center gap-2 text-sm text-yellow-400">
          <AlertTriangle className="w-4 h-4" />
          Engine is running. Changes apply on the next scan cycle.
        </div>
      )}

      {/* Trading Mode */}
      <Section title="Trading Mode" icon={Shield}>
        <div className="grid grid-cols-3 gap-3">
          {TRADE_MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => update('mode', m.value)}
              className={`p-4 rounded-xl border-2 transition text-center ${
                form.mode === m.value
                  ? `${m.bg} ${m.border} ${m.color}`
                  : 'border-slate-700 text-slate-400 hover:border-slate-600'
              }`}
            >
              <p className="font-bold text-sm">{m.label}</p>
              <p className="text-xs mt-1 opacity-60">
                {m.value === 'PAPER' && 'Simulated with live LTP'}
                {m.value === 'DRY_RUN' && 'Zerodha API, no real orders'}
                {m.value === 'LIVE' && 'Real money trades'}
              </p>
            </button>
          ))}
        </div>
        {form.mode === 'LIVE' && (
          <div className="mt-3 bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-sm text-red-400 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            LIVE mode will place real orders on Zerodha. Use with extreme caution.
          </div>
        )}
      </Section>

      {/* Underlyings */}
      <Section title="Instruments" icon={BarChart3}>
        <div className="flex gap-2 flex-wrap">
          {UNDERLYING_OPTIONS.map((u) => {
            const selected = (form.underlyings || []).includes(u);
            return (
              <button
                key={u}
                onClick={() => {
                  const current = form.underlyings || [];
                  update('underlyings', selected
                    ? current.filter((x: string) => x !== u)
                    : [...current, u]
                  );
                }}
                className={`px-4 py-2 rounded-lg border transition font-medium text-sm ${
                  selected
                    ? 'bg-blue-500/20 border-blue-500/40 text-blue-400'
                    : 'border-slate-700 text-slate-400 hover:border-slate-500'
                }`}
              >
                {u}
              </button>
            );
          })}
        </div>
      </Section>

      {/* Capital & Position */}
      <Section title="Capital & Sizing" icon={DollarSign}>
        <div className="grid grid-cols-3 gap-4">
          <InputField label="Capital (₹)" type="number" value={form.capital}
            onChange={(v) => update('capital', Number(v))} />
          <InputField label="Lots" type="number" value={form.lots}
            onChange={(v) => update('lots', Number(v))} />
          <InputField label="Max Open Positions" type="number" value={form.max_open_positions}
            onChange={(v) => update('max_open_positions', Number(v))} />
        </div>
      </Section>

      {/* Risk */}
      <Section title="Risk Management" icon={Shield}>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Risk Mode</label>
            <select
              value={form.risk_mode}
              onChange={(e) => update('risk_mode', e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm"
            >
              {RISK_MODES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <InputField label="Min Confidence (%)" type="number" value={form.min_confidence}
            onChange={(v) => update('min_confidence', Number(v))} />
          <InputField label="Max Daily Loss (₹)" type="number" value={form.max_daily_loss}
            onChange={(v) => update('max_daily_loss', Number(v))} />
          <InputField label="Scan Interval (sec)" type="number" value={form.scan_interval_sec}
            onChange={(v) => update('scan_interval_sec', Number(v))} />
        </div>
      </Section>

      {/* SL / TP */}
      <Section title="Stop Loss & Take Profit" icon={ArrowUpDown}>
        <div className="grid grid-cols-3 gap-4">
          <InputField label="Default TP (₹, 0=auto)" type="number" value={form.default_tp || 0}
            onChange={(v) => update('default_tp', Number(v))} />
          <InputField label="Default SL (₹, 0=auto)" type="number" value={form.default_sl || 0}
            onChange={(v) => update('default_sl', Number(v))} />
          <InputField label="Trailing SL (%)" type="number" value={form.trailing_sl_pct}
            onChange={(v) => update('trailing_sl_pct', Number(v))} />
        </div>
        <p className="text-xs text-slate-500 mt-2">
          Set to 0 for auto-calculated values based on risk mode and capital.
        </p>
      </Section>

      {/* AI Gate */}
      <Section title="AI Pipeline Gate" icon={Brain}>
        <p className="text-xs text-slate-400 mb-3">
          Require the 9-agent AI analysis pipeline to approve BUY/SELL before the auto-trader enters a position.
        </p>
        <ToggleField label="Enable AI Gate" checked={form.use_ai_gate ?? false}
          onChange={(v) => update('use_ai_gate', v)}
          description="Block entries unless AI pipeline confidence meets threshold" />
        {form.use_ai_gate && (
          <div className="mt-3">
            <InputField label="Min AI Confidence (0.0 – 1.0)" type="number" value={form.ai_gate_min_confidence ?? 0.65}
              onChange={(v) => update('ai_gate_min_confidence', Number(v))} />
            <p className="text-xs text-slate-500 mt-1">Entries blocked unless AI confidence ≥ this value. Recommended: 0.65</p>
          </div>
        )}
      </Section>

      {/* Stock Universe */}
      <Section title="Stock Universe" icon={BarChart3}>
        <ToggleField label="Scan Stocks" checked={form.trade_stocks ?? false}
          onChange={(v) => update('trade_stocks', v)}
          description="Also scan individual stocks using momentum strategy" />
        {form.trade_stocks && (
          <div className="mt-3">
            <label className="text-xs text-slate-400 mb-1 block">Stock Symbols (comma-separated)</label>
            <input
              type="text"
              value={(form.stock_symbols || []).join(', ')}
              onChange={(e) => update('stock_symbols', e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean))}
              placeholder="RELIANCE, TCS, INFY, HDFC"
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none transition"
            />
          </div>
        )}
      </Section>

      {/* Reversal handling */}
      <Section title="TA Reversal Handling" icon={AlertTriangle}>
        <p className="text-xs text-slate-400 mb-3">
          What happens when the TA engine signals a reversal against your open position?
        </p>
        <div className="grid grid-cols-2 gap-4 mb-4">
          <ToggleField label="Auto-Exit on Reversal" checked={form.auto_exit_on_reversal}
            onChange={(v) => update('auto_exit_on_reversal', v)}
            description="Exit position when TA flips against it" />
          <ToggleField label="Auto-Hedge on Reversal" checked={form.auto_hedge_on_reversal}
            onChange={(v) => update('auto_hedge_on_reversal', v)}
            description="Open opposite position instead of exiting" />
        </div>
        <InputField label="Reversal Confidence Threshold (%)" type="number"
          value={form.reversal_confidence_threshold}
          onChange={(v) => update('reversal_confidence_threshold', Number(v))} />
      </Section>

      {/* Schedule */}
      <Section title="Schedule" icon={Clock}>
        <ToggleField label="Market Hours Only" checked={form.market_hours_only}
          onChange={(v) => update('market_hours_only', v)}
          description="Only scan and manage positions during 9:15 AM - 3:15 PM IST" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <InputField label="Fresh Entry Start (IST)" type="time" value={form.entry_start_time || '10:00'}
            onChange={(v) => update('entry_start_time', v)} />
          <InputField label="Fresh Entry End (IST)" type="time" value={form.entry_end_time || '15:15'}
            onChange={(v) => update('entry_end_time', v)} />
        </div>
        <p className="text-xs text-slate-500">
          New positions will only be opened inside this window. Default start is <strong className="text-slate-300">10:00 AM</strong> for fresh entries.
        </p>
      </Section>

      {/* Save button */}
      {dirty && (
        <div className="flex justify-end">
          <button
            onClick={save}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition flex items-center gap-2"
          >
            <CheckCircle className="w-4 h-4" /> Save Configuration
          </button>
        </div>
      )}
    </div>
  );
};

// ─── Logs Panel ─────────────────────────────────────────────────────

const LogsPanel: React.FC<{
  logs: LogEntry[];
  filter: string;
  onFilterChange: (f: string) => void;
  onClear: () => void;
}> = ({ logs, filter, onFilterChange, onClear }) => {
  const filteredLogs = filter
    ? logs.filter(l => l.action === filter)
    : logs;

  const actions = ['ENTRY', 'EXIT', 'REVERSAL_EXIT', 'HEDGE', 'SCAN', 'SKIP', 'ERROR', 'START', 'STOP'];

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => onFilterChange('')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
            !filter ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' : 'text-slate-400 hover:text-white bg-slate-800'
          }`}
        >
          All
        </button>
        {actions.map(a => (
          <button
            key={a}
            onClick={() => onFilterChange(a)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              filter === a ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' : 'text-slate-400 hover:text-white bg-slate-800'
            }`}
          >
            {a}
          </button>
        ))}
        <div className="flex-1" />
        <button
          onClick={onClear}
          className="flex items-center gap-1 px-3 py-1.5 text-xs text-red-400 hover:text-red-300 transition"
        >
          <Trash2 className="w-3.5 h-3.5" /> Clear All
        </button>
      </div>

      {/* Log list */}
      {filteredLogs.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No logs to display</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredLogs.map(log => (
            <LogRow key={log.id} log={log} />
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Reusable Sub-components ────────────────────────────────────────

const StatCard: React.FC<{
  label: string; value: string; icon: any; color: string; bg: string;
}> = ({ label, value, icon: Icon, color, bg }) => (
  <div className={`${bg} border border-slate-800 rounded-xl p-4`}>
    <div className="flex items-center gap-2 mb-2">
      <Icon className={`w-4 h-4 ${color}`} />
      <span className="text-xs text-slate-400">{label}</span>
    </div>
    <p className={`text-lg font-bold ${color}`}>{value}</p>
  </div>
);

const MiniStat: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
    <p className="text-xs text-slate-400 mb-1">{label}</p>
    <p className="text-sm font-semibold text-white">{value}</p>
  </div>
);

const Section: React.FC<{
  title: string; icon: any; children: React.ReactNode;
}> = ({ title, icon: Icon, children }) => (
  <div className="card-glass p-5 rounded-xl space-y-4">
    <h3 className="text-white font-semibold flex items-center gap-2">
      <Icon className="w-4 h-4 text-slate-400" /> {title}
    </h3>
    {children}
  </div>
);

const InputField: React.FC<{
  label: string; type: string; value: number | string;
  onChange: (val: string) => void;
}> = ({ label, type, value, onChange }) => (
  <div>
    <label className="text-xs text-slate-400 mb-1 block">{label}</label>
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none transition"
    />
  </div>
);

const ToggleField: React.FC<{
  label: string; checked: boolean; onChange: (val: boolean) => void; description?: string;
}> = ({ label, checked, onChange, description }) => (
  <div
    onClick={() => onChange(!checked)}
    className={`p-3 rounded-lg border cursor-pointer transition ${
      checked
        ? 'bg-blue-500/10 border-blue-500/40'
        : 'bg-slate-800/50 border-slate-700 hover:border-slate-600'
    }`}
  >
    <div className="flex items-center justify-between">
      <span className="text-sm font-medium text-white">{label}</span>
      <div className={`w-10 h-5 rounded-full transition-colors relative ${
        checked ? 'bg-blue-500' : 'bg-slate-600'
      }`}>
        <div className={`w-4 h-4 rounded-full bg-white absolute top-0.5 transition-all ${
          checked ? 'left-5' : 'left-0.5'
        }`} />
      </div>
    </div>
    {description && <p className="text-xs text-slate-500 mt-1">{description}</p>}
  </div>
);

const LogRow: React.FC<{ log: LogEntry; compact?: boolean }> = ({ log, compact }) => {
  const [expanded, setExpanded] = useState(false);
  const sevClass = SEVERITY_BADGES[log.severity] || SEVERITY_BADGES.INFO;
  const actionColor = ACTION_COLORS[log.action] || 'text-slate-400';

  return (
    <div
      className="bg-slate-800/50 border border-slate-700/50 rounded-lg p-3 hover:border-slate-600 transition cursor-pointer"
      onClick={() => !compact && setExpanded(!expanded)}
    >
      <div className="flex items-center gap-3">
        <span className={`text-xs font-mono font-bold ${actionColor} min-w-[100px]`}>
          {log.action}
        </span>
        {log.underlying && (
          <span className="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-300 font-medium">
            {log.underlying}
          </span>
        )}
        {log.strategy && (
          <span className="text-xs text-slate-400">{log.strategy}</span>
        )}
        <span className="flex-1 text-xs text-slate-500 truncate">
          {log.reason}
        </span>
        {log.pnl_impact != null && log.pnl_impact !== 0 && (
          <span className={`text-xs font-bold ${log.pnl_impact >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {log.pnl_impact >= 0 ? '+' : ''}₹{log.pnl_impact.toFixed(0)}
          </span>
        )}
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${sevClass}`}>
          {log.severity}
        </span>
        <span className="text-[10px] text-slate-500 min-w-[65px] text-right">
          {new Date(log.created_at).toLocaleTimeString()}
        </span>
      </div>

      {expanded && log.details && (
        <div className="mt-3 pt-3 border-t border-slate-700">
          <pre className="text-xs text-slate-400 whitespace-pre-wrap overflow-auto max-h-40">
            {JSON.stringify(log.details, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

const UnderlyingBreakdown: React.FC<{ logs: LogEntry[]; underlyings: string[] }> = ({ logs, underlyings }) => {
  const stats = underlyings.map((u) => {
    const uLogs = logs.filter(l => l.underlying === u);
    const entries = uLogs.filter(l => l.action === 'ENTRY').length;
    const exits = uLogs.filter(l => ['EXIT', 'REVERSAL_EXIT'].includes(l.action)).length;
    const pnl = uLogs.reduce((s, l) => s + (l.pnl_impact || 0), 0);
    const errors = uLogs.filter(l => l.action === 'ERROR').length;
    return { underlying: u, entries, exits, pnl, errors };
  });

  return (
    <div className="card-glass p-5 rounded-xl">
      <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
        <BarChart3 className="w-4 h-4 text-slate-400" /> Per-Underlying Performance
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {stats.map(({ underlying, entries, exits, pnl, errors }) => (
          <div key={underlying} className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
            <p className="text-sm font-bold text-white mb-2">{underlying}</p>
            <div className="grid grid-cols-2 gap-1 text-xs">
              <span className="text-slate-400">Entries</span>
              <span className="text-green-400 font-medium">{entries}</span>
              <span className="text-slate-400">Exits</span>
              <span className="text-red-400 font-medium">{exits}</span>
              <span className="text-slate-400">P&L</span>
              <span className={`font-medium ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {pnl >= 0 ? '+' : ''}₹{pnl.toFixed(0)}
              </span>
              {errors > 0 && (
                <><span className="text-slate-400">Errors</span><span className="text-red-500">{errors}</span></>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AutoTrader;
