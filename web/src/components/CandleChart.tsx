import React, { useEffect, useState } from 'react';
import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
import { marketAPI } from '../lib/api';
import TimeframeSelector, { Timeframe } from './TimeframeSelector';

interface CandleChartProps {
  symbol: string;
  defaultTimeframe?: Timeframe;
  height?: number;
  showTimeframeSelector?: boolean;
}

interface CandleData {
  timestamp?: string;
  date?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ChartDataPoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  color: string;
  candleBody: number;
  wickLow: number;
  wickHigh: number;
}

const CandleChart: React.FC<CandleChartProps> = ({
  symbol,
  defaultTimeframe = '15m',
  height = 400,
  showTimeframeSelector = true,
}) => {
  const [timeframe, setTimeframe] = useState<Timeframe>(defaultTimeframe);
  const [resolvedTimeframe, setResolvedTimeframe] = useState<Timeframe>(defaultTimeframe);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);

  useEffect(() => {
    const fetchCandles = async () => {
      setLoading(true);
      setError(null);

      try {
        const fallbackCandidates: Timeframe[] = [timeframe, '15m', 'daily'];
        const uniqueCandidates = fallbackCandidates.filter((value, index) => fallbackCandidates.indexOf(value) === index);

        let candles: CandleData[] = [];
        let timeframeUsed: Timeframe = timeframe;

        for (const candidate of uniqueCandidates) {
          const response = await marketAPI.getCandlesDB(symbol, candidate, 100);
          const candidateCandles: CandleData[] = Array.isArray(response.data) ? response.data : [];
          if (candidateCandles.length > 0) {
            candles = candidateCandles;
            timeframeUsed = candidate;
            break;
          }
        }

        if (!candles || candles.length === 0) {
          setError('No candle data available');
          setLoading(false);
          return;
        }

        setResolvedTimeframe(timeframeUsed);

        // Reverse to show chronological order (oldest to newest)
        const reversedCandles = [...candles].reverse();

        // Transform data for charting
        const transformed: ChartDataPoint[] = reversedCandles.map((candle) => {
          const timestamp = candle.timestamp || candle.date;
          if (!timestamp) {
            console.warn('Candle missing timestamp/date', candle);
          }
          
          const date = new Date(timestamp || Date.now());
          const timeStr =
            timeframeUsed === 'daily'
              ? date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

          const isGreen = candle.close >= candle.open;
          
          return {
            time: timeStr,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close,
            volume: candle.volume,
            color: isGreen ? '#10b981' : '#ef4444',
            candleBody: isGreen ? candle.open : candle.close,
            wickLow: candle.low,
            wickHigh: candle.high,
          };
        });

        setChartData(transformed);
        
        // Calculate price change
        if (transformed.length >= 2) {
          const latest = transformed[transformed.length - 1];
          const previous = transformed[transformed.length - 2];
          setCurrentPrice(latest.close);
          setPriceChange(((latest.close - previous.close) / previous.close) * 100);
        }
        
        setLoading(false);
      } catch (err: any) {
        console.error('Error fetching candles:', err);
        setError(err.response?.data?.detail || err.message || 'Failed to load chart data');
        setLoading(false);
      }
    };

    fetchCandles();
  }, [symbol, timeframe]);

  const formatVolume = (value: number): string => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
    return value.toString();
  };

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <p className="text-gray-400 text-sm">Loading {timeframe} candles...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <Activity className="w-12 h-12 text-red-500 mx-auto mb-3" />
            <p className="text-red-400 font-medium">{error}</p>
            <p className="text-gray-500 text-sm mt-2">No data available for {timeframe} timeframe</p>
          </div>
        </div>
      </div>
    );
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const isGreen = data.close >= data.open;
      
      return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-lg">
          <p className="text-gray-400 text-xs mb-2">{data.time}</p>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between gap-4">
              <span className="text-gray-500">Open:</span>
              <span className="text-white font-mono">{data.open.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-500">High:</span>
              <span className="text-green-400 font-mono">{data.high.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-500">Low:</span>
              <span className="text-red-400 font-mono">{data.low.toFixed(2)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-gray-500">Close:</span>
              <span className={`font-mono ${isGreen ? 'text-green-400' : 'text-red-400'}`}>
                {data.close.toFixed(2)}
              </span>
            </div>
            <div className="flex justify-between gap-4 pt-1 border-t border-gray-700">
              <span className="text-gray-500">Volume:</span>
              <span className="text-blue-400 font-mono">{formatVolume(data.volume)}</span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-800">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-semibold text-white">{symbol}</h3>
                {priceChange !== 0 && (
                  <span
                    className={`flex items-center gap-1 text-sm font-medium ${
                      priceChange >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {priceChange >= 0 ? (
                      <TrendingUp className="w-4 h-4" />
                    ) : (
                      <TrendingDown className="w-4 h-4" />
                    )}
                    {Math.abs(priceChange).toFixed(2)}%
                  </span>
                )}
              </div>
              {currentPrice > 0 && (
                <p className="text-xl font-mono text-gray-300 mt-1">
                  ₹{currentPrice.toFixed(2)}
                </p>
              )}
              {resolvedTimeframe !== timeframe && (
                <p className="text-xs text-amber-400 mt-1">Showing {resolvedTimeframe} candles (requested {timeframe})</p>
              )}
            </div>
          </div>
          
          {showTimeframeSelector && (
            <TimeframeSelector
              selectedTimeframe={timeframe}
              onTimeframeChange={setTimeframe}
            />
          )}
        </div>
      </div>

      {/* Chart */}
      <div className="p-4">
        <ResponsiveContainer width="100%" height={height}>
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="time"
              stroke="#9CA3AF"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#9CA3AF' }}
            />
            <YAxis
              yAxisId="price"
              stroke="#9CA3AF"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#9CA3AF' }}
              domain={['auto', 'auto']}
            />
            <YAxis
              yAxisId="volume"
              orientation="right"
              stroke="#6B7280"
              style={{ fontSize: '12px' }}
              tick={{ fill: '#6B7280' }}
              tickFormatter={formatVolume}
            />
            <Tooltip content={<CustomTooltip />} />

            {/* Volume bars */}
            <Bar yAxisId="volume" dataKey="volume" fill="#3B82F6" opacity={0.6} />

            {/* Candlestick wicks (high-low lines) */}
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="low"
              stroke="transparent"
              dot={false}
              isAnimationActive={false}
            />

            {/* Candlestick bodies */}
            <Bar yAxisId="price" dataKey="high" fill="transparent" isAnimationActive={false}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default CandleChart;
