/**
 * SpreadGrouping Component
 * Displays grouped spreads, naked positions, and warnings
 */

import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, Info, TrendingUp, X } from 'lucide-react';
import { journalAPI } from '../lib/api';

interface PositionLeg {
  intent_id: string;
  strategy: string;
  side: 'BUY' | 'SELL';
  option_type: 'CE' | 'PE';
  strike: number;
  quantity: number;
  expiry?: string;
  underlying?: string;
  entry_credit?: number;
  pnl?: number;
  unrealized_pnl?: number;
  current_ltp?: number;
}

interface SpreadWarning {
  level: 'INFO' | 'WARNING' | 'CRITICAL';
  message: string;
  affected_intent_ids: string[];
  missing_legs?: Array<{
    side: string;
    strike: number | string;
    option_type: string;
  }>;
}

interface DetectedSpread {
  spread_type: string;
  underlying: string;
  expiry?: string;
  legs: PositionLeg[];
  confidence: number;
  warnings: SpreadWarning[];
  max_profit?: number;
  max_loss?: number;
  breakeven_points?: number[];
}

interface GroupedPositionsData {
  spreads: DetectedSpread[];
  naked_positions: PositionLeg[];
  incomplete_spreads: Array<{
    leg: PositionLeg;
    warning: SpreadWarning;
  }>;
  total_warnings: SpreadWarning[];
  has_critical_warnings: boolean;
}

const SpreadGrouping: React.FC<{ limit?: number; onRefresh?: () => void; onDataLoaded?: (data: GroupedPositionsData) => void }> = ({ 
  limit = 50,
  onRefresh,
  onDataLoaded,
}) => {
  const [data, setData] = useState<GroupedPositionsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSpreads, setExpandedSpreads] = useState<Set<number>>(new Set());

  useEffect(() => {
    fetchSpreadAnalysis();
  }, [limit]);

  const fetchSpreadAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await journalAPI.getSpreadAnalysis(limit);
      setData(response.data);
      if (onDataLoaded) onDataLoaded(response.data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch spread analysis');
      console.error('Spread analysis error:', err);
    } finally {
      setLoading(false);
    }
  };

  const toggleSpreadExpand = (index: number) => {
    const newExpanded = new Set(expandedSpreads);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSpreads(newExpanded);
  };

  const getSpreadDisplayName = (type: string): string => {
    const names: Record<string, string> = {
      BULL_CALL_SPREAD: '📈 Bull Call Spread',
      BULL_PUT_SPREAD: '📈 Bull Put Spread',
      BEAR_CALL_SPREAD: '📉 Bear Call Spread',
      BEAR_PUT_SPREAD: '📉 Bear Put Spread',
      IRON_CONDOR: '🦅 Iron Condor',
      BUTTERFLY_CALL: '🦋 Call Butterfly',
      BUTTERFLY_PUT: '🦋 Put Butterfly',
      LONG_STRADDLE: '🎯 Long Straddle',
      SHORT_STRADDLE: '🎯 Short Straddle',
      LONG_STRANGLE: '🎪 Long Strangle',
      SHORT_STRANGLE: '🎪 Short Strangle',
      CALENDAR_SPREAD: '📅 Calendar Spread',
      RATIO_CALL_BACKSPREAD: '⚖️ Ratio Call Backspread',
      RATIO_PUT_BACKSPREAD: '⚖️ Ratio Put Backspread',
    };
    return names[type] || type;
  };

  const getWarningIcon = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      case 'WARNING':
        return <AlertTriangle className="w-5 h-5 text-yellow-500" />;
      case 'INFO':
        return <Info className="w-5 h-5 text-blue-500" />;
      default:
        return <Info className="w-5 h-5 text-slate-500" />;
    }
  };

  const getWarningBgColor = (level: string) => {
    switch (level) {
      case 'CRITICAL':
        return 'bg-red-500/10 border-red-500/30';
      case 'WARNING':
        return 'bg-yellow-500/10 border-yellow-500/30';
      case 'INFO':
        return 'bg-blue-500/10 border-blue-500/30';
      default:
        return 'bg-slate-500/10 border-slate-500/30';
    }
  };

  if (loading) {
    return (
      <div className="card-glass p-6">
        <div className="text-center py-8">
          <p className="text-slate-400">Analyzing spreads...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card-glass p-6">
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded">
          <p className="text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const totalSpreads = data.spreads.length;
  const totalNaked = data.naked_positions.length;
  const totalIncomplete = data.incomplete_spreads.length;
  const criticalWarnings = data.total_warnings.filter((w) => w.level === 'CRITICAL').length;

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card-glass p-4">
          <p className="text-xs text-slate-400 mb-1">Grouped Spreads</p>
          <p className="text-3xl font-bold text-green-400">{totalSpreads}</p>
          <p className="text-xs text-slate-500 mt-1">Properly hedged</p>
        </div>
        
        <div className="card-glass p-4">
          <p className="text-xs text-slate-400 mb-1">Naked Positions</p>
          <p className={`text-3xl font-bold ${totalNaked > 0 ? 'text-red-400' : 'text-green-400'}`}>
            {totalNaked}
          </p>
          <p className="text-xs text-slate-500 mt-1">Unhedged</p>
        </div>

        <div className="card-glass p-4">
          <p className="text-xs text-slate-400 mb-1">Incomplete Spreads</p>
          <p className={`text-3xl font-bold ${totalIncomplete > 0 ? 'text-yellow-400' : 'text-green-400'}`}>
            {totalIncomplete}
          </p>
          <p className="text-xs text-slate-500 mt-1">Missing hedge</p>
        </div>

        <div className="card-glass p-4">
          <p className="text-xs text-slate-400 mb-1">Critical Alerts</p>
          <p className={`text-3xl font-bold ${criticalWarnings > 0 ? 'text-red-500' : 'text-green-400'}`}>
            {criticalWarnings}
          </p>
          <p className="text-xs text-slate-500 mt-1">Require action</p>
        </div>
      </div>

      {/* Critical Warnings Alert */}
      {data.has_critical_warnings && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-6 h-6 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-400 mb-2">⚠️ Critical Risks Detected</h3>
              <p className="text-sm text-red-300 mb-2">
                You have {criticalWarnings} naked position(s) with unlimited risk. Consider adding protective hedges.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Grouped Spreads */}
      {totalSpreads > 0 && (
        <div className="card-glass p-6">
          <h3 className="text-lg font-semibold text-green-400 mb-4">✅ Properly Grouped Spreads</h3>
          <div className="space-y-3">
            {data.spreads.map((spread, idx) => (
              <div
                key={idx}
                className="border border-green-500/30 rounded-lg overflow-hidden bg-green-500/5"
              >
                <button
                  onClick={() => toggleSpreadExpand(idx)}
                  className="w-full p-4 hover:bg-green-500/10 transition flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <CheckCircle className="w-5 h-5 text-green-400" />
                    <div className="text-left">
                      <p className="font-semibold text-white">
                        {getSpreadDisplayName(spread.spread_type)}
                      </p>
                      <p className="text-xs text-slate-400">
                        {spread.underlying} • {spread.expiry || 'N/A'} • Confidence: {(spread.confidence * 100).toFixed(0)}%
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    {spread.max_profit !== undefined && (
                      <p className="text-sm text-green-400">
                        Max: ₹{Math.abs(spread.max_profit || 0).toLocaleString()}
                      </p>
                    )}
                  </div>
                </button>

                {expandedSpreads.has(idx) && (
                  <div className="border-t border-green-500/20 p-4 bg-slate-900/50">
                    <div className="space-y-3">
                      {/* Legs */}
                      <div>
                        <p className="text-xs font-semibold text-slate-400 mb-2">Legs:</p>
                        <div className="grid grid-cols-2 gap-2">
                          {spread.legs.map((leg, legIdx) => (
                            <div key={legIdx} className="p-2 bg-slate-800 rounded text-xs">
                              <p className={leg.side === 'SELL' ? 'text-red-400' : 'text-green-400'}>
                                {leg.side} {leg.strike} {leg.option_type}
                              </p>
                              <p className="text-slate-500">Qty: {leg.quantity}</p>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Metrics */}
                      {(spread.max_profit !== undefined || spread.max_loss !== undefined) && (
                        <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-700">
                          {spread.max_profit !== undefined && spread.max_profit !== null && (
                            <div>
                              <p className="text-xs text-slate-500">Max Profit</p>
                              <p className="font-semibold text-green-400">
                                ₹{spread.max_profit.toLocaleString()}
                              </p>
                            </div>
                          )}
                          {spread.max_loss !== undefined && spread.max_loss !== null && (
                            <div>
                              <p className="text-xs text-slate-500">Max Loss</p>
                              <p className="font-semibold text-red-400">
                                ₹{Math.abs(spread.max_loss).toLocaleString()}
                              </p>
                            </div>
                          )}
                          {spread.breakeven_points && spread.breakeven_points.length > 0 && (
                            <div>
                              <p className="text-xs text-slate-500">Breakeven{spread.breakeven_points.length > 1 ? 's' : ''}</p>
                              <p className="font-semibold text-blue-400">
                                {spread.breakeven_points.map(b => b.toFixed(1)).join(' / ')}
                              </p>
                            </div>
                          )}
                          {spread.max_profit != null && spread.max_loss != null && spread.max_loss > 0 && (
                            <div>
                              <p className="text-xs text-slate-500">Risk:Reward</p>
                              <p className="font-semibold text-purple-400">
                                1:{(spread.max_profit / spread.max_loss).toFixed(2)}
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Incomplete Spreads */}
      {totalIncomplete > 0 && (
        <div className="card-glass p-6">
          <h3 className="text-lg font-semibold text-yellow-400 mb-4">⚠️ Incomplete Spreads</h3>
          <div className="space-y-3">
            {data.incomplete_spreads.map((item, idx) => (
              <div
                key={idx}
                className={`p-4 rounded-lg border ${getWarningBgColor(item.warning.level)}`}
              >
                <div className="flex items-start gap-3">
                  {getWarningIcon(item.warning.level)}
                  <div className="flex-1">
                    <p className="font-semibold text-white mb-1">
                      {item.leg.side} {item.leg.strike} {item.leg.option_type}
                    </p>
                    <p className="text-sm text-slate-300 mb-2">{item.warning.message}</p>
                    {item.warning.missing_legs && item.warning.missing_legs.length > 0 && (
                      <p className="text-xs text-slate-400">
                        Consider adding: {item.warning.missing_legs
                          .map((ml) => `${ml.side} ${ml.strike} ${ml.option_type}`)
                          .join(', ')}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Naked Positions */}
      {totalNaked > 0 && (
        <div className="card-glass p-6">
          <h3 className="text-lg font-semibold text-red-400 mb-4">🚨 Naked Positions (High Risk)</h3>
          <div className="space-y-3">
            {data.naked_positions.map((leg, idx) => (
              <div
                key={idx}
                className="p-4 rounded-lg border border-red-500/30 bg-red-500/5"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-white mb-1">
                        {leg.side === 'SELL' ? '📉' : '📈'} {leg.side} {leg.strike} {leg.option_type}
                      </p>
                      <p className="text-sm text-red-300 mb-2">
                        Unhedged {leg.side === 'SELL' ? 'naked sell' : 'naked buy'} - 
                        {leg.side === 'SELL' ? ' Unlimited loss potential!' : ' Significant downside risk!'}
                      </p>
                      <p className="text-xs text-slate-400">
                        Underlying: {leg.underlying} • Expiry: {leg.expiry || 'N/A'}
                      </p>
                    </div>
                  </div>
                  <button className="px-3 py-1 rounded text-xs bg-orange-500/20 text-orange-300 hover:bg-orange-500/30 transition">
                    Hedge
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* No Issues */}
      {totalSpreads > 0 && totalNaked === 0 && totalIncomplete === 0 && !data.has_critical_warnings && (
        <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-6 h-6 text-green-400" />
            <p className="text-green-300">
              ✅ All positions are properly grouped into spreads. No critical risks detected!
            </p>
          </div>
        </div>
      )}

      {/* No Positions */}
      {totalSpreads === 0 && totalNaked === 0 && totalIncomplete === 0 && (
        <div className="p-4 bg-slate-600/20 border border-slate-500/30 rounded-lg">
          <p className="text-slate-300">No open positions to analyze</p>
        </div>
      )}
    </div>
  );
};

export default SpreadGrouping;
