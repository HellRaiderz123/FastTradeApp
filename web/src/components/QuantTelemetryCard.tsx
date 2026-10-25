import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  Target,
  AlertTriangle,
  Zap,
  Loader2,
  RefreshCw,
  Play,
  Pause,
  Bot,
} from 'lucide-react';
import { quantAPI, CashQuantReport, OptionsQuantReport } from '../api/quantAPI';

interface QuantTelemetryCardProps {
  symbol: string;
  showOptions?: boolean;
  className?: string;
  autoRefreshInterval?: number; // seconds, 0 = disabled
  onReportUpdate?: (cash: CashQuantReport | null, options: OptionsQuantReport | null) => void;
}

const QuantTelemetryCard: React.FC<QuantTelemetryCardProps> = ({
  symbol,
  showOptions = false,
  className = '',
  autoRefreshInterval = 0,
  onReportUpdate,
}) => {
  const [cashReport, setCashReport] = useState<CashQuantReport | null>(null);
  const [optionsReport, setOptionsReport] = useState<OptionsQuantReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(autoRefreshInterval > 0);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    if (!symbol || symbol.length < 2) return;

    setLoading(true);
    setError(null);

    try {
      // Fetch cash report
      const cashRes = await quantAPI.getCashReport(symbol);
      setCashReport(cashRes.data);

      // Fetch options report if requested
      let optRes: OptionsQuantReport | null = null;
      if (showOptions) {
        try {
          const optData = await quantAPI.getOptionsReport(symbol);
          optRes = optData.data;
          setOptionsReport(optRes);
        } catch {
          setOptionsReport(null);
        }
      }

      setLastUpdate(new Date());
      onReportUpdate?.(cashRes.data, optRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to fetch quant data');
      setCashReport(null);
      setOptionsReport(null);
      onReportUpdate?.(null, null);
    }

    setLoading(false);
  }, [symbol, showOptions, onReportUpdate]);

  // Initial fetch
  useEffect(() => {
    fetchData();
  }, [symbol, showOptions]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh || autoRefreshInterval <= 0) return;

    const interval = setInterval(fetchData, autoRefreshInterval * 1000);
    return () => clearInterval(interval);
  }, [autoRefresh, autoRefreshInterval, fetchData]);

  if (loading) {
    return (
      <div className={`p-4 bg-slate-800 border border-slate-700 rounded-xl ${className}`}>
        <div className="flex items-center justify-center gap-2 text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          Loading quant data...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 bg-slate-800 border border-slate-700 rounded-xl ${className}`}>
        <div className="flex items-center gap-2 text-amber-400">
          <AlertTriangle className="w-4 h-4" />
          <span className="text-sm">{error}</span>
        </div>
      </div>
    );
  }

  if (!cashReport) return null;

  const regimeColor = {
    TRENDING: 'text-green-400',
    MEAN_REVERTING: 'text-amber-400',
    RANDOM: 'text-slate-400',
  }[cashReport.regime];

  const rvolColor = {
    HIGH: 'text-green-400',
    LOW: 'text-red-400',
    NORMAL: 'text-slate-400',
  }[cashReport.rvol_signal];

  const orbColor = {
    BULLISH: 'text-green-400',
    BEARISH: 'text-red-400',
    NONE: 'text-slate-400',
  }[cashReport.orb_breakout];

  return (
    <div className={`bg-slate-800 border border-slate-700 rounded-xl overflow-hidden ${className}`}>
      {/* Header with Bot Controls */}
      <div className="px-4 py-3 bg-slate-700/50 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <Bot className="w-4 h-4 text-purple-400" />
            Quant Telemetry
          </h3>
          <div className="flex items-center gap-2">
            {/* Auto-refresh toggle */}
            {autoRefreshInterval > 0 && (
              <button
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={`p-1.5 rounded transition-colors ${
                  autoRefresh
                    ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
                    : 'bg-slate-600 text-slate-400 hover:bg-slate-500'
                }`}
                title={autoRefresh ? 'Pause auto-refresh' : 'Start auto-refresh'}
              >
                {autoRefresh ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
              </button>
            )}
            {/* Manual refresh */}
            <button
              onClick={fetchData}
              disabled={loading}
              className="p-1.5 rounded bg-slate-600 text-slate-400 hover:bg-slate-500 hover:text-white transition-colors disabled:opacity-50"
              title="Refresh now"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <span className="text-xs text-slate-400">{symbol}</span>
          </div>
        </div>
        {/* Last update indicator */}
        {lastUpdate && (
          <div className="mt-1 text-xs text-slate-500">
            Updated {lastUpdate.toLocaleTimeString()}
            {autoRefresh && <span className="ml-1 text-green-400">• Live</span>}
          </div>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Regime & Hurst */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 bg-slate-700/50 rounded-lg">
            <p className="text-xs text-slate-400 mb-1">Market Regime</p>
            <p className={`text-lg font-bold ${regimeColor}`}>
              {cashReport.regime.replace('_', ' ')}
            </p>
            <p className="text-xs text-slate-500">H = {cashReport.hurst_exponent.toFixed(3)}</p>
          </div>
          <div className="p-3 bg-slate-700/50 rounded-lg">
            <p className="text-xs text-slate-400 mb-1">RVOL</p>
            <p className={`text-lg font-bold ${rvolColor}`}>
              {cashReport.rvol.toFixed(2)}x
            </p>
            <p className="text-xs text-slate-500">{cashReport.rvol_signal}</p>
          </div>
        </div>

        {/* ORB & VWAP */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 bg-slate-700/50 rounded-lg">
            <p className="text-xs text-slate-400 mb-1">ORB Breakout</p>
            <p className={`text-sm font-bold ${orbColor}`}>
              {cashReport.orb_breakout}
            </p>
            <p className="text-xs text-slate-500">
              H: {cashReport.orb_high.toFixed(2)} | L: {cashReport.orb_low.toFixed(2)}
            </p>
          </div>
          <div className="p-3 bg-slate-700/50 rounded-lg">
            <p className="text-xs text-slate-400 mb-1">VWAP</p>
            <p className="text-sm font-bold text-white">
              {cashReport.vwap.toFixed(2)}
            </p>
            <p className={`text-xs ${
              cashReport.price_vs_vwap === 'ABOVE' ? 'text-green-400' :
              cashReport.price_vs_vwap === 'BELOW' ? 'text-red-400' : 'text-slate-400'
            }`}>
              {cashReport.price_vs_vwap}
            </p>
          </div>
        </div>

        {/* RS & Z-Score */}
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2 bg-slate-700/30 rounded">
            <p className="text-xs text-slate-500">RS vs Nifty</p>
            <p className={`text-sm font-semibold ${cashReport.rs_vs_nifty_5d > 0 ? 'text-green-400' : 'text-red-400'}`}>
              {cashReport.rs_vs_nifty_5d > 0 ? '+' : ''}{cashReport.rs_vs_nifty_5d.toFixed(2)}%
            </p>
          </div>
          <div className="p-2 bg-slate-700/30 rounded">
            <p className="text-xs text-slate-500">Z-Score</p>
            <p className={`text-sm font-semibold ${
              Math.abs(cashReport.zscore_20) > 2 ? 'text-amber-400' : 'text-slate-300'
            }`}>
              {cashReport.zscore_20.toFixed(2)}
            </p>
          </div>
          <div className="p-2 bg-slate-700/30 rounded">
            <p className="text-xs text-slate-500">BB Width %</p>
            <p className="text-sm font-semibold text-slate-300">
              {cashReport.bb_width_percentile.toFixed(0)}%
            </p>
          </div>
        </div>

        {/* ATR & Position Sizing */}
        <div className="grid grid-cols-2 gap-3">
          <div className="p-3 bg-slate-700/50 rounded-lg">
            <p className="text-xs text-slate-400 mb-1">ATR (14)</p>
            <p className="text-lg font-bold text-white">
              ₹{cashReport.atr_14.toFixed(2)}
            </p>
            <p className="text-xs text-red-400">
              SL: ₹{cashReport.suggested_stop_loss.toFixed(2)}
            </p>
          </div>
          <div className="p-3 bg-slate-700/50 rounded-lg">
            <p className="text-xs text-slate-400 mb-1">Position Size</p>
            <p className="text-lg font-bold text-white">
              {cashReport.position_size_lots} lots
            </p>
            <p className="text-xs text-slate-500">Based on 1% risk</p>
          </div>
        </div>

        {/* Delivery */}
        {cashReport.delivery_pct > 0 && (
          <div className={`p-3 rounded-lg ${
            cashReport.institutional_accumulation
              ? 'bg-green-500/10 border border-green-500/30'
              : 'bg-slate-700/50'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-400">Delivery %</p>
                <p className={`text-lg font-bold ${
                  cashReport.delivery_pct > 60 ? 'text-green-400' : 'text-slate-300'
                }`}>
                  {cashReport.delivery_pct.toFixed(1)}%
                </p>
              </div>
              {cashReport.institutional_accumulation && (
                <div className="flex items-center gap-1 text-green-400">
                  <Zap className="w-4 h-4" />
                  <span className="text-xs font-semibold">Institutional</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Options Data */}
        {optionsReport && (
          <div className="border-t border-slate-700 pt-4 mt-4">
            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-purple-400" />
              Options Telemetry
            </h4>

            {/* IV & GEX */}
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div className="p-3 bg-slate-700/50 rounded-lg">
                <p className="text-xs text-slate-400 mb-1">IV Percentile</p>
                <p className={`text-lg font-bold ${
                  optionsReport.iv_percentile > 65 ? 'text-red-400' :
                  optionsReport.iv_percentile < 35 ? 'text-green-400' : 'text-slate-300'
                }`}>
                  {optionsReport.iv_percentile.toFixed(0)}%
                </p>
                <p className="text-xs text-slate-500">
                  ATM IV: {(optionsReport.atm_iv * 100).toFixed(1)}%
                </p>
              </div>
              <div className="p-3 bg-slate-700/50 rounded-lg">
                <p className="text-xs text-slate-400 mb-1">GEX Regime</p>
                <p className={`text-lg font-bold ${
                  optionsReport.gex_regime === 'POSITIVE_GEX' ? 'text-green-400' :
                  optionsReport.gex_regime === 'NEGATIVE_GEX' ? 'text-red-400' : 'text-slate-300'
                }`}>
                  {optionsReport.gex_regime.replace('_', ' ')}
                </p>
                <p className="text-xs text-slate-500">
                  Net: {optionsReport.net_gex.toFixed(2)}B
                </p>
              </div>
            </div>

            {/* PCR & Max Pain */}
            <div className="grid grid-cols-3 gap-2 mb-3">
              <div className="p-2 bg-slate-700/30 rounded">
                <p className="text-xs text-slate-500">PCR (OI)</p>
                <p className={`text-sm font-semibold ${
                  optionsReport.pcr_oi > 1.2 ? 'text-green-400' :
                  optionsReport.pcr_oi < 0.8 ? 'text-red-400' : 'text-slate-300'
                }`}>
                  {optionsReport.pcr_oi.toFixed(2)}
                </p>
              </div>
              <div className="p-2 bg-slate-700/30 rounded">
                <p className="text-xs text-slate-500">Max Pain</p>
                <p className="text-sm font-semibold text-slate-300">
                  {optionsReport.max_pain.toFixed(0)}
                </p>
              </div>
              <div className="p-2 bg-slate-700/30 rounded">
                <p className="text-xs text-slate-500">ATM Strike</p>
                <p className="text-sm font-semibold text-slate-300">
                  {optionsReport.atm_strike.toFixed(0)}
                </p>
              </div>
            </div>

            {/* Walls */}
            <div className="grid grid-cols-2 gap-2 mb-3">
              <div className="p-2 bg-red-500/10 border border-red-500/20 rounded">
                <p className="text-xs text-red-400">Call Wall</p>
                <p className="text-sm font-semibold text-red-300">
                  {optionsReport.call_wall.toFixed(0)}
                </p>
              </div>
              <div className="p-2 bg-green-500/10 border border-green-500/20 rounded">
                <p className="text-xs text-green-400">Put Wall</p>
                <p className="text-sm font-semibold text-green-300">
                  {optionsReport.put_wall.toFixed(0)}
                </p>
              </div>
            </div>

            {/* Recommendation */}
            {optionsReport.recommended_structure !== 'NONE' && (
              <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded-lg">
                <p className="text-xs text-purple-400 mb-1">Recommended Structure</p>
                <p className="text-sm font-bold text-purple-300">
                  {optionsReport.recommended_structure.replace(/_/g, ' ')}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  {optionsReport.structure_rationale}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default QuantTelemetryCard;
