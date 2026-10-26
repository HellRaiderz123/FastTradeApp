import React, { useState } from 'react';
import { Bot, Search } from 'lucide-react';
import QuantTelemetryCard from '../components/QuantTelemetryCard';
import QuantBotPanel from '../components/QuantBotPanel';

const QuantBot: React.FC = () => {
  const [symbol, setSymbol] = useState('NIFTY');
  const [inputValue, setInputValue] = useState('NIFTY');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      setSymbol(inputValue.trim().toUpperCase());
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <Bot className="w-7 h-7 text-purple-400" />
          Quant Bot
        </h1>
        <p className="text-slate-400 mt-1">
          Quantitative analysis with ORB, RVOL, VWAP, Hurst, Greeks, GEX, and more
        </p>
      </div>

      {/* Symbol Search */}
      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex gap-2 max-w-md">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Enter symbol (e.g., RELIANCE, NIFTY)"
              className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
            />
          </div>
          <button
            type="submit"
            className="px-4 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg transition-colors"
          >
            Analyze
          </button>
        </div>
      </form>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Bot Control Panel */}
        <div className="lg:col-span-1">
          <QuantBotPanel symbol={symbol} />
        </div>

        {/* Telemetry Card */}
        <div className="lg:col-span-2">
          <QuantTelemetryCard
            symbol={symbol}
            showOptions={true}
            autoRefreshInterval={60}
          />
        </div>
      </div>
    </div>
  );
};

export default QuantBot;
