import React, { useState, useEffect, useCallback } from 'react';
import {
  Zap, TrendingUp, TrendingDown, RefreshCw, Play, BarChart3,
  Clock, Target, AlertTriangle, CheckCircle, XCircle, Download,
  Activity, DollarSign, Percent, Award, Filter, Eye
} from 'lucide-react';
import api from '../lib/api';

// ─── Types ──────────────────────────────────────────────────────────

interface ScalpTrade {
  trade_id: string;
  underlying: string;
  signal_type: string;
  option_symbol: string;
  entry_time: string | null;
  entry_price: number | null;
  exit_time: string | null;
  exit_price: number | null;
  exit_reason: string | null;
  pnl: number | null;
  pnl_pct: number | null;
  status: string;
  tp_price?: number;
  sl_price?: number;
}

interface ScalpStats {
  period_days: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  total_pnl: number;
  avg_win: number;
  avg_loss: number;
  risk_reward_ratio: number;
  profit_factor: number | string;
  by_exit_reason: Record<string, { count: number; pnl: number; wins: number }>;
  by_underlying: Record<string, { count: number; pnl: number; wins: number }>;
  by_signal_type: Record<string, { count: number; pnl: number; wins: number }>;
  error?: string;
}

interface ScalpSignal {
  underlying: string;
  signal_type: string;
  confidence: number;
  reason: string;
  scalp_ready: boolean;
  indicators: Record<string, any>;
}

interface ScalpConfig {
  underlyings: string[];
  lots: number;
  capital_per_trade: number;
  tp_pct: number;
  sl_pct: number;
  max_hold_minutes: number;
  min_confidence: number;
  require_scalp_ready: boolean;
  max_open_scalps: number;
  max_daily_trades: number;
  max_daily_loss: number;
}

// ─── API ────────────────────────────────────────────────────────────

const scalpAPI = {
  getStats: (days: number = 30) => api.get(`/scalp/stats?days=${days}`),
  getTrades: (limit: number = 50) => api.get(`/scalp/trades?limit=${limit}`),
  getSignals: () => api.get('/scalp/signals'),
  getConfig: () => api.get('/scalp/config'),
  runCycle: () => api.post('/scalp/run'),
  exportCSV: (days: number = 30) => api.post(`/scalp/export?days=${days}`),
};

// ─── Main Component ─────────────────────────────────────────────────

const ScalpTrading: React.FC = () => {
  const [stats, setStats] = useState<ScalpStats | null>(null);
  const [trades, setTrades] = useState<ScalpTrade[]>([]);
  const [signals, setSignals] = useState<ScalpSignal[]>([]);
  const [config, setConfig] = useState<ScalpConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'trades' | 'signals'>('dashboard');
  const [statsDays, setStatsDays] = useState(30);
  const [runningCycle, setRunningCycle] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [statsRes, tradesRes, signalsRes, configRes] = await Promise.all([
        scalpAPI.getStats(statsDays),
        scalpAPI.getTrades(100),
        scalpAPI.getSignals(),
        scalpAPI.getConfig(),
      ]);
      setStats(statsRes.data);
      setTrades(tradesRes.data || []);
      setSignals(signalsRes.data?.signals || []);
      setConfig(configRes.data);
    } catch (err) {
      console.error('Scalp fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [statsDays]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleRunCycle = async () => {
    setRunningCycle(true);
    try {
      const res = await scalpAPI.runCycle();
      console.log('Cycle result:', res.data);
      await fetchAll();
    } catch (err) {
      console.error('Run cycle error:', err);
    }
    setRunningCycle(false);
  };

  const handleExport = async () => {
    try {
      const res = await scalpAPI.exportCSV(statsDays);
      alert(`Exported to: ${res.data?.filepath}`);
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  const openTrades = trades.filter(t => t.status === 'OPEN');
  const closedTrades = trades.filter(t => t.status === 'CLOSED');

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gradient-to-br from-yellow-500 to-orange-600 rounded-xl flex items-center justify-center">
            <Zap className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Scalp Trading</h1>
            <p className="text-sm text-slate-400">
              5-minute momentum scalping with auto TP/SL
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleRunCycle}
            disabled={runningCycle}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium transition disabled:opacity-50"
          >
            {runningCycle ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Run Cycle
          </button>
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium transition"
          >
            <Download className="w-4 h-4" /> Export CSV
          </button>
          <button
            onClick={fetchAll}
            className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-400 rounded-lg transition"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-slate-900/50 p-1 rounded-xl border border-slate-800">
        {(['dashboard', 'trades', 'signals'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 px-4 py-2.5 rounded-lg text-sm font-medium transition capitalize ${
              activeTab === tab
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            {tab === 'dashboard' && <BarChart3 className="w-4 h-4 inline-block mr-2" />}
            {tab === 'trades' && <Activity className="w-4 h-4 inline-block mr-2" />}
            {tab === 'signals' && <Eye className="w-4 h-4 inline-block mr-2" />}
            {tab}
          </button>
        ))}
      </div>

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && stats && (
        <DashboardView
          stats={stats}
          config={config}
          openTrades={openTrades}
          statsDays={statsDays}
          onDaysChange={setStatsDays}
        />
      )}

      {/* Trades Tab */}
      {activeTab === 'trades' && (
        <TradesView trades={trades} />
      )}

      {/* Signals Tab */}
      {activeTab === 'signals' && (
        <SignalsView signals={signals} config={config} />
      )}
    </div>
  );
};

// ─── Dashboard View ─────────────────────────────────────────────────

const DashboardView: React.FC<{
  stats: ScalpStats;
  config: ScalpConfig | null;
  openTrades: ScalpTrade[];
  statsDays: number;
  onDaysChange: (days: number) => void;
}> = ({ stats, config, openTrades, statsDays, onDaysChange }) => {
  const pnlPositive = (stats.total_pnl || 0) >= 0;

  return (
    <div className="space-y-6">
      {/* Period selector */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-slate-400">Period:</span>
        {[7, 14, 30, 60].map(d => (
          <button
            key={d}
            onClick={() => onDaysChange(d)}
            className={`px-3 py-1 rounded-lg text-sm font-medium transition ${
              statsDays === d
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
                : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            {d}d
          </button>
        ))}
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Total P&L"
          value={`₹${(stats.total_pnl || 0).toLocaleString()}`}
          icon={pnlPositive ? TrendingUp : TrendingDown}
          color={pnlPositive ? 'text-green-400' : 'text-red-400'}
          bg={pnlPositive ? 'bg-green-500/10' : 'bg-red-500/10'}
        />
        <StatCard
          label="Win Rate"
          value={`${stats.win_rate_pct || 0}%`}
          icon={Award}
          color={stats.win_rate_pct >= 50 ? 'text-green-400' : 'text-yellow-400'}
          bg={stats.win_rate_pct >= 50 ? 'bg-green-500/10' : 'bg-yellow-500/10'}
        />
        <StatCard
          label="Total Trades"
          value={`${stats.total_trades || 0}`}
          icon={Activity}
          color="text-blue-400"
          bg="bg-blue-500/10"
        />
        <StatCard
          label="Profit Factor"
          value={`${stats.profit_factor || 0}`}
          icon={Percent}
          color="text-purple-400"
          bg="bg-purple-500/10"
        />
      </div>

      {/* Win/Loss breakdown */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MiniStat label="Winning Trades" value={`${stats.winning_trades}`} color="text-green-400" />
        <MiniStat label="Losing Trades" value={`${stats.losing_trades}`} color="text-red-400" />
        <MiniStat label="Avg Win" value={`₹${(stats.avg_win || 0).toFixed(0)}`} color="text-green-400" />
        <MiniStat label="Avg Loss" value={`₹${(stats.avg_loss || 0).toFixed(0)}`} color="text-red-400" />
      </div>

      {/* Open Positions */}
      {openTrades.length > 0 && (
        <div className="card-glass p-5 rounded-xl">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            Open Scalp Positions ({openTrades.length})
          </h3>
          <div className="space-y-2">
            {openTrades.map(trade => (
              <TradeRow key={trade.trade_id} trade={trade} />
            ))}
          </div>
        </div>
      )}

      {/* By Exit Reason */}
      {stats.by_exit_reason && Object.keys(stats.by_exit_reason).length > 0 && (
        <div className="card-glass p-5 rounded-xl">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Target className="w-4 h-4 text-slate-400" />
            Performance by Exit Reason
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {Object.entries(stats.by_exit_reason).map(([reason, data]) => (
              <BreakdownCard
                key={reason}
                label={reason}
                count={data.count}
                pnl={data.pnl}
                wins={data.wins}
              />
            ))}
          </div>
        </div>
      )}

      {/* By Underlying */}
      {stats.by_underlying && Object.keys(stats.by_underlying).length > 0 && (
        <div className="card-glass p-5 rounded-xl">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-slate-400" />
            Performance by Underlying
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {Object.entries(stats.by_underlying).map(([underlying, data]) => (
              <BreakdownCard
                key={underlying}
                label={underlying}
                count={data.count}
                pnl={data.pnl}
                wins={data.wins}
              />
            ))}
          </div>
        </div>
      )}

      {/* Config Overview */}
      {config && (
        <div className="card-glass p-5 rounded-xl">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            Configuration
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <ConfigItem label="Underlyings" value={config.underlyings.join(', ')} />
            <ConfigItem label="TP %" value={`${config.tp_pct}%`} />
            <ConfigItem label="SL %" value={`${config.sl_pct}%`} />
            <ConfigItem label="Max Hold" value={`${config.max_hold_minutes} min`} />
            <ConfigItem label="Min Confidence" value={`${config.min_confidence}%`} />
            <ConfigItem label="Max Open" value={`${config.max_open_scalps}`} />
            <ConfigItem label="Max Daily Trades" value={`${config.max_daily_trades}`} />
            <ConfigItem label="Max Daily Loss" value={`₹${config.max_daily_loss}`} />
          </div>
        </div>
      )}
    </div>
  );
};

// ─── Trades View ────────────────────────────────────────────────────

const TradesView: React.FC<{ trades: ScalpTrade[] }> = ({ trades }) => {
  const [filter, setFilter] = useState<'all' | 'open' | 'closed'>('all');

  const filteredTrades = trades.filter(t => {
    if (filter === 'open') return t.status === 'OPEN';
    if (filter === 'closed') return t.status === 'CLOSED';
    return true;
  });

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex gap-2">
        {(['all', 'open', 'closed'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition capitalize ${
              filter === f
                ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40'
                : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Trades list */}
      {filteredTrades.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Activity className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No trades found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredTrades.map(trade => (
            <TradeRow key={trade.trade_id} trade={trade} expanded />
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Signals View ───────────────────────────────────────────────────

const SignalsView: React.FC<{ signals: ScalpSignal[]; config: ScalpConfig | null }> = ({ signals, config }) => {
  return (
    <div className="space-y-4">
      <div className="card-glass p-4 rounded-xl">
        <p className="text-sm text-slate-400">
          Current scalp signals based on 5-minute TA analysis. Signals require{' '}
          <span className="text-white font-medium">{config?.min_confidence || 60}%+ confidence</span> and{' '}
          <span className="text-white font-medium">scalp_ready = true</span> to trigger entries.
        </p>
      </div>

      {signals.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Eye className="w-10 h-10 mx-auto mb-3 opacity-30" />
          <p>No scalp signals currently</p>
          <p className="text-xs mt-2">Signals appear when momentum + volume conditions are met</p>
        </div>
      ) : (
        <div className="space-y-3">
          {signals.map((sig, idx) => (
            <SignalCard key={idx} signal={sig} />
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Reusable Components ────────────────────────────────────────────

const StatCard: React.FC<{
  label: string; value: string; icon: any; color: string; bg: string;
}> = ({ label, value, icon: Icon, color, bg }) => (
  <div className={`${bg} border border-slate-800 rounded-xl p-4`}>
    <div className="flex items-center gap-2 mb-2">
      <Icon className={`w-4 h-4 ${color}`} />
      <span className="text-xs text-slate-400">{label}</span>
    </div>
    <p className={`text-xl font-bold ${color}`}>{value}</p>
  </div>
);

const MiniStat: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color = 'text-white' }) => (
  <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 text-center">
    <p className="text-xs text-slate-400 mb-1">{label}</p>
    <p className={`text-sm font-semibold ${color}`}>{value}</p>
  </div>
);

const ConfigItem: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div>
    <p className="text-xs text-slate-500">{label}</p>
    <p className="text-white font-medium">{value}</p>
  </div>
);

const BreakdownCard: React.FC<{
  label: string; count: number; pnl: number; wins: number;
}> = ({ label, count, pnl, wins }) => {
  const winRate = count > 0 ? ((wins / count) * 100).toFixed(0) : '0';
  const pnlPositive = pnl >= 0;

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
      <p className="text-sm font-bold text-white mb-2">{label}</p>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <span className="text-slate-400">Trades</span>
          <p className="text-white font-medium">{count}</p>
        </div>
        <div>
          <span className="text-slate-400">Win Rate</span>
          <p className="text-blue-400 font-medium">{winRate}%</p>
        </div>
        <div>
          <span className="text-slate-400">P&L</span>
          <p className={`font-medium ${pnlPositive ? 'text-green-400' : 'text-red-400'}`}>
            ₹{pnl.toFixed(0)}
          </p>
        </div>
      </div>
    </div>
  );
};

const TradeRow: React.FC<{ trade: ScalpTrade; expanded?: boolean }> = ({ trade, expanded }) => {
  const isOpen = trade.status === 'OPEN';
  const pnlPositive = (trade.pnl || 0) >= 0;

  return (
    <div className={`bg-slate-800/50 border rounded-lg p-3 ${
      isOpen ? 'border-yellow-500/30' : 'border-slate-700/50'
    }`}>
      <div className="flex items-center gap-3">
        {/* Status indicator */}
        <span className={`w-2 h-2 rounded-full ${
          isOpen ? 'bg-yellow-400 animate-pulse' : pnlPositive ? 'bg-green-400' : 'bg-red-400'
        }`} />

        {/* Trade ID */}
        <span className="text-xs font-mono text-slate-500 min-w-[140px]">
          {trade.trade_id}
        </span>

        {/* Underlying */}
        <span className="text-xs bg-slate-700 px-2 py-0.5 rounded text-slate-300 font-medium">
          {trade.underlying}
        </span>

        {/* Signal type */}
        <span className={`text-xs font-bold ${
          trade.signal_type?.includes('BULLISH') ? 'text-green-400' : 'text-red-400'
        }`}>
          {trade.signal_type}
        </span>

        {/* Option symbol */}
        <span className="text-xs text-slate-400 flex-1 truncate">
          {trade.option_symbol}
        </span>

        {/* Entry price */}
        <span className="text-xs text-slate-400">
          Entry: ₹{trade.entry_price?.toFixed(2) || '-'}
        </span>

        {/* Exit info */}
        {!isOpen && (
          <>
            <span className="text-xs text-slate-400">
              Exit: ₹{trade.exit_price?.toFixed(2) || '-'}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded ${
              trade.exit_reason === 'TP_HIT' ? 'bg-green-500/20 text-green-400' :
              trade.exit_reason === 'SL_HIT' ? 'bg-red-500/20 text-red-400' :
              'bg-slate-500/20 text-slate-400'
            }`}>
              {trade.exit_reason}
            </span>
          </>
        )}

        {/* P&L */}
        {trade.pnl != null && (
          <span className={`text-sm font-bold min-w-[80px] text-right ${
            pnlPositive ? 'text-green-400' : 'text-red-400'
          }`}>
            {pnlPositive ? '+' : ''}₹{trade.pnl.toFixed(0)}
          </span>
        )}

        {/* Status badge */}
        <span className={`text-xs px-2 py-0.5 rounded font-medium ${
          isOpen ? 'bg-yellow-500/20 text-yellow-400' : 'bg-slate-500/20 text-slate-400'
        }`}>
          {trade.status}
        </span>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="mt-2 pt-2 border-t border-slate-700 grid grid-cols-4 gap-2 text-xs">
          <div>
            <span className="text-slate-500">Entry Time</span>
            <p className="text-slate-300">
              {trade.entry_time ? new Date(trade.entry_time).toLocaleString() : '-'}
            </p>
          </div>
          <div>
            <span className="text-slate-500">Exit Time</span>
            <p className="text-slate-300">
              {trade.exit_time ? new Date(trade.exit_time).toLocaleString() : '-'}
            </p>
          </div>
          <div>
            <span className="text-slate-500">TP Target</span>
            <p className="text-green-400">₹{trade.tp_price?.toFixed(2) || '-'}</p>
          </div>
          <div>
            <span className="text-slate-500">SL Target</span>
            <p className="text-red-400">₹{trade.sl_price?.toFixed(2) || '-'}</p>
          </div>
        </div>
      )}
    </div>
  );
};

const SignalCard: React.FC<{ signal: ScalpSignal }> = ({ signal }) => {
  const isBullish = signal.signal_type?.includes('BULLISH');

  return (
    <div className={`card-glass p-4 rounded-xl border ${
      isBullish ? 'border-green-500/30' : 'border-red-500/30'
    }`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-white">{signal.underlying}</span>
          <span className={`px-3 py-1 rounded-full text-sm font-bold ${
            isBullish ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
          }`}>
            {signal.signal_type}
          </span>
          {signal.scalp_ready && (
            <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded font-medium">
              SCALP READY
            </span>
          )}
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-white">{signal.confidence}%</p>
          <p className="text-xs text-slate-400">confidence</p>
        </div>
      </div>

      <p className="text-sm text-slate-300 mb-3">{signal.reason}</p>

      {/* Indicators */}
      <div className="grid grid-cols-4 md:grid-cols-6 gap-2 text-xs">
        {Object.entries(signal.indicators || {}).slice(0, 6).map(([key, value]) => (
          <div key={key} className="bg-slate-800/50 rounded p-2">
            <span className="text-slate-500 block">{key}</span>
            <span className="text-white font-medium">
              {typeof value === 'number' ? value.toFixed(2) : String(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ScalpTrading;
