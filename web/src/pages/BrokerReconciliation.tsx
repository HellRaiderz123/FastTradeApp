import React, { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle, AlertTriangle, Clock, TrendingUp, TrendingDown, Play } from 'lucide-react';
import api from '../lib/api';

interface IntentRow {
  intent_id: string;
  strategy: string;
  underlying: string;
  status: string;
  mode: string;
  pnl: number | null;
  created_at: string | null;
  closed_at: string | null;
  exit_reason: string | null;
}

interface ReconcileStatus {
  open_intents: IntentRow[];
  broker_closed_log: IntentRow[];
  open_count: number;
  broker_closed_count: number;
}

const BrokerReconciliation: React.FC = () => {
  const [status, setStatus] = useState<ReconcileStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [syncResult, setSyncResult] = useState<{ closed_count: number; closed_ids: string[] } | null>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await api.get('/reconcile/status');
      setStatus(res.data);
    } catch (e) {
      console.error('Failed to fetch reconciliation status:', e);
    } finally {
      setLoading(false);
    }
  };

  const runSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const res = await api.post('/reconcile/run');
      setSyncResult({ closed_count: res.data.closed_count, closed_ids: res.data.closed_ids });
      setLastSync(new Date().toLocaleTimeString());
      await fetchStatus();
    } catch (e) {
      console.error('Reconciliation failed:', e);
    } finally {
      setSyncing(false);
    }
  };

  const fmtPnl = (pnl: number | null) => {
    if (pnl === null || pnl === undefined) return '-';
    return `₹${Math.abs(pnl).toLocaleString()}`;
  };

  const fmtDate = (d: string | null) => {
    if (!d) return '-';
    return new Date(d).toLocaleString();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <RefreshCw className="w-8 h-8 text-blue-400" />
            Broker Reconciliation
          </h1>
          <p className="text-slate-400 mt-1">
            Detect positions closed directly on Zerodha and sync them to FastTrade
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastSync && (
            <span className="text-xs text-slate-400 flex items-center gap-1">
              <Clock className="w-3 h-3" /> Last sync: {lastSync}
            </span>
          )}
          <button
            onClick={fetchStatus}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition text-sm"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={runSync}
            disabled={syncing}
            className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white rounded-lg transition font-semibold"
          >
            <Play className={`w-4 h-4 ${syncing ? 'animate-pulse' : ''}`} />
            {syncing ? 'Syncing...' : 'One-Click Sync'}
          </button>
        </div>
      </div>

      {/* Sync Result Banner */}
      {syncResult && (
        <div className={`p-4 rounded-lg border flex items-center gap-3 ${
          syncResult.closed_count > 0
            ? 'bg-green-500/10 border-green-500/40 text-green-300'
            : 'bg-blue-500/10 border-blue-500/40 text-blue-300'
        }`}>
          <CheckCircle className="w-5 h-5 flex-shrink-0" />
          <div>
            {syncResult.closed_count > 0 ? (
              <>
                <p className="font-semibold">Synced {syncResult.closed_count} position{syncResult.closed_count > 1 ? 's' : ''} from Zerodha</p>
                <p className="text-xs mt-0.5 opacity-80">IDs: {syncResult.closed_ids.join(', ')}</p>
              </>
            ) : (
              <p className="font-semibold">All positions are in sync — no discrepancies found</p>
            )}
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card-glass p-5">
          <p className="text-xs text-slate-400 mb-1">Open in FastTrade</p>
          <p className="text-3xl font-bold text-white">{status?.open_count ?? '-'}</p>
          <p className="text-xs text-slate-500 mt-1">EXECUTED positions not yet closed</p>
        </div>
        <div className="card-glass p-5">
          <p className="text-xs text-slate-400 mb-1">Auto-Closed by Reconciler</p>
          <p className="text-3xl font-bold text-green-400">{status?.broker_closed_count ?? '-'}</p>
          <p className="text-xs text-slate-500 mt-1">Positions synced from Zerodha</p>
        </div>
        <div className="card-glass p-5 bg-amber-500/5 border border-amber-500/20">
          <p className="text-xs text-slate-400 mb-1">How it works</p>
          <p className="text-sm text-amber-300 leading-relaxed">
            Compares local EXECUTED positions against Zerodha's live net positions. Any position with zero quantity at broker gets marked CLOSED.
          </p>
        </div>
      </div>

      {/* Open Positions (potential discrepancies) */}
      <div className="card-glass p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          Open Positions in FastTrade
          <span className="text-xs text-slate-400 font-normal ml-1">(may be stale if closed on Zerodha)</span>
        </h2>

        {loading ? (
          <div className="text-center py-8 text-slate-400">Loading...</div>
        ) : !status?.open_intents.length ? (
          <div className="text-center py-8 text-slate-400">
            <CheckCircle className="w-10 h-10 mx-auto mb-2 text-green-400" />
            No open positions — everything is in sync
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="pb-3 pr-4">Strategy</th>
                  <th className="pb-3 pr-4">Underlying</th>
                  <th className="pb-3 pr-4">Mode</th>
                  <th className="pb-3 pr-4">P&L</th>
                  <th className="pb-3 pr-4">Opened</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {status.open_intents.map((row) => (
                  <tr key={row.intent_id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 pr-4 text-white font-medium">{row.strategy}</td>
                    <td className="py-3 pr-4 text-slate-300">{row.underlying}</td>
                    <td className="py-3 pr-4">
                      <span className={`text-xs px-2 py-0.5 rounded border ${
                        row.mode.includes('LIVE')
                          ? 'bg-red-500/20 text-red-300 border-red-500/30'
                          : row.mode.includes('ZERODHA')
                          ? 'bg-blue-500/20 text-blue-300 border-blue-500/30'
                          : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                      }`}>
                        {row.mode || 'PAPER'}
                      </span>
                    </td>
                    <td className="py-3 pr-4">
                      {row.pnl !== null ? (
                        <span className={row.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {row.pnl >= 0 ? '+' : '-'}{fmtPnl(row.pnl)}
                        </span>
                      ) : <span className="text-slate-500">-</span>}
                    </td>
                    <td className="py-3 pr-4 text-slate-400 text-xs">{fmtDate(row.created_at)}</td>
                    <td className="py-3">
                      <span className="text-xs px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Reconciliation Audit Log */}
      <div className="card-glass p-6">
        <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
          <CheckCircle className="w-5 h-5 text-green-400" />
          Reconciliation Audit Log
          <span className="text-xs text-slate-400 font-normal ml-1">(positions auto-closed by reconciler)</span>
        </h2>

        {!status?.broker_closed_log.length ? (
          <div className="text-center py-8 text-slate-400">No reconciliation events yet</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="pb-3 pr-4">Strategy</th>
                  <th className="pb-3 pr-4">Underlying</th>
                  <th className="pb-3 pr-4">P&L</th>
                  <th className="pb-3 pr-4">Opened</th>
                  <th className="pb-3 pr-4">Closed At</th>
                  <th className="pb-3">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {status.broker_closed_log.map((row) => (
                  <tr key={row.intent_id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 pr-4 text-white font-medium">{row.strategy}</td>
                    <td className="py-3 pr-4 text-slate-300">{row.underlying}</td>
                    <td className="py-3 pr-4">
                      {row.pnl !== null ? (
                        <span className={`flex items-center gap-1 ${row.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {row.pnl >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                          {row.pnl >= 0 ? '+' : '-'}{fmtPnl(row.pnl)}
                        </span>
                      ) : <span className="text-slate-500">-</span>}
                    </td>
                    <td className="py-3 pr-4 text-slate-400 text-xs">{fmtDate(row.created_at)}</td>
                    <td className="py-3 pr-4 text-slate-400 text-xs">{fmtDate(row.closed_at)}</td>
                    <td className="py-3">
                      <span className="text-xs px-2 py-0.5 rounded bg-green-500/20 text-green-300 border border-green-500/30">
                        {row.exit_reason || 'BROKER_CLOSED'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default BrokerReconciliation;
