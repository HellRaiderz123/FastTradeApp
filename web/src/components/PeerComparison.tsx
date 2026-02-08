import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, BarChart3, AlertCircle, RefreshCw } from 'lucide-react';
import axios from 'axios';

interface PeerMetrics {
  symbol: string;
  name: string;
  sector: string;
  ltp: number;
  change: number;
  change_percent: number;
  pe_ratio: number | null;
  pb_ratio: number | null;
  roe: number | null;
  dividend_yield: number | null;
  rsi: number | null;
  market_cap: number | null;
}

interface PeerComparisonProps {
  symbol: string;
  onClose?: () => void;
}

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';

const PeerComparison: React.FC<PeerComparisonProps> = ({ symbol, onClose }) => {
  const [stock, setStock] = useState<PeerMetrics | null>(null);
  const [peers, setPeers] = useState<PeerMetrics[]>([]);
  const [sectorAvg, setSectorAvg] = useState<Record<string, number | null>>({});
  const [sector, setSector] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPeerComparison();
  }, [symbol]);

  const fetchPeerComparison = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await axios.get(
        `${API_BASE}/peer-comparison/stock/${symbol}`
      );

      const data = response.data;
      setStock(data.stock);
      setPeers(data.peers || []);
      setSectorAvg(data.sector_avg || {});
      setSector(data.sector || 'Unknown');
    } catch (err: any) {
      console.error('Failed to fetch peer comparison:', err);
      setError(err.response?.data?.detail || 'Failed to load peer comparison data');
    } finally {
      setLoading(false);
    }
  };

  const formatMetric = (value: number | null, isCurrency = false): string => {
    if (value === null || value === undefined) return 'N/A';
    if (isCurrency && value > 1000) return `₹${(value / 1000).toFixed(0)}K Cr`;
    return value.toFixed(2);
  };

  const compareToAvg = (value: number | null, avgValue: number | null): string => {
    if (!value || !avgValue) return '';
    const diff = value - avgValue;
    if (diff > 0) return `+${diff.toFixed(2)}`;
    return diff.toFixed(2);
  };

  const getMetricColor = (value: number | null, avgValue: number | null, isPositiveBetter = true): string => {
    if (!value || !avgValue) return 'text-slate-400';
    const diff = value - avgValue;
    
    if (isPositiveBetter) {
      if (diff > 0) return 'text-emerald-400';
      if (diff < 0) return 'text-red-400';
    } else {
      if (diff < 0) return 'text-emerald-400';
      if (diff > 0) return 'text-red-400';
    }
    return 'text-slate-400';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <RefreshCw className="w-5 h-5 text-blue-400 animate-spin" />
        <span className="ml-2 text-sm text-slate-400">Loading peer comparison...</span>
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

  if (!stock) {
    return null;
  }

  const allStocks = [stock, ...peers];

  return (
    <div className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <div>
            <h2 className="text-lg font-bold text-white">{sector} Peer Comparison</h2>
            <p className="text-xs text-slate-400 mt-1">Comparing {stock.symbol} with {peers.length} peers</p>
          </div>
        </div>
        <button
          onClick={fetchPeerComparison}
          className="p-2 text-slate-400 hover:text-white hover:bg-slate-800/50 rounded transition"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Metrics Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700/50">
              <th className="text-left py-3 px-3 text-slate-300 font-semibold">Stock</th>
              <th className="text-right py-3 px-3 text-slate-300 font-semibold">Price</th>
              <th className="text-right py-3 px-3 text-slate-300 font-semibold">Change</th>
              <th className="text-right py-3 px-3 text-slate-300 font-semibold">P/E Ratio</th>
              <th className="text-right py-3 px-3 text-slate-300 font-semibold">P/B Ratio</th>
              <th className="text-right py-3 px-3 text-slate-300 font-semibold">ROE %</th>
              <th className="text-right py-3 px-3 text-slate-300 font-semibold">Div Yield %</th>
              <th className="text-right py-3 px-3 text-slate-300 font-semibold">RSI(14)</th>
            </tr>
          </thead>
          <tbody>
            {/* Main Stock Row */}
            <tr className="bg-emerald-500/5 border-b border-slate-700/30">
              <td className="py-4 px-3">
                <div>
                  <div className="font-bold text-white">{stock.symbol}</div>
                  <div className="text-xs text-slate-400">{stock.name}</div>
                </div>
              </td>
              <td className="text-right py-4 px-3">
                <div className="font-semibold text-white">₹{stock.ltp.toFixed(2)}</div>
              </td>
              <td className="text-right py-4 px-3">
                <div className={`flex items-center justify-end gap-1 ${stock.change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {stock.change >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  <span className="font-medium">
                    {stock.change >= 0 ? '+' : ''}{stock.change.toFixed(2)} ({stock.change_percent.toFixed(2)}%)
                  </span>
                </div>
              </td>
              <td className="text-right py-4 px-3 text-slate-300">{formatMetric(stock.pe_ratio)}</td>
              <td className="text-right py-4 px-3 text-slate-300">{formatMetric(stock.pb_ratio)}</td>
              <td className="text-right py-4 px-3 text-slate-300">{formatMetric(stock.roe)}</td>
              <td className="text-right py-4 px-3 text-slate-300">{formatMetric(stock.dividend_yield)}</td>
              <td className="text-right py-4 px-3 text-slate-300">{formatMetric(stock.rsi)}</td>
            </tr>

            {/* Peer Rows */}
            {peers.map((peer) => (
              <tr key={peer.symbol} className="border-b border-slate-700/30 hover:bg-slate-800/30 transition">
                <td className="py-3 px-3">
                  <div>
                    <div className="font-semibold text-slate-200">{peer.symbol}</div>
                    <div className="text-xs text-slate-500">{peer.name}</div>
                  </div>
                </td>
                <td className="text-right py-3 px-3">
                  <div className="text-white">₹{peer.ltp.toFixed(2)}</div>
                </td>
                <td className="text-right py-3 px-3">
                  <div className={peer.change >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                    {peer.change >= 0 ? '+' : ''}{peer.change.toFixed(2)} ({peer.change_percent.toFixed(2)}%)
                  </div>
                </td>
                <td className={`text-right py-3 px-3 ${getMetricColor(peer.pe_ratio, sectorAvg.pe_ratio, false)}`}>
                  {formatMetric(peer.pe_ratio)}
                  {sectorAvg.pe_ratio && (
                    <div className="text-xs text-slate-500">
                      {compareToAvg(peer.pe_ratio, sectorAvg.pe_ratio)}
                    </div>
                  )}
                </td>
                <td className={`text-right py-3 px-3 ${getMetricColor(peer.pb_ratio, sectorAvg.pb_ratio, false)}`}>
                  {formatMetric(peer.pb_ratio)}
                  {sectorAvg.pb_ratio && (
                    <div className="text-xs text-slate-500">
                      {compareToAvg(peer.pb_ratio, sectorAvg.pb_ratio)}
                    </div>
                  )}
                </td>
                <td className={`text-right py-3 px-3 ${getMetricColor(peer.roe, sectorAvg.roe, true)}`}>
                  {formatMetric(peer.roe)}
                  {sectorAvg.roe && (
                    <div className="text-xs text-slate-500">
                      {compareToAvg(peer.roe, sectorAvg.roe)}
                    </div>
                  )}
                </td>
                <td className={`text-right py-3 px-3 ${getMetricColor(peer.dividend_yield, sectorAvg.dividend_yield, true)}`}>
                  {formatMetric(peer.dividend_yield)}
                  {sectorAvg.dividend_yield && (
                    <div className="text-xs text-slate-500">
                      {compareToAvg(peer.dividend_yield, sectorAvg.dividend_yield)}
                    </div>
                  )}
                </td>
                <td className={`text-right py-3 px-3 ${getMetricColor(peer.rsi, sectorAvg.rsi, true)}`}>
                  {formatMetric(peer.rsi)}
                  {sectorAvg.rsi && (
                    <div className="text-xs text-slate-500">
                      {compareToAvg(peer.rsi, sectorAvg.rsi)}
                    </div>
                  )}
                </td>
              </tr>
            ))}

            {/* Sector Average Row */}
            {Object.values(sectorAvg).some(v => v !== null) && (
              <tr className="bg-slate-800/40 border-t-2 border-slate-600">
                <td className="py-3 px-3 font-semibold text-slate-300">Sector Average</td>
                <td className="text-right py-3 px-3 text-slate-400">—</td>
                <td className="text-right py-3 px-3 text-slate-400">—</td>
                <td className="text-right py-3 px-3 text-slate-300">{formatMetric(sectorAvg.pe_ratio)}</td>
                <td className="text-right py-3 px-3 text-slate-300">{formatMetric(sectorAvg.pb_ratio)}</td>
                <td className="text-right py-3 px-3 text-slate-300">{formatMetric(sectorAvg.roe)}</td>
                <td className="text-right py-3 px-3 text-slate-300">{formatMetric(sectorAvg.dividend_yield)}</td>
                <td className="text-right py-3 px-3 text-slate-300">{formatMetric(sectorAvg.rsi)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-4 pt-4 border-t border-slate-700/50">
        <p className="text-xs text-slate-400 mb-2">📊 Comparison Values:</p>
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <span className="text-emerald-400">■ Above Average</span> - Better valuation/metrics
          </div>
          <div>
            <span className="text-red-400">■ Below Average</span> - Cheaper/lower metrics
          </div>
        </div>
      </div>
    </div>
  );
};

export default PeerComparison;
