import React, { useState, useEffect } from 'react';
import { Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { marketDashboardAPI, type HeatmapStock } from '../lib/marketDashboardAPI';

const Heatmap: React.FC = () => {
  const [heatmapData, setHeatmapData] = useState<HeatmapStock[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchHeatmapData = async () => {
      try {
        setLoading(true);
        const data = await marketDashboardAPI.getHeatmap();
        setHeatmapData(data.stocks);
      } catch (error) {
        console.error('Failed to fetch heatmap:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchHeatmapData();
    const interval = setInterval(fetchHeatmapData, 30000); // Refresh every 30s

    return () => clearInterval(interval);
  }, []);

  // Calculate grid size based on number of stocks
  const getGridCols = () => {
    const count = heatmapData.length;
    if (count <= 12) return 'grid-cols-4';
    if (count <= 24) return 'grid-cols-6';
    return 'grid-cols-8';
  };

  const getColorClass = (changePercent: number) => {
    if (changePercent >= 2.0) return 'bg-emerald-600 text-white';
    if (changePercent >= 1.0) return 'bg-emerald-500 text-white';
    if (changePercent >= 0.5) return 'bg-emerald-400/80 text-white';
    if (changePercent > 0) return 'bg-emerald-300/60 text-slate-900';
    if (changePercent === 0) return 'bg-slate-500/40 text-slate-200';
    if (changePercent > -0.5) return 'bg-red-300/60 text-slate-900';
    if (changePercent > -1.0) return 'bg-red-400/80 text-white';
    if (changePercent > -2.0) return 'bg-red-500 text-white';
    return 'bg-red-600 text-white';
  };

  const getCellSize = (marketCapRank: number) => {
    // Top 10 stocks get larger cells
    if (marketCapRank <= 10) return 'h-24';
    if (marketCapRank <= 25) return 'h-20';
    return 'h-16';
  };

  return (
    <div className="h-full flex flex-col gap-4 terminal-pattern overflow-y-auto pb-6">
      {/* Header */}
      <header className="terminal-panel rounded-2xl px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Market Overview</p>
            <h1 className="terminal-title text-3xl text-white">NIFTY 50 Heatmap</h1>
          </div>
          
          {loading && (
            <Activity size={18} className="text-blue-400 animate-pulse" />
          )}
        </div>

        {/* Legend */}
        <div className="flex items-center gap-4 mt-4 flex-wrap">
          <span className="text-xs text-slate-400 uppercase tracking-wider">Performance:</span>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-emerald-600"></div>
              <span className="text-xs text-slate-300">&gt; 2%</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-emerald-400/80"></div>
              <span className="text-xs text-slate-300">0.5-2%</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-slate-500/40"></div>
              <span className="text-xs text-slate-300">0%</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-red-400/80"></div>
              <span className="text-xs text-slate-300">-0.5 to -2%</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-4 h-4 rounded bg-red-600"></div>
              <span className="text-xs text-slate-300">&lt; -2%</span>
            </div>
          </div>
        </div>
      </header>

      {/* Heatmap Grid */}
      <div className="terminal-panel rounded-2xl p-6">
        {loading ? (
          <div className="flex items-center justify-center h-96">
            <div className="text-slate-500">Loading heatmap data...</div>
          </div>
        ) : heatmapData.length > 0 ? (
          <div className={`grid ${getGridCols()} gap-2`}>
            {heatmapData.map((stock) => (
              <div
                key={stock.symbol}
                className={`
                  ${getColorClass(stock.change_percent)}
                  ${getCellSize(stock.market_cap_rank)}
                  rounded-lg p-3 flex flex-col justify-between
                  hover:scale-105 transition-transform cursor-pointer
                  border border-black/20
                `}
                title={`${stock.symbol}: ${stock.change_percent >= 0 ? '+' : ''}${stock.change_percent.toFixed(2)}%`}
              >
                <div>
                  <div className="text-sm font-bold">
                    {stock.symbol}
                  </div>
                  {stock.market_cap_rank <= 10 && (
                    <div className="text-xs opacity-70 mt-0.5">
                      ₹{stock.ltp.toFixed(2)}
                    </div>
                  )}
                </div>
                
                <div className="flex items-center justify-between mt-2">
                  <div className="text-lg font-bold">
                    {stock.change_percent >= 0 ? '+' : ''}{stock.change_percent.toFixed(2)}%
                  </div>
                  {stock.change_percent >= 0 ? (
                    <TrendingUp size={16} />
                  ) : (
                    <TrendingDown size={16} />
                  )}
                </div>
                
                {stock.market_cap_rank <= 10 && stock.volume > 0 && (
                  <div className="text-[10px] opacity-60 mt-1">
                    Vol: {(stock.volume / 1000000).toFixed(1)}M
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center h-96">
            <div className="text-slate-500">No heatmap data available</div>
          </div>
        )}
      </div>

      {/* Stats Summary */}
      {heatmapData.length > 0 && (
        <div className="grid grid-cols-4 gap-4">
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Gainers</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-400">
                {heatmapData.filter(s => s.change_percent > 0).length}
              </span>
              <span className="text-xs text-slate-400">stocks</span>
            </div>
          </div>
          
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Losers</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-red-400">
                {heatmapData.filter(s => s.change_percent < 0).length}
              </span>
              <span className="text-xs text-slate-400">stocks</span>
            </div>
          </div>
          
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Avg Change</p>
            <div className="flex items-baseline gap-2">
              <span className={`text-2xl font-bold ${
                (heatmapData.reduce((sum, s) => sum + s.change_percent, 0) / heatmapData.length) >= 0
                  ? 'text-emerald-400'
                  : 'text-red-400'
              }`}>
                {(heatmapData.reduce((sum, s) => sum + s.change_percent, 0) / heatmapData.length).toFixed(2)}%
              </span>
            </div>
          </div>
          
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Total Volume</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">
                {(heatmapData.reduce((sum, s) => sum + s.volume, 0) / 1000000).toFixed(0)}M
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Heatmap;
