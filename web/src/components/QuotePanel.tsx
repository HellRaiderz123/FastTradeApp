import React from 'react';
import { TrendingUp, TrendingDown, Activity, BarChart3 } from 'lucide-react';
import { QuoteData } from '../hooks/useRealtimeQuotes';

interface QuotePanelProps {
  symbol: string;
  quote: QuoteData | null;
  onClick?: () => void;
}

const QuotePanel: React.FC<QuotePanelProps> = ({ symbol, quote, onClick }) => {
  if (!quote) {
    return (
      <div 
        className="terminal-panel rounded-xl p-4 cursor-pointer hover:border-blue-500/50 transition-all"
        onClick={onClick}
      >
        <div className="flex items-center gap-2 mb-2">
          <Activity size={16} className="text-slate-400 animate-pulse" />
          <h3 className="text-sm font-semibold text-slate-300">{symbol}</h3>
        </div>
        <div className="space-y-2 animate-pulse">
          <div className="h-5 bg-slate-800 rounded w-20"></div>
          <div className="h-3 bg-slate-800 rounded w-14"></div>
        </div>
      </div>
    );
  }

  const isPositive = quote.change >= 0;
  const changeColor = isPositive ? 'text-emerald-400' : 'text-red-400';
  const bgColor = isPositive ? 'bg-emerald-500/10' : 'bg-red-500/10';

  return (
    <div
      className="terminal-panel rounded-xl p-4 cursor-pointer hover:border-blue-500/50 transition-all group"
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-white">{symbol}</h3>
        <div className={`p-1.5 rounded-lg ${bgColor}`}>
          {isPositive ? (
            <TrendingUp size={14} className="text-emerald-400" />
          ) : (
            <TrendingDown size={14} className="text-red-400" />
          )}
        </div>
      </div>

      {/* Price */}
      <div className="mb-2">
        <p className="text-2xl font-bold text-white">
          ₹{quote.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </p>
      </div>

      {/* Change */}
      <div className="flex items-center gap-2 mb-3">
        <span className={`text-sm font-medium ${changeColor}`}>
          {isPositive ? '+' : ''}
          {quote.change.toFixed(2)}
        </span>
        <span className={`text-sm font-medium ${changeColor}`}>
          ({isPositive ? '+' : ''}{quote.change_percent.toFixed(2)}%)
        </span>
      </div>

      {/* Volume */}
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <BarChart3 size={12} />
        <span>Vol: {(quote.volume / 100000).toFixed(2)}L</span>
      </div>

      {/* Hover Effect Indicator */}
      <div className="mt-3 pt-3 border-t border-slate-700/50 opacity-0 group-hover:opacity-100 transition-opacity">
        <p className="text-xs text-blue-400">Click to view chart</p>
      </div>
    </div>
  );
};

export default QuotePanel;
