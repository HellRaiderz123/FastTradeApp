/**
 * TradingChart — professional candlestick chart using lightweight-charts v5.
 *
 * Replaces the recharts-based fake candle chart everywhere in FastTrade.
 * Uses the same charting library that powers OpenAlgo's charts.
 *
 * Features:
 * - Real candlestick series (not bar approximations)
 * - Volume histogram on a separate pane
 * - Crosshair OHLCV legend
 * - Timeframe selector
 * - Theme-aware (dark / light via CSS vars)
 * - Auto-fits on load, handles resize
 */

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type Time,
  type MouseEventParams,
  ColorType,
} from 'lightweight-charts';
import { TrendingUp, TrendingDown, Activity, RefreshCw, AlertTriangle } from 'lucide-react';
import { marketAPI } from '../lib/api';
import api from '../lib/api';
import { cn } from '@/lib/utils';

export type Timeframe = '1m' | '5m' | '15m' | '1h' | 'daily';

const TF_LABELS: Record<Timeframe, string> = {
  '1m': '1m', '5m': '5m', '15m': '15m', '1h': '1H', 'daily': '1D',
};
const TF_LIST: Timeframe[] = ['1m', '5m', '15m', '1h', 'daily'];

interface RawCandle {
  timestamp?: string;
  date?: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface OhlcvLegend {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  up: boolean;
}

export interface TradingChartProps {
  symbol: string;
  defaultTimeframe?: Timeframe;
  height?: number;
  /** Hide the timeframe pill bar */
  showTimeframeSelector?: boolean;
  /** Hide the symbol/price header */
  showHeader?: boolean;
  className?: string;
}

function isDarkMode() {
  return !document.documentElement.classList.contains('light-mode');
}

function buildChartColors(dark: boolean) {
  return {
    bg:          dark ? '#0b1222' : '#ffffff',
    text:        dark ? '#94a3b8' : '#64748b',
    grid:        dark ? 'rgba(148,163,184,0.08)' : 'rgba(100,116,139,0.12)',
    border:      dark ? 'rgba(148,163,184,0.15)' : 'rgba(100,116,139,0.2)',
    crosshair:   dark ? 'rgba(148,163,184,0.4)' : 'rgba(100,116,139,0.5)',
    upCandle:    '#10b981',
    downCandle:  '#ef4444',
    upWick:      '#10b981',
    downWick:    '#ef4444',
    upVol:       'rgba(16,185,129,0.45)',
    downVol:     'rgba(239,68,68,0.45)',
  };
}

function fmtVol(v: number) {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  return String(v);
}

const TradingChart: React.FC<TradingChartProps> = ({
  symbol,
  defaultTimeframe = '15m',
  height = 340,
  showTimeframeSelector = true,
  showHeader = true,
  className,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  const [timeframe, setTimeframe] = useState<Timeframe>(defaultTimeframe);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [legend, setLegend] = useState<OhlcvLegend | null>(null);
  const [lastBar, setLastBar] = useState<{ price: number; change: number } | null>(null);
  const [staleDate, setStaleDate] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Build / rebuild chart when container mounts
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const dark = isDarkMode();
    const c = buildChartColors(dark);

    const chart = createChart(el, {
      autoSize: true,
      height,
      layout: {
        background: { type: ColorType.Solid, color: c.bg },
        textColor: c.text,
        fontFamily: "'IBM Plex Sans', system-ui, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: c.grid },
        horzLines: { color: c.grid },
      },
      crosshair: {
        vertLine: { color: c.crosshair, labelBackgroundColor: dark ? '#1e293b' : '#f1f5f9' },
        horzLine: { color: c.crosshair, labelBackgroundColor: dark ? '#1e293b' : '#f1f5f9' },
      },
      rightPriceScale: {
        borderColor: c.border,
      },
      timeScale: {
        borderColor: c.border,
        timeVisible: true,
        secondsVisible: false,
        fixLeftEdge: false,
        fixRightEdge: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    // Candlestick series
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: c.upCandle,
      downColor: c.downCandle,
      borderUpColor: c.upCandle,
      borderDownColor: c.downCandle,
      wickUpColor: c.upWick,
      wickDownColor: c.downWick,
    });

    // Volume histogram — separate pane
    const vol = chart.addSeries(HistogramSeries, {
      color: c.upVol,
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
    });
    vol.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleRef.current = candle;
    volRef.current = vol;

    // Crosshair legend
    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      if (!param.time || !param.seriesData) {
        setLegend(null);
        return;
      }
      const bar = param.seriesData.get(candle) as CandlestickData | undefined;
      const volBar = param.seriesData.get(vol) as HistogramData | undefined;
      if (!bar) { setLegend(null); return; }

      const t = param.time as number;
      const date = new Date(t * 1000);
      const timeStr = timeframe === 'daily'
        ? date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' })
        : date.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

      setLegend({
        time: timeStr,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: (volBar?.value as number) ?? 0,
        up: bar.close >= bar.open,
      });
    });

    // Resize observer — autoSize handles width, but we still need it for
    // cases where the parent container changes size after mount.
    const ro = new ResizeObserver(() => {
      chartRef.current?.applyOptions({ height });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volRef.current = null;
    };
  }, [height]); // only rebuild if height prop changes

  // Re-theme when OS/app theme changes
  useEffect(() => {
    const observer = new MutationObserver(() => {
      const chart = chartRef.current;
      if (!chart) return;
      const dark = isDarkMode();
      const c = buildChartColors(dark);
      chart.applyOptions({
        layout: { background: { type: ColorType.Solid, color: c.bg }, textColor: c.text },
        grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
        crosshair: {
          vertLine: { color: c.crosshair, labelBackgroundColor: dark ? '#1e293b' : '#f1f5f9' },
          horzLine: { color: c.crosshair, labelBackgroundColor: dark ? '#1e293b' : '#f1f5f9' },
        },
        rightPriceScale: { borderColor: c.border },
        timeScale: { borderColor: c.border },
      });
      candleRef.current?.applyOptions({
        upColor: c.upCandle, downColor: c.downCandle,
        borderUpColor: c.upCandle, borderDownColor: c.downCandle,
        wickUpColor: c.upWick, wickDownColor: c.downWick,
      });
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  // TF → scanner backfill label
  const TF_TO_BACKFILL: Record<Timeframe, string> = {
    '1m': '1 Min', '5m': '5 Min', '15m': '15 Min', '1h': '1 Hour', 'daily': 'Day',
  };

  // Load candles from DB
  const loadData = useCallback(async () => {
    if (!candleRef.current || !volRef.current) return;
    setLoading(true);
    setError(null);
    setLegend(null);
    setStaleDate(null);

    try {
      let raw: RawCandle[] = [];
      const candidates: Timeframe[] = [timeframe, '15m', 'daily'];
      for (const tf of [...new Set(candidates)]) {
        const res = await marketAPI.getCandlesDB(symbol, tf, 300);
        const data = Array.isArray(res.data) ? res.data : [];
        if (data.length > 0) { raw = data; break; }
      }

      if (raw.length === 0) {
        setError('No candle data — click Refresh to load from Zerodha');
        setLoading(false);
        return;
      }

      const sorted = [...raw].sort((a, b) =>
        new Date(a.timestamp || a.date || 0).getTime() -
        new Date(b.timestamp || b.date || 0).getTime()
      );

      // Detect stale data: last candle older than 1 day
      const last = sorted[sorted.length - 1];
      const lastTs = new Date(last.timestamp || last.date || 0);
      const daysSinceLastCandle = (Date.now() - lastTs.getTime()) / 86400000;
      if (daysSinceLastCandle > 1) {
        setStaleDate(lastTs.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }));
      }

      const dark = isDarkMode();
      const c = buildChartColors(dark);
      const candles: CandlestickData[] = [];
      const vols: HistogramData[] = [];

      for (const row of sorted) {
        const ts = Math.floor(new Date(row.timestamp || row.date || 0).getTime() / 1000) as Time;
        if (!ts) continue;
        candles.push({ time: ts, open: row.open, high: row.high, low: row.low, close: row.close });
        vols.push({ time: ts, value: row.volume, color: row.close >= row.open ? c.upVol : c.downVol });
      }

      candleRef.current.setData(candles);
      volRef.current.setData(vols);
      chartRef.current?.timeScale().fitContent();

      const prev = sorted[sorted.length - 2];
      if (last && prev) {
        setLastBar({ price: last.close, change: ((last.close - prev.close) / prev.close) * 100 });
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load chart data');
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);

  // Trigger backfill for this symbol+timeframe then reload
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await api.post('/condition-scanner/backfill-candles', null, {
        params: { timeframe: TF_TO_BACKFILL[timeframe], symbols: symbol, days: timeframe === 'daily' ? 365 : 60 },
      });
    } catch { /* ignore — loadData will show whatever is in DB */ }
    await loadData();
    setRefreshing(false);
  }, [symbol, timeframe, loadData]);

  useEffect(() => { loadData(); }, [loadData]);

  const up = (lastBar?.change ?? 0) >= 0;

  return (
    <div className={cn('flex flex-col bg-card border border-border rounded-xl overflow-hidden', className)}>
      {/* Header */}
      {showHeader && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-border shrink-0">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-foreground">{symbol}</span>
            {lastBar && (
              <>
                <span className="text-sm font-mono text-foreground">
                  ₹{lastBar.price.toFixed(2)}
                </span>
                <span className={cn(
                  'flex items-center gap-0.5 text-xs font-semibold',
                  up ? 'text-emerald-500' : 'text-red-500'
                )}>
                  {up ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                  {up ? '+' : ''}{lastBar.change.toFixed(2)}%
                </span>
              </>
            )}
            {/* Stale data warning + refresh */}
            {staleDate && (
              <span className="flex items-center gap-1 text-[10px] text-amber-500 bg-amber-500/10 border border-amber-500/30 rounded px-1.5 py-0.5">
                <AlertTriangle className="h-3 w-3" />
                Data up to {staleDate}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1">
            {/* Refresh button */}
            <button
              onClick={handleRefresh}
              disabled={refreshing || loading}
              title="Refresh candles from Zerodha"
              className="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition disabled:opacity-40"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', (refreshing || loading) && 'animate-spin')} />
            </button>

            {showTimeframeSelector && (
              <div className="flex items-center gap-0.5 rounded-lg border border-border bg-muted/40 p-0.5">
                {TF_LIST.map((tf) => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={cn(
                      'px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors',
                      timeframe === tf
                        ? 'bg-primary text-primary-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent'
                    )}
                  >
                    {TF_LABELS[tf]}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* OHLCV crosshair legend */}
      {legend && (
        <div className="flex items-center gap-3 px-4 py-1.5 border-b border-border bg-muted/20 text-[11px] font-mono shrink-0">
          <span className="text-muted-foreground">{legend.time}</span>
          <span className="text-muted-foreground">O <span className={legend.up ? 'text-emerald-500' : 'text-red-500'}>{legend.open.toFixed(2)}</span></span>
          <span className="text-muted-foreground">H <span className="text-emerald-500">{legend.high.toFixed(2)}</span></span>
          <span className="text-muted-foreground">L <span className="text-red-500">{legend.low.toFixed(2)}</span></span>
          <span className="text-muted-foreground">C <span className={legend.up ? 'text-emerald-500' : 'text-red-500'}>{legend.close.toFixed(2)}</span></span>
          <span className="text-muted-foreground">V <span className="text-blue-400">{fmtVol(legend.volume)}</span></span>
        </div>
      )}

      {/* Chart area — explicit pixel height so lightweight-charts has a real box */}
      <div className="relative" style={{ height }}>
        <div ref={containerRef} className="absolute inset-0" />

        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-card/80 backdrop-blur-sm z-10">
            <div className="flex flex-col items-center gap-2">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span className="text-xs text-muted-foreground">Loading {symbol}…</span>
            </div>
          </div>
        )}

        {/* Error overlay */}
        {!loading && error && (
          <div className="absolute inset-0 flex items-center justify-center bg-card z-10">
            <div className="flex flex-col items-center gap-3 text-center px-4">
              <Activity className="h-8 w-8 text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">{error}</p>
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 transition disabled:opacity-50"
              >
                <RefreshCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
                {refreshing ? 'Loading from Zerodha…' : 'Load candles from Zerodha'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TradingChart;
