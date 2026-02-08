import React, { useState, useEffect } from 'react';
import {
  Play,
  Zap,
  Plus,
  TrendingUp,
  Activity,
  AlertCircle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';
import { strategyAPI, executionAPI, stockSuggestionsAPI } from '../lib/api';

interface Strategy {
  id: number;
  name: string;
  description: string;
  strategy_type: string;
  underlying: string;
  parameters: Record<string, any>;
  enabled: boolean;
  deployed_at: string | null;
  created_at: string;
}

interface ExecutionResult {
  success: boolean;
  strategy_id: number;
  strategy_name: string;
  executed_at: string;
  strategy?: string;
  reason?: string;
  approved?: boolean;
  signal?: Record<string, any>;
  ticket?: Record<string, any>;
  run_id?: number;
  error?: string;
}

interface StockSuggestion {
  symbol: string;
  strategy: string;
  strategy_name: string;
  approved: boolean;
  reason: string;
  score: number;
  current_price?: number;
  signal?: string;
  entry_price?: number;
  stop_loss?: number;
  target?: number;
  confidence?: number;
  indicators?: Record<string, any>;
  risk_reward_ratio?: number;
}

interface StockStrategyPanelProps {
  symbol: string;
  currentPrice: number;
}

const StockStrategyPanel: React.FC<StockStrategyPanelProps> = ({ symbol, currentPrice }) => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState<number | null>(null);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  
  // Suggestions state
  const [suggestions, setSuggestions] = useState<StockSuggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([symbol]);
  const [watchlist] = useState<string[]>([
    'RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN',
    'BHARTIARTL', 'KOTAKBANK', 'ITC', 'HINDUNILVR'
  ]);

  useEffect(() => {
    loadStrategies();
    loadSuggestions();
  }, [symbol]);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const response = await strategyAPI.listStrategies();
      const allStrategies = Array.isArray(response.data) ? response.data : [];
      
      // Filter for stock strategies that match this symbol or are general stock strategies
      const stockStrategies = allStrategies.filter((s: Strategy) => {
        // Include stock strategies (momentum, trend_following, mean_reversion, and their registry names)
        const isStockStrategy = [
          'momentum', 
          'trend_following', 
          'mean_reversion', 
          'StockMomentum15m',
          'stock_momentum_15m',
          'stock_mean_reversion_15m',
          'stock_trend_following_15m'
        ].includes(s.strategy_type);
        
        // Include if it's a stock strategy and either matches the symbol or has no specific underlying
        return isStockStrategy && (!s.underlying || s.underlying === symbol);
      });
      
      setStrategies(stockStrategies);
    } catch (error) {
      console.error('Failed to load strategies:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadSuggestions = async () => {
    setSuggestionsLoading(true);
    try {
      const symbolsToAnalyze = selectedSymbols.length > 0 ? selectedSymbols : [symbol];
      
      const response = await stockSuggestionsAPI.get({
        symbols: symbolsToAnalyze,
        capital: 100000,
        quantity: 1,
        min_confidence: 60
      });
      
      const data = response?.data;
      setSuggestions(Array.isArray(data?.suggestions) ? data.suggestions : []);
    } catch (error) {
      console.error('Failed to load stock suggestions:', error);
      setSuggestions([]);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const toggleSymbolSelection = (sym: string) => {
    setSelectedSymbols(prev => {
      if (prev.includes(sym)) {
        return prev.filter(s => s !== sym);
      }
      return [...prev, sym];
    });
  };

  const handleExecute = async (strategyId: number) => {
    setExecuting(strategyId);
    setResult(null);
    
    try {
      const selected = strategies.find((s) => s.id === strategyId);
      if (!selected) return;

      // Enable strategy if not already enabled
      if (!selected.enabled) {
        await strategyAPI.enableStrategy(strategyId);
      }

      // Execute strategy with symbol context
      const response = await executionAPI.executeSingle(strategyId, {
        symbol: symbol,
        current_price: currentPrice
      });
      
      const runResult = response.data;
      const runId = runResult?.run_id;

      if (!runId) {
        setResult({
          success: false,
          strategy_id: strategyId,
          strategy_name: selected.name,
          executed_at: new Date().toISOString(),
          error: 'No run_id returned'
        });
        return;
      }

      // Create execution intent
      const intentResp = await executionAPI.createIntent(runId);
      const intentData = intentResp.data;
      const intentId = intentData?.intent_id;

      if (!intentId) {
        setResult({
          success: false,
          strategy_id: strategyId,
          strategy_name: selected.name,
          executed_at: new Date().toISOString(),
          error: 'Intent creation failed'
        });
        return;
      }

      // Execute paper trade
      const idempotencyKey = (globalThis.crypto && 'randomUUID' in globalThis.crypto)
        ? (globalThis.crypto as any).randomUUID()
        : `${Date.now()}-${Math.random()}`;

      const execResp = await executionAPI.executeIntent(intentId, idempotencyKey);
      const execData = execResp.data;

      setResult({
        success: true,
        strategy_id: strategyId,
        strategy_name: selected.name,
        executed_at: new Date().toISOString(),
        ...runResult,
        execution: execData
      });

      // Reload strategies to get updated state
      await loadStrategies();
    } catch (error: any) {
      console.error('Execution failed:', error);
      const selected = strategies.find((s) => s.id === strategyId);
      setResult({
        success: false,
        strategy_id: strategyId,
        strategy_name: selected?.name || 'Unknown',
        executed_at: new Date().toISOString(),
        error: error.response?.data?.detail || error.message || 'Execution failed'
      });
    } finally {
      setExecuting(null);
    }
  };

  const handleCreateStrategy = () => {
    setShowCreateForm(true);
  };

  const getStrategyTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      'momentum': 'Momentum',
      'StockMomentum15m': 'Momentum 15m',
      'stock_momentum_15m': 'Momentum 15m',
      'trend_following': 'Trend Following',
      'stock_trend_following_15m': 'Trend Following 15m',
      'mean_reversion': 'Mean Reversion',
      'stock_mean_reversion_15m': 'Mean Reversion 15m'
    };
    return labels[type] || type;
  };

  const getStrategyIcon = (type: string) => {
    if (type.includes('momentum')) return TrendingUp;
    if (type.includes('trend')) return Activity;
    return Zap;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Trade Suggestions */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h2 className="text-lg font-semibold text-white">Trade Suggestions</h2>
            <p className="text-xs text-slate-400">Ranked stock ideas based on technical analysis</p>
          </div>
          <button
            onClick={loadSuggestions}
            disabled={suggestionsLoading}
            className="p-2 hover:bg-slate-700 rounded text-slate-300 hover:text-white transition disabled:opacity-50"
            title="Refresh suggestions"
          >
            <RefreshCw size={18} className={suggestionsLoading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Symbol Filter */}
        <div className="mt-3 flex flex-wrap gap-2 mb-4">
          {watchlist.slice(0, 6).map((sym) => {
            const active = selectedSymbols.includes(sym);
            return (
              <button
                key={sym}
                onClick={() => {
                  toggleSymbolSelection(sym);
                  // Reload suggestions after a short delay
                  setTimeout(() => loadSuggestions(), 100);
                }}
                className={`px-2.5 py-1 rounded text-xs font-semibold border transition ${
                  active
                    ? 'bg-blue-600 text-white border-blue-500'
                    : 'bg-slate-900 text-slate-300 border-slate-700 hover:bg-slate-700'
                }`}
                aria-pressed={active}
              >
                {sym}
              </button>
            );
          })}
        </div>

        {/* Suggestions Grid */}
        {suggestionsLoading ? (
          <div className="text-slate-400 text-sm mt-3">Loading suggestions...</div>
        ) : suggestions.length === 0 ? (
          <div className="text-slate-400 text-sm mt-3">
            No trade suggestions available. Market conditions may not favor any strategy at this time.
          </div>
        ) : (
          <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 mt-3">
            {suggestions.slice(0, 6).map((suggestion, idx) => (
              <div key={idx} className="bg-slate-900 border border-slate-700 rounded p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-white font-semibold">{suggestion.symbol}</div>
                    <div className="text-xs text-slate-400">
                      Score: <span className="font-mono text-slate-200">{suggestion.score.toFixed(1)}</span>
                    </div>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    suggestion.approved ? 'bg-green-900 text-green-200' : 'bg-slate-700 text-slate-200'
                  }`}>
                    {suggestion.approved ? 'Approved' : 'No Trade'}
                  </span>
                </div>

                <div className="mt-2 text-xs text-slate-200">
                  <div>
                    <span className="text-slate-400">Strategy:</span>{' '}
                    <span className="font-mono">{suggestion.strategy_name || suggestion.strategy}</span>
                  </div>
                  {suggestion.signal && (
                    <div className="mt-1 flex items-center gap-1">
                      <span className="text-slate-400">Signal:</span>
                      <span className={`font-mono font-semibold flex items-center gap-1 ${
                        suggestion.signal === 'BUY' ? 'text-emerald-400' : 
                        suggestion.signal === 'SELL' ? 'text-red-400' : 'text-slate-400'
                      }`}>
                        {suggestion.signal === 'BUY' && <ArrowUpRight size={12} />}
                        {suggestion.signal === 'SELL' && <ArrowDownRight size={12} />}
                        {suggestion.signal}
                      </span>
                    </div>
                  )}
                  <div className="mt-1">
                    <span className="text-slate-400">Reason:</span>{' '}
                    <span className="font-mono text-xs">{suggestion.reason}</span>
                  </div>
                </div>

                {suggestion.current_price && (
                  <div className="mt-2 p-2 bg-slate-800 rounded">
                    <div className="text-slate-300 font-semibold text-xs mb-1">Levels</div>
                    <div className="text-xs text-slate-200 space-y-0.5">
                      <div>
                        <span className="text-slate-400">Price:</span> ₹{suggestion.current_price.toFixed(2)}
                      </div>
                      {suggestion.entry_price && (
                        <div>
                          <span className="text-slate-400">Entry:</span> ₹{suggestion.entry_price.toFixed(2)}
                        </div>
                      )}
                      {suggestion.stop_loss && (
                        <div>
                          <span className="text-slate-400">Stop:</span> ₹{suggestion.stop_loss.toFixed(2)}
                        </div>
                      )}
                      {suggestion.target && (
                        <div>
                          <span className="text-slate-400">Target:</span> ₹{suggestion.target.toFixed(2)}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {suggestion.confidence && (
                  <div className="mt-2 text-xs">
                    <span className="text-slate-400">Confidence:</span>{' '}
                    <span className="font-mono text-slate-200">{suggestion.confidence.toFixed(0)}%</span>
                    {suggestion.risk_reward_ratio && (
                      <>
                        {' | '}
                        <span className="text-slate-400">R:R</span>{' '}
                        <span className="font-mono text-slate-200">1:{suggestion.risk_reward_ratio.toFixed(1)}</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Header */}
      <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Zap size={20} className="text-emerald-400" />
              Trading Strategies
            </h3>
            <p className="text-sm text-slate-400 mt-1">
              Execute automated strategies for {symbol}
            </p>
          </div>
          <button
            onClick={handleCreateStrategy}
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white text-sm transition"
          >
            <Plus size={16} />
            Create
          </button>
        </div>
      </div>

      {/* Execution Result */}
      {result && (
        <div className={`border rounded-xl p-4 ${
          result.success 
            ? 'bg-emerald-500/10 border-emerald-500/30' 
            : 'bg-red-500/10 border-red-500/30'
        }`}>
          <div className="flex items-start gap-3">
            {result.success ? (
              <CheckCircle size={20} className="text-emerald-400 flex-shrink-0 mt-0.5" />
            ) : (
              <XCircle size={20} className="text-red-400 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <h4 className={`font-semibold ${result.success ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.success ? 'Strategy Executed' : 'Execution Failed'}
              </h4>
              <p className="text-sm text-slate-300 mt-1">{result.strategy_name}</p>
              {result.reason && (
                <p className="text-xs text-slate-400 mt-2">
                  <span className="font-semibold">Reason:</span> {result.reason}
                </p>
              )}
              {result.error && (
                <p className="text-xs text-red-400 mt-2">
                  <span className="font-semibold">Error:</span> {result.error}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Strategies List */}
      {strategies.length === 0 ? (
        <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-8 text-center">
          <AlertCircle size={32} className="text-slate-500 mx-auto mb-3" />
          <p className="text-slate-400 mb-4">No strategies configured for {symbol}</p>
          <button
            onClick={handleCreateStrategy}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-white transition"
          >
            <Plus size={16} />
            Create Strategy
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {strategies.map((strategy) => {
            const Icon = getStrategyIcon(strategy.strategy_type);
            const isExecuting = executing === strategy.id;
            
            return (
              <div
                key={strategy.id}
                className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 hover:border-slate-600/50 transition"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Icon size={20} className="text-blue-400" />
                      <div>
                        <h4 className="text-white font-semibold">{strategy.name}</h4>
                        <p className="text-xs text-slate-400">
                          {getStrategyTypeLabel(strategy.strategy_type)}
                        </p>
                      </div>
                    </div>
                    {strategy.description && (
                      <p className="text-sm text-slate-400 mb-3">{strategy.description}</p>
                    )}
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded text-xs font-semibold ${
                        strategy.enabled
                          ? 'bg-emerald-500/20 text-emerald-400'
                          : 'bg-slate-600/20 text-slate-400'
                      }`}>
                        {strategy.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                      {strategy.parameters && (
                        <span className="text-xs text-slate-500">
                          {Object.keys(strategy.parameters).length} parameters
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => handleExecute(strategy.id)}
                    disabled={isExecuting}
                    className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg text-white text-sm transition"
                  >
                    <Play size={16} className={isExecuting ? 'animate-pulse' : ''} />
                    {isExecuting ? 'Executing...' : 'Execute'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
      
      {/* Info Box */}
      <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
        <div className="flex items-start gap-3">
          <AlertCircle size={18} className="text-blue-400 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-slate-300">
            <p className="font-semibold text-blue-400 mb-1">About Stock Strategies</p>
            <p className="text-xs">
              Stock strategies analyze price action, momentum, and technical indicators to generate buy/sell signals. 
              Executions are paper-traded by default for testing.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StockStrategyPanel;
