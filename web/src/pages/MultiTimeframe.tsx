import React from 'react';
import { BarChart3 } from 'lucide-react';
import CandleChart from '../components/CandleChart';

const MultiTimeframeDemo: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <BarChart3 className="w-8 h-8 text-blue-500" />
          <div>
            <h1 className="text-3xl font-bold text-white">Multi-Timeframe Candles</h1>
            <p className="text-gray-400 mt-1">
              View candlestick data across multiple timeframes (1m, 5m, 15m, 1h, daily)
            </p>
          </div>
        </div>

        {/* Candle Charts */}
        <div className="space-y-6">
          {/* NIFTY Chart */}
          <CandleChart
            symbol="NIFTY"
            defaultTimeframe="15m"
            height={400}
            showTimeframeSelector={true}
          />

          {/* Additional examples */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <CandleChart
              symbol="BANKNIFTY"
              defaultTimeframe="5m"
              height={300}
              showTimeframeSelector={true}
            />
            
            <CandleChart
              symbol="FINNIFTY"
              defaultTimeframe="1h"
              height={300}
              showTimeframeSelector={true}
            />
          </div>
        </div>

        {/* Info Box */}
        <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-4">
          <h3 className="text-blue-400 font-semibold mb-2">📊 About Multi-Timeframe Candles</h3>
          <ul className="text-gray-300 text-sm space-y-1 list-disc list-inside">
            <li><strong>1m:</strong> 1-minute candles for ultra-short-term scalping</li>
            <li><strong>5m:</strong> 5-minute candles for intraday trading</li>
            <li><strong>15m:</strong> 15-minute candles for swing trades</li>
            <li><strong>1h:</strong> 1-hour candles for medium-term analysis</li>
            <li><strong>Daily:</strong> Daily candles for long-term trends</li>
          </ul>
          <p className="text-gray-400 text-xs mt-3">
            💡 <strong>Tip:</strong> Use smaller timeframes (1m, 5m) for entry/exit timing and larger timeframes (1h, daily) for trend confirmation.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MultiTimeframeDemo;
