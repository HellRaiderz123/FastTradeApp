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
  ReferenceLine,
  Area,
} from 'recharts';
import { Activity, TrendingUp, TrendingDown, BarChart3, Zap } from 'lucide-react';
import { marketAPI } from '../lib/api';
import { marketDashboardAPI } from '../lib/marketDashboardAPI';

interface TechnicalChartProps {
  symbol: string;
  timeframe?: '1m' | '5m' | '15m' | '30m' | '1h' | '1d';
  height?: number;
}

interface ChartDataPoint {
  time: string;
  price: number;
  volume: number;
  open: number;
  high: number;
  low: number;
  close: number;
  // Technical indicators
  rsi?: number;
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
  bb_upper?: number;
  bb_middle?: number;
  bb_lower?: number;
  sma_20?: number;
  ema_12?: number;
  ema_26?: number;
}

const TechnicalChart: React.FC<TechnicalChartProps> = ({
  symbol,
  timeframe = '15m',
  height = 500,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);
  
  // Indicator toggles
  const [showBB, setShowBB] = useState(true);
  const [showRSI, setShowRSI] = useState(true);
  const [showMACD, setShowMACD] = useState(true);
  const [showSMA, setShowSMA] = useState(false);
  const [showEMA, setShowEMA] = useState(false);

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

  // Calculate technical indicators from candle data
  const calculateIndicators = (candles: any[]): ChartDataPoint[] => {
    const closes = candles.map(c => c.close);
    const highs = candles.map(c => c.high);
    const lows = candles.map(c => c.low);
    const volumes = candles.map(c => c.volume);
    
    const result: ChartDataPoint[] = [];
    
    for (let i = 0; i < candles.length; i++) {
      const candle = candles[i];
      const date = new Date(candle.timestamp);
      const timeStr =
        timeframe === '1d'
          ? date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
          : date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
      
      const dataPoint: ChartDataPoint = {
        time: timeStr,
        price: candle.close,
        volume: candle.volume,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      };
      
      // RSI (14-period)
      if (i >= 14) {
        const period = 14;
        let gains = 0, losses = 0;
        for (let j = i - period + 1; j <= i; j++) {
          const change = closes[j] - closes[j - 1];
          if (change > 0) gains += change;
          else losses += Math.abs(change);
        }
        const avgGain = gains / period;
        const avgLoss = losses / period;
        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        dataPoint.rsi = 100 - (100 / (1 + rs));
      }
      
      // SMA 20
      if (i >= 19) {
        const sum = closes.slice(i - 19, i + 1).reduce((a, b) => a + b, 0);
        dataPoint.sma_20 = sum / 20;
      }
      
      // EMA 12 & 26
      if (i >= 11) {
        const multiplier12 = 2 / (12 + 1);
        let ema12 = closes.slice(i - 11, i + 1).reduce((a, b) => a + b, 0) / 12;
        if (i > 11 && result[i - 1].ema_12) {
          ema12 = (closes[i] - result[i - 1].ema_12!) * multiplier12 + result[i - 1].ema_12!;
        }
        dataPoint.ema_12 = ema12;
      }
      
      if (i >= 25) {
        const multiplier26 = 2 / (26 + 1);
        let ema26 = closes.slice(i - 25, i + 1).reduce((a, b) => a + b, 0) / 26;
        if (i > 25 && result[i - 1].ema_26) {
          ema26 = (closes[i] - result[i - 1].ema_26!) * multiplier26 + result[i - 1].ema_26!;
        }
        dataPoint.ema_26 = ema26;
        
        // MACD
        if (dataPoint.ema_12 && dataPoint.ema_26) {
          dataPoint.macd = dataPoint.ema_12 - dataPoint.ema_26;
          
          // MACD Signal (9-period EMA of MACD)
          if (i >= 34) {
            const macdValues = result.slice(i - 8, i).filter(d => d.macd).map(d => d.macd!);
            if (macdValues.length === 9) {
              macdValues.push(dataPoint.macd);
              dataPoint.macd_signal = macdValues.reduce((a, b) => a + b, 0) / 9;
              dataPoint.macd_histogram = dataPoint.macd - dataPoint.macd_signal;
            }
          }
        }
      }
      
      // Bollinger Bands (20-period, 2 std dev)
      if (i >= 19 && dataPoint.sma_20) {
        const period = 20;
        const slice = closes.slice(i - 19, i + 1);
        const mean = dataPoint.sma_20;
        const variance = slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period;
        const stdDev = Math.sqrt(variance);
        dataPoint.bb_upper = mean + (2 * stdDev);
        dataPoint.bb_middle = mean;
        dataPoint.bb_lower = mean - (2 * stdDev);
      }
      
      result.push(dataPoint);
    }
    
    return result;
  };

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const interval = getInterval(timeframe);
        const [candlesResponse, quoteResponse] = await Promise.all([
          marketAPI.getCandles(symbol, interval),
          marketAPI.getBulkQuotes([symbol])
        ]);
        
        const candles = candlesResponse.data.candles;

        if (!candles || candles.length === 0) {
          throw new Error('No candle data available');
        }

        // Calculate indicators
        const chartDataWithIndicators = calculateIndicators(candles);
        setChartData(chartDataWithIndicators);

        // Set current price
        const quotes = quoteResponse.data.quotes;
        if (quotes && quotes.length > 0) {
          const quote = quotes[0];
          setCurrentPrice(quote.ltp);
          setPriceChange(quote.change);
        }

        setLoading(false);
      } catch (err: any) {
        console.error('Error fetching chart data:', err);
        setError(err.message || 'Failed to load chart');
        setLoading(false);
      }
    };

    if (symbol) {
      fetchData();
    }
  }, [symbol, timeframe]);

  const priceHeight = showRSI && showMACD ? height * 0.5 : showRSI || showMACD ? height * 0.65 : height;

  return (
    <div className="terminal-panel rounded-2xl p-5 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-xl font-semibold text-white flex items-center gap-2">
            <BarChart3 size={20} className="text-blue-400" />
            {symbol}
          </h3>
          {currentPrice > 0 && (
            <div className="flex items-center gap-3 mt-2">
              <span className="text-3xl font-bold text-white">
                ₹{currentPrice.toFixed(2)}
              </span>
              <span
                className={`flex items-center gap-1 text-sm px-2 py-1 rounded ${
                  priceChange >= 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'
                }`}
              >
                {priceChange >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {priceChange >= 0 ? '+' : ''}
                {priceChange.toFixed(2)} ({((priceChange / (currentPrice - priceChange)) * 100).toFixed(2)}%)
              </span>
            </div>
          )}
        </div>
        
        {/* Indicator Toggles */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBB(!showBB)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition ${
              showBB ? 'bg-purple-500/30 text-purple-300 border border-purple-500/50' : 'bg-slate-700 text-slate-400 border border-transparent'
            }`}
          >
            BB
          </button>
          <button
            onClick={() => setShowSMA(!showSMA)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition ${
              showSMA ? 'bg-orange-500/30 text-orange-300 border border-orange-500/50' : 'bg-slate-700 text-slate-400 border border-transparent'
            }`}
          >
            SMA
          </button>
          <button
            onClick={() => setShowEMA(!showEMA)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition ${
              showEMA ? 'bg-yellow-500/30 text-yellow-300 border border-yellow-500/50' : 'bg-slate-700 text-slate-400 border border-transparent'
            }`}
          >
            EMA
          </button>
          <button
            onClick={() => setShowRSI(!showRSI)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition ${
              showRSI ? 'bg-cyan-500/30 text-cyan-300 border border-cyan-500/50' : 'bg-slate-700 text-slate-400 border border-transparent'
            }`}
          >
            RSI
          </button>
          <button
            onClick={() => setShowMACD(!showMACD)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition ${
              showMACD ? 'bg-emerald-500/30 text-emerald-300 border border-emerald-500/50' : 'bg-slate-700 text-slate-400 border border-transparent'
            }`}
          >
            MACD
          </button>
        </div>
      </div>

      {/* Charts Container */}
      <div className="flex-1 relative flex flex-col gap-3">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50 rounded-lg backdrop-blur-sm z-10">
            <div className="flex items-center gap-2 text-slate-300">
              <Activity size={18} className="animate-pulse" />
              <span>Loading technical chart...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex items-center justify-center bg-slate-900/50 rounded-lg backdrop-blur-sm z-10">
            <div className="text-center">
              <p className="text-red-400 mb-2">{error}</p>
            </div>
          </div>
        )}

        {!loading && !error && chartData.length > 0 && (
          <>
            {/* Main Price Chart with Volume */}
            <div className="flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" vertical={false} />
                  <XAxis
                    dataKey="time"
                    stroke="#64748b"
                    style={{ fontSize: '10px' }}
                    tick={{ fill: '#64748b' }}
                  />
                  <YAxis
                    yAxisId="price"
                    orientation="right"
                    stroke="#64748b"
                    style={{ fontSize: '11px' }}
                    tick={{ fill: '#64748b' }}
                    domain={['auto', 'auto']}
                  />
                  <YAxis
                    yAxisId="volume"
                    orientation="left"
                    stroke="#64748b"
                    style={{ fontSize: '10px' }}
                    tick={{ fill: '#64748b' }}
                    domain={[0, 'auto']}
                    width={40}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(15, 23, 42, 0.98)',
                      border: '1px solid rgba(59, 130, 246, 0.3)',
                      borderRadius: '8px',
                      padding: '8px 12px',
                    }}
                    labelStyle={{ color: '#94a3b8', marginBottom: '4px' }}
                  />
                  
                  {/* Volume Bars */}
                  <Bar
                    yAxisId="volume"
                    dataKey="volume"
                    fill="#3b82f6"
                    opacity={0.25}
                    radius={[2, 2, 0, 0]}
                  />
                  
                  {/* Bollinger Bands */}
                  {showBB && (
                    <>
                      <Line yAxisId="price" type="monotone" dataKey="bb_upper" stroke="#a855f7" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                      <Line yAxisId="price" type="monotone" dataKey="bb_middle" stroke="#a855f7" strokeWidth={1} dot={false} opacity={0.5} />
                      <Line yAxisId="price" type="monotone" dataKey="bb_lower" stroke="#a855f7" strokeWidth={1} dot={false} strokeDasharray="3 3" />
                    </>
                  )}
                  
                  {/* SMA */}
                  {showSMA && (
                    <Line yAxisId="price" type="monotone" dataKey="sma_20" stroke="#f97316" strokeWidth={2} dot={false} />
                  )}
                  
                  {/* EMA */}
                  {showEMA && (
                    <>
                      <Line yAxisId="price" type="monotone" dataKey="ema_12" stroke="#eab308" strokeWidth={1.5} dot={false} />
                      <Line yAxisId="price" type="monotone" dataKey="ema_26" stroke="#fbbf24" strokeWidth={1.5} dot={false} strokeDasharray="4 4" />
                    </>
                  )}
                  
                  {/* Price Line */}
                  <Area
                    yAxisId="price"
                    type="monotone"
                    dataKey="price"
                    stroke="#3b82f6"
                    strokeWidth={2.5}
                    fill="url(#priceGradient)"
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* RSI Chart */}
            {showRSI && (
              <div style={{ height: '120px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis
                      domain={[0, 100]}
                      ticks={[30, 50, 70]}
                      stroke="#64748b"
                      style={{ fontSize: '10px' }}
                      tick={{ fill: '#64748b' }}
                      width={40}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'rgba(15, 23, 42, 0.98)',
                        border: '1px solid rgba(6, 182, 212, 0.3)',
                        borderRadius: '8px',
                        padding: '6px 10px',
                      }}
                    />
                    <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" strokeWidth={1} />
                    <ReferenceLine y={50} stroke="#64748b" strokeDasharray="2 2" strokeWidth={1} opacity={0.3} />
                    <ReferenceLine y={30} stroke="#10b981" strokeDasharray="3 3" strokeWidth={1} />
                    <Area
                      type="monotone"
                      dataKey="rsi"
                      stroke="#06b6d4"
                      fill="#06b6d4"
                      fillOpacity={0.2}
                      strokeWidth={2}
                      dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* MACD Chart */}
            {showMACD && (
              <div style={{ height: '120px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" vertical={false} />
                    <XAxis dataKey="time" hide />
                    <YAxis
                      stroke="#64748b"
                      style={{ fontSize: '10px' }}
                      tick={{ fill: '#64748b' }}
                      width={40}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'rgba(15, 23, 42, 0.98)',
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                        borderRadius: '8px',
                        padding: '6px 10px',
                      }}
                    />
                    <ReferenceLine y={0} stroke="#64748b" strokeWidth={1} />
                    <Bar
                      dataKey="macd_histogram"
                      fill="#10b981"
                      opacity={0.6}
                      radius={[2, 2, 2, 2]}
                    />
                    <Line type="monotone" dataKey="macd" stroke="#10b981" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="macd_signal" stroke="#ef4444" strokeWidth={2} dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default TechnicalChart;
