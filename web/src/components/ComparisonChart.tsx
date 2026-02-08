import React, { useState, useEffect } from 'react';
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer 
} from 'recharts';
import { TrendingUp, Plus, X, AlertCircle, RefreshCw } from 'lucide-react';
import axios from 'axios';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';

interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ComparisonDataPoint {
  date: string;
  [symbol: string]: number | string; // symbol_return: number, date: string
}

interface SymbolData {
  symbol: string;
  candles: Candle[];
  color: string;
}

interface ComparisonChartProps {
  initialSymbols?: string[];
  timeframe?: '1M' | '3M' | '6M' | '1Y' | 'YTD';
}

const SYMBOL_COLORS = [
  '#10b981', // green
  '#3b82f6', // blue
  '#f59e0b', // amber
  '#ec4899', // pink
  '#8b5cf6', // purple
  '#06b6d4', // cyan
];

const AVAILABLE_STOCKS = [
  'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN',
  'BHARTIARTL', 'HINDUNILVR', 'ITC', 'LT', 'KOTAKBANK', 'AXISBANK',
  'WIPRO', 'HCLTECH', 'MARUTI', 'TATAMOTORS', 'ASIANPAINT', 'BAJFINANCE'
];

const ComparisonChart: React.FC<ComparisonChartProps> = ({ 
  initialSymbols = ['RELIANCE', 'TCS', 'INFY'],
  timeframe = '3M'
}) => {
  const [symbols, setSymbols] = useState<string[]>(initialSymbols);
  const [comparisonData, setComparisonData] = useState<ComparisonDataPoint[]>([]);
  const [correlations, setCorrelations] = useState<{[key: string]: {[key: string]: number}}>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState(timeframe);
  const [showSymbolPicker, setShowSymbolPicker] = useState(false);

  useEffect(() => {
    if (symbols.length > 0) {
      fetchComparisonData();
    }
  }, [symbols, selectedTimeframe]);

  const fetchComparisonData = async () => {
    setLoading(true);
    setError(null);

    try {
      // Calculate date range based on timeframe
      const toDate = new Date();
      const fromDate = new Date();
      
      switch (selectedTimeframe) {
        case '1M':
          fromDate.setMonth(fromDate.getMonth() - 1);
          break;
        case '3M':
          fromDate.setMonth(fromDate.getMonth() - 3);
          break;
        case '6M':
          fromDate.setMonth(fromDate.getMonth() - 6);
          break;
        case '1Y':
          fromDate.setFullYear(fromDate.getFullYear() - 1);
          break;
        case 'YTD':
          fromDate.setMonth(0, 1); // January 1st of current year
          break;
      }

      const fromDateStr = fromDate.toISOString().split('T')[0];
      const toDateStr = toDate.toISOString().split('T')[0];

      // Fetch data for all symbols
      const fetchPromises = symbols.map(symbol =>
        axios.get(`${API_BASE}/market/candles/${symbol}`, {
          params: {
            interval: 'day',
            from_date: fromDateStr,
            to_date: toDateStr
          }
        }).then(res => ({
          symbol,
          candles: res.data.candles || []
        }))
      );

      const results = await Promise.all(fetchPromises);

      // Normalize data to percentage returns
      const normalizedData = normalizeToPercentageReturns(results);
      setComparisonData(normalizedData);

      // Calculate correlations
      if (results.length > 1) {
        const corr = calculateCorrelations(results);
        setCorrelations(corr);
      }
    } catch (err: any) {
      console.error('Failed to fetch comparison data:', err);
      setError(err.response?.data?.detail || 'Failed to load comparison data');
    } finally {
      setLoading(false);
    }
  };

  const normalizeToPercentageReturns = (symbolsData: {symbol: string, candles: Candle[]}[]): ComparisonDataPoint[] => {
    if (symbolsData.length === 0 || symbolsData[0].candles.length === 0) {
      return [];
    }

    // Find common date range (intersection of all symbols' dates)
    const allDates = symbolsData.map(sd => 
      sd.candles.map(c => c.timestamp.split('T')[0])
    );
    
    // Get intersection of all date arrays
    const commonDates = allDates.reduce((acc, dates) => 
      acc.filter(date => dates.includes(date))
    );

    commonDates.sort();

    // Build normalized data
    const normalized: ComparisonDataPoint[] = [];

    commonDates.forEach((date, idx) => {
      const dataPoint: ComparisonDataPoint = { date };

      symbolsData.forEach(sd => {
        const candle = sd.candles.find(c => c.timestamp.split('T')[0] === date);
        if (candle) {
          // Get baseline (first common date price)
          const baselineCandle = sd.candles.find(c => 
            c.timestamp.split('T')[0] === commonDates[0]
          );
          
          if (baselineCandle) {
            const baselinePrice = baselineCandle.close;
            const currentPrice = candle.close;
            const returnPercent = ((currentPrice - baselinePrice) / baselinePrice) * 100;
            dataPoint[sd.symbol] = parseFloat(returnPercent.toFixed(2));
          }
        }
      });

      normalized.push(dataPoint);
    });

    return normalized;
  };

  const calculateCorrelations = (symbolsData: {symbol: string, candles: Candle[]}[]): {[key: string]: {[key: string]: number}} => {
    const correlationMatrix: {[key: string]: {[key: string]: number}} = {};

    // Extract price arrays for each symbol
    const priceArrays: {[symbol: string]: number[]} = {};
    
    symbolsData.forEach(sd => {
      priceArrays[sd.symbol] = sd.candles.map(c => c.close);
    });

    // Calculate correlation for each pair
    const symbolNames = Object.keys(priceArrays);
    
    symbolNames.forEach(symbol1 => {
      correlationMatrix[symbol1] = {};
      
      symbolNames.forEach(symbol2 => {
        if (symbol1 === symbol2) {
          correlationMatrix[symbol1][symbol2] = 1.0;
        } else {
          const correlation = calculatePearsonCorrelation(
            priceArrays[symbol1],
            priceArrays[symbol2]
          );
          correlationMatrix[symbol1][symbol2] = correlation;
        }
      });
    });

    return correlationMatrix;
  };

  const calculatePearsonCorrelation = (x: number[], y: number[]): number => {
    const n = Math.min(x.length, y.length);
    if (n === 0) return 0;

    const sumX = x.slice(0, n).reduce((a, b) => a + b, 0);
    const sumY = y.slice(0, n).reduce((a, b) => a + b, 0);
    const sumXY = x.slice(0, n).reduce((sum, xi, i) => sum + xi * y[i], 0);
    const sumX2 = x.slice(0, n).reduce((sum, xi) => sum + xi * xi, 0);
    const sumY2 = y.slice(0, n).reduce((sum, yi) => sum + yi * yi, 0);

    const numerator = n * sumXY - sumX * sumY;
    const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));

    if (denominator === 0) return 0;
    return numerator / denominator;
  };

  const addSymbol = (symbol: string) => {
    if (!symbols.includes(symbol) && symbols.length < 6) {
      setSymbols([...symbols, symbol]);
      setShowSymbolPicker(false);
    }
  };

  const removeSymbol = (symbol: string) => {
    if (symbols.length > 1) {
      setSymbols(symbols.filter(s => s !== symbol));
    }
  };

  const getSymbolColor = (symbol: string): string => {
    const index = symbols.indexOf(symbol);
    return SYMBOL_COLORS[index % SYMBOL_COLORS.length];
  };

  const getCorrelationColor = (value: number): string => {
    if (value > 0.7) return 'text-emerald-400';
    if (value > 0.3) return 'text-blue-400';
    if (value > -0.3) return 'text-slate-400';
    if (value > -0.7) return 'text-orange-400';
    return 'text-red-400';
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-slate-800/95 border border-slate-700 rounded-lg p-3">
          <p className="text-xs text-slate-400 mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <div key={index} className="flex items-center justify-between gap-4">
              <span className="text-sm" style={{ color: entry.color }}>
                {entry.name}:
              </span>
              <span className="text-sm font-semibold text-white">
                {entry.value > 0 ? '+' : ''}{entry.value.toFixed(2)}%
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <TrendingUp className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-bold text-white">Multi-Symbol Comparison</h2>
        </div>
        
        <div className="flex items-center gap-3">
          {/* Timeframe Selector */}
          <div className="flex items-center gap-1 bg-slate-800/50 rounded-lg p-1">
            {(['1M', '3M', '6M', '1Y', 'YTD'] as const).map(tf => (
              <button
                key={tf}
                onClick={() => setSelectedTimeframe(tf)}
                className={`px-3 py-1 text-xs font-medium rounded transition ${
                  selectedTimeframe === tf
                    ? 'bg-blue-500 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700/50'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>

          {/* Refresh Button */}
          <button
            onClick={fetchComparisonData}
            disabled={loading}
            className="p-2 text-slate-400 hover:text-white hover:bg-slate-800/50 rounded transition"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Symbol Pills */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {symbols.map((symbol, idx) => (
          <div
            key={symbol}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full border"
            style={{ 
              borderColor: getSymbolColor(symbol),
              backgroundColor: `${getSymbolColor(symbol)}20`
            }}
          >
            <span className="text-sm font-semibold" style={{ color: getSymbolColor(symbol) }}>
              {symbol}
            </span>
            {symbols.length > 1 && (
              <button
                onClick={() => removeSymbol(symbol)}
                className="hover:bg-slate-700/50 rounded-full p-0.5 transition"
              >
                <X className="w-3 h-3" style={{ color: getSymbolColor(symbol) }} />
              </button>
            )}
          </div>
        ))}

        {symbols.length < 6 && (
          <button
            onClick={() => setShowSymbolPicker(true)}
            className="flex items-center gap-1 px-3 py-1.5 border border-dashed border-slate-600 rounded-full text-slate-400 hover:text-white hover:border-slate-500 transition text-sm"
          >
            <Plus className="w-3 h-3" />
            Add Stock
          </button>
        )}
      </div>

      {/* Symbol Picker Dropdown */}
      {showSymbolPicker && (
        <div className="mb-4 bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-slate-400">Select a stock to add:</span>
            <button
              onClick={() => setShowSymbolPicker(false)}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="grid grid-cols-6 gap-2">
            {AVAILABLE_STOCKS.filter(s => !symbols.includes(s)).map(stock => (
              <button
                key={stock}
                onClick={() => addSymbol(stock)}
                className="px-2 py-1 text-xs bg-slate-700/50 hover:bg-slate-700 rounded text-slate-300 hover:text-white transition"
              >
                {stock}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <span className="text-sm text-red-400">{error}</span>
        </div>
      )}

      {/* Chart */}
      <div className="bg-slate-800/30 rounded-lg p-4 mb-4" style={{ height: '400px' }}>
        {loading ? (
          <div className="flex items-center justify-center h-full">
            <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={comparisonData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis 
                dataKey="date" 
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickFormatter={(value) => {
                  const date = new Date(value);
                  return `${date.getMonth() + 1}/${date.getDate()}`;
                }}
              />
              <YAxis 
                stroke="#94a3b8"
                tick={{ fill: '#94a3b8', fontSize: 11 }}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend 
                wrapperStyle={{ paddingTop: '20px' }}
                iconType="line"
              />
              {symbols.map((symbol, idx) => (
                <Line
                  key={symbol}
                  type="monotone"
                  dataKey={symbol}
                  stroke={getSymbolColor(symbol)}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Correlation Matrix */}
      {symbols.length > 1 && Object.keys(correlations).length > 0 && (
        <div className="bg-slate-800/30 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-300 mb-3">Correlation Matrix</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr>
                  <th className="text-left text-slate-500 pb-2">Symbol</th>
                  {symbols.map(symbol => (
                    <th 
                      key={symbol} 
                      className="text-center text-slate-500 pb-2"
                      style={{ color: getSymbolColor(symbol) }}
                    >
                      {symbol}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {symbols.map(symbol1 => (
                  <tr key={symbol1}>
                    <td 
                      className="py-1 font-medium"
                      style={{ color: getSymbolColor(symbol1) }}
                    >
                      {symbol1}
                    </td>
                    {symbols.map(symbol2 => {
                      const value = correlations[symbol1]?.[symbol2] || 0;
                      return (
                        <td 
                          key={symbol2}
                          className={`text-center py-1 font-semibold ${getCorrelationColor(value)}`}
                        >
                          {value.toFixed(2)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
            <span><span className="text-emerald-400">■</span> Strong positive (&gt;0.7)</span>
            <span><span className="text-blue-400">■</span> Moderate (0.3-0.7)</span>
            <span><span className="text-slate-400">■</span> Weak (-0.3-0.3)</span>
            <span><span className="text-red-400">■</span> Negative (&lt;-0.7)</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ComparisonChart;
