/**
 * Calculate historical returns for different time periods
 */

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface PeriodReturn {
  period: string;
  return_percent: number;
  start_price: number;
  end_price: number;
  days: number;
}

export interface HistoricalReturns {
  symbol: string;
  current_price: number;
  returns: {
    '1D': PeriodReturn | null;
    '1W': PeriodReturn | null;
    '1M': PeriodReturn | null;
    '3M': PeriodReturn | null;
    '6M': PeriodReturn | null;
    '1Y': PeriodReturn | null;
  };
}

/**
 * Calculate return percentage between two prices
 */
function calculateReturn(startPrice: number, endPrice: number): number {
  if (startPrice === 0) return 0;
  return ((endPrice - startPrice) / startPrice) * 100;
}

/**
 * Find candle closest to target date (going backwards)
 */
function findCandleNearDate(candles: Candle[], targetDate: Date): Candle | null {
  if (!candles || candles.length === 0) return null;
  
  // Sort candles by date (newest first)
  const sorted = [...candles].sort((a, b) => 
    new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
  
  // Find the first candle on or before target date
  for (const candle of sorted) {
    const candleDate = new Date(candle.timestamp);
    if (candleDate <= targetDate) {
      return candle;
    }
  }
  
  // If no candle found before target, return oldest candle
  return sorted[sorted.length - 1];
}

/**
 * Calculate historical returns from daily candle data
 * 
 * @param candles - Array of daily candles (sorted by date)
 * @param currentPrice - Current market price
 * @param symbol - Stock symbol
 * @returns HistoricalReturns object with returns for all periods
 */
export function calculateHistoricalReturns(
  candles: Candle[],
  currentPrice: number,
  symbol: string
): HistoricalReturns {
  const result: HistoricalReturns = {
    symbol,
    current_price: currentPrice,
    returns: {
      '1D': null,
      '1W': null,
      '1M': null,
      '3M': null,
      '6M': null,
      '1Y': null,
    }
  };
  
  if (!candles || candles.length === 0) {
    return result;
  }
  
  const now = new Date();
  
  // Define periods (working backwards from today)
  const periods = [
    { key: '1D' as const, days: 1, label: '1 Day' },
    { key: '1W' as const, days: 7, label: '1 Week' },
    { key: '1M' as const, days: 30, label: '1 Month' },
    { key: '3M' as const, days: 90, label: '3 Months' },
    { key: '6M' as const, days: 180, label: '6 Months' },
    { key: '1Y' as const, days: 365, label: '1 Year' },
  ];
  
  // Calculate returns for each period
  for (const period of periods) {
    const targetDate = new Date(now);
    targetDate.setDate(targetDate.getDate() - period.days);
    
    const historicalCandle = findCandleNearDate(candles, targetDate);
    
    if (historicalCandle) {
      const startPrice = historicalCandle.close;
      const returnPercent = calculateReturn(startPrice, currentPrice);
      
      result.returns[period.key] = {
        period: period.label,
        return_percent: parseFloat(returnPercent.toFixed(2)),
        start_price: startPrice,
        end_price: currentPrice,
        days: period.days,
      };
    }
  }
  
  return result;
}

/**
 * Format return percentage with color and sign
 */
export function formatReturnPercent(returnPercent: number): {
  formatted: string;
  color: string;
  sign: string;
} {
  const sign = returnPercent >= 0 ? '+' : '';
  const color = returnPercent >= 0 ? 'text-green-400' : 'text-red-400';
  const formatted = `${sign}${returnPercent.toFixed(2)}%`;
  
  return { formatted, color, sign };
}

/**
 * Calculate annualized return from period return
 */
export function calculateAnnualizedReturn(periodReturn: number, days: number): number {
  if (days === 0) return 0;
  const yearsElapsed = days / 365;
  return Math.pow(1 + periodReturn / 100, 1 / yearsElapsed) - 1;
}
