import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Play, Square, RefreshCw, Terminal, Activity, TrendingUp,
  TrendingDown, AlertTriangle, CheckCircle2, Zap,
} from 'lucide-react';
import api, { authTokenStore } from '../lib/api';

const API = (import.meta as any).env?.VITE_API_BASE || '';

interface Position {
  strategy: string;
  current_pnl: number;
  max_profit: number;
  max_loss: number;
  net_credit: number;
  entry_time: string;
  legs: { side: string; symbol: string; strike: number; type: string; qty: number; price: number }[];
}

interface Status {
  running: boolean;
  underlying: string;
  mode: string;
  session_pnl: number;
  trade_count: number;
  started_at: string | null;
  position: Position | null;
}

const DEFAULT_CONFIG = {
  underlying: 'NIFTY',
  mode: 'PAPER',
  stop_loss: 3000,
  target: 2000,
  daily_limit: 5000,
  lots: 1,
};

function pnlColor(v: number) {
  return v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-slate-400';
}

const ScalpTrading: React.FC = () => {
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [status, setStatus] = useState<Status | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const authHeaders = useCallback(() => {
    const token = authTokenStore.get();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const r = await api.get('/scalp/status');
      setStatus(r.data);
    } catch { /* ignore */ }
  }, []);

  const fetchLogs = useCallback(async () => {
    try {
      const r = await api.get('/scalp/logs?limit=200');
      setLogs(r.data.lines || []);
    } catch { /* ignore */ }
  }, []);

  // Poll status every 5s
  useEffect(() => {
    fetchStatus();
    fetchLogs();
    pollRef.current = setInterval(() => {
      fetchStatus();
      fetchLogs();
    }, 5000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [fetchStatus, fetchLogs]);

  // SSE stream when running
  useEffect(() => {
    if (!status?.running) {
      esRef.current?.close();
      esRef.current = null;
      return;
    }
    if (esRef.current) return; // already connected

    const token = authTokenStore.get();
    const url = `${API}/scalp/stream${token ? `?token=${token}` : ''}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.line) setLogs(prev => [...prev.slice(-499), d.line]);
        if (d.done) { es.close(); esRef.current = null; }
      } catch { /* ignore */ }
    };
    es.onerror = () => { es.close(); esRef.current = null; };

    return () => { es.close(); esRef.current = null; };
  }, [status?.running]);

  // Auto-scroll logs
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const handleStart = async () => {
    setLoading(true);
    try {
      await api.post('/scalp/start', config);
      setLogs([]);
      await fetchStatus();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Failed to start');
    }
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await api.post('/scalp/stop');
      await fetchStatus();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Failed to stop');
    }
    setLoading(false);
  };

  const running = status?.running ?? false;
  const pos = status?.position;

  return (
    <div className="min-h-screen bg-slate-900 p-6 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Zap className="w-7 h-7 text-yellow-400" />
            Scalp Trading
          </h1>
          <p className="text-slate-400 mt-1 text-sm">
            Live paper options engine — IRON_CONDOR / BULL_PUT / BEAR_CALL on NIFTY/BANKNIFTY
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${
            running
              ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
              : 'bg-slate-700/50 border-slate-600 text-slate-400'
          }`}>
            <Activity className={`w-3.5 h-3.5 ${running ? 'animate-pulse' : ''}`} />
            {running ? 'LIVE' : 'STOPPED'}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Config + Controls */}
        <div className="space-y-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 space-y-3">
            <h2 className="text-sm font-semibold text-white">Configuration</h2>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Underlying</label>
                <select
                  value={config.underlying}
                  onChange={e => setConfig(c => ({ ...c, underlying: e.target.value }))}
                  disabled={running}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none disabled:opacity-50"
                >
                  <option>NIFTY</option>
                  <option>BANKNIFTY</option>
                  <option>FINNIFTY</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-slate-400 mb-1 block">Mode</label>
                <select
                  value={config.mode}
                  onChange={e => setConfig(c => ({ ...c, mode: e.target.value }))}
                  disabled={running}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none disabled:opacity-50"
                >
                  <option>PAPER</option>
                  <option>DRY_RUN</option>
                </select>
              </div>
            </div>

            {[
              { key: 'stop_loss', label: 'Stop Loss (₹)' },
              { key: 'target', label: 'Target (₹)' },
              { key: 'daily_limit', label: 'Daily Limit (₹)' },
              { key: 'lots', label: 'Lots' },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="text-xs text-slate-400 mb-1 block">{label}</label>
                <input
                  type="number"
                  value={(config as any)[key]}
                  onChange={e => setConfig(c => ({ ...c, [key]: Number(e.target.value) }))}
                  disabled={running}
                  className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none disabled:opacity-50"
                />
              </div>
            ))}

            <div className="flex gap-2 pt-1">
              {!running ? (
                <button
                  onClick={handleStart}
                  disabled={loading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 text-white font-semibold rounded-lg transition text-sm"
                >
                  <Play className="w-4 h-4" />
                  Start Session
                </button>
              ) : (
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-red-600 hover:bg-red-500 disabled:bg-slate-600 text-white font-semibold rounded-lg transition text-sm"
                >
                  <Square className="w-4 h-4" />
                  Stop Session
                </button>
              )}
              <button
                onClick={() => { fetchStatus(); fetchLogs(); }}
                className="px-3 py-2.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Session Stats */}
          {status && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 space-y-3">
              <h2 className="text-sm font-semibold text-white">Session Stats</h2>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="bg-slate-700/50 rounded-lg p-2.5">
                  <p className="text-xs text-slate-400">Session P&L</p>
                  <p className={`text-lg font-bold ${pnlColor(status.session_pnl)}`}>
                    ₹{status.session_pnl.toFixed(2)}
                  </p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-2.5">
                  <p className="text-xs text-slate-400">Trades</p>
                  <p className="text-lg font-bold text-white">{status.trade_count}</p>
                </div>
              </div>
            </div>
          )}

          {/* Open Position */}
          {pos && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-white">Open Position</h2>
                <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 font-semibold">
                  {pos.strategy}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="bg-slate-700/50 rounded-lg p-2.5">
                  <p className="text-xs text-slate-400">Current P&L</p>
                  <p className={`text-base font-bold ${pnlColor(pos.current_pnl)}`}>
                    ₹{pos.current_pnl.toFixed(2)}
                  </p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-2.5">
                  <p className="text-xs text-slate-400">Net Credit</p>
                  <p className="text-base font-bold text-emerald-400">₹{pos.net_credit.toFixed(2)}</p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-2.5">
                  <p className="text-xs text-slate-400">Max Profit</p>
                  <p className="text-base font-bold text-emerald-400">₹{pos.max_profit.toFixed(2)}</p>
                </div>
                <div className="bg-slate-700/50 rounded-lg p-2.5">
                  <p className="text-xs text-slate-400">Max Loss</p>
                  <p className="text-base font-bold text-red-400">₹{pos.max_loss.toFixed(2)}</p>
                </div>
              </div>
              <div className="space-y-1">
                {pos.legs.map((leg, i) => (
                  <div key={i} className="flex items-center justify-between text-xs bg-slate-700/30 rounded px-2 py-1.5">
                    <span className={leg.side === 'SELL' ? 'text-red-400 font-semibold' : 'text-emerald-400 font-semibold'}>
                      {leg.side}
                    </span>
                    <span className="text-slate-300 font-mono text-[10px] truncate mx-2 flex-1">{leg.symbol}</span>
                    <span className="text-slate-400">₹{leg.price.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Terminal Log */}
        <div className="xl:col-span-2">
          <div className="bg-slate-950 border border-slate-700 rounded-xl overflow-hidden h-full flex flex-col" style={{ minHeight: '600px' }}>
            <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 border-b border-slate-700">
              <Terminal className="w-4 h-4 text-emerald-400" />
              <span className="text-sm font-semibold text-white">Engine Terminal</span>
              {running && (
                <span className="ml-auto flex items-center gap-1.5 text-xs text-emerald-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  LIVE
                </span>
              )}
            </div>
            <div
              ref={logRef}
              className="flex-1 overflow-y-auto p-4 font-mono text-xs leading-relaxed"
              style={{ maxHeight: '560px' }}
            >
              {logs.length === 0 ? (
                <p className="text-slate-600">No logs yet. Start a session to see output.</p>
              ) : (
                logs.map((line, i) => {
                  const isError = line.includes('ERROR') || line.includes('STOP LOSS') || line.includes('DAILY LIMIT');
                  const isSuccess = line.includes('ENTERED') || line.includes('TARGET HIT') || line.includes('started');
                  const isWarn = line.includes('Decision') || line.includes('Trade |') || line.includes('MTM');
                  return (
                    <div
                      key={i}
                      className={`${
                        isError ? 'text-red-400' :
                        isSuccess ? 'text-emerald-400' :
                        isWarn ? 'text-yellow-300' :
                        'text-slate-300'
                      }`}
                    >
                      {line}
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScalpTrading;
