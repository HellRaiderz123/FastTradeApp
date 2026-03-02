import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, BarChart3, Target, Award, Percent } from 'lucide-react';
import { backtestAPI, strategyAPI } from '../lib/api';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts';

interface BacktestSummary {
  id: number;
  strategy_config_id: number;
  strategy_name?: string;
  total_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown_pct: number;
  calmar_ratio: number;
  win_rate_pct: number;
  profit_factor: number;
  total_trades: number;
}

interface ComparisonResult {
  best_return: BacktestSummary;
  best_sharpe: BacktestSummary;
  best_win_rate: BacktestSummary;
  all_results: BacktestSummary[];
}

const BacktestComparison: React.FC = () => {
  const [strategies, setStrategies] = useState<any[]>([]);
  const [selectedBacktests, setSelectedBacktests] = useState<number[]>([]);
  const [availableBacktests, setAvailableBacktests] = useState<any[]>([]);
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStrategiesAndBacktests();
  }, []);

  const loadStrategiesAndBacktests = async () => {
    try {
      const stratResponse = await strategyAPI.listStrategies();
      const strats = Array.isArray(stratResponse.data) ? stratResponse.data : [];
      setStrategies(strats);

      // Load all backtests for all strategies
      const allBacktests: any[] = [];
      for (const strat of strats) {
        try {
          const btResponse = await backtestAPI.listForStrategy(strat.id);
          const backtests = btResponse.data || [];
          
          // Add strategy name to each backtest
          backtests.forEach((bt: any) => {
            allBacktests.push({
              ...bt,
              strategy_name: strat.name,
              strategy_id: strat.id,
            });
          });
        } catch (err) {
          console.warn(`No backtests for strategy ${strat.id}`);
        }
      }
      
      setAvailableBacktests(allBacktests);
    } catch (err) {
      console.error('Failed to load data:', err);
      setError('Failed to load strategies and backtests');
    }
  };

  const handleCompare = async () => {
    if (selectedBacktests.length < 2) {
      setError('Please select at least 2 backtests to compare');
      return;
    }

    setLoading(true);
    setError(null);
    setComparison(null);

    try {
      const response = await backtestAPI.compare(selectedBacktests);
      
      // Enrich with strategy names
      const enriched = {
        ...response.data,
        all_results: response.data.all_results.map((result: BacktestSummary) => {
          const bt = availableBacktests.find((b) => b.id === result.id);
          return { ...result, strategy_name: bt?.strategy_name || 'Unknown' };
        }),
      };
      
      setComparison(enriched);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to compare backtests');
    } finally {
      setLoading(false);
    }
  };

  const toggleBacktest = (id: number) => {
    setSelectedBacktests((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const MetricCard = ({ icon: Icon, label, value, color, isBest = false }: any) => (
    <div className={`bg-gray-800 rounded-lg p-4 border ${isBest ? 'border-yellow-500 ring-2 ring-yellow-500/50' : 'border-gray-700'}`}>
      {isBest && (
        <div className="flex items-center gap-1 text-yellow-500 text-xs font-semibold mb-2">
          <Award className="w-3 h-3" />
          BEST
        </div>
      )}
      <div className="flex items-center gap-3">
        <Icon className={`w-8 h-8 ${color}`} />
        <div>
          <p className="text-gray-400 text-xs">{label}</p>
          <p className="text-white text-xl font-bold">{value}</p>
        </div>
      </div>
    </div>
  );

  if (loading && !comparison) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          <p className="text-gray-400">Comparing backtests...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <BarChart3 className="w-8 h-8 text-blue-500" />
          <div>
            <h1 className="text-3xl font-bold text-white">Backtest Comparison</h1>
            <p className="text-gray-400 mt-1">
              Compare multiple backtest results side-by-side
            </p>
          </div>
        </div>

        {/* Backtest Selection */}
        <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
          <h2 className="text-lg font-semibold text-white mb-4">Select Backtests to Compare</h2>
          
          {availableBacktests.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              No backtests available. Run some backtests first.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
              {availableBacktests.map((bt) => (
                <button
                  key={bt.id}
                  onClick={() => toggleBacktest(bt.id)}
                  className={`
                    p-4 rounded-lg border text-left transition-all
                    ${
                      selectedBacktests.includes(bt.id)
                        ? 'bg-blue-900/30 border-blue-500 ring-2 ring-blue-500/50'
                        : 'bg-gray-800 border-gray-700 hover:border-gray-600'
                    }
                  `}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-white font-semibold">#{bt.id}</span>
                    <span
                      className={`text-xs px-2 py-1 rounded ${
                        bt.total_return_pct >= 0
                          ? 'bg-green-900/30 text-green-400'
                          : 'bg-red-900/30 text-red-400'
                      }`}
                    >
                      {bt.total_return_pct?.toFixed(2)}%
                    </span>
                  </div>
                  <p className="text-gray-400 text-sm">{bt.strategy_name}</p>
                  <p className="text-gray-500 text-xs mt-1">
                    {bt.start_date} → {bt.end_date}
                  </p>
                  <div className="flex gap-3 mt-2 text-xs text-gray-400">
                    <span>SR: {bt.sharpe_ratio?.toFixed(2)}</span>
                    <span>Win: {bt.win_rate_pct?.toFixed(1)}%</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          <button
            onClick={handleCompare}
            disabled={selectedBacktests.length < 2 || loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-lg transition-colors"
          >
            {loading ? 'Comparing...' : `Compare ${selectedBacktests.length} Backtests`}
          </button>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-800 rounded-lg p-4">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {/* Comparison Results */}
        {comparison && (
          <div className="space-y-6">
            {/* Top Performers */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <MetricCard
                icon={TrendingUp}
                label="Best Total Return"
                value={`${comparison.best_return.total_return_pct.toFixed(2)}%`}
                color="text-green-400"
                isBest
              />
              <MetricCard
                icon={Target}
                label="Best Sharpe Ratio"
                value={comparison.best_sharpe.sharpe_ratio.toFixed(2)}
                color="text-blue-400"
                isBest
              />
              <MetricCard
                icon={Percent}
                label="Best Win Rate"
                value={`${comparison.best_win_rate.win_rate_pct.toFixed(1)}%`}
                color="text-purple-400"
                isBest
              />
            </div>

            {/* Comparison Table */}
            <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-800 border-b border-gray-700">
                      <th className="text-left p-4 text-gray-400 font-semibold">ID</th>
                      <th className="text-left p-4 text-gray-400 font-semibold">Strategy</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">Return %</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">Sharpe</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">Sortino</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">Max DD %</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">Calmar</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">Win Rate</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">PF</th>
                      <th className="text-right p-4 text-gray-400 font-semibold">Trades</th>
                    </tr>
                  </thead>
                  <tbody>
                    {comparison.all_results.map((result, idx) => (
                      <tr
                        key={result.id}
                        className={`border-b border-gray-800 hover:bg-gray-800/50 ${
                          idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-900/50'
                        }`}
                      >
                        <td className="p-4 text-white font-mono">#{result.id}</td>
                        <td className="p-4 text-gray-300">{result.strategy_name}</td>
                        <td className={`p-4 text-right font-semibold ${result.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {result.total_return_pct.toFixed(2)}%
                        </td>
                        <td className="p-4 text-right text-white">{result.sharpe_ratio.toFixed(2)}</td>
                        <td className="p-4 text-right text-white">{result.sortino_ratio.toFixed(2)}</td>
                        <td className="p-4 text-right text-red-400">{result.max_drawdown_pct.toFixed(2)}%</td>
                        <td className="p-4 text-right text-white">{result.calmar_ratio.toFixed(2)}</td>
                        <td className="p-4 text-right text-blue-400">{result.win_rate_pct.toFixed(1)}%</td>
                        <td className="p-4 text-right text-white">{result.profit_factor.toFixed(2)}</td>
                        <td className="p-4 text-right text-gray-400">{result.total_trades}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Bar Chart Comparison */}
            <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
              <h3 className="text-lg font-semibold text-white mb-4">Performance Comparison</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={comparison.all_results}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="id" tickFormatter={(id) => `#${id}`} stroke="#9CA3AF" />
                  <YAxis stroke="#9CA3AF" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                    labelStyle={{ color: '#F3F4F6' }}
                  />
                  <Legend />
                  <Bar dataKey="total_return_pct" name="Return %" fill="#10b981" />
                  <Bar dataKey="sharpe_ratio" name="Sharpe Ratio" fill="#3b82f6" />
                  <Bar dataKey="win_rate_pct" name="Win Rate %" fill="#8b5cf6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BacktestComparison;
