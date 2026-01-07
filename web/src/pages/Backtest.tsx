import React, { useState, useEffect } from 'react';
import { Play, Calendar, Settings, TrendingUp, TrendingDown } from 'lucide-react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ComposedChart
} from 'recharts';
import { strategyAPI } from '../lib/api';

interface Strategy {
  id: number;
  name: string;
  strategy_type: string;
  underlying: string;
}

interface BacktestResult {
  id: number;
  strategy_config_id: number;
  start_date: string;
  end_date: string;
  initial_capital: number;
  total_return_pct: number;
  annual_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  calmar_ratio: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  largest_win: number;
  largest_loss: number;
  total_profit: number;
  total_loss: number;
  final_equity: number;
  peak_equity: number;
  trades: Array<{
    entry_date: string;
    exit_date: string;
    entry_price: number;
    exit_price: number;
    quantity: number;
    pnl: number;
    pnl_pct: number;
    strategy: string;
  }>;
  equity_curve: number[];
  drawdown_periods: Array<{
    start: number;
    end: number;
    drawdown_pct: number;
  }>;
}

export const Backtest: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<number | null>(null);
  const [startDate, setStartDate] = useState('2024-01-01');
  const [endDate, setEndDate] = useState('2024-12-31');
  const [initialCapital, setInitialCapital] = useState(100000);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load strategies on mount
  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const response = await strategyAPI.listStrategies();
      setStrategies(Array.isArray(response.data) ? response.data : []);
    } catch (err) {
      console.error('Failed to load strategies:', err);
    }
  };

  const handleRunBacktest = async () => {
    if (!selectedStrategy) {
      setError('Please select a strategy');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch('http://localhost:8000/backtest/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_config_id: selectedStrategy,
          start_date: startDate,
          end_date: endDate,
          initial_capital: initialCapital,
        }),
      });

      if (!response.ok) throw new Error('Backtest failed');
      const data = await response.json();

      if (data.success) {
        setResult(data);
      } else {
        setError(data.error || 'Backtest failed');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  // Prepare equity curve data for chart
  const equityData = result?.equity_curve.map((equity, idx) => ({
    day: idx,
    equity: equity,
  })) || [];

  // Prepare trades for histogram
  const tradeData = result?.trades.slice(0, 20).map((trade, idx) => ({
    trade: `T${idx + 1}`,
    pnl: trade.pnl,
    type: trade.pnl > 0 ? 'win' : 'loss',
  })) || [];

  return (
    <div className="space-y-6 p-6 bg-slate-950 min-h-screen text-white">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold mb-2">Strategy Backtest</h1>
        <p className="text-slate-400">Validate strategies on historical data</p>
      </div>

      {/* Input Section */}
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Strategy Selector */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Strategy</label>
            <select
              value={selectedStrategy || ''}
              onChange={(e) => setSelectedStrategy(parseInt(e.target.value))}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select strategy...</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Start Date */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">From</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">To</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Initial Capital */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Capital</label>
            <input
              type="number"
              value={initialCapital}
              onChange={(e) => setInitialCapital(parseInt(e.target.value))}
              className="w-full px-4 py-2 bg-slate-800 border border-slate-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Run Button */}
          <div className="flex items-end">
            <button
              onClick={handleRunBacktest}
              disabled={loading}
              className="w-full px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center justify-center gap-2 font-semibold"
            >
              <Play size={18} />
              {loading ? 'Running...' : 'Run'}
            </button>
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-900 border border-red-600 rounded p-4 text-red-200">
          {error}
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div className="space-y-6">
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-sm mb-1">Total Return</div>
              <div className={`text-3xl font-bold ${result.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {result.total_return_pct.toFixed(2)}%
              </div>
              <div className="text-xs text-slate-500 mt-1">
                ₹{result.initial_capital.toLocaleString()} → ₹{result.final_equity.toLocaleString()}
              </div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-sm mb-1">Sharpe Ratio</div>
              <div className="text-3xl font-bold text-blue-400">{result.sharpe_ratio.toFixed(2)}</div>
              <div className="text-xs text-slate-500 mt-1">Risk-adjusted return</div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-sm mb-1">Max Drawdown</div>
              <div className="text-3xl font-bold text-red-400">{result.max_drawdown_pct.toFixed(2)}%</div>
              <div className="text-xs text-slate-500 mt-1">Worst peak-to-trough</div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-sm mb-1">Win Rate</div>
              <div className="text-3xl font-bold text-green-400">{result.win_rate_pct.toFixed(1)}%</div>
              <div className="text-xs text-slate-500 mt-1">
                {result.winning_trades} / {result.total_trades} trades
              </div>
            </div>
          </div>

          {/* Additional Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-xs mb-2">Sortino Ratio</div>
              <div className="text-2xl font-bold text-blue-400">{result.sortino_ratio.toFixed(2)}</div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-xs mb-2">Profit Factor</div>
              <div className="text-2xl font-bold text-green-400">{result.profit_factor.toFixed(2)}</div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-xs mb-2">Avg Win</div>
              <div className="text-2xl font-bold text-green-400">₹{result.avg_win.toLocaleString()}</div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-xs mb-2">Avg Loss</div>
              <div className="text-2xl font-bold text-red-400">₹{result.avg_loss.toLocaleString()}</div>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
              <div className="text-slate-400 text-xs mb-2">Calmar Ratio</div>
              <div className="text-2xl font-bold text-blue-400">{result.calmar_ratio.toFixed(2)}</div>
            </div>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Equity Curve */}
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4 text-white">Equity Curve</h3>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={equityData}>
                  <defs>
                    <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.1} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                  <XAxis dataKey="day" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
                    labelStyle={{ color: '#e2e8f0' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="equity"
                    stroke="#3b82f6"
                    fillOpacity={1}
                    fill="url(#colorEquity)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Trade Distribution */}
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
              <h3 className="text-lg font-semibold mb-4 text-white">Trade P&L Distribution</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={tradeData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
                  <XAxis dataKey="trade" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
                    labelStyle={{ color: '#e2e8f0' }}
                  />
                  <Bar dataKey="pnl" radius={[4, 4, 0, 0]} fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Trade Details Table */}
          {result.trades.length > 0 && (
            <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden">
              <div className="p-6 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Recent Trades</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-700 text-slate-300">
                    <tr>
                      <th className="px-6 py-3 text-left">Entry Date</th>
                      <th className="px-6 py-3 text-left">Exit Date</th>
                      <th className="px-6 py-3 text-right">Entry Price</th>
                      <th className="px-6 py-3 text-right">Exit Price</th>
                      <th className="px-6 py-3 text-right">Qty</th>
                      <th className="px-6 py-3 text-right">P&L</th>
                      <th className="px-6 py-3 text-right">P&L %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-700">
                    {result.trades.slice(0, 15).map((trade, idx) => (
                      <tr key={idx} className="hover:bg-slate-700">
                        <td className="px-6 py-3">{trade.entry_date}</td>
                        <td className="px-6 py-3">{trade.exit_date}</td>
                        <td className="px-6 py-3 text-right">₹{trade.entry_price.toFixed(2)}</td>
                        <td className="px-6 py-3 text-right">₹{trade.exit_price.toFixed(2)}</td>
                        <td className="px-6 py-3 text-right">{trade.quantity}</td>
                        <td className={`px-6 py-3 text-right font-semibold ${trade.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          ₹{trade.pnl.toLocaleString()}
                        </td>
                        <td className={`px-6 py-3 text-right ${trade.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {trade.pnl_pct.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Backtest;
