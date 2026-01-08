import React, { useState, useEffect, useRef } from 'react';
import { TrendingUp, TrendingDown, X } from 'lucide-react';
import { exitAPI, journalAPI } from '../lib/api';
import { useTradeStore } from '../lib/store';

const Positions: React.FC = () => {
  const { trades, setTrades } = useTradeStore();
  const [loading, setLoading] = useState(false);
  const [localTrades, setLocalTrades] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    fetchPositions();

    // Poll as a fallback (e.g., if WS is blocked)
    pollRef.current = window.setInterval(fetchPositions, 30000);

    // Live updates via WebSocket
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const wsUrl = `${proto}://${window.location.host}/api/ws/positions`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Once live is connected, polling is less important.
        if (pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg?.type !== 'positions_update') return;
          const updates = Array.isArray(msg?.intents) ? msg.intents : [];

          setLocalTrades((prev) => {
            const byId = new Map<string, any>();
            for (const t of Array.isArray(prev) ? prev : []) {
              const id = String(t?.intent_id ?? '');
              if (id) byId.set(id, t);
            }
            for (const u of updates) {
              const id = String(u?.intent_id ?? '');
              if (!id) continue;
              byId.set(id, { ...(byId.get(id) || {}), ...u });
            }
            return Array.from(byId.values());
          });
        } catch (e) {
          // ignore malformed messages
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
        // Restore polling if live stream drops
        if (!pollRef.current) {
          pollRef.current = window.setInterval(fetchPositions, 30000);
        }
      };

      ws.onerror = () => {
        // Let onclose restore polling
      };
    } catch (e) {
      // Keep polling only
    }

    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
      if (wsRef.current) wsRef.current.close();
      wsRef.current = null;
    };
  }, []);

  const fetchPositions = async () => {
    try {
      setLoading(true);
      // Fetch execution intents (active trades)
      const response = await journalAPI.getExecutionIntents(50);
      const data = response?.data;
      const intents = Array.isArray(data) ? data : [];
      const activeIntents = intents.filter((intent: any) => intent?.status === 'EXECUTED');
      setLocalTrades(activeIntents);
    } catch (error) {
      console.error('Failed to fetch positions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleClosePosition = async (intentId: string) => {
    setLoading(true);
    try {
      await exitAPI.manualExit(intentId);
      setLocalTrades(localTrades.filter((t) => t.intent_id !== intentId));
      alert('Position closed successfully!');
    } catch (error) {
      console.error('Failed to close position:', error);
      alert('Failed to close position');
    } finally {
      setLoading(false);
    }
  };

  const displayTrades = localTrades.length > 0 ? localTrades : trades;
  const openPositions = displayTrades.filter((t) => t?.status === 'EXECUTED');
  const totalPnL = openPositions.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const totalPnLPercent = openPositions.length > 0 ? (totalPnL / 100000) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Open Positions"
          value={openPositions.length.toString()}
          color="blue"
        />
        <SummaryCard
          label="Total P&L"
          value={`₹${totalPnL.toLocaleString()}`}
          subtext={`${totalPnLPercent.toFixed(2)}%`}
          color={totalPnL >= 0 ? 'green' : 'red'}
        />
        <SummaryCard
          label="Avg P&L per Trade"
          value={`₹${openPositions.length > 0 ? Math.round(totalPnL / openPositions.length) : 0}`}
          color="purple"
        />
        <SummaryCard
          label="Largest Win"
          value={`₹${Math.max(0, ...openPositions.map((t) => t.pnl || 0)).toLocaleString()}`}
          color="green"
        />
      </div>

      {/* Positions List */}
      <div className="card-glass p-6">
        <h2 className="text-2xl font-bold mb-6 text-white">Open Positions {loading && '(updating...)'}</h2>

        {openPositions.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-400 mb-4">No open positions</p>
            <p className="text-sm text-slate-500">Execute a strategy to open a position</p>
          </div>
        ) : (
          <div className="space-y-4">
            {openPositions.map((trade) => (
              <PositionCard
                key={trade.intent_id || trade.id}
                trade={trade}
                onClose={() => handleClosePosition(String(trade.intent_id || ''))}
                loading={loading}
              />
            ))}
          </div>
        )}
      </div>

      {/* Risk Metrics */}
      <div className="card-glass p-6">
        <h3 className="text-lg font-semibold mb-4 text-white">Risk Metrics</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <RiskMetric label="Portfolio Heat" value="2.5%" status="good" />
          <RiskMetric label="Max Drawdown" value="-1.2%" status="warning" />
          <RiskMetric label="Daily Loss Limit" value="2.0%" status="good" />
        </div>
      </div>

      {/* Coming Soon */}
      <div className="card-glass p-6 opacity-50">
        <h3 className="text-lg font-semibold text-slate-300 mb-4">More Features Coming</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {['Hedge Positions', 'Adjust Strikes', 'Add to Position', 'Share Strategy'].map(
            (feature) => (
              <div key={feature} className="text-center py-6 bg-slate-900/50 rounded-lg">
                <p className="text-sm text-slate-400">{feature}</p>
              </div>
            )
          )}
        </div>
      </div>
    </div>
  );
};

interface SummaryCardProps {
  label: string;
  value: string;
  subtext?: string;
  color: string;
}

const SummaryCard: React.FC<SummaryCardProps> = ({ label, value, subtext, color }) => {
  const bgClass = {
    blue: 'from-blue-500/20',
    green: 'from-green-500/20',
    red: 'from-red-500/20',
    purple: 'from-purple-500/20',
  }[color] || 'from-slate-500/20';

  return (
    <div className={`card-glass p-4 bg-gradient-to-br ${bgClass}`}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  );
};

interface PositionCardProps {
  trade: any;
  onClose: () => void;
  loading: boolean;
}

const PositionCard: React.FC<PositionCardProps> = ({ trade, onClose, loading }) => {
  const [showLegs, setShowLegs] = React.useState(false);
  
  const pnl = Number(trade?.pnl ?? trade?.unrealized_pnl ?? 0);
  const tp = trade?.tp !== null && trade?.tp !== undefined ? Number(trade.tp) : null;
  const sl = trade?.sl !== null && trade?.sl !== undefined ? Number(trade.sl) : null;
  const entryCredit = Number(trade?.entry_credit ?? trade?.entry_price ?? 0);
  const marginRequired = Number(trade?.margin_required ?? 0);

  const isProfitable = pnl >= 0;
  const tpHit = tp !== null ? pnl >= tp : false;
  const slHit = sl !== null ? pnl <= sl : false;

  const openedAtRaw = trade?.created_at ?? trade?.entry_time ?? trade?.filled_at;
  const openedAtLabel = openedAtRaw ? new Date(openedAtRaw).toLocaleString() : '-';

  // If pnl is computed as (entry_credit - cost_to_close), then cost_to_close = entry_credit - pnl.
  const currentValue = entryCredit - pnl;
  // Percent metrics
  const pnlPercentPremium = entryCredit !== 0 ? (pnl / Math.abs(entryCredit)) * 100 : null;
  const pnlPercentMargin = marginRequired > 0 ? (pnl / marginRequired) * 100 : null;
  
  // Extract legs from ticket
  const legs = trade?.ticket?.legs || [];
  const legsMetrics = trade?.legs_metrics || [];
  const mode = trade?.mode || 'UNKNOWN';
  
  // Show margin only for Zerodha modes
  const isZerodhaMode = mode && String(mode).toUpperCase().includes('ZERODHA');

  return (
    <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 hover:border-slate-600 transition">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          {isProfitable ? (
            <TrendingUp className="w-6 h-6 text-green-400" />
          ) : (
            <TrendingDown className="w-6 h-6 text-red-400" />
          )}
          <div>
            <p className="font-semibold text-white">{trade.strategy}</p>
            <p className="text-xs text-slate-400">
              {trade.underlying} • {mode} • Opened: {openedAtLabel}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          disabled={loading}
          aria-label="Close position"
          title="Close position"
          className="text-slate-400 hover:text-red-400 transition"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className={`grid gap-4 py-3 border-t border-b border-slate-700 ${isZerodhaMode && marginRequired > 0 ? 'grid-cols-2 md:grid-cols-6' : 'grid-cols-2 md:grid-cols-5'}`}>
        <div>
          <p className="text-xs text-slate-400">Premium {isZerodhaMode ? 'Collected' : ''}</p>
          <p className="font-semibold text-white">₹{entryCredit.toLocaleString()}</p>
        </div>
        {isZerodhaMode && marginRequired > 0 && (
          <div>
            <p className="text-xs text-slate-400">Margin Blocked</p>
            <p className="font-semibold text-amber-400">₹{marginRequired.toLocaleString()}</p>
          </div>
        )}
        <div>
          <p className="text-xs text-slate-400">Current</p>
          <p className="font-semibold text-white">₹{Number.isFinite(currentValue) ? currentValue.toLocaleString() : '-'}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">P&L</p>
          <p className={`font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            ₹{Math.abs(pnl).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">TP: {tp ?? '-'}</p>
          <p className={`font-semibold ${tpHit ? 'text-green-400 animate-pulse' : 'text-slate-300'}`}>
            {tpHit ? '✓ TP Hit' : '-'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">SL: {sl ?? '-'}</p>
          <p className={`font-semibold ${slHit ? 'text-red-400 animate-pulse' : 'text-slate-300'}`}>
            {slHit ? '✗ SL Hit' : '-'}
          </p>
        </div>
      </div>

      {/* Legs Section - Expandable */}
      {legs.length > 0 && (
        <div className="mt-3 border-t border-slate-700 pt-3">
          <button
            onClick={() => setShowLegs(!showLegs)}
            className="text-xs text-slate-400 hover:text-slate-300 transition flex items-center gap-2"
          >
            <span>{showLegs ? '▼' : '▶'}</span>
            <span>{legs.length} Leg{legs.length > 1 ? 's' : ''}</span>
          </button>
          
          {showLegs && (
            <div className="mt-2 space-y-1">
              {legs.map((leg: any, idx: number) => {
                const m = Array.isArray(legsMetrics) ? legsMetrics[idx] : undefined;
                const legPnl = m?.pnl_total ?? null;
                const legLtp = m?.ltp ?? null;
                const legEntry = m?.entry ?? leg.price ?? null;
                const isLegProfit = typeof legPnl === 'number' ? legPnl >= 0 : null;
                return (
                  <div key={idx} className="text-xs bg-slate-800/50 p-2 rounded flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded ${
                        leg.side === 'SELL' ? 'bg-red-500/20 text-red-300' : 'bg-green-500/20 text-green-300'
                      }`}>
                        {leg.side}
                      </span>
                      <span className="text-slate-300 font-mono">
                        {leg.strike} {leg.type}
                      </span>
                      {leg.symbol && (
                        <span className="text-slate-500 text-[10px]">{leg.symbol}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      {typeof legEntry === 'number' ? (
                        <span className="text-slate-400">Entry ₹{legEntry}</span>
                      ) : (
                        <span className="text-slate-600">Entry N/A</span>
                      )}
                      {typeof legLtp === 'number' && (
                        <span className="text-slate-400">LTP ₹{legLtp}</span>
                      )}
                      {typeof legPnl === 'number' ? (
                        <span className={`font-semibold ${isLegProfit ? 'text-green-400' : 'text-red-400'}`}>
                          P&L ₹{Math.abs(legPnl).toLocaleString()}
                        </span>
                      ) : (
                        <span className="text-slate-600">P&L N/A</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div className="flex justify-between items-center mt-3">
        <div className="flex items-center gap-3">
          <p className={`text-sm font-medium ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            {pnlPercentPremium === null ? '-' : `${isProfitable ? '+' : ''}${pnlPercentPremium.toFixed(2)}%`}
          </p>
          {isZerodhaMode && pnlPercentMargin !== null && (
            <p className="text-xs font-medium text-amber-400">
              ROM: {`${pnlPercentMargin >= 0 ? '+' : ''}${pnlPercentMargin.toFixed(2)}%`}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="btn-danger py-1 px-3 text-sm"
          disabled={loading}
        >
          {loading ? 'Closing...' : 'Close'}
        </button>
      </div>
    </div>
  );
};

const RiskMetric: React.FC<{ label: string; value: string; status: 'good' | 'warning' | 'danger' }> = ({
  label,
  value,
  status,
}) => {
  const statusColor = {
    good: 'text-green-400',
    warning: 'text-orange-400',
    danger: 'text-red-400',
  }[status];

  return (
    <div className="bg-slate-900/50 p-4 rounded-lg">
      <p className="text-xs text-slate-400 mb-2">{label}</p>
      <p className={`text-2xl font-bold ${statusColor}`}>{value}</p>
    </div>
  );
};

export default Positions;
