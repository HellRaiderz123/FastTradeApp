import React, { useState, useEffect } from 'react';
import { Play, Pause, Trash2, Plus, RefreshCw, Zap } from 'lucide-react';
import { strategyAPI, executionAPI } from '../lib/api';

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
  spot?: number;
  atm?: number;
  signal?: Record<string, any>;
  ticket?: Record<string, any>;
  risk_metrics?: Record<string, any>;
  run_id?: number;
  error?: string;
  [key: string]: any;  // Allow any other fields from strategy result
}

export const StrategyManager: React.FC = () => {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState<number | null>(null);
  const [results, setResults] = useState<ExecutionResult[]>([]);
  const [selectedStrategies, setSelectedStrategies] = useState<Set<number>>(new Set());
  const [showNewForm, setShowNewForm] = useState(false);

  // Load strategies on mount
  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    setLoading(true);
    try {
      const response = await strategyAPI.listStrategies();
      setStrategies(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to load strategies:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExecuteSingle = async (strategyId: number) => {
    setExecuting(strategyId);
    try {
      const response = await executionAPI.executeSingle(strategyId);
      setResults([response.data, ...results]);
      alert(`Executed: ${response.data.strategy_name}`);
    } catch (error) {
      console.error('Execution failed:', error);
      alert('Failed to execute strategy');
    } finally {
      setExecuting(null);
    }
  };

  const handleExecuteMultiple = async () => {
    if (selectedStrategies.size === 0) {
      alert('Please select at least one strategy');
      return;
    }

    setExecuting(-1);
    try {
      const ids = Array.from(selectedStrategies);
      const response = await executionAPI.executeMultiple(ids);
      
      // Add all results
      if (response.data.results) {
        setResults([...response.data.results, ...results]);
      }
      
      alert(
        `Executed: ${response.data.completed}/${response.data.total} strategies`
      );
      setSelectedStrategies(new Set());
    } catch (error) {
      console.error('Multi-execution failed:', error);
      alert('Failed to execute strategies');
    } finally {
      setExecuting(null);
    }
  };

  const handleExecuteAll = async () => {
    setExecuting(-2);
    try {
      const response = await executionAPI.executeAll();
      
      if (response.data.results) {
        setResults([...response.data.results, ...results]);
      }
      
      alert(
        `Executed: ${response.data.completed}/${response.data.total} strategies`
      );
    } catch (error) {
      console.error('Execute all failed:', error);
      alert('Failed to execute all strategies');
    } finally {
      setExecuting(null);
    }
  };

  const handleToggleEnable = async (strategyId: number, enabled: boolean) => {
    try {
      if (enabled) {
        await strategyAPI.disableStrategy(strategyId);
      } else {
        await strategyAPI.enableStrategy(strategyId);
      }
      loadStrategies();
    } catch (error) {
      console.error('Failed to toggle strategy:', error);
    }
  };

  const handleDelete = async (strategyId: number) => {
    if (!window.confirm('Are you sure?')) return;
    
    try {
      await strategyAPI.deleteStrategy(strategyId);
      loadStrategies();
    } catch (error) {
      console.error('Failed to delete strategy:', error);
    }
  };

  const toggleStrategySelection = (id: number) => {
    const newSelected = new Set(selectedStrategies);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedStrategies(newSelected);
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-white">Strategy Manager</h1>
        <button
          onClick={loadStrategies}
          disabled={loading}
          className="p-2 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition"
        >
          <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Bulk Actions */}
      {strategies.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 space-y-3">
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={selectedStrategies.size === strategies.length}
              onChange={(e) => {
                if (e.target.checked) {
                  setSelectedStrategies(new Set(strategies.map(s => s.id)));
                } else {
                  setSelectedStrategies(new Set());
                }
              }}
              className="w-4 h-4"
            />
            <span className="text-sm font-medium text-slate-300">
              {selectedStrategies.size > 0 
                ? `${selectedStrategies.size} selected` 
                : 'Select strategies'}
            </span>
          </div>

          <div className="flex space-x-2">
            <button
              onClick={handleExecuteMultiple}
              disabled={selectedStrategies.size === 0 || executing !== null}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition"
            >
              <Zap size={16} />
              <span>Execute Selected</span>
            </button>

            <button
              onClick={handleExecuteAll}
              disabled={executing !== null}
              className="flex items-center space-x-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 transition"
            >
              <Zap size={16} />
              <span>Execute All Enabled</span>
            </button>
          </div>
        </div>
      )}

      {/* Strategies Grid */}
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
        {loading ? (
          <div className="col-span-full text-center py-8 text-slate-400">
            Loading strategies...
          </div>
        ) : strategies.length === 0 ? (
          <div className="col-span-full text-center py-8 text-slate-400">
            No strategies found. Create one to get started.
          </div>
        ) : (
          strategies.map(strategy => (
            <div
              key={strategy.id}
              className="bg-slate-800 border border-slate-700 rounded-lg p-4 space-y-3 hover:border-slate-600 transition"
            >
              {/* Checkbox */}
              <div className="flex items-start space-x-3">
                <input
                  type="checkbox"
                  checked={selectedStrategies.has(strategy.id)}
                  onChange={() => toggleStrategySelection(strategy.id)}
                  className="w-4 h-4 mt-1"
                />

                <div className="flex-1">
                  <h3 className="font-semibold text-lg text-white">{strategy.name}</h3>
                  <p className="text-sm text-slate-400">{strategy.description}</p>
                </div>
              </div>

              {/* Info */}
              <div className="text-sm space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-400">Type:</span>
                  <span className="font-mono text-slate-300">{strategy.strategy_type}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Underlying:</span>
                  <span className="font-semibold text-white">{strategy.underlying}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Status:</span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      strategy.enabled
                        ? 'bg-green-100 text-green-700'
                        : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {strategy.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>

              {/* Parameters Preview */}
              <div className="bg-gray-50 rounded p-2 text-xs">
                <div className="font-semibold mb-1">Parameters:</div>
                <div className="space-y-0.5 text-gray-600">
                  {Object.entries(strategy.parameters).slice(0, 3).map(([key, value]) => (
                    <div key={key}>
                      {key}: {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                    </div>
                  ))}
                </div>
              </div>

              {/* Actions */}
              <div className="flex space-x-2">
                <button
                  onClick={() => handleExecuteSingle(strategy.id)}
                  disabled={executing !== null}
                  className="flex-1 flex items-center justify-center space-x-1 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  <Zap size={14} />
                  <span>Execute</span>
                </button>

                <button
                  onClick={() => handleToggleEnable(strategy.id, strategy.enabled)}
                  className={`flex items-center justify-center px-3 py-2 rounded text-sm ${
                    strategy.enabled
                      ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                      : 'bg-green-100 text-green-700 hover:bg-green-200'
                  }`}
                >
                  {strategy.enabled ? <Pause size={14} /> : <Play size={14} />}
                </button>

                <button
                  onClick={() => handleDelete(strategy.id)}
                  className="flex items-center justify-center px-3 py-2 bg-red-100 text-red-700 rounded hover:bg-red-200"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
          <h2 className="text-lg font-semibold mb-3 text-white">Recent Executions</h2>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {results.map((result, idx) => (
              <div
                key={idx}
                className={`p-4 rounded border ${
                  result.success
                    ? 'bg-slate-700 border-green-600'
                    : 'bg-slate-700 border-red-600'
                }`}
              >
                {/* Header */}
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="font-semibold text-white">{result.strategy_name}</div>
                    <div className="text-xs text-slate-400">{result.executed_at}</div>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    result.success 
                      ? 'bg-green-900 text-green-200' 
                      : 'bg-red-900 text-red-200'
                  }`}>
                    {result.success ? '✓ Success' : '✗ Failed'}
                  </span>
                </div>

                {/* Error Message */}
                {result.error && (
                  <div className="mb-2 p-2 bg-red-900 text-red-200 rounded text-xs">
                    Error: {result.error}
                  </div>
                )}

                {/* Trade Details - Display full result object */}
                {result.success && (
                  <div className="text-xs space-y-1 text-slate-200">
                    {/* Strategy & Reason */}
                    {result.strategy && (
                      <div><span className="text-slate-400">Strategy:</span> <span className="font-mono">{result.strategy}</span></div>
                    )}
                    {result.reason && (
                      <div><span className="text-slate-400">Reason:</span> <span className="font-mono">{result.reason}</span></div>
                    )}

                    {/* Approval Status */}
                    {result.approved !== undefined && (
                      <div><span className="text-slate-400">Approved:</span> <span>{result.approved ? '✓ Yes' : '✗ No'}</span></div>
                    )}

                    {/* Market Data */}
                    {result.spot && (
                      <div><span className="text-slate-400">Spot:</span> <span className="font-mono">₹{result.spot.toFixed(2)}</span></div>
                    )}
                    {result.atm && (
                      <div><span className="text-slate-400">ATM Strike:</span> <span className="font-mono">{result.atm}</span></div>
                    )}

                    {/* Signal Data */}
                    {result.signal && (
                      <div className="mt-2 p-2 bg-slate-600 rounded">
                        <div className="text-slate-300 font-semibold mb-1">Signal:</div>
                        <div><span className="text-slate-400">Direction:</span> <span className="font-mono">{result.signal.direction}</span></div>
                        <div><span className="text-slate-400">Confidence:</span> <span className="font-mono">{(result.signal.confidence * 100).toFixed(1)}%</span></div>
                        {result.signal.reason && (
                          <div><span className="text-slate-400">Signal Reason:</span> <span className="text-xs">{result.signal.reason}</span></div>
                        )}
                      </div>
                    )}

                    {/* Ticket/Spread Details */}
                    {result.ticket && (
                      <div className="mt-2 p-2 bg-slate-600 rounded">
                        <div className="text-slate-300 font-semibold mb-1">Ticket:</div>
                        <div><span className="text-slate-400">Lots:</span> <span className="font-mono">{result.ticket.lots}</span></div>
                        <div><span className="text-slate-400">Lot Size:</span> <span className="font-mono">{result.ticket.lot_size}</span></div>
                        {result.ticket.legs && result.ticket.legs.length > 0 && (
                          <div className="mt-1">
                            <div className="text-slate-400">Legs:</div>
                            {result.ticket.legs.map((leg: any, legIdx: number) => (
                              <div key={legIdx} className="ml-2 text-xs">
                                <span>{leg.side}</span> {leg.strike} {leg.type}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Risk Metrics */}
                    {result.risk_metrics && (
                      <div className="mt-2 p-2 bg-slate-600 rounded">
                        <div className="text-slate-300 font-semibold mb-1">Risk:</div>
                        {result.risk_metrics.max_loss && (
                          <div><span className="text-slate-400">Max Loss:</span> <span className="font-mono">₹{result.risk_metrics.max_loss.toFixed(2)}</span></div>
                        )}
                        {result.risk_metrics.max_profit && (
                          <div><span className="text-slate-400">Max Profit:</span> <span className="font-mono">₹{result.risk_metrics.max_profit.toFixed(2)}</span></div>
                        )}
                        {result.risk_metrics.breakeven && (
                          <div><span className="text-slate-400">Breakeven:</span> <span className="font-mono">₹{result.risk_metrics.breakeven.toFixed(2)}</span></div>
                        )}
                      </div>
                    )}

                    {/* Run ID */}
                    {result.run_id && (
                      <div className="text-xs text-slate-500 mt-2">Run ID: {result.run_id}</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default StrategyManager;
