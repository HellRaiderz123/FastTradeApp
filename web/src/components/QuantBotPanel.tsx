import React, { useState, useEffect, useCallback } from 'react';
import {
  Bot,
  Play,
  Square,
  RefreshCw,
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Settings2,
  TrendingUp,
} from 'lucide-react';
import { quantAPI, CashQuantReport, OptionsQuantReport } from '../api/quantAPI';

interface QuantBotPanelProps {
  symbol: string;
  onReportUpdate?: (cash: CashQuantReport | null, options: OptionsQuantReport | null) => void;
  className?: string;
}

type BotStatus = 'IDLE' | 'RUNNING' | 'ERROR' | 'COOLDOWN';

const QuantBotPanel: React.FC<QuantBotPanelProps> = ({
  symbol,
  onReportUpdate,
  className = '',
}) => {
  const [status, setStatus] = useState<BotStatus>('IDLE');
  const [lastRun, setLastRun] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState(60); // seconds
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cashReport, setCashReport] = useState<CashQuantReport | null>(null);
  const [optionsReport, setOptionsReport] = useState<OptionsQuantReport | null>(null);

  const runAnalysis = useCallback(async () => {
    if (!symbol || symbol.length < 2) return;

    setLoading(true);
    setStatus('RUNNING');
    setError(null);

    try {
      // Fetch cash report
      const cashRes = await quantAPI.getCashReport(symbol);
      setCashReport(cashRes.data);

      // Try options report (may not be available)
      let optRes: OptionsQuantReport | null = null;
      try {
        const optData = await quantAPI.getOptionsReport(symbol);
        optRes = optData.data;
        setOptionsReport(optRes);
      } catch {
        setOptionsReport(null);
      }

      setLastRun(new Date());
      setStatus('IDLE');
      onReportUpdate?.(cashRes.data, optRes);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Analysis failed');
      setStatus('ERROR');
      setCashReport(null);
      setOptionsReport(null);
      onReportUpdate?.(null, null);
    }

    setLoading(false);
  }, [symbol, onReportUpdate]);

  // Auto-refresh effect
  useEffect(() => {
    if (!autoRefresh || !symbol) return;

    const interval = setInterval(() => {
      runAnalysis();
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, symbol, runAnalysis]);

  // Initial run when symbol changes
  useEffect(() => {
    if (symbol && symbol.length >= 2) {
      runAnalysis();
    }
  }, [symbol]);

  const statusConfig = {
    IDLE: { color: 'text-slate-400', bg: 'bg-slate-500/20', icon: Clock },
    RUNNING: { color: 'text-blue-400', bg: 'bg-blue-500/20', icon: Activity },
    ERROR: { color: 'text-red-400', bg: 'bg-red-500/20', icon: AlertTriangle },
    COOLDOWN: { color: 'text-amber-400', bg: 'bg-amber-500/20', icon: Clock },
  };

  const StatusIcon = statusConfig[status].icon;

  return (
    <div className={`bg-slate-800 border border-slate-700 rounded-xl overflow-hidden ${className}`}>
      {/* Header */}
      <div className="px-4 py-3 bg-slate-700/50 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <h3 className="font-semibold text-white flex items-center gap-2">
            <Bot className="w-4 h-4 text-purple-400" />
            Quant Bot
          </h3>
          <div className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs ${statusConfig[status].bg} ${statusConfig[status].color}`}>
            <StatusIcon className="w-3 h-3" />
            {status}
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Symbol Display */}
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-400">Symbol</span>
          <span className="text-sm font-semibold text-white">{symbol || '—'}</span>
        </div>

        {/* Controls */}
        <div className="flex gap-2">
          <button
            onClick={runAnalysis}
            disabled={loading || !symbol}
            className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-slate-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            {loading ? 'Analyzing...' : 'Run Analysis'}
          </button>

          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              autoRefresh
                ? 'bg-green-600 hover:bg-green-500 text-white'
                : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
            }`}
            title={autoRefresh ? 'Stop auto-refresh' : 'Start auto-refresh'}
          >
            {autoRefresh ? <Square className="w-4 h-4" /> : <RefreshCw className="w-4 h-4" />}
          </button>
        </div>

        {/* Auto-refresh Settings */}
        {autoRefresh && (
          <div className="flex items-center gap-2 p-2 bg-green-500/10 border border-green-500/30 rounded-lg">
            <Settings2 className="w-4 h-4 text-green-400" />
            <span className="text-xs text-green-400">Auto-refresh every</span>
            <select
              value={refreshInterval}
              onChange={(e) => setRefreshInterval(Number(e.target.value))}
              className="bg-slate-700 text-white text-xs px-2 py-1 rounded border border-slate-600"
            >
              <option value={30}>30s</option>
              <option value={60}>1m</option>
              <option value={120}>2m</option>
              <option value={300}>5m</option>
            </select>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="flex items-center gap-2 p-2 bg-red-500/10 border border-red-500/30 rounded-lg">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span className="text-xs text-red-400">{error}</span>
          </div>
        )}

        {/* Last Run */}
        {lastRun && (
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>Last run</span>
            <span>{lastRun.toLocaleTimeString()}</span>
          </div>
        )}

        {/* Quick Stats */}
        {cashReport && (
          <div className="border-t border-slate-700 pt-3 space-y-2">
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <TrendingUp className="w-4 h-4" />
              Quick Stats
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 bg-slate-700/50 rounded">
                <p className="text-xs text-slate-500">Regime</p>
                <p className={`text-sm font-semibold ${
                  cashReport.regime === 'TRENDING' ? 'text-green-400' :
                  cashReport.regime === 'MEAN_REVERTING' ? 'text-amber-400' : 'text-slate-400'
                }`}>
                  {cashReport.regime.replace('_', ' ')}
                </p>
              </div>
              <div className="p-2 bg-slate-700/50 rounded">
                <p className="text-xs text-slate-500">RVOL</p>
                <p className={`text-sm font-semibold ${
                  cashReport.rvol_signal === 'HIGH' ? 'text-green-400' :
                  cashReport.rvol_signal === 'LOW' ? 'text-red-400' : 'text-slate-400'
                }`}>
                  {cashReport.rvol.toFixed(2)}x
                </p>
              </div>
              <div className="p-2 bg-slate-700/50 rounded">
                <p className="text-xs text-slate-500">ORB</p>
                <p className={`text-sm font-semibold ${
                  cashReport.orb_breakout === 'BULLISH' ? 'text-green-400' :
                  cashReport.orb_breakout === 'BEARISH' ? 'text-red-400' : 'text-slate-400'
                }`}>
                  {cashReport.orb_breakout}
                </p>
              </div>
              <div className="p-2 bg-slate-700/50 rounded">
                <p className="text-xs text-slate-500">vs VWAP</p>
                <p className={`text-sm font-semibold ${
                  cashReport.price_vs_vwap === 'ABOVE' ? 'text-green-400' :
                  cashReport.price_vs_vwap === 'BELOW' ? 'text-red-400' : 'text-slate-400'
                }`}>
                  {cashReport.price_vs_vwap}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Options Quick Stats */}
        {optionsReport && (
          <div className="border-t border-slate-700 pt-3 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2 bg-slate-700/50 rounded">
                <p className="text-xs text-slate-500">IV Percentile</p>
                <p className={`text-sm font-semibold ${
                  optionsReport.iv_percentile > 65 ? 'text-red-400' :
                  optionsReport.iv_percentile < 35 ? 'text-green-400' : 'text-slate-400'
                }`}>
                  {optionsReport.iv_percentile.toFixed(0)}%
                </p>
              </div>
              <div className="p-2 bg-slate-700/50 rounded">
                <p className="text-xs text-slate-500">GEX</p>
                <p className={`text-sm font-semibold ${
                  optionsReport.gex_regime === 'POSITIVE_GEX' ? 'text-green-400' :
                  optionsReport.gex_regime === 'NEGATIVE_GEX' ? 'text-red-400' : 'text-slate-400'
                }`}>
                  {optionsReport.gex_regime.replace('_', ' ')}
                </p>
              </div>
            </div>
            {optionsReport.recommended_structure !== 'NONE' && (
              <div className="p-2 bg-purple-500/10 border border-purple-500/30 rounded">
                <p className="text-xs text-purple-400">Recommended</p>
                <p className="text-sm font-semibold text-purple-300">
                  {optionsReport.recommended_structure.replace(/_/g, ' ')}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Success indicator */}
        {cashReport && !error && (
          <div className="flex items-center gap-2 text-xs text-green-400">
            <CheckCircle2 className="w-3 h-3" />
            Analysis complete
          </div>
        )}
      </div>
    </div>
  );
};

export default QuantBotPanel;
