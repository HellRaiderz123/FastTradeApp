import React from 'react';
import { cn } from '@/lib/utils';

export type Timeframe = '1m' | '5m' | '15m' | '1h' | 'daily';

interface TimeframeSelectorProps {
  selectedTimeframe: Timeframe;
  onTimeframeChange: (timeframe: Timeframe) => void;
  availableTimeframes?: Timeframe[];
  className?: string;
}

const DEFAULT_TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', 'daily'];

const LABELS: Record<Timeframe, string> = {
  '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1H', 'daily': '1D',
};

const TimeframeSelector: React.FC<TimeframeSelectorProps> = ({
  selectedTimeframe,
  onTimeframeChange,
  availableTimeframes = DEFAULT_TIMEFRAMES,
  className,
}) => (
  <div className={cn('flex items-center gap-0.5 rounded-lg border border-border bg-muted/40 p-0.5', className)}>
    {availableTimeframes.map((tf) => (
      <button
        key={tf}
        onClick={() => onTimeframeChange(tf)}
        className={cn(
          'px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors',
          selectedTimeframe === tf
            ? 'bg-primary text-primary-foreground shadow-sm'
            : 'text-muted-foreground hover:text-foreground hover:bg-accent'
        )}
      >
        {LABELS[tf]}
      </button>
    ))}
  </div>
);

export default TimeframeSelector;
