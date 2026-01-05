import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, X } from 'lucide-react';
import { paperAPI, exitAPI, journalAPI } from '../lib/api';
import { useTradeStore } from '../lib/store';

const Positions: React.FC = () => {
  const { trades, setTrades } = useTradeStore();
  const [loading, setLoading] = useState(false);
  const [localTrades, setLocalTrades] = useState<any[]>([]);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchPositions = async () => {
    try {
      setLoading(true);
      // Fetch execution intents (active trades)
      const response = await journalAPI.getExecutionIntents(50);
      const activeIntents = response.data.filter((intent: any) => intent.status === 'EXECUTED');
      setLocalTrades(activeIntents);
    } catch (error) {
      console.error('Failed to fetch positions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleClosePosition = async (tradeId: number) => {
    setLoading(true);
    try {
      await exitAPI.manualExit(tradeId.toString());
      setLocalTrades(localTrades.filter((t) => t.id !== tradeId));
      alert('Position closed successfully!');
    } catch (error) {
      console.error('Failed to close position:', error);
      alert('Failed to close position');
    } finally {
      setLoading(false);
    }
  };

  const displayTrades = localTrades.length > 0 ? localTrades : trades;
  const openPositions = displayTrades.filter((t) => t.status === 'EXECUTED');
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
                key={trade.id}
                trade={trade}
                onClose={() => handleClosePosition(trade.id)}
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
  const isProfitable = trade.pnl >= 0;
  const tpHit = trade.pnl >= trade.tp;
  const slHit = trade.pnl <= trade.sl;

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
            <p className="text-xs text-slate-400">{trade.underlying} • Opened: {new Date(trade.entry_time).toLocaleString()}</p>
          </div>
        </div>
        <button
          onClick={onClose}
          disabled={loading}
          className="text-slate-400 hover:text-red-400 transition"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 py-3 border-t border-b border-slate-700">
        <div>
          <p className="text-xs text-slate-400">Entry</p>
          <p className="font-semibold text-white">₹{trade.entry_price.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Current</p>
          <p className="font-semibold text-white">₹{trade.current_price.toLocaleString()}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">P&L</p>
          <p className={`font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            ₹{Math.abs(trade.pnl).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">TP: {trade.tp}</p>
          <p className={`font-semibold ${tpHit ? 'text-green-400 animate-pulse' : 'text-slate-300'}`}>
            {tpHit ? '✓ TP Hit' : '-'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">SL: {trade.sl}</p>
          <p className={`font-semibold ${slHit ? 'text-red-400 animate-pulse' : 'text-slate-300'}`}>
            {slHit ? '✗ SL Hit' : '-'}
          </p>
        </div>
      </div>

      <div className="flex justify-between items-center mt-3">
        <p className={`text-sm font-medium ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
          {isProfitable ? '+' : ''}{trade.pnl_percent.toFixed(2)}%
        </p>
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
