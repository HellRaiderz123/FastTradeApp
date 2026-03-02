import React, { useState, useEffect } from 'react';
import { Play, Pause, Trash2, Plus, RefreshCw, Zap, Edit2 } from 'lucide-react';
import { strategyAPI, executionAPI, suggestionsAPI } from '../lib/api';
import { StrategyForm } from './StrategyForm';
import { useToast } from './Toast';

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

interface Suggestion {
  underlying: string;
  strategy: string;
  approved: boolean;
  reason: string;
  score: number;
  confidence?: number;
  spot?: number;
  atm?: number;
  ticket?: Record<string, any>;
  risk_metrics?: Record<string, any>;
  signal?: Record<string, any>;
  context?: Record<string, any>;
}

export const StrategyManager: React.FC = () => {
  const { showToast } = useToast();
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState<number | null>(null);
  const [results, setResults] = useState<ExecutionResult[]>([]);
  const [selectedStrategies, setSelectedStrategies] = useState<Set<number>>(new Set());
  const [showNewForm, setShowNewForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [suggestionUnderlyings, setSuggestionUnderlyings] = useState<string[]>([
    'NIFTY',
    'BANKNIFTY',
    'FINNIFTY',
    'NIFTY_IT',
  ]);

  const underlyingLabels: Record<string, string> = {
    NIFTY: 'NIFTY50',
    BANKNIFTY: 'BANKNIFTY',
    FINNIFTY: 'FINNIFTY',
    NIFTY_IT: 'NIFTY IT',
  };

  // Load strategies on mount
  useEffect(() => {
    loadStrategies();
  }, []);

  useEffect(() => {
    // Auto-load suggestions after strategies are available
    if (strategies.length > 0) {
      refreshSuggestions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategies.length]);

  useEffect(() => {
    if (strategies.length === 0) return;
    const interval = setInterval(() => {
      refreshSuggestions();
    }, 60000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [strategies.length, suggestionUnderlyings]);

  const refreshSuggestions = async () => {
    setSuggestionsLoading(true);
    try {
      const underlyings = suggestionUnderlyings.length > 0
        ? suggestionUnderlyings
        : ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];
      const payload = {
        underlyings,
        capital: 100000,
        lots: 2,
        risk_mode: 'Conservative',
        use_ml: false,
        min_confidence: 75,
      };

      const response = await suggestionsAPI.get(payload);
      const data = response?.data;
      setSuggestions(Array.isArray(data?.suggestions) ? data.suggestions : []);
    } catch (error) {
      console.error('Failed to load suggestions:', error);
      setSuggestions([]);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const createStrategyFromSuggestion = async (suggestion: Suggestion) => {
    try {
      const payload = {
        underlying: suggestion.underlying,
        strategy_type: suggestion.strategy,
        reason: suggestion.reason,
        confidence: suggestion.confidence || 0,
        capital: 100000,
        lots: 2,
        risk_mode: 'Conservative',
        min_confidence: 75,
        spot: suggestion.spot || 0,
        atm: suggestion.atm || 0,
        ticket: suggestion.ticket || null,
        risk_metrics: suggestion.risk_metrics || null,
      };

      const response = await strategyAPI.createFromSuggestion(payload);
      
      if (response.data) {
        showToast('success', 'Strategy Created', `"${response.data.name}" created successfully! Enable it from the list below.`);
        await loadStrategies();
      }
    } catch (error: any) {
      console.error('Failed to create strategy from suggestion:', error);
      showToast('error', 'Creation Failed', error?.response?.data?.detail || error.message);
    }
  };

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
      const selected = strategies.find((s) => s.id === strategyId);
      if (selected && !selected.enabled) {
        await strategyAPI.enableStrategy(strategyId);
        await loadStrategies();
      }
      // 1) Run strategy (build ticket + create StrategyRun)
      const response = await executionAPI.executeSingle(strategyId);
      const runResult = response.data;

      // 2) Create execution intent from run_id
      const runId = runResult?.run_id;
      if (!runId) {
        setResults([runResult, ...results]);
        showToast('warning', 'Partial Run', 'Strategy ran but no run_id returned');
        return;
      }

      const intentResp = await executionAPI.createIntent(runId);
      const intentData = intentResp.data;
      const intentId = intentData?.intent_id;
      if (!intentId) {
        setResults([
          { ...runResult, intent: intentData },
          ...results,
        ]);
        showToast('warning', 'Intent Failed', 'Intent creation failed (no intent_id)');
        return;
      }

      // 3) Execute paper
      const idempotencyKey = (globalThis.crypto && 'randomUUID' in globalThis.crypto)
        ? (globalThis.crypto as any).randomUUID()
        : `${Date.now()}-${Math.random()}`;

      const execResp = await executionAPI.executeIntent(intentId, idempotencyKey);
      const execData = execResp.data;

      setResults([
        { ...runResult, intent_id: intentId, execution: execData },
        ...results,
      ]);
      showToast('success', 'Executed', `Paper trade: ${runResult?.strategy_name || 'strategy'}`);
    } catch (error) {
      console.error('Execution failed:', error);
      showToast('error', 'Execution Failed', 'Failed to execute strategy');
    } finally {
      setExecuting(null);
    }
  };

  const handleExecuteMultiple = async () => {
    if (selectedStrategies.size === 0) {
      showToast('warning', 'No Selection', 'Please select at least one strategy');
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
      
      showToast('success', 'Batch Executed', `${response.data.completed}/${response.data.total} strategies executed`);
      setSelectedStrategies(new Set());
    } catch (error) {
      console.error('Multi-execution failed:', error);
      showToast('error', 'Batch Failed', 'Failed to execute strategies');
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
      
      showToast('success', 'All Executed', `${response.data.completed}/${response.data.total} strategies executed`);
    } catch (error) {
      console.error('Execute all failed:', error);
      showToast('error', 'Execute All Failed', 'Failed to execute all strategies');
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

  const handleEdit = (strategyId: number) => {
    setEditingId(strategyId);
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

  const toggleSuggestionUnderlying = (value: string) => {
    setSuggestionUnderlyings((prev) => {
      if (prev.includes(value)) {
        return prev.filter((u) => u !== value);
      }
      return [...prev, value];
    });
  };

  const filteredSuggestions = suggestionUnderlyings.length > 0
    ? suggestions.filter((s) => suggestionUnderlyings.includes(s.underlying))
    : suggestions;

  return (
    <div className="space-y-6 p-6">
      {/* Suggestions */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white">Trade Suggestions</h2>
            <p className="text-xs text-slate-400">Ranked ideas (bull put / bear call / iron condor)</p>
          </div>
          <button
            onClick={refreshSuggestions}
            disabled={suggestionsLoading}
            className="p-2 hover:bg-slate-700 rounded text-slate-300 hover:text-white transition disabled:opacity-50"
            title="Refresh suggestions"
          >
            <RefreshCw size={18} className={suggestionsLoading ? 'animate-spin' : ''} />
          </button>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          {['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'NIFTY_IT'].map((u) => {
            const active = suggestionUnderlyings.includes(u);
            return (
              <button
                key={u}
                onClick={() => toggleSuggestionUnderlying(u)}
                className={`px-2.5 py-1 rounded text-xs font-semibold border transition ${
                  active
                    ? 'bg-blue-600 text-white border-blue-500'
                    : 'bg-slate-900 text-slate-300 border-slate-700 hover:bg-slate-700'
                }`}
                aria-pressed={active}
                title={`Filter ${underlyingLabels[u] || u}`}
              >
                {underlyingLabels[u] || u}
              </button>
            );
          })}
        </div>

        {suggestionsLoading ? (
          <div className="text-slate-400 text-sm mt-3">Loading suggestions...</div>
        ) : filteredSuggestions.length === 0 ? (
          <div className="text-slate-400 text-sm mt-3">No suggestions available right now.</div>
        ) : (
          <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3 mt-3">
            {filteredSuggestions.slice(0, 6).map((s, idx) => (
              <div key={idx} className="bg-slate-900 border border-slate-700 rounded p-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-white font-semibold">{underlyingLabels[s.underlying] || s.underlying}</div>
                    <div className="text-xs text-slate-400">Score: <span className="font-mono text-slate-200">{s.score}</span></div>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    s.approved ? 'bg-green-900 text-green-200' : 'bg-slate-700 text-slate-200'
                  }`}>
                    {s.approved ? 'Approved' : 'No Trade'}
                  </span>
                </div>

                <div className="mt-2 text-xs text-slate-200">
                  <div><span className="text-slate-400">Strategy:</span> <span className="font-mono">{s.strategy}</span></div>
                  <div className="mt-1"><span className="text-slate-400">Reason:</span> <span className="font-mono">{s.reason}</span></div>
                  {typeof s.spot === 'number' && (
                    <div className="mt-1"><span className="text-slate-400">Spot:</span> <span className="font-mono">₹{s.spot.toFixed(2)}</span></div>
                  )}
                  {typeof s.atm === 'number' && (
                    <div className="mt-1"><span className="text-slate-400">ATM:</span> <span className="font-mono">{s.atm}</span></div>
                  )}
                </div>

                {s.ticket?.legs?.length > 0 && (
                  <div className="mt-2 p-2 bg-slate-800 rounded">
                    <div className="text-slate-300 font-semibold text-xs mb-1">Ticket</div>
                    {s.ticket?.legs?.map((leg: any, legIdx: number) => (
                      <div key={legIdx} className="text-xs text-slate-200">
                        {leg.side} {leg.strike} {leg.type}
                      </div>
                    ))}
                  </div>
                )}

                {typeof s.risk_metrics?.risk_pct_capital === 'number' && (
                  <div className="mt-2 text-xs text-slate-300">
                    Risk: <span className="font-mono">{s.risk_metrics.risk_pct_capital.toFixed(2)}%</span>
                  </div>
                )}

                {s.approved && (
                  <button
                    onClick={() => createStrategyFromSuggestion(s)}
                    className="mt-3 w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs py-2 px-3 rounded transition flex items-center justify-center space-x-1"
                    title="Create strategy from this suggestion"
                  >
                    <Plus size={14} />
                    <span>Create Strategy</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Header */}
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold text-white">Strategy Manager</h1>
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setShowNewForm(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded transition"
            title="Create new strategy"
          >
            <Plus size={18} />
            <span>New Strategy</span>
          </button>
          <button
            onClick={loadStrategies}
            disabled={loading}
            title="Refresh strategies"
            aria-label="Refresh strategies"
            className="p-2 hover:bg-slate-800 rounded text-slate-400 hover:text-white transition"
          >
            <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Bulk Actions */}
      {strategies.length > 0 && (
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 space-y-3">
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              aria-label="Select all strategies"
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
                  aria-label={`Select strategy ${strategy.name}`}
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
                        ? 'bg-green-900/50 text-green-300'
                        : 'bg-slate-700 text-slate-400'
                    }`}
                  >
                    {strategy.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
              </div>

              {/* Parameters Preview */}
              <div className="bg-slate-900 rounded p-2 text-xs">
                <div className="font-semibold mb-1 text-slate-300">Parameters:</div>
                <div className="space-y-0.5 text-slate-400">
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
                  title={strategy.enabled ? 'Disable strategy' : 'Enable strategy'}
                  aria-label={strategy.enabled ? 'Disable strategy' : 'Enable strategy'}
                  className={`flex items-center justify-center px-3 py-2 rounded text-sm ${
                    strategy.enabled
                      ? 'bg-yellow-900/40 text-yellow-300 hover:bg-yellow-900/60'
                      : 'bg-green-900/40 text-green-300 hover:bg-green-900/60'
                  }`}
                >
                  {strategy.enabled ? <Pause size={14} /> : <Play size={14} />}
                </button>

                <button
                  onClick={() => handleEdit(strategy.id)}
                  disabled={strategy.enabled}
                  title={strategy.enabled ? 'Cannot edit deployed strategy' : 'Edit strategy'}
                  aria-label="Edit strategy"
                  className={`flex items-center justify-center px-3 py-2 rounded text-sm ${
                    strategy.enabled
                      ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                      : 'bg-blue-900/40 text-blue-300 hover:bg-blue-900/60'
                  }`}
                >
                  <Edit2 size={14} />
                </button>

                <button
                  onClick={() => handleDelete(strategy.id)}
                  title="Delete strategy"
                  aria-label="Delete strategy"
                  className="flex items-center justify-center px-3 py-2 bg-red-900/40 text-red-300 rounded hover:bg-red-900/60"
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
                        <div><span className="text-slate-400">Bias:</span> <span className="font-mono">{result.signal.bias || result.signal.signal || result.signal.direction || 'N/A'}</span></div>
                        <div><span className="text-slate-400">Confidence:</span> <span className="font-mono">{typeof result.signal.confidence === 'number' ? `${result.signal.confidence.toFixed(1)}%` : 'N/A'}</span></div>
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

      {/* Edit Form Modal */}
      {editingId !== null && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-lg max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <StrategyForm
              initialData={strategies.find((s) => s.id === editingId)}
              onClose={() => setEditingId(null)}
              onSuccess={() => {
                setEditingId(null);
                loadStrategies();
              }}
            />
          </div>
        </div>
      )}

      {/* Create Form Modal */}
      {showNewForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-lg max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <StrategyForm
              onClose={() => setShowNewForm(false)}
              onSuccess={() => {
                setShowNewForm(false);
                loadStrategies();
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default StrategyManager;
