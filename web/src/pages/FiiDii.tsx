import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, RefreshCw, Activity, BarChart3,
  ArrowUpRight, ArrowDownRight, Minus, AlertCircle, Clock
} from 'lucide-react';
import axios from 'axios';
import { authTokenStore } from '../lib/api';

// ── Types ────────────────────────────────────────────────────────────────────
interface FnoData {
  fii_idx_fut_long: number | null; fii_idx_fut_short: number | null; fii_idx_fut_net: number | null;
  dii_idx_fut_long: number | null; dii_idx_fut_short: number | null; dii_idx_fut_net: number | null;
  fii_stk_fut_long: number | null; fii_stk_fut_short: number | null; fii_stk_fut_net: number | null;
  fii_idx_call_long: number | null; fii_idx_call_short: number | null; fii_idx_call_net: number | null;
  fii_idx_put_long: number | null; fii_idx_put_short: number | null; fii_idx_put_net: number | null;
  sentiment: string | null; fno_date?: string | null;
}
interface Summary {
  latest_date: string; fii_net: number; dii_net: number;
  fii_buy: number; fii_sell: number; dii_buy: number; dii_sell: number;
  flow_strength_fii_pct: number; flow_strength_dii_pct: number;
  fii_direction: string; dii_direction: string;
  fii_streak_days: number; dii_streak_days: number;
  avg_fii_20d: number; avg_dii_20d: number;
  mtd_fii: number; mtd_dii: number; ytd_fii: number; ytd_dii: number;
  sentiment_score: number | null; pcr: number | null;
  fno: FnoData; updated_at: string; cached_at: string;
  heatmap?: { date: string; fii_net: number | null; dii_net: number | null; sentiment_score: number | null }[];
}
interface HistoryRecord {
  date: string; _parsed_date: string;
  fii_net: number; dii_net: number; fii_buy: number; fii_sell: number;
  dii_buy: number; dii_sell: number; sentiment_score: number | null;
}

type Tab = 'cash' | 'fno' | 'chart' | 'history';

// ── Helpers ──────────────────────────────────────────────────────────────────
const api = axios.create({ baseURL: '/api/fii-dii' });
api.interceptors.request.use(c => {
  const t = authTokenStore.get(); if (t) c.headers['Authorization'] = `Bearer ${t}`; return c;
});

const cr = (v: number | null | undefined) => {
  if (v == null) return 'N/A';
  const abs = Math.abs(v);
  const s = abs >= 10000 ? `₹${(abs / 1000).toFixed(1)}K Cr` : `₹${abs.toFixed(0)} Cr`;
  return v < 0 ? `-${s}` : `+${s}`;
};
const netColor = (v: number | null | undefined) =>
  v == null ? 'text-slate-400' : v >= 0 ? 'text-emerald-400' : 'text-red-400';
const heatColor = (v: number | null | undefined, type: 'fii' | 'dii') => {
  if (v == null) return 'bg-slate-800';
  if (type === 'fii') {
    if (v > 5000) return 'bg-emerald-500/80'; if (v > 2000) return 'bg-emerald-500/50';
    if (v > 0) return 'bg-emerald-500/25'; if (v > -2000) return 'bg-red-500/25';
    if (v > -5000) return 'bg-red-500/50'; return 'bg-red-500/80';
  }
  if (v > 5000) return 'bg-blue-500/80'; if (v > 2000) return 'bg-blue-500/50';
  if (v > 0) return 'bg-blue-500/25'; if (v > -2000) return 'bg-orange-500/25';
  if (v > -5000) return 'bg-orange-500/50'; return 'bg-orange-500/80';
};

// ── Sub-components ────────────────────────────────────────────────────────────
const StatCard: React.FC<{ label: string; value: string; sub?: string; color?: string; icon?: React.ReactNode }> = ({
  label, value, sub, color = 'text-white', icon
}) => (
  <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
    <div className="flex items-center justify-between mb-1">
      <p className="text-xs text-slate-400">{label}</p>
      {icon}
    </div>
    <p className={`text-xl font-bold ${color}`}>{value}</p>
    {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
  </div>
);

const FnoBar: React.FC<{ label: string; long: number | null; short: number | null; net: number | null }> = ({
  label, long, short, net
}) => {
  const total = (long ?? 0) + (short ?? 0);
  const longPct = total > 0 ? ((long ?? 0) / total) * 100 : 50;
  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-semibold text-white">{label}</span>
        <span className={`text-sm font-bold ${netColor(net)}`}>{net != null ? (net >= 0 ? '+' : '') + net.toLocaleString('en-IN') : 'N/A'}</span>
      </div>
      <div className="h-2 bg-slate-700 rounded-full overflow-hidden flex">
        <div className="h-full bg-emerald-500 transition-all" style={{ width: `${longPct}%` }} />
        <div className="h-full bg-red-500 flex-1" />
      </div>
      <div className="flex justify-between mt-1 text-xs text-slate-500">
        <span className="text-emerald-400">L: {(long ?? 0).toLocaleString('en-IN')}</span>
        <span className="text-red-400">S: {(short ?? 0).toLocaleString('en-IN')}</span>
      </div>
    </div>
  );
};

// ── Main Page ─────────────────────────────────────────────────────────────────
const FiiDii: React.FC = () => {
  const [tab, setTab] = useState<Tab>('cash');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [sumRes, histRes] = await Promise.all([
        api.get<Summary>('/summary'),
        api.get<{ records: HistoryRecord[] }>('/history?days=60'),
      ]);
      setSummary(sumRes.data);
      setHistory(histRes.data.records.slice().reverse()); // newest first
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load FII/DII data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: 'cash', label: 'Cash Flows', icon: TrendingUp },
    { id: 'fno', label: 'F&O Positions', icon: BarChart3 },
    { id: 'chart', label: 'Heatmap', icon: Activity },
    { id: 'history', label: 'History', icon: Clock },
  ];

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Activity size={32} className="text-emerald-400 animate-pulse" />
    </div>
  );

  if (error) return (
    <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
      <AlertCircle size={20} className="text-red-400" />
      <span className="text-red-400">{error}</span>
    </div>
  );

  if (!summary) return null;

  const fiiUp = summary.fii_direction === 'BUY';
  const diiUp = summary.dii_direction === 'BUY';

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">FII / DII Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">
            Institutional money flows · {summary.latest_date}
            {summary.updated_at && <span className="ml-2 text-slate-500">· {summary.updated_at}</span>}
          </p>
        </div>
        <button onClick={load} className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition">
          <RefreshCw size={16} />
        </button>
      </div>

      {/* Hero cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* FII card */}
        <div className={`rounded-2xl p-6 border-2 ${fiiUp ? 'bg-emerald-500/10 border-emerald-500/40' : 'bg-red-500/10 border-red-500/40'}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              {fiiUp ? <ArrowUpRight size={20} className="text-emerald-400" /> : <ArrowDownRight size={20} className="text-red-400" />}
              <span className="text-sm font-semibold text-slate-300">FII / FPI Net</span>
            </div>
            <span className={`text-xs px-2 py-1 rounded-full font-semibold ${fiiUp ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
              {fiiUp ? 'NET BUYER' : 'NET SELLER'}
            </span>
          </div>
          <p className={`text-4xl font-bold ${netColor(summary.fii_net)}`}>{cr(summary.fii_net)}</p>
          <div className="flex gap-4 mt-3 text-xs text-slate-400">
            <span>Buy: <span className="text-emerald-400">{cr(summary.fii_buy)}</span></span>
            <span>Sell: <span className="text-red-400">{cr(-summary.fii_sell)}</span></span>
          </div>
          <div className="mt-3 text-xs text-slate-500">
            Streak: <span className={fiiUp ? 'text-emerald-400' : 'text-red-400'}>{Math.abs(summary.fii_streak_days)}d {fiiUp ? '▲' : '▼'}</span>
            <span className="ml-3">20d avg: <span className={netColor(summary.avg_fii_20d)}>{cr(summary.avg_fii_20d)}</span></span>
          </div>
        </div>

        {/* DII card */}
        <div className={`rounded-2xl p-6 border-2 ${diiUp ? 'bg-blue-500/10 border-blue-500/40' : 'bg-orange-500/10 border-orange-500/40'}`}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              {diiUp ? <ArrowUpRight size={20} className="text-blue-400" /> : <ArrowDownRight size={20} className="text-orange-400" />}
              <span className="text-sm font-semibold text-slate-300">DII Net</span>
            </div>
            <span className={`text-xs px-2 py-1 rounded-full font-semibold ${diiUp ? 'bg-blue-500/20 text-blue-400' : 'bg-orange-500/20 text-orange-400'}`}>
              {diiUp ? 'NET BUYER' : 'NET SELLER'}
            </span>
          </div>
          <p className={`text-4xl font-bold ${diiUp ? 'text-blue-400' : 'text-orange-400'}`}>{cr(summary.dii_net)}</p>
          <div className="flex gap-4 mt-3 text-xs text-slate-400">
            <span>Buy: <span className="text-blue-400">{cr(summary.dii_buy)}</span></span>
            <span>Sell: <span className="text-orange-400">{cr(-summary.dii_sell)}</span></span>
          </div>
          <div className="mt-3 text-xs text-slate-500">
            Streak: <span className={diiUp ? 'text-blue-400' : 'text-orange-400'}>{Math.abs(summary.dii_streak_days)}d {diiUp ? '▲' : '▼'}</span>
            <span className="ml-3">20d avg: <span className={diiUp ? 'text-blue-400' : 'text-orange-400'}>{cr(summary.avg_dii_20d)}</span></span>
          </div>
        </div>
      </div>

      {/* Flow strength meter */}
      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
        <p className="text-xs text-slate-400 mb-2">Flow Strength Meter</p>
        <div className="h-3 bg-slate-700 rounded-full overflow-hidden flex">
          <div className={`h-full transition-all ${fiiUp ? 'bg-emerald-500' : 'bg-red-500'}`}
            style={{ width: `${summary.flow_strength_fii_pct}%` }} />
          <div className={`h-full flex-1 ${diiUp ? 'bg-blue-500' : 'bg-orange-500'}`} />
        </div>
        <div className="flex justify-between mt-1 text-xs">
          <span className={fiiUp ? 'text-emerald-400' : 'text-red-400'}>FII {summary.flow_strength_fii_pct}%</span>
          <span className={diiUp ? 'text-blue-400' : 'text-orange-400'}>DII {summary.flow_strength_dii_pct}%</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
              tab === id ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
            }`}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {/* ── Cash Flows Tab ── */}
      {tab === 'cash' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="MTD FII" value={cr(summary.mtd_fii)} color={netColor(summary.mtd_fii)} />
            <StatCard label="MTD DII" value={cr(summary.mtd_dii)} color={summary.mtd_dii >= 0 ? 'text-blue-400' : 'text-orange-400'} />
            <StatCard label="YTD FII" value={cr(summary.ytd_fii)} color={netColor(summary.ytd_fii)} />
            <StatCard label="YTD DII" value={cr(summary.ytd_dii)} color={summary.ytd_dii >= 0 ? 'text-blue-400' : 'text-orange-400'} />
          </div>
          {summary.sentiment_score != null && (
            <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-white">Sentiment Score</span>
                <span className={`text-lg font-bold ${summary.sentiment_score >= 60 ? 'text-emerald-400' : summary.sentiment_score >= 40 ? 'text-yellow-400' : 'text-red-400'}`}>
                  {summary.sentiment_score}/100
                </span>
              </div>
              <div className="h-2 bg-slate-700 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${summary.sentiment_score >= 60 ? 'bg-emerald-500' : summary.sentiment_score >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                  style={{ width: `${summary.sentiment_score}%` }} />
              </div>
              {summary.pcr != null && (
                <p className="text-xs text-slate-500 mt-2">PCR: <span className="text-white">{summary.pcr.toFixed(2)}</span></p>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── F&O Positions Tab ── */}
      {tab === 'fno' && (
        <div className="space-y-4">
          {summary.fno.fno_date && summary.fno.fno_date !== summary.latest_date && (
            <div className="flex items-center gap-2 px-3 py-2 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-xs text-yellow-400">
              <AlertCircle size={12} />
              F&O data from {summary.fno.fno_date} (latest available — NSE releases with a lag)
            </div>
          )}
          {summary.fno.sentiment && (
            <div className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold w-fit ${
              summary.fno.sentiment === 'Bullish' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
              summary.fno.sentiment === 'Bearish' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
              'bg-slate-700 text-slate-300'
            }`}>
              {summary.fno.sentiment === 'Bullish' ? <TrendingUp size={14} /> : summary.fno.sentiment === 'Bearish' ? <TrendingDown size={14} /> : <Minus size={14} />}
              F&O Sentiment: {summary.fno.sentiment}
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FnoBar label="FII Index Futures" long={summary.fno.fii_idx_fut_long} short={summary.fno.fii_idx_fut_short} net={summary.fno.fii_idx_fut_net} />
            <FnoBar label="DII Index Futures" long={summary.fno.dii_idx_fut_long} short={summary.fno.dii_idx_fut_short} net={summary.fno.dii_idx_fut_net} />
            <FnoBar label="FII Stock Futures" long={summary.fno.fii_stk_fut_long} short={summary.fno.fii_stk_fut_short} net={summary.fno.fii_stk_fut_net} />
            <FnoBar label="FII Index Calls" long={summary.fno.fii_idx_call_long} short={summary.fno.fii_idx_call_short} net={summary.fno.fii_idx_call_net} />
            <FnoBar label="FII Index Puts" long={summary.fno.fii_idx_put_long} short={summary.fno.fii_idx_put_short} net={summary.fno.fii_idx_put_net} />
          </div>
          {summary.fno.fii_idx_fut_long == null && (
            <p className="text-sm text-slate-500 text-center py-4">F&O data not available for this session</p>
          )}
        </div>
      )}

      {/* ── Heatmap Tab ── */}
      {tab === 'chart' && summary.heatmap && (
        <div className="space-y-6">
          <div>
            <h3 className="text-sm font-semibold text-white mb-3">FII 45-Day Heatmap</h3>
            <div className="flex flex-wrap gap-1">
              {summary.heatmap.map((d, i) => (
                <div key={i} title={`${d.date}: ${cr(d.fii_net)}`}
                  className={`w-7 h-7 rounded cursor-default transition-opacity hover:opacity-80 ${heatColor(d.fii_net, 'fii')}`} />
              ))}
            </div>
            <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/80 inline-block" /> Strong Buy</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-500/25 inline-block" /> Mild Buy</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/25 inline-block" /> Mild Sell</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-500/80 inline-block" /> Strong Sell</span>
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white mb-3">DII 45-Day Absorption</h3>
            <div className="flex flex-wrap gap-1">
              {summary.heatmap.map((d, i) => (
                <div key={i} title={`${d.date}: ${cr(d.dii_net)}`}
                  className={`w-7 h-7 rounded cursor-default transition-opacity hover:opacity-80 ${heatColor(d.dii_net, 'dii')}`} />
              ))}
            </div>
            <div className="flex items-center gap-3 mt-2 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-500/80 inline-block" /> Strong Buy</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-blue-500/25 inline-block" /> Mild Buy</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-500/25 inline-block" /> Mild Sell</span>
              <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-orange-500/80 inline-block" /> Strong Sell</span>
            </div>
          </div>
        </div>
      )}

      {/* ── History Tab ── */}
      {tab === 'history' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700/50 text-slate-400 text-xs">
                <th className="text-left py-3 px-3">Date</th>
                <th className="text-right py-3 px-3">FII Buy</th>
                <th className="text-right py-3 px-3">FII Sell</th>
                <th className="text-right py-3 px-3">FII Net</th>
                <th className="text-right py-3 px-3">DII Buy</th>
                <th className="text-right py-3 px-3">DII Sell</th>
                <th className="text-right py-3 px-3">DII Net</th>
                <th className="text-right py-3 px-3">Sentiment</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r, i) => (
                <tr key={i} className="border-b border-slate-700/30 hover:bg-slate-800/30 transition">
                  <td className="py-2 px-3 text-slate-300 text-xs">{r.date}</td>
                  <td className="text-right py-2 px-3 text-emerald-400 text-xs">{cr(r.fii_buy)}</td>
                  <td className="text-right py-2 px-3 text-red-400 text-xs">{cr(-r.fii_sell)}</td>
                  <td className={`text-right py-2 px-3 font-semibold text-xs ${netColor(r.fii_net)}`}>{cr(r.fii_net)}</td>
                  <td className="text-right py-2 px-3 text-blue-400 text-xs">{cr(r.dii_buy)}</td>
                  <td className="text-right py-2 px-3 text-orange-400 text-xs">{cr(-r.dii_sell)}</td>
                  <td className={`text-right py-2 px-3 font-semibold text-xs ${r.dii_net >= 0 ? 'text-blue-400' : 'text-orange-400'}`}>{cr(r.dii_net)}</td>
                  <td className="text-right py-2 px-3 text-xs">
                    {r.sentiment_score != null ? (
                      <span className={`px-2 py-0.5 rounded-full ${r.sentiment_score >= 60 ? 'bg-emerald-500/20 text-emerald-400' : r.sentiment_score >= 40 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'}`}>
                        {r.sentiment_score}
                      </span>
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-slate-600 text-right">
        Data: MrChartist/fii-dii-data (GitHub) · Cache: 4h · Source: NSE India
      </p>
    </div>
  );
};

export default FiiDii;
