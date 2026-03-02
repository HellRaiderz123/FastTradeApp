import React from 'react';
import { Clock } from 'lucide-react';

export type Timeframe = '1m' | '5m' | '15m' | '1h' | 'daily';

interface TimeframeSelectorProps {
  selectedTimeframe: Timeframe;
  onTimeframeChange: (timeframe: Timeframe) => void;
  availableTimeframes?: Timeframe[];
  className?: string;
}

const DEFAULT_TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', 'daily'];

const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  '1m': '1M',
  '5m': '5M',
  '15m': '15M',
  '1h': '1H',
  'daily': '1D',
};

const TimeframeSelector: React.FC<TimeframeSelectorProps> = ({
  selectedTimeframe,
  onTimeframeChange,
  availableTimeframes = DEFAULT_TIMEFRAMES,
  className = '',
}) => {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Clock className="w-4 h-4 text-gray-400" />
      <div className="inline-flex rounded-lg border border-gray-700 bg-gray-800 p-1">
        {availableTimeframes.map((tf) => (
          <button
            key={tf}
            onClick={() => onTimeframeChange(tf)}
            className={`
              px-3 py-1 text-xs font-medium rounded-md transition-colors
              ${
                selectedTimeframe === tf
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }
            `}
          >
            {TIMEFRAME_LABELS[tf]}
          </button>
        ))}
      </div>
    </div>
  );
};

export default TimeframeSelector;
