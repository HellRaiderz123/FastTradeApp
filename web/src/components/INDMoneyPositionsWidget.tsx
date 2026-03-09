import React, { useEffect, useState } from 'react';
import { RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';
import { financeAPI } from '../lib/api';

interface INDMoneyPosition {
  tradingsymbol?: string;
  trading_symbol?: string;
  symbol?: string;
  quantity?: number;
  qty?: number;
  net_quantity?: number;
  average_price?: number;
  avg_price?: number;
  last_traded_price?: number;
  last_price?: number;
  ltp?: number;
  pnl?: number;
  m2m?: number;
}

function pickSymbol(p: INDMoneyPosition): string {
  return p.tradingsymbol || p.trading_symbol || p.symbol || '-';
}

function pickQty(p: INDMoneyPosition): number {
  return Number(p.quantity ?? p.qty ?? p.net_quantity ?? 0);
}

function pickAvg(p: INDMoneyPosition): number {
  return Number(p.average_price ?? p.avg_price ?? 0);
}

function pickLtp(p: INDMoneyPosition): number {
  return Number(p.last_traded_price ?? p.last_price ?? p.ltp ?? 0);
}

function pickPnl(p: INDMoneyPosition): number {
  return Number(p.pnl ?? p.m2m ?? 0);
}

export default function INDMoneyPositionsWidget() {
  const [positions, setPositions] = useState<INDMoneyPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPositions = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await financeAPI.getINDMoneyPositions({ segment: 'derivative', product: 'margin' });
      const netPositions = res.data?.net || [];
      setPositions(Array.isArray(netPositions) ? netPositions : []);
    } catch (err) {
      setError('Failed to load INDMoney positions');
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPositions();
    const interval = setInterval(loadPositions, 30000);
    return () => clearInterval(interval);
  }, []);

  const totalPnL = positions.reduce((sum, p) => sum + pickPnl(p), 0);
  const openPositions = positions.filter((p) => pickQty(p) !== 0);
  const winningPositions = openPositions.filter((p) => pickPnl(p) > 0).length;
  const losingPositions = openPositions.filter((p) => pickPnl(p) < 0).length;

  return (
    <div className="card-glass p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-2xl font-bold text-white">INDMoney Live Positions</h3>
        <button
          onClick={loadPositions}
          disabled={loading}
          className="px-3 py-1 bg-indigo-600 hover:bg-indigo-700 rounded text-sm text-white flex items-center gap-1 disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {openPositions.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-slate-700/30 p-3 rounded text-center">
            <p className="text-xs text-slate-400">Total P&L</p>
            <p className={`text-lg font-bold ${totalPnL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              Rs {Math.abs(totalPnL).toLocaleString()}
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

      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded p-3 mb-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {openPositions.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-slate-400">
            {loading ? 'Loading positions...' : 'No open positions on INDMoney'}
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
              {openPositions.map((pos, idx) => {
                const avg = pickAvg(pos);
                const ltp = pickLtp(pos);
                const pnl = pickPnl(pos);
                const pnlPercent = avg > 0 ? ((ltp - avg) / avg) * 100 : 0;
                const isProfitable = pnl >= 0;

                return (
                  <tr key={idx} className={`hover:bg-slate-700/20 ${isProfitable ? 'bg-green-900/10' : 'bg-red-900/10'}`}>
                    <td className="px-4 py-2 text-white font-medium">
                      <div className="flex items-center gap-2">
                        {isProfitable ? (
                          <TrendingUp size={14} className="text-green-400" />
                        ) : (
                          <TrendingDown size={14} className="text-red-400" />
                        )}
                        {pickSymbol(pos)}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right text-slate-300">{pickQty(pos)}</td>
                    <td className="px-4 py-2 text-right text-slate-300">Rs {avg.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right text-slate-300">Rs {ltp.toFixed(2)}</td>
                    <td className={`px-4 py-2 text-right font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                      Rs {pnl.toFixed(2)}
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
        Data from INDMoney • Updated every 30 seconds
      </p>
    </div>
  );
}
