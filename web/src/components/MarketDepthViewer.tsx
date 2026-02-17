import React, { useState, useEffect } from 'react';
import {
  getMarketDepth,
  getDepthAnalysis,
  MarketDepth,
  DepthAnalysis,
} from '../api/marketDepthAPI';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart2,
  AlertCircle,
  RefreshCw,
} from 'lucide-react';

interface MarketDepthViewerProps {
  symbol: string;
  height?: number;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

const MarketDepthViewer: React.FC<MarketDepthViewerProps> = ({
  symbol,
  height = 600,
  autoRefresh = true,
  refreshInterval = 3000,
}) => {
  const [depth, setDepth] = useState<MarketDepth | null>(null);
  const [analysis, setAnalysis] = useState<DepthAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  useEffect(() => {
    loadDepth();

    if (autoRefresh) {
      const interval = setInterval(() => {
        loadDepth();
      }, refreshInterval);

      return () => clearInterval(interval);
    }
  }, [symbol, autoRefresh, refreshInterval]);

  const loadDepth = async () => {
    try {
      const [depthData, analysisData] = await Promise.all([
        getMarketDepth(symbol),
        getDepthAnalysis(symbol),
      ]);

      setDepth(depthData);
      setAnalysis(analysisData);
      setLastUpdate(new Date());
      setLoading(false);
    } catch (error) {
      console.error('Failed to load market depth:', error);
      setLoading(false);
    }
  };

  const formatNumber = (num: number) => {
    if (num >= 100000) return `${(num / 100000).toFixed(2)}L`;
    if (num >= 1000) return `${(num / 1000).toFixed(2)}K`;
    return num.toString();
  };

  const formatPrice = (price: number) => {
    return `₹${price.toFixed(2)}`;
  };

  const getImbalanceColor = (imbalance: number) => {
    if (imbalance > 15) return 'text-green-400 bg-green-500/20 border-green-500/40';
    if (imbalance > 5) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
    if (imbalance < -15) return 'text-red-400 bg-red-500/20 border-red-500/40';
    if (imbalance < -5) return 'text-red-400 bg-red-500/10 border-red-500/30';
    return 'text-gray-400 bg-gray-500/10 border-gray-500/30';
  };

  const getBarWidth = (quantity: number, maxQty: number) => {
    return `${(quantity / maxQty) * 100}%`;
  };

  if (loading || !depth || !analysis) {
    return (
      <div style={{ height: `${height}px` }} className="flex items-center justify-center bg-slate-900/50 rounded-lg border border-slate-700">
        <div className="text-gray-400 text-sm flex items-center gap-2">
          <Activity className="w-4 h-4 animate-pulse" />
          Loading market depth...
        </div>
      </div>
    );
  }

  const maxBidQty = Math.max(...depth.bids.map((b) => b.quantity));
  const maxAskQty = Math.max(...depth.asks.map((a) => a.quantity));
  const maxQty = Math.max(maxBidQty, maxAskQty);

  return (
    <div style={{ height: `${height}px` }} className="flex flex-col bg-slate-900/50 rounded-lg border border-slate-700">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <div>
            <div className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5 text-blue-400" />
              <h3 className="text-lg font-semibold text-gray-200">{symbol} Order Book</h3>
              {depth.data_source === 'simulated' ? (
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40">
                  SIMULATED
                </span>
              ) : (
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-green-500/20 text-green-300 border border-green-500/40">
                  LIVE
                </span>
              )}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Last update: {lastUpdate.toLocaleTimeString()}
            </div>
          </div>
          <button
            onClick={loadDepth}
            className="p-2 rounded bg-slate-800 border border-slate-700 hover:bg-slate-700 transition"
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        {/* Key Metrics */}
        <div className="grid grid-cols-4 gap-3">
          <div className="bg-slate-800/50 rounded p-2 border border-slate-700">
            <div className="text-xs text-gray-500 mb-1">LTP</div>
            <div className="text-lg font-bold text-white">{formatPrice(depth.spot_price)}</div>
          </div>

          <div className="bg-slate-800/50 rounded p-2 border border-slate-700">
            <div className="text-xs text-gray-500 mb-1">Spread</div>
            <div className="text-sm font-semibold text-gray-300">
              {formatPrice(depth.spread)}
              <span className="text-xs text-gray-500 ml-1">
                ({depth.spread_percentage.toFixed(3)}%)
              </span>
            </div>
          </div>

          <div className="bg-slate-800/50 rounded p-2 border border-slate-700">
            <div className="text-xs text-gray-500 mb-1">Imbalance</div>
            <div className={`text-sm font-semibold ${
              depth.imbalance > 0 ? 'text-green-400' : depth.imbalance < 0 ? 'text-red-400' : 'text-gray-400'
            }`}>
              {depth.imbalance > 0 ? '+' : ''}{depth.imbalance.toFixed(1)}%
            </div>
          </div>

          <div className={`rounded p-2 border ${getImbalanceColor(depth.imbalance)}`}>
            <div className="text-xs opacity-70 mb-1">Signal</div>
            <div className="text-sm font-bold">{analysis.order_flow.signal}</div>
          </div>
        </div>
      </div>

      {/* Order Book */}
      <div className="flex-1 overflow-hidden flex flex-col">
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {/* Header Row */}
          <div className="sticky top-0 z-10 bg-slate-800/90 backdrop-blur-sm border-b border-slate-700 px-4 py-2">
            <div className="grid grid-cols-12 gap-2 text-xs font-semibold text-gray-400">
              <div className="col-span-3 text-left">BID QTY</div>
              <div className="col-span-2 text-center">ORDERS</div>
              <div className="col-span-2 text-center">PRICE</div>
              <div className="col-span-2 text-center">ORDERS</div>
              <div className="col-span-3 text-right">ASK QTY</div>
            </div>
          </div>

          {/* Order Levels */}
          <div className="px-4 py-2 space-y-1">
            {[...Array(5)].map((_, index) => {
              const bid = depth.bids[index];
              const ask = depth.asks[index];

              return (
                <div key={index} className="grid grid-cols-12 gap-2 text-xs relative">
                  {/* Bid Side */}
                  <div className="col-span-3 relative">
                    <div
                      className="absolute right-0 top-0 h-full bg-green-500/10 rounded"
                      style={{ width: getBarWidth(bid.quantity, maxQty) }}
                    />
                    <div className="relative z-10 text-green-400 font-semibold text-right pr-2 py-1">
                      {formatNumber(bid.quantity)}
                    </div>
                  </div>

                  <div className="col-span-2 flex items-center justify-center text-gray-500 py-1">
                    {bid.orders}
                  </div>

                  <div className="col-span-2 flex items-center justify-center bg-green-500/5 rounded py-1">
                    <span className="text-green-400 font-mono font-semibold">
                      {bid.price.toFixed(2)}
                    </span>
                  </div>

                  <div className="col-span-2 flex items-center justify-center text-gray-500 py-1">
                    {ask.orders}
                  </div>

                  {/* Ask Side */}
                  <div className="col-span-3 relative">
                    <div
                      className="absolute left-0 top-0 h-full bg-red-500/10 rounded"
                      style={{ width: getBarWidth(ask.quantity, maxQty) }}
                    />
                    <div className="relative z-10 text-red-400 font-semibold text-left pl-2 py-1">
                      {formatNumber(ask.quantity)}
                    </div>
                  </div>

                  <div className="col-span-2 flex items-center justify-center bg-red-500/5 rounded py-1">
                    <span className="text-red-400 font-mono font-semibold">
                      {ask.price.toFixed(2)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Depth Chart Visualization */}
        <div className="border-t border-slate-700 p-4">
          <div className="text-xs font-semibold text-gray-400 mb-2">Order Flow Imbalance</div>
          <div className="relative h-8 bg-slate-800 rounded-full overflow-hidden">
            {/* Bid side (left) */}
            <div
              className="absolute left-0 top-0 h-full bg-gradient-to-r from-green-500/40 to-green-500/20 flex items-center justify-start pl-3"
              style={{ width: `${(depth.total_bid_qty / (depth.total_bid_qty + depth.total_ask_qty)) * 100}%` }}
            >
              <span className="text-xs font-semibold text-green-300">
                {formatNumber(depth.total_bid_qty)} ({((depth.total_bid_qty / (depth.total_bid_qty + depth.total_ask_qty)) * 100).toFixed(1)}%)
              </span>
            </div>

            {/* Ask side (right) */}
            <div
              className="absolute right-0 top-0 h-full bg-gradient-to-l from-red-500/40 to-red-500/20 flex items-center justify-end pr-3"
              style={{ width: `${(depth.total_ask_qty / (depth.total_bid_qty + depth.total_ask_qty)) * 100}%` }}
            >
              <span className="text-xs font-semibold text-red-300">
                {formatNumber(depth.total_ask_qty)} ({((depth.total_ask_qty / (depth.total_bid_qty + depth.total_ask_qty)) * 100).toFixed(1)}%)
              </span>
            </div>
          </div>
        </div>

        {/* Analysis Footer */}
        <div className="border-t border-slate-700 px-4 py-3 bg-slate-800/30">
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <div className="text-gray-500 mb-1">Support/Resistance</div>
              <div className="flex items-center justify-between">
                <span className="text-green-400">Support: {formatPrice(analysis.support_resistance.support || 0)}</span>
                <span className="text-red-400">Resistance: {formatPrice(analysis.support_resistance.resistance || 0)}</span>
              </div>
            </div>

            <div>
              <div className="text-gray-500 mb-1">Avg Order Size</div>
              <div className="flex items-center justify-between">
                <span className="text-green-400">Bid: {formatNumber(analysis.liquidity.avg_bid_size)}</span>
                <span className="text-red-400">Ask: {formatNumber(analysis.liquidity.avg_ask_size)}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MarketDepthViewer;
