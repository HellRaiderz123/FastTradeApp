import React, { useState, useEffect } from 'react';
import { RefreshCw, TrendingUp, TrendingDown, AlertTriangle, Shield, Eye, CheckCircle, X  } from 'lucide-react';
import { financeAPI, smartSuggestionsAPI } from '../lib/api';

interface ZerodhaPosition {
  tradingsymbol: string;
  quantity: number;
  average_price: number;
  last_price: number;
  close_price: number;
  pnl: number;
  p_l: number;
  m2m: number;
  unrealised: number;
  realised: number;
  multiplier: number;
}

export default function ZerodhaPositionsWidget() {
  const [positions, setPositions] = useState<ZerodhaPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [spreadAdvice, setSpreadAdvice] = useState<any[]>([]);
  const [adviceDismissed, setAdviceDismissed] = useState<Set<number>>(new Set());

  const loadPositions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await financeAPI.getZerodhaPositions();
      const netPositions = res.data?.net || [];
      setPositions(netPositions.filter((p: ZerodhaPosition) => p.quantity !== 0));
    } catch (err) {
      setError('Failed to load Zerodha positions');
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadSmartSuggestions = async () => {
    try {
      const res = await smartSuggestionsAPI.get();
      const data = res?.data;
      if (data?.spread_suggestions?.length > 0) {
        setSpreadAdvice(data.spread_suggestions);
      }
    } catch (e) {
      console.debug('[ZerodhaPositions] Smart suggestions fetch failed:', e);
    }
  };

  useEffect(() => {
    loadPositions();
    loadSmartSuggestions();
    const interval = setInterval(loadPositions, 30000);
    const smartInterval = setInterval(loadSmartSuggestions, 60000);
    return () => { clearInterval(interval); clearInterval(smartInterval); };
  }, []);

  const totalPnL = positions.reduce((sum, p) => sum + (p.pnl || 0), 0);
  const winningPositions = positions.filter(p => (p.pnl || 0) > 0).length;
  const losingPositions = positions.filter(p => (p.pnl || 0) < 0).length;

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-2xl font-bold text-white">🔗 Zerodha Live Positions</h3>
        <button
          onClick={loadPositions}
          disabled={loading}
          className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white flex items-center gap-1 disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Summary Cards */}
      {positions.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-slate-700/30 p-3 rounded text-center">
            <p className="text-xs text-slate-400">Total P&L</p>
            <p className={`text-lg font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              ₹{Math.abs(totalPnL).toLocaleString()}
            </p>
          </div>
          <div className="bg-slate-700/30 p-3 rounded text-center">
            <p className="text-xs text-slate-400">Profits</p>
            <p className="text-lg font-bold text-green-400">{winningPositions}</p>
          </div>
          <div className="bg-slate-700/30 p-3 rounded text-center">
            <p className="text-xs text-slate-400">Losses</p>
            <p className="text-lg font-bold text-red-400">{losingPositions}</p>
          </div>
        </div>
      )}

      {/* Smart Position Suggestions */}
      {spreadAdvice.filter((_, i) => !adviceDismissed.has(i)).length > 0 && (
        <div className="space-y-2 mb-4">
          {spreadAdvice.map((ss, idx) => {
            if (adviceDismissed.has(idx)) return null;
            const advice = ss.advice || {};
            const severity = advice.severity || 'LOW';
            const action = advice.action || 'HOLD';
            if (severity === 'NONE') return null;

            const colorMap: Record<string, { bg: string; border: string; text: string; badge: string }> = {
              HIGH: { bg: 'bg-red-500/10', border: 'border-red-500/40', text: 'text-red-300', badge: 'bg-red-500/20 text-red-300 border-red-500/40' },
              MEDIUM: { bg: 'bg-amber-500/10', border: 'border-amber-500/40', text: 'text-amber-300', badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40' },
              LOW: { bg: 'bg-blue-500/10', border: 'border-blue-500/30', text: 'text-blue-300', badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30' },
            };
            const colors = colorMap[severity] || colorMap.LOW;

            const ActionIcon = { CONSIDER_EXIT: AlertTriangle, HEDGE_SUGGESTED: Shield, WATCH: Eye, HOLD: CheckCircle }[action] || Eye;
            const actionLabel = { CONSIDER_EXIT: 'Consider Exiting', HEDGE_SUGGESTED: 'Hedge Suggested', WATCH: 'Watch Closely', HOLD: 'Hold' }[action] || action;

            return (
              <SmartAdviceBanner
                key={idx}
                idx={idx}
                ss={ss}
                advice={advice}
                severity={severity}
                action={action}
                colors={colors}
                ActionIcon={ActionIcon}
                actionLabel={actionLabel}
                onDismiss={() => setAdviceDismissed(prev => new Set([...prev, idx]))}
              />
            );
          })}
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded p-3 mb-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Positions Table */}
      {positions.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-slate-400">
            {loading ? 'Loading positions...' : 'No open positions on Zerodha'}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/50 border-b border-slate-700">
              <tr>
                <th className="px-4 py-2 text-left text-slate-300">Symbol</th>
                <th className="px-4 py-2 text-right text-slate-300">Qty</th>
                <th className="px-4 py-2 text-right text-slate-300">Avg Price</th>
                <th className="px-4 py-2 text-right text-slate-300">LTP</th>
                <th className="px-4 py-2 text-right text-slate-300">P&L</th>
                <th className="px-4 py-2 text-right text-slate-300">% Return</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {positions.map((pos, idx) => {
                const pnlPercent = pos.average_price > 0 ? ((pos.last_price - pos.average_price) / pos.average_price) * 100 : 0;
                const isProfitable = (pos.pnl || 0) >= 0;

                return (
                  <tr key={idx} className={`hover:bg-slate-700/20 ${isProfitable ? 'bg-green-900/10' : 'bg-red-900/10'}`}>
                    <td className="px-4 py-2 text-white font-medium">
                      <div className="flex items-center gap-2">
                        {isProfitable ? (
                          <TrendingUp size={14} className="text-green-400" />
                        ) : (
                          <TrendingDown size={14} className="text-red-400" />
                        )}
                        {pos.tradingsymbol}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right text-slate-300">{pos.quantity}</td>
                    <td className="px-4 py-2 text-right text-slate-300">₹{pos.average_price.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right text-slate-300">₹{pos.last_price.toFixed(2)}</td>
                    <td className={`px-4 py-2 text-right font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                      ₹{(pos.pnl || 0).toFixed(2)}
                    </td>
                    <td className={`px-4 py-2 text-right font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                      {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-slate-500 mt-3 text-center">
        Data from Zerodha • Updated every 30 seconds
      </p>
    </div>
  );
}

// ── Smart Advice Banner (expandable) ────────────────────>>>>
function SmartAdviceBanner({
  idx, ss, advice, severity, action, colors, ActionIcon, actionLabel, onDismiss
}: {
  idx: number;
  ss: any;
  advice: any;
  severity: string;
  action: string;
  colors: { bg: string; border: string; text: string; badge: string };
  ActionIcon: React.ElementType;
  actionLabel: string;
  onDismiss: () => void;
}) {
  const [expanded, setExpanded] = React.useState(false);

  const currentBias = advice.current_signal_bias || '?';
  const confidence = advice.current_confidence || 0;
  const details = advice.details || '';
  const marketMode = advice.current_market_mode || '?';
  const ivRegime = advice.current_iv_regime || '?';
  const currentStrategy = advice.current_strategy_name || '?';

  return (
    <div className={`${colors.bg} border ${colors.border} rounded-lg p-3`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1">
          <ActionIcon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${colors.text}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-xs font-bold px-2 py-0.5 rounded border ${colors.badge}`}>
                🧠 {actionLabel}
              </span>
              <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded">
                {ss.spread_type?.replace(/_/g, ' ')} • {ss.underlying}
              </span>
              <span className="text-xs text-slate-400">
                TA: <span className={`font-semibold ${
                  currentBias === 'BULLISH' ? 'text-green-400' :
                  currentBias === 'BEARISH' ? 'text-red-400' : 'text-slate-300'
                }`}>{currentBias}</span> • {confidence}% conf
              </span>
            </div>
            <p className={`text-xs mt-1 ${colors.text}`}>{advice.reason}</p>

            {expanded && (
              <div className="mt-2 space-y-2">
                <p className="text-xs text-slate-400 leading-relaxed">{details}</p>
                <div className="flex flex-wrap gap-2">
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                    Now suggests: {currentStrategy}
                  </span>
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                    Market: {marketMode}
                  </span>
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                    IV: {ivRegime}
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-slate-500 hover:text-slate-300 transition px-1"
          >
            {expanded ? '▲' : '▼'}
          </button>
          <button onClick={onDismiss} className="text-slate-600 hover:text-slate-400 transition">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
