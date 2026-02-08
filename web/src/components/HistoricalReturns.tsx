import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Clock, AlertCircle } from 'lucide-react';
import axios from 'axios';
import { 
  calculateHistoricalReturns, 
  formatReturnPercent,
  type Candle,
  type HistoricalReturns as HistoricalReturnsType
} from '../utils/calculateReturns';

interface HistoricalReturnsProps {
  symbol: string;
  currentPrice: number;
}

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';

const HistoricalReturns: React.FC<HistoricalReturnsProps> = ({ symbol, currentPrice }) => {
  const [returns, setReturns] = useState<HistoricalReturnsType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHistoricalData = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch 1 year of daily candles
        const oneYearAgo = new Date();
        oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
        
        const fromDate = oneYearAgo.toISOString().split('T')[0];
        const toDate = new Date().toISOString().split('T')[0];

        const response = await axios.get(
          `${API_BASE}/market/candles/${symbol}`,
          {
            params: {
              interval: 'day',
              from_date: fromDate,
              to_date: toDate
            }
          }
        );

        if (response.data && response.data.candles) {
          const candles: Candle[] = response.data.candles;
          const calculatedReturns = calculateHistoricalReturns(candles, currentPrice, symbol);
          setReturns(calculatedReturns);
        } else {
          setError('No historical data available');
        }
      } catch (err: any) {
        console.error('Failed to fetch historical returns:', err);
        setError(err.response?.data?.detail || 'Failed to load historical data');
      } finally {
        setLoading(false);
      }
    };

    if (symbol && currentPrice > 0) {
      fetchHistoricalData();
    }
  }, [symbol, currentPrice]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Clock className="w-5 h-5 text-slate-400 animate-pulse" />
        <span className="ml-2 text-sm text-slate-400">Loading historical returns...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
        <AlertCircle className="w-4 h-4 text-red-400" />
        <span className="text-sm text-red-400">{error}</span>
      </div>
    );
  }

  if (!returns) {
    return null;
  }

  const periods = [
    { key: '1D' as const, label: '1D' },
    { key: '1W' as const, label: '1W' },
    { key: '1M' as const, label: '1M' },
    { key: '3M' as const, label: '3M' },
    { key: '6M' as const, label: '6M' },
    { key: '1Y' as const, label: '1Y' },
  ];

  return (
    <div className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-blue-400" />
          Historical Returns
        </h3>
        <span className="text-xs text-slate-500">Last Updated: {new Date().toLocaleTimeString()}</span>
      </div>

      {/* Returns Grid */}
      <div className="grid grid-cols-3 gap-3">
        {periods.map(({ key, label }) => {
          const periodReturn = returns.returns[key];
          
          if (!periodReturn) {
            return (
              <div
                key={key}
                className="bg-slate-800/40 rounded-lg p-3 border border-slate-700/30"
              >
                <div className="text-xs text-slate-500 mb-1">{label}</div>
                <div className="text-sm text-slate-600">N/A</div>
              </div>
            );
          }

          const { formatted, color } = formatReturnPercent(periodReturn.return_percent);
          const isPositive = periodReturn.return_percent >= 0;

          return (
            <div
              key={key}
              className={`rounded-lg p-3 border transition-all ${
                isPositive
                  ? 'bg-green-500/5 border-green-500/20 hover:bg-green-500/10'
                  : 'bg-red-500/5 border-red-500/20 hover:bg-red-500/10'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-slate-400">{label}</span>
                {isPositive ? (
                  <TrendingUp className="w-3 h-3 text-green-400" />
                ) : (
                  <TrendingDown className="w-3 h-3 text-red-400" />
                )}
              </div>
              <div className={`text-lg font-bold ${color}`}>
                {formatted}
              </div>
              <div className="text-xs text-slate-500 mt-1">
                ₹{periodReturn.start_price.toFixed(2)} → ₹{periodReturn.end_price.toFixed(2)}
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Stats */}
      <div className="mt-4 pt-4 border-t border-slate-700/50">
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-slate-500">Best Period: </span>
            <span className="text-slate-300 font-medium">
              {(() => {
                let bestPeriod = '';
                let bestReturn = -Infinity;
                periods.forEach(({ key, label }) => {
                  const ret = returns.returns[key];
                  if (ret && ret.return_percent > bestReturn) {
                    bestReturn = ret.return_percent;
                    bestPeriod = label;
                  }
                });
                const { formatted, color } = formatReturnPercent(bestReturn);
                return (
                  <>
                    {bestPeriod} <span className={color}>({formatted})</span>
                  </>
                );
              })()}
            </span>
          </div>
          <div>
            <span className="text-slate-500">Worst Period: </span>
            <span className="text-slate-300 font-medium">
              {(() => {
                let worstPeriod = '';
                let worstReturn = Infinity;
                periods.forEach(({ key, label }) => {
                  const ret = returns.returns[key];
                  if (ret && ret.return_percent < worstReturn) {
                    worstReturn = ret.return_percent;
                    worstPeriod = label;
                  }
                });
                const { formatted, color } = formatReturnPercent(worstReturn);
                return (
                  <>
                    {worstPeriod} <span className={color}>({formatted})</span>
                  </>
                );
              })()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HistoricalReturns;
