import React, { useEffect, useState } from 'react';
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { marketAPI } from '../lib/api';

interface ChartPanelProps {
  symbol: string;
  timeframe?: '1m' | '5m' | '15m' | '30m' | '1h' | '1d';
  height?: number;
}

interface CandleData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ChartDataPoint {
  time: string;
  price: number;
  volume: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

const ChartPanel: React.FC<ChartPanelProps> = ({
  symbol,
  timeframe = '15m',
  height = 400,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);

  // Map timeframe to API interval
  const getInterval = (tf: string): string => {
    const mapping: { [key: string]: string } = {
      '1m': 'minute',
      '5m': '5minute',
      '15m': '15minute',
      '30m': '30minute',
      '1h': '60minute',
      '1d': 'day',
    };
    return mapping[tf] || '15minute';
  };

  // Fetch candle data
  useEffect(() => {
    const fetchCandles = async () => {
      setLoading(true);
      setError(null);

      try {
        // Fetch both candles and current quote in parallel
        const interval = getInterval(timeframe);
        const [candlesResponse, quoteResponse] = await Promise.all([
          marketAPI.getCandles(symbol, interval),
          marketAPI.getBulkQuotes([symbol])
        ]);
        
        const candles: CandleData[] = candlesResponse.data.candles;

        if (!candles || candles.length === 0) {
          throw new Error('No candle data available');
        }

        // Transform data for Recharts
        const transformed: ChartDataPoint[] = candles.map((candle) => {
          const date = new Date(candle.timestamp);
          const timeStr =
            timeframe === '1d'
              ? date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

          return {
            time: timeStr,
            price: candle.close,
            volume: candle.volume,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
          };
        });

        setChartData(transformed);

        // Use real-time quote for header (matches watchlist exactly)
        const quotes = quoteResponse.data.quotes;
        if (quotes && quotes.length > 0) {
          const quote = quotes[0];
          setCurrentPrice(quote.ltp);
          setPriceChange(quote.change);
        } else {
          // Fallback to last candle if quote fetch fails
          const lastCandle = candles[candles.length - 1];
          setCurrentPrice(lastCandle.close);
          setPriceChange(0);
        }

        setLoading(false);
      } catch (err: any) {
        console.error('[ChartPanel] Error fetching candles:', err);
        setError(err.message || 'Failed to load chart data');
        setLoading(false);
      }
    };

    if (symbol) {
      fetchCandles();
    }
  }, [symbol, timeframe]);

  return (
    <div className="terminal-panel rounded-xl p-4 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white flex items-center gap-2">
            <Activity size={18} className="text-blue-400" />
            {symbol}
          </h3>
          {currentPrice > 0 && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-2xl font-bold text-white">
                ₹{currentPrice.toFixed(2)}
              </span>
              <span
                className={`flex items-center gap-1 text-sm ${
                  priceChange >= 0 ? 'text-emerald-400' : 'text-red-400'
                }`}
              >
                {priceChange >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {priceChange >= 0 ? '+' : ''}
                {priceChange.toFixed(2)} ({((priceChange / currentPrice) * 100).toFixed(2)}%)
              </span>
            </div>
          )}
        </div>
        <div className="text-xs text-slate-400 uppercase tracking-wider">
          {timeframe}
        </div>
      </div>

      {/* Chart Container */}
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50 rounded-lg backdrop-blur-sm z-10">
            <div className="flex items-center gap-2 text-slate-300">
              <Activity size={18} className="animate-pulse" />
              <span>Loading chart...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50 rounded-lg backdrop-blur-sm z-10">
            <div className="text-center">
              <p className="text-red-400 mb-2">{error}</p>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-sm text-white transition-colors"
              >
                Retry
              </button>
            </div>
          </div>
        )}

        {!loading && !error && chartData.length > 0 && (
          <ResponsiveContainer width="100%" height={height}>
            <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
              <XAxis
                dataKey="time"
                stroke="#94a3b8"
                style={{ fontSize: '11px' }}
                tick={{ fill: '#94a3b8' }}
              />
              <YAxis
                yAxisId="price"
                orientation="right"
                stroke="#94a3b8"
                style={{ fontSize: '11px' }}
                tick={{ fill: '#94a3b8' }}
                domain={['auto', 'auto']}
              />
              <YAxis
                yAxisId="volume"
                orientation="left"
                stroke="#94a3b8"
                style={{ fontSize: '11px' }}
                tick={{ fill: '#94a3b8' }}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  border: '1px solid rgba(148, 163, 184, 0.2)',
                  borderRadius: '8px',
                  color: '#fff',
                }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value: any, name: string) => {
                  if (name === 'volume') {
                    return [(value / 100000).toFixed(2) + 'L', 'Volume'];
                  }
                  if (name === 'price') {
                    return ['₹' + Number(value).toFixed(2), 'Price'];
                  }
                  return ['₹' + Number(value).toFixed(2), name];
                }}
              />
              <Bar
                yAxisId="volume"
                dataKey="volume"
                fill="#3b82f6"
                opacity={0.3}
                radius={[4, 4, 0, 0]}
              />
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="price"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                fill="url(#priceGradient)"
              />
            </ComposedChart>
          </ResponsiveContainer>
        )}

        {!loading && !error && chartData.length === 0 && (
          <div className="flex items-center justify-center h-full text-slate-500">
            <p>No chart data available</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ChartPanel;
