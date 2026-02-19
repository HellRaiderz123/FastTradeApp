import React, { useState, useEffect } from 'react';
import { RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { financeAPI } from '../lib/api';

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

  useEffect(() => {
    loadPositions();
    const interval = setInterval(loadPositions, 30000); // Refresh every 30s
    return () => clearInterval(interval);
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
