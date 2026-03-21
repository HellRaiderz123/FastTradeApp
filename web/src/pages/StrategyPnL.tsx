import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from 'recharts';
import {
  TrendingUp, TrendingDown, BarChart3, RefreshCw,
  Download, Trophy, AlertTriangle, Target, Activity,
} from 'lucide-react';
import api from '../lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Summary {
  total_trades: number;
  total_wins: number;
  total_losses: number;
  win_rate: number;
  total_pnl: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number | null;
  avg_win: number;
  avg_loss: number;
  max_drawdown: number;
  days: number;
}

interface StrategyStat {
  strategy: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number | null;
  total_pnl: number;
  gross_profit: number;
  gross_loss: number;
}

interface EquityPoint {
  date: string;
  pnl: number;
  cumulative: number;
  strategy: string;
  underlying: string;
}

interface DrawdownPoint { date: string; drawdown: number; }
interface MonthlyPoint { month: string; pnl: number; }

interface Analytics {
  summary: Summary;
  strategy_stats: StrategyStat[];
  equity_curve: EquityPoint[];
  drawdown_series: DrawdownPoint[];
  monthly_heatmap: MonthlyPoint[];
  exit_reasons: Record<string, number>;
  filters: { strategies: string[]; underlyings: string[] };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  `${n >= 0 ? '+' : ''}₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;

const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`;

const pnlColor = (v: number) => (v >= 0 ? '#10b981' : '#ef4444');

// ─── Custom Tooltip ───────────────────────────────────────────────────────────
const EquityTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as EquityPoint;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className={`font-bold ${d.cumulative >= 0 ? 'text-green-400' : 'text-red-400'}`}>
        Cumulative: {fmt(d.cumulative)}
      </p>
      <p className="text-slate-300">Trade P&L: {fmt(d.pnl)}</p>
      <p className="text-slate-500">{d.strategy} · {d.underlying}</p>
    </div>
  );
};

const DrawdownTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className="text-red-400 font-bold">{payload[0].value.toFixed(2)}%</p>
    </div>
  );
};

const MonthlyTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  const v = payload[0].value as number;
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">{label}</p>
      <p className={`font-bold ${v >= 0 ? 'text-green-400' : 'text-red-400'}`}>{fmt(v)}</p>
    </div>
  );
};

// ─── Stat Card ────────────────────────────────────────────────────────────────
const StatCard: React.FC<{
  label: string; value: string; sub?: string;
  color?: 'green' | 'red' | 'blue' | 'amber' | 'purple';
  icon?: React.ReactNode;
}> = ({ label, value, sub, color = 'blue', icon }) => {
  const colors = {
    green: 'text-green-400 bg-green-500/10 border-green-500/20',
    red: 'text-red-400 bg-red-500/10 border-red-500/20',
    blue: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
  }[color];

  return (
    <div className={`card-glass p-5 border ${colors}`}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs text-slate-400">{label}</p>
        {icon && <span className="opacity-60">{icon}</span>}
      </div>
      <p className={`text-2xl font-bold ${colors.split(' ')[0]}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
};

// ─── Main Component ───────────────────────────────────────────────────────────
const StrategyPnL: React.FC = () => {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [days, setDays] = useState(90);
  const [filterStrategy, setFilterStrategy] = useState('');
  const [filterUnderlying, setFilterUnderlying] = useState('');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { days };
      if (filterStrategy) params.strategy = filterStrategy;
      if (filterUnderlying) params.underlying = filterUnderlying;
      const res = await api.get('/analytics/pnl', { params });
      setData(res.data);
    } catch (e) {
      console.error('Failed to load P&L analytics:', e);
    } finally {
      setLoading(false);
    }
  }, [days, filterStrategy, filterUnderlying]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const exportCSV = () => {
    if (!data) return;
    const rows = [
      ['Strategy', 'Trades', 'Wins', 'Losses', 'Win Rate', 'Avg Win', 'Avg Loss', 'Profit Factor', 'Total P&L'],
      ...data.strategy_stats.map(s => [
        s.strategy, s.total_trades, s.wins, s.losses,
        `${s.win_rate}%`, s.avg_win, s.avg_loss,
        s.profit_factor ?? 'N/A', s.total_pnl,
      ]),
    ].map(r => r.join(',')).join('\n');
    const blob = new Blob([rows], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `strategy_pnl_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const s = data?.summary;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <BarChart3 className="w-8 h-8 text-green-400" />
            Strategy P&L Dashboard
          </h1>
          <p className="text-slate-400 mt-1">Equity curve, win rate, drawdown & monthly performance</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {/* Days filter */}
          {[30, 60, 90, 180, 365].map(d => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                days === d
                  ? 'bg-green-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {d}D
            </button>
          ))}
          <button onClick={fetchData} disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={exportCSV} disabled={!data}
            className="flex items-center gap-2 px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition">
            <Download className="w-4 h-4" />
            CSV
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <select
          value={filterStrategy}
          onChange={e => setFilterStrategy(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-green-500"
        >
          <option value="">All Strategies</option>
          {data?.filters.strategies.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <select
          value={filterUnderlying}
          onChange={e => setFilterUnderlying(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-green-500"
        >
          <option value="">All Underlyings</option>
          {data?.filters.underlyings.map(u => <option key={u} value={u}>{u}</option>)}
        </select>
      </div>

      {/* No data state */}
      {!loading && data && data.summary.total_trades === 0 && (
        <div className="card-glass p-12 text-center">
          <Activity className="w-12 h-12 mx-auto mb-3 text-slate-600" />
          <p className="text-slate-400 text-lg font-medium">No closed trades in the last {days} days</p>
          <p className="text-slate-500 text-sm mt-1">Execute and close some trades to see analytics here</p>
        </div>
      )}

      {s && s.total_trades > 0 && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
            <div className="col-span-2">
              <StatCard
                label="Total P&L"
                value={fmt(s.total_pnl)}
                sub={`${s.total_trades} closed trades`}
                color={s.total_pnl >= 0 ? 'green' : 'red'}
                icon={s.total_pnl >= 0 ? <TrendingUp className="w-4 h-4 text-green-400" /> : <TrendingDown className="w-4 h-4 text-red-400" />}
              />
            </div>
            <div className="col-span-2">
              <StatCard
                label="Win Rate"
                value={`${s.win_rate}%`}
                sub={`${s.total_wins}W / ${s.total_losses}L`}
                color={s.win_rate >= 50 ? 'green' : 'amber'}
                icon={<Trophy className="w-4 h-4" />}
              />
            </div>
            <div className="col-span-2">
              <StatCard
                label="Profit Factor"
                value={s.profit_factor !== null ? s.profit_factor.toFixed(2) : 'N/A'}
                sub={`Gross profit / loss`}
                color={s.profit_factor !== null && s.profit_factor >= 1.5 ? 'green' : 'amber'}
                icon={<Target className="w-4 h-4" />}
              />
            </div>
            <div className="col-span-2">
              <StatCard
                label="Max Drawdown"
                value={`${s.max_drawdown.toFixed(1)}%`}
                sub={`Avg Win ₹${s.avg_win.toLocaleString()} / Avg Loss ₹${s.avg_loss.toLocaleString()}`}
                color={s.max_drawdown > -20 ? 'amber' : 'red'}
                icon={<AlertTriangle className="w-4 h-4" />}
              />
            </div>
          </div>

          {/* Equity Curve */}
          <div className="card-glass p-6">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-green-400" />
              Equity Curve
              <span className="text-xs text-slate-500 font-normal ml-1">Cumulative P&L over time</span>
            </h2>
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={data.equity_curve} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false}
                  tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip content={<EquityTooltip />} />
                <ReferenceLine y={0} stroke="rgba(148,163,184,0.3)" strokeDasharray="4 4" />
                <Area type="monotone" dataKey="cumulative" stroke="#10b981" strokeWidth={2}
                  fill="url(#equityGrad)" dot={false} activeDot={{ r: 4, fill: '#10b981' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Drawdown + Monthly side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Drawdown Chart */}
            <div className="card-glass p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-400" />
                Drawdown
                <span className="text-xs text-slate-500 font-normal ml-1">% from peak equity</span>
              </h2>
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={data.drawdown_series} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                  <XAxis dataKey="date" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false}
                    tickFormatter={v => `${v}%`} />
                  <Tooltip content={<DrawdownTooltip />} />
                  <Area type="monotone" dataKey="drawdown" stroke="#ef4444" strokeWidth={2}
                    fill="url(#ddGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Monthly Heatmap Bar Chart */}
            <div className="card-glass p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-blue-400" />
                Monthly P&L
                <span className="text-xs text-slate-500 font-normal ml-1">Bar per month</span>
              </h2>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data.monthly_heatmap} margin={{ top: 5, right: 10, left: 10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                  <XAxis dataKey="month" tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} tickLine={false} axisLine={false}
                    tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`} />
                  <Tooltip content={<MonthlyTooltip />} />
                  <ReferenceLine y={0} stroke="rgba(148,163,184,0.3)" />
                  <Bar dataKey="pnl" radius={[3, 3, 0, 0]}>
                    {data.monthly_heatmap.map((entry, i) => (
                      <Cell key={i} fill={pnlColor(entry.pnl)} fillOpacity={0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Per-Strategy Table + Exit Reasons side by side */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Strategy Table */}
            <div className="lg:col-span-2 card-glass p-6">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Trophy className="w-5 h-5 text-amber-400" />
                Per-Strategy Breakdown
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-400 border-b border-slate-700 text-xs">
                      <th className="pb-3 pr-3">Strategy</th>
                      <th className="pb-3 pr-3 text-right">Trades</th>
                      <th className="pb-3 pr-3 text-right">Win%</th>
                      <th className="pb-3 pr-3 text-right">Avg Win</th>
                      <th className="pb-3 pr-3 text-right">Avg Loss</th>
                      <th className="pb-3 pr-3 text-right">PF</th>
                      <th className="pb-3 text-right">Total P&L</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {data.strategy_stats.map(row => (
                      <tr key={row.strategy} className="hover:bg-slate-800/30 transition">
                        <td className="py-3 pr-3 text-white font-medium text-xs max-w-[140px] truncate" title={row.strategy}>
                          {row.strategy}
                        </td>
                        <td className="py-3 pr-3 text-right text-slate-300">{row.total_trades}</td>
                        <td className="py-3 pr-3 text-right">
                          <span className={`font-semibold ${row.win_rate >= 50 ? 'text-green-400' : 'text-amber-400'}`}>
                            {row.win_rate}%
                          </span>
                        </td>
                        <td className="py-3 pr-3 text-right text-green-400">₹{row.avg_win.toLocaleString()}</td>
                        <td className="py-3 pr-3 text-right text-red-400">₹{row.avg_loss.toLocaleString()}</td>
                        <td className="py-3 pr-3 text-right">
                          <span className={row.profit_factor !== null && row.profit_factor >= 1 ? 'text-green-400' : 'text-red-400'}>
                            {row.profit_factor !== null ? row.profit_factor.toFixed(2) : '—'}
                          </span>
                        </td>
                        <td className="py-3 text-right font-semibold">
                          <span className={row.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                            {fmt(row.total_pnl)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Exit Reasons + Gross P&L */}
            <div className="space-y-4">
              {/* Exit Reasons */}
              <div className="card-glass p-5">
                <h3 className="text-sm font-semibold text-white mb-3">Exit Reasons</h3>
                <div className="space-y-2">
                  {Object.entries(data.exit_reasons)
                    .sort(([, a], [, b]) => b - a)
                    .map(([reason, count]) => {
                      const total = Object.values(data.exit_reasons).reduce((a, b) => a + b, 0);
                      const pct = Math.round(count / total * 100);
                      return (
                        <div key={reason}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-300">{reason}</span>
                            <span className="text-slate-400">{count} ({pct}%)</span>
                          </div>
                          <div className="w-full bg-slate-800 rounded-full h-1.5">
                            <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                          </div>
                        </div>
                      );
                    })}
                </div>
              </div>

              {/* Gross P&L breakdown */}
              <div className="card-glass p-5">
                <h3 className="text-sm font-semibold text-white mb-3">Gross Breakdown</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Gross Profit</span>
                    <span className="text-green-400 font-semibold">+₹{s.gross_profit.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Gross Loss</span>
                    <span className="text-red-400 font-semibold">-₹{s.gross_loss.toLocaleString()}</span>
                  </div>
                  <div className="border-t border-slate-700 pt-2 flex justify-between">
                    <span className="text-slate-300 font-medium">Net P&L</span>
                    <span className={`font-bold ${s.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {fmt(s.total_pnl)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Avg Win</span>
                    <span className="text-green-400">₹{s.avg_win.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Avg Loss</span>
                    <span className="text-red-400">₹{s.avg_loss.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {loading && (
        <div className="card-glass p-12 text-center">
          <RefreshCw className="w-8 h-8 mx-auto mb-3 text-slate-500 animate-spin" />
          <p className="text-slate-400">Loading analytics...</p>
        </div>
      )}
    </div>
  );
};

export default StrategyPnL;
