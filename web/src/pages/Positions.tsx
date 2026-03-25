import React, { useState, useEffect, useRef } from 'react';
import { TrendingUp, TrendingDown, X, AlertTriangle, Shield, Eye, CheckCircle } from 'lucide-react';
import { exitAPI, journalAPI, smartSuggestionsAPI } from '../lib/api';
import { useTradeStore } from '../lib/store';
import { useToast } from '../components/Toast';
import SpreadGrouping from '../components/SpreadGrouping';

const Positions: React.FC = () => {
  const { showToast } = useToast();
  const { trades, setTrades } = useTradeStore();
  const [loading, setLoading] = useState(false);
  const [localTrades, setLocalTrades] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const pollRef = useRef<number | null>(null);

  const [spreadData, setSpreadData] = useState<any>(null);
  // Smart suggestions state (keyed by intent_id)
  const [smartSuggestions, setSmartSuggestions] = useState<Record<string, any>>({});

  // Fetch smart suggestions via REST (fallback when WS doesn't have them yet)
  const fetchSmartSuggestions = async () => {
    try {
      const res = await smartSuggestionsAPI.get();
      const data = res?.data;
      if (data?.suggestions) {
        setSmartSuggestions(data.suggestions);
      }
    } catch (e) {
      console.debug('[Positions] Smart suggestions fetch failed:', e);
    }
  };

  useEffect(() => {
    fetchPositions();
    // Fetch smart suggestions on mount and every 60s
    fetchSmartSuggestions();
    const smartPoll = window.setInterval(fetchSmartSuggestions, 60000);

    // Poll as a fallback (e.g., if WS is blocked)
    pollRef.current = window.setInterval(fetchPositions, 30000);

    // Live updates via WebSocket
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const wsUrl = `${proto}://${window.location.host}/api/ws/positions`;
      console.log('[Positions] Connecting to WebSocket:', wsUrl);
      
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[Positions] ✅ WebSocket connected');
        // Once live is connected, polling is less important.
        if (pollRef.current) {
          window.clearInterval(pollRef.current);
          pollRef.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg?.type !== 'positions_update') {
            console.debug('[Positions] Ignoring non-position message:', msg?.type);
            return;
          }
          const updates = Array.isArray(msg?.intents) ? msg.intents : [];
          console.log('[Positions] 📊 Received update with', updates.length, 'intents');

          // Merge WS smart suggestions into state
          const wsSuggestions: Record<string, any> = {};
          for (const u of updates) {
            if (u?.smart_suggestion && u?.intent_id) {
              wsSuggestions[u.intent_id] = u.smart_suggestion;
            }
          }
          if (Object.keys(wsSuggestions).length > 0) {
            setSmartSuggestions((prev) => ({ ...prev, ...wsSuggestions }));
          }

          setLocalTrades((prev) => {
            const byId = new Map<string, any>();
            for (const t of Array.isArray(prev) ? prev : []) {
              const id = String(t?.intent_id ?? '');
              if (id) byId.set(id, t);
            }
            for (const u of updates) {
              const id = String(u?.intent_id ?? '');
              if (!id) continue;
              byId.set(id, { ...(byId.get(id) || {}), ...u });
            }
            return Array.from(byId.values());
          });
        } catch (e) {
          console.error('[Positions] WebSocket message parse error:', e);
        }
      };

      ws.onclose = () => {
        console.log('[Positions] ⚠️  WebSocket disconnected');
        wsRef.current = null;
        // Restore polling if live stream drops
        if (!pollRef.current) {
          console.log('[Positions] Falling back to polling (30s interval)');
          pollRef.current = window.setInterval(fetchPositions, 30000);
        }
      };

      ws.onerror = (error) => {
        console.error('[Positions] ❌ WebSocket error:', error);
        // Let onclose restore polling
      };
    } catch (e) {
      console.error('[Positions] Failed to create WebSocket:', e);
      // Keep polling only
    }

    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
      if (wsRef.current) wsRef.current.close();
      wsRef.current = null;
      window.clearInterval(smartPoll);
    };
  }, []);

  const fetchPositions = async () => {
    try {
      setLoading(true);
      // Fetch execution intents (active trades)
      const response = await journalAPI.getExecutionIntents(50);
      const data = response?.data;
      const intents = Array.isArray(data) ? data : [];
      const ZERODHA_STRATEGIES = ['ZERODHA_HOLDING', 'ZERODHA_ACTUAL', 'DIRECT_ZERODHA'];
      const activeIntents = intents.filter((intent: any) =>
        intent?.status === 'EXECUTED' &&
        !ZERODHA_STRATEGIES.includes(intent?.strategy)
      );
      setLocalTrades(activeIntents);
    } catch (error) {
      console.error('Failed to fetch positions:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleClosePosition = async (intentId: string) => {
    setLoading(true);
    try {
      await exitAPI.manualExit(intentId);
      setLocalTrades(localTrades.filter((t) => t.intent_id !== intentId));
      showToast('success', 'Position Closed', 'Position closed successfully!');
    } catch (error) {
      console.error('Failed to close position:', error);
      showToast('error', 'Close Failed', 'Failed to close position');
    } finally {
      setLoading(false);
    }
  };

  const displayTrades = localTrades.length > 0 ? localTrades : trades;
  // Exclude positions synced from Zerodha API (shown in ZerodhaPositionsWidget)
  const openPositions = displayTrades.filter((t) => t?.status === 'EXECUTED');
  const totalPnL = openPositions.reduce((sum, t) => sum + (t.pnl || 0), 0);
  const totalPnLPercent = openPositions.length > 0 ? (totalPnL / 100000) * 100 : 0;

  // Smart suggestion summary counts
  const allSuggestions = openPositions.map(
    (t) => t.smart_suggestion || smartSuggestions[t.intent_id]
  ).filter(Boolean);
  const criticalAlerts = allSuggestions.filter((s: any) => s.severity === 'HIGH').length;
  const warnings = allSuggestions.filter((s: any) => s.severity === 'MEDIUM').length;
  const watchCount = allSuggestions.filter((s: any) => s.action === 'WATCH').length;

  return (
    <div className="space-y-6">
      {/* Smart Alerts Banner */}
      {criticalAlerts > 0 && (
        <div className="bg-red-500/10 border border-red-500/40 rounded-lg p-4 flex items-center gap-3 animate-pulse">
          <AlertTriangle className="w-6 h-6 text-red-400 flex-shrink-0" />
          <div>
            <p className="text-red-300 font-semibold">
              {criticalAlerts} position{criticalAlerts > 1 ? 's' : ''} conflict{criticalAlerts === 1 ? 's' : ''} with current TA signal
            </p>
            <p className="text-red-400/70 text-xs mt-0.5">
              The market has shifted against your open position{criticalAlerts > 1 ? 's' : ''}. Review the suggestions below.
            </p>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <SummaryCard
          label="Open Positions"
          value={openPositions.length.toString()}
          color="blue"
        />
        <SummaryCard
          label="Total P&L"
          value={`₹${totalPnL.toLocaleString()}`}
          subtext={`${totalPnLPercent.toFixed(2)}%`}
          color={totalPnL >= 0 ? 'green' : 'red'}
        />
        <SummaryCard
          label="Avg P&L per Trade"
          value={`₹${openPositions.length > 0 ? Math.round(totalPnL / openPositions.length) : 0}`}
          color="purple"
        />
        <SummaryCard
          label="Largest Win"
          value={`₹${Math.max(0, ...openPositions.map((t) => t.pnl || 0)).toLocaleString()}`}
          color="green"
        />
      </div>

      {/* Positions List */}
      <div className="card-glass p-6">
        <h2 className="text-2xl font-bold mb-6 text-white">Open Positions {loading && '(updating...)'}</h2>

        {openPositions.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-slate-400 mb-4">No open positions</p>
            <p className="text-sm text-slate-500">Execute a strategy to open a position</p>
          </div>
        ) : (
          <div className="space-y-4">
            {openPositions.map((trade) => (
              <PositionCard
                key={trade.intent_id || trade.id}
                trade={trade}
                onClose={() => handleClosePosition(String(trade.intent_id || ''))}
                loading={loading}
                smartSuggestion={
                  trade.smart_suggestion ||
                  smartSuggestions[trade.intent_id] ||
                  null
                }
              />
            ))}
          </div>
        )}
      </div>

      {/* Spread Grouping & Smart Analysis */}
      {openPositions.length > 0 && (
        <div>
          <h2 className="text-2xl font-bold mb-6 text-white">🎯 Spread Intelligence</h2>
          <SpreadGrouping limit={50} onRefresh={fetchPositions} onDataLoaded={setSpreadData} />
        </div>
      )}

      {/* Risk Metrics */}
      <div className="card-glass p-6">
        <h3 className="text-lg font-semibold mb-4 text-white">📊 Risk Metrics</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {(() => {
            // Compute spread-aware risk metrics
            const spreads = spreadData?.spreads || [];
            const totalMaxProfit = spreads.reduce((s: number, sp: any) => s + (sp.max_profit || 0), 0);
            const totalMaxLoss = spreads.reduce((s: number, sp: any) => s + (sp.max_loss || 0), 0);
            const nakedCount = (spreadData?.naked_positions || []).length;
            const incompleteCount = (spreadData?.incomplete_spreads || []).length;
            const currentPnL = totalPnL;

            // % of max profit captured so far
            const profitCapture = totalMaxProfit > 0 ? (currentPnL / totalMaxProfit) * 100 : 0;
            // % of max loss used
            const riskUsed = totalMaxLoss > 0 ? (Math.abs(Math.min(0, currentPnL)) / totalMaxLoss) * 100 : 0;
            // Reward:Risk ratio
            const rrRatio = totalMaxLoss > 0 ? totalMaxProfit / totalMaxLoss : 0;
            // Win rate
            const winCount = openPositions.filter(t => (t.pnl || 0) > 0).length;
            const winRate = openPositions.length > 0 ? Math.round((winCount / openPositions.length) * 100) : 0;

            return (
              <>
                <RiskMetric
                  label="Current P&L"
                  value={`₹${Math.abs(currentPnL).toLocaleString()}`}
                  subtext={currentPnL >= 0 ? `+${profitCapture.toFixed(1)}% of max profit` : `${riskUsed.toFixed(1)}% of max loss used`}
                  status={currentPnL >= 0 ? 'good' : riskUsed <= 30 ? 'warning' : 'danger'}
                />
                <RiskMetric
                  label="Max Possible Loss"
                  value={totalMaxLoss > 0 ? `₹${totalMaxLoss.toLocaleString()}` : nakedCount > 0 ? 'Unlimited' : '-'}
                  subtext={totalMaxLoss > 0 ? `Max Profit: ₹${totalMaxProfit.toLocaleString()}` : nakedCount > 0 ? `${nakedCount} naked position(s)` : 'No open derivatives'}
                  status={nakedCount > 0 ? 'danger' : totalMaxLoss <= 15000 ? 'good' : 'warning'}
                />
                <RiskMetric
                  label="Reward : Risk"
                  value={rrRatio > 0 ? `1:${(1 / rrRatio).toFixed(2)}` : '-'}
                  subtext={spreads.length > 0 ? `${spreads.length} spread(s) grouped` : incompleteCount > 0 ? `${incompleteCount} incomplete` : 'No spreads'}
                  status={rrRatio >= 0.3 ? 'good' : rrRatio > 0 ? 'warning' : 'danger'}
                />
                <RiskMetric
                  label="Win Rate"
                  value={`${winCount}/${openPositions.length}`}
                  subtext={openPositions.length > 0 ? `${winRate}% Win Ratio` : 'N/A'}
                  status={winRate >= 50 ? 'good' : 'warning'}
                />
              </>
            );
          })()}
        </div>

        {/* Breakeven Levels */}
        {spreadData?.spreads?.some((s: any) => s.breakeven_points?.length > 0) && (
          <div className="mt-4 pt-4 border-t border-slate-700">
            <p className="text-xs text-slate-400 mb-2">Breakeven Levels</p>
            <div className="flex flex-wrap gap-3">
              {spreadData.spreads.filter((s: any) => s.breakeven_points?.length > 0).map((s: any, i: number) => (
                <div key={i} className="bg-slate-800/50 px-3 py-1.5 rounded border border-slate-700">
                  <span className="text-xs text-slate-400">{s.underlying} {s.spread_type.replace(/_/g, ' ')}: </span>
                  <span className="text-sm font-semibold text-blue-400">
                    {s.breakeven_points.map((b: number) => b.toFixed(1)).join(' / ')}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>


    </div>
  );
};

interface SummaryCardProps {
  label: string;
  value: string;
  subtext?: string;
  color: string;
}

const SummaryCard: React.FC<SummaryCardProps> = ({ label, value, subtext, color }) => {
  const bgClass = {
    blue: 'from-blue-500/20',
    green: 'from-green-500/20',
    red: 'from-red-500/20',
    purple: 'from-purple-500/20',
  }[color] || 'from-slate-500/20';

  return (
    <div className={`card-glass p-4 bg-gradient-to-br ${bgClass}`}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  );
};

interface PositionCardProps {
  trade: any;
  onClose: () => void;
  loading: boolean;
  smartSuggestion?: any;
}

// Hedge Position Modal Component
const HedgeModal: React.FC<{ trade: any; onClose: () => void; onSuccess: () => void }> = ({ trade, onClose, onSuccess }) => {
  const { showToast } = useToast();
  const [hedgeType, setHedgeType] = React.useState<'strangle' | 'wing' | 'opposite'>('strangle');
  const [loading, setLoading] = React.useState(false);
  
  const handleHedge = async () => {
    setLoading(true);
    try {
      showToast('info', 'Coming Soon', `Hedge feature: Adding ${hedgeType} hedge to ${trade.strategy}`);
      // TODO: Implement actual hedge logic
      onSuccess();
    } catch (err) {
      showToast('error', 'Hedge Failed', 'Failed to add hedge');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-md space-y-4">
        <h3 className="text-lg font-bold text-white">🛡️ Hedge Position</h3>
        <p className="text-sm text-slate-300">Add protective legs to reduce risk</p>
        
        <div className="space-y-3">
          <div className="p-3 bg-slate-800 rounded border border-slate-700">
            <p className="text-xs text-slate-400 mb-1">Current Position</p>
            <p className="text-sm font-semibold text-white">{trade.strategy} • {trade.underlying}</p>
            <p className="text-xs text-slate-400">Unrealized P&L: <span className={Number(trade.pnl) >= 0 ? 'text-green-400' : 'text-red-400'}>₹{Math.abs(Number(trade.pnl)).toLocaleString()}</span></p>
          </div>

          <div className="space-y-2">
            <label className="block text-xs text-slate-300 font-semibold">Hedge Strategy</label>
            <select 
              value={hedgeType} 
              onChange={(e) => setHedgeType(e.target.value as any)}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
            >
              <option value="strangle">Short Strangle (Sell OTM Call & Put)</option>
              <option value="wing">Add Wings (Protect existing spread)</option>
              <option value="opposite">Opposite Side (Counter current position)</option>
            </select>
          </div>

          <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded">
            <p className="text-xs text-blue-300">
              {hedgeType === 'strangle' && '• Reduces delta exposure\n• Generates premium credit\n• Limits max profit'}
              {hedgeType === 'wing' && '• Caps maximum loss\n• Reduces margin requirement\n• Converts to Iron Condor'}
              {hedgeType === 'opposite' && '• Creates synthetic position\n• Locks in current P&L\n• Zero delta hedge'}
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <button 
            onClick={handleHedge} 
            disabled={loading}
            className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded font-semibold transition"
          >
            {loading ? 'Adding Hedge...' : 'Add Hedge'}
          </button>
          <button 
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Adjust Strikes Modal Component
const AdjustStrikesModal: React.FC<{ trade: any; onClose: () => void; onSuccess: () => void }> = ({ trade, onClose, onSuccess }) => {
  const { showToast } = useToast();
  const [adjustment, setAdjustment] = React.useState<number>(50);
  const [direction, setDirection] = React.useState<'up' | 'down'>('up');
  const [loading, setLoading] = React.useState(false);
  
  const legs = trade?.ticket?.legs || [];

  const handleAdjust = async () => {
    setLoading(true);
    try {
      showToast('info', 'Adjusting', `Adjusting strikes ${direction} by ${adjustment} points`);
      // TODO: Close current legs and open new ones with adjusted strikes
      onSuccess();
    } catch (err) {
      showToast('error', 'Adjust Failed', 'Failed to adjust strikes');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-md space-y-4">
        <h3 className="text-lg font-bold text-white">📊 Adjust Strikes</h3>
        <p className="text-sm text-slate-300">Roll strikes up or down</p>
        
        <div className="space-y-3">
          <div className="p-3 bg-slate-800 rounded border border-slate-700">
            <p className="text-xs text-slate-400 mb-2">Current Strikes</p>
            {legs.map((leg: any, idx: string) => (
              <p key={idx} className="text-xs text-white mb-1">
                <span className={leg.side === 'SELL' ? 'text-red-400' : 'text-green-400'}>{leg.side}</span> {leg.strike} {leg.type}
              </p>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-300 mb-1">Direction</label>
              <select 
                value={direction} 
                onChange={(e) => setDirection(e.target.value as any)}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
              >
                <option value="up">Move Up ⬆️</option>
                <option value="down">Move Down ⬇️</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-300 mb-1">Adjustment</label>
              <input 
                type="number" 
                value={adjustment} 
                onChange={(e) => setAdjustment(Number(e.target.value))}
                step="50"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
              />
            </div>
          </div>

          <div className="p-3 bg-slate-800 rounded border border-slate-700">
            <p className="text-xs text-slate-400 mb-2">New Strikes (Preview)</p>
            {legs.map((leg: any, idx: string) => {
              const newStrike = direction === 'up' ? leg.strike + adjustment : leg.strike - adjustment;
              return (
                <p key={idx} className="text-xs text-green-400 mb-1">
                  <span className={leg.side === 'SELL' ? 'text-red-400' : 'text-green-400'}>{leg.side}</span> {newStrike} {leg.type}
                </p>
              );
            })}
          </div>

          <div className="p-3 bg-purple-500/10 border border-purple-500/30 rounded">
            <p className="text-xs text-purple-300">
              ⚠️ This will close current position and open new one with adjusted strikes
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <button 
            onClick={handleAdjust} 
            disabled={loading}
            className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded font-semibold transition"
          >
            {loading ? 'Rolling...' : 'Roll Position'}
          </button>
          <button 
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Add to Position Modal Component
const AddToPositionModal: React.FC<{ trade: any; onClose: () => void; onSuccess: () => void }> = ({ trade, onClose, onSuccess }) => {
  const { showToast } = useToast();
  const [quantity, setQuantity] = React.useState<number>(1);
  const [loading, setLoading] = React.useState(false);
  
  const currentQty = trade?.ticket?.lots || 1;

  const handleAdd = async () => {
    setLoading(true);
    try {
      showToast('info', 'Adding', `Adding ${quantity} more contracts to position`);
      // TODO: Execute additional legs with same strikes
      onSuccess();
    } catch (err) {
      showToast('error', 'Add Failed', 'Failed to add to position');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-md space-y-4">
        <h3 className="text-lg font-bold text-white">➕ Add to Position</h3>
        <p className="text-sm text-slate-300">Scale into this position</p>
        
        <div className="space-y-3">
          <div className="p-3 bg-slate-800 rounded border border-slate-700">
            <p className="text-xs text-slate-400">Current Position Size</p>
            <p className="text-2xl font-bold text-white">{currentQty} Lot{currentQty > 1 ? 's' : ''}</p>
          </div>

          <div>
            <label className="block text-xs text-slate-300 mb-1 font-semibold">Add Quantity</label>
            <input 
              type="number" 
              value={quantity} 
              onChange={(e) => setQuantity(Number(e.target.value))}
              min="1"
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
            />
          </div>

          <div className="p-3 bg-slate-800 rounded border border-slate-700">
            <p className="text-xs text-slate-400">New Position Size</p>
            <p className="text-2xl font-bold text-green-400">{currentQty + quantity} Lot{(currentQty + quantity) > 1 ? 's' : ''}</p>
            <p className="text-xs text-slate-400 mt-1">+{((quantity / currentQty) * 100).toFixed(0)}% increase</p>
          </div>

          <div className="p-3 bg-green-500/10 border border-green-500/30 rounded">
            <p className="text-xs text-green-300">
              • Same strikes as current position<br/>
              • Averages entry price<br/>
              • Increases position risk
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <button 
            onClick={handleAdd} 
            disabled={loading}
            className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded font-semibold transition"
          >
            {loading ? 'Adding...' : `Add ${quantity} Lot${quantity > 1 ? 's' : ''}`}
          </button>
          <button 
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
};

// Share Strategy Modal Component
const ShareStrategyModal: React.FC<{ trade: any; onClose: () => void }> = ({ trade, onClose }) => {
  const [copied, setCopied] = React.useState(false);
  
  const strategyConfig = {
    strategy: trade.strategy,
    underlying: trade.underlying,
    legs: trade.ticket?.legs || [],
    expiry: trade.expiry,
    entry_credit: trade.entry_credit,
  };

  const shareText = JSON.stringify(strategyConfig, null, 2);

  const handleCopy = () => {
    navigator.clipboard.writeText(shareText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-lg space-y-4">
        <h3 className="text-lg font-bold text-white">📤 Share Strategy</h3>
        <p className="text-sm text-slate-300">Export your position configuration</p>
        
        <div className="space-y-3">
          <div className="p-3 bg-slate-800 rounded border border-slate-700">
            <p className="text-xs text-slate-400 mb-1">Strategy</p>
            <p className="text-sm font-semibold text-white">{trade.strategy}</p>
          </div>

          <div>
            <label className="block text-xs text-slate-300 mb-1 font-semibold">Configuration JSON</label>
            <textarea 
              readOnly 
              value={shareText}
              className="w-full h-48 px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-xs font-mono"
            />
          </div>

          <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded">
            <p className="text-xs text-amber-300">
              💡 Share this configuration with others to replicate your strategy
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-6">
          <button 
            onClick={handleCopy}
            className="flex-1 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded font-semibold transition"
          >
            {copied ? '✓ Copied!' : 'Copy to Clipboard'}
          </button>
          <button 
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

// ──────────── Smart Suggestion Banner ────────────
interface SmartSuggestionBannerProps {
  suggestion: any;
  onDismiss: () => void;
  onClose: () => void;    // close position
  onHedge: () => void;    // open hedge modal
}

const SmartSuggestionBanner: React.FC<SmartSuggestionBannerProps> = ({
  suggestion,
  onDismiss,
  onClose,
  onHedge,
}) => {
  const [expanded, setExpanded] = React.useState(false);

  const action = suggestion?.action || 'HOLD';
  const severity = suggestion?.severity || 'LOW';
  const reason = suggestion?.reason || '';
  const details = suggestion?.details || '';
  const currentBias = suggestion?.current_signal_bias || '?';
  const currentStrategy = suggestion?.current_strategy_name || '?';
  const confidence = suggestion?.current_confidence || 0;
  const marketMode = suggestion?.current_market_mode || '?';
  const ivRegime = suggestion?.current_iv_regime || '?';

  // Color scheme based on severity
  const colorMap: Record<string, { bg: string; border: string; text: string; icon: string; badge: string }> = {
    HIGH: {
      bg: 'bg-red-500/10',
      border: 'border-red-500/40',
      text: 'text-red-300',
      icon: 'text-red-400',
      badge: 'bg-red-500/20 text-red-300 border-red-500/40',
    },
    MEDIUM: {
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/40',
      text: 'text-amber-300',
      icon: 'text-amber-400',
      badge: 'bg-amber-500/20 text-amber-300 border-amber-500/40',
    },
    LOW: {
      bg: 'bg-blue-500/10',
      border: 'border-blue-500/30',
      text: 'text-blue-300',
      icon: 'text-blue-400',
      badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    },
  };

  const colors = colorMap[severity] || colorMap.LOW;

  // Icon based on action
 const actionIcons = {
  CONSIDER_EXIT: AlertTriangle,
  HEDGE_SUGGESTED: Shield,
  WATCH: Eye,
  HOLD: CheckCircle,
} as const;

type ActionType2 = keyof typeof actionIcons;

const ActionIcon =
  actionIcons[action as ActionType2] ?? Eye;

  // Action label
 const actionLabels = {
  CONSIDER_EXIT: 'Consider Exiting',
  HEDGE_SUGGESTED: 'Hedge Suggested',
  WATCH: 'Watch Closely',
  HOLD: 'Hold',
} as const;

type ActionType = keyof typeof actionLabels;

const actionLabel =
  actionLabels[action as ActionType] ?? 'Unknown';

  return (
    <div className={`${colors.bg} border ${colors.border} rounded-lg p-3 mb-2`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2 flex-1">
          <ActionIcon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${colors.icon}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`text-xs font-bold px-2 py-0.5 rounded border ${colors.badge}`}>
                🧠 {actionLabel}
              </span>
              <span className="text-xs text-slate-400">
                TA now: <span className={`font-semibold ${
                  currentBias === 'BULLISH' ? 'text-green-400' :
                  currentBias === 'BEARISH' ? 'text-red-400' : 'text-slate-300'
                }`}>{currentBias}</span> • {confidence}% conf
              </span>
            </div>
            <p className={`text-xs mt-1 ${colors.text}`}>{reason}</p>

            {expanded && (
              <div className="mt-2 space-y-2">
                <p className="text-xs text-slate-400 leading-relaxed">{details}</p>
                <div className="flex flex-wrap gap-2 mt-2">
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                    Now suggests: {currentStrategy}
                  </span>
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                    Market: {marketMode}
                  </span>
                  <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                    IV: {ivRegime}
                  </span>
                </div>

                {/* Quick action buttons */}
                {(action === 'CONSIDER_EXIT' || action === 'HEDGE_SUGGESTED') && (
                  <div className="flex gap-2 mt-2 pt-2 border-t border-slate-700/50">
                    {action === 'CONSIDER_EXIT' && (
                      <button
                        onClick={onClose}
                        className="px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-300 text-xs border border-red-500/30 rounded transition"
                      >
                        Exit Position
                      </button>
                    )}
                    <button
                      onClick={onHedge}
                      className="px-3 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 text-xs border border-blue-500/30 rounded transition"
                    >
                      Add Hedge
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-slate-500 hover:text-slate-300 transition px-1"
            title={expanded ? 'Collapse' : 'See details'}
          >
            {expanded ? '▲' : '▼'}
          </button>
          <button
            onClick={onDismiss}
            className="text-slate-600 hover:text-slate-400 transition"
            title="Dismiss suggestion"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};

const PositionCard: React.FC<PositionCardProps> = ({ trade, onClose, loading, smartSuggestion }) => {
  const { showToast } = useToast();
  const [showLegs, setShowLegs] = React.useState(false);
  const [showAdvice, setShowAdvice] = React.useState(true);
  const [editOpen, setEditOpen] = React.useState(false);
  const [hedgeOpen, setHedgeOpen] = React.useState(false);
  const [adjustOpen, setAdjustOpen] = React.useState(false);
  const [addOpen, setAddOpen] = React.useState(false);
  const [shareOpen, setShareOpen] = React.useState(false);
  const [editTp, setEditTp] = React.useState(trade?.tp ?? '');
  const [editSl, setEditSl] = React.useState(trade?.sl ?? '');
  const [editTrailing, setEditTrailing] = React.useState(trade?.trailing_sl ?? '');
  const [editLoading, setEditLoading] = React.useState(false);

  const pnl = Number(trade?.pnl ?? trade?.unrealized_pnl ?? 0);
  const tp = trade?.tp !== null && trade?.tp !== undefined ? Number(trade.tp) : null;
  const sl = trade?.sl !== null && trade?.sl !== undefined ? Number(trade.sl) : null;
  const trailing = trade?.trailing_sl !== null && trade?.trailing_sl !== undefined ? Number(trade.trailing_sl) : null;
  const entryCredit = Number(trade?.entry_credit ?? trade?.entry_price ?? 0);
  const marginRequired = Number(trade?.margin_required ?? 0);

  const isProfitable = pnl >= 0;
  const tpHit = tp !== null ? pnl >= tp : false;
  const slHit = sl !== null ? pnl <= sl : false;
  const trailingActive = trailing !== null && trailing !== undefined;

  const openedAtRaw = trade?.created_at ?? trade?.entry_time ?? trade?.filled_at;
  const openedAtLabel = openedAtRaw ? new Date(openedAtRaw).toLocaleString() : '-';

  // If pnl is computed as (entry_credit - cost_to_close), then cost_to_close = entry_credit - pnl.
  const currentValue = entryCredit - pnl;
  // Percent metrics
  const pnlPercentPremium = entryCredit !== 0 ? (pnl / Math.abs(entryCredit)) * 100 : null;
  const pnlPercentMargin = marginRequired > 0 ? (pnl / marginRequired) * 100 : null;

  // Extract legs from ticket
  const legs = trade?.ticket?.legs || [];
  const legsMetrics = trade?.legs_metrics || [];
  const execution_result = trade?.execution_result || {};
  const mode = (execution_result && execution_result.mode) || trade?.mode || 'UNKNOWN';

  // Format mode for display
  const getModeLabel = (m: string) => {
    if (m.includes('ZERODHA_LIVE')) return 'Executed as Zerodha LIVE RUN';
    if (m.includes('ZERODHA_DRY_RUN')) return 'Executed as DRY RUN (Zerodha)';
    if (m.includes('PAPER')) return 'Executed as DRY RUN (Paper)';
    return 'Executed as DRY RUN';
  };

  const getModeColor = (m: string) => {
    if (m.includes('ZERODHA_LIVE')) return 'bg-red-500/20 text-red-300 border-red-500/30';
    if (m.includes('ZERODHA')) return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
    return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
  };

  // Show margin only for Zerodha modes
  const isZerodhaMode = mode && String(mode).toUpperCase().includes('ZERODHA');

  // Placeholder: update TP/SL/trailing for position (replace with real API call)
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEditLoading(true);
    try {
      // Real API call to update TP/SL/trailing for this position
      // @ts-ignore
      const { positionsAPI } = await import('../lib/api');
      await positionsAPI.updateTPSL(trade.intent_id, {
        tp: editTp !== '' ? Number(editTp) : undefined,
        sl: editSl !== '' ? Number(editSl) : undefined,
        trailing_sl: editTrailing !== '' ? Number(editTrailing) : undefined,
      });
      setEditOpen(false);
      // Optionally, refresh positions here (reload page or trigger parent refresh)
      window.location.reload();
    } catch (err) {
      showToast('error', 'Update Failed', 'Failed to update TP/SL/Trailing');
    } finally {
      setEditLoading(false);
    }
  };

  return (
    <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 hover:border-slate-600 transition">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          {isProfitable ? (
            <TrendingUp className="w-6 h-6 text-green-400" />
          ) : (
            <TrendingDown className="w-6 h-6 text-red-400" />
          )}
          <div>
            <p className="font-semibold text-white">{trade.strategy}</p>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-xs text-slate-400">
                {trade.underlying} • Opened: {openedAtLabel}
              </p>
              <span className={`inline-block px-2 py-0.5 rounded text-xs border ${getModeColor(mode)}`}>
                {getModeLabel(mode)}
              </span>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setEditOpen(true)}
            aria-label="Edit TP/SL/Trailing"
            title="Edit TP/SL/Trailing"
            className="text-slate-400 hover:text-blue-400 transition border border-slate-600 rounded px-2 py-1 text-xs"
          >
            Edit TP/SL
          </button>
          <button
            onClick={onClose}
            disabled={loading}
            aria-label="Close position"
            title="Close position"
            className="text-slate-400 hover:text-red-400 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* 🧠 Smart Suggestion Banner */}
      {smartSuggestion && smartSuggestion.severity !== 'NONE' && showAdvice && (
        <SmartSuggestionBanner
          suggestion={smartSuggestion}
          onDismiss={() => setShowAdvice(false)}
          onClose={onClose}
          onHedge={() => setHedgeOpen(true)}
        />
      )}

      <div className={`grid gap-4 py-3 border-t border-b border-slate-700 ${isZerodhaMode && marginRequired > 0 ? 'grid-cols-2 md:grid-cols-7' : 'grid-cols-2 md:grid-cols-6'}`}>
        <div>
          <p className="text-xs text-slate-400">Premium {isZerodhaMode ? 'Collected' : ''}</p>
          <p className="font-semibold text-white">₹{entryCredit.toLocaleString()}</p>
        </div>
        {isZerodhaMode && marginRequired > 0 && (
          <div>
            <p className="text-xs text-slate-400">Margin Blocked</p>
            <p className="font-semibold text-amber-400">₹{marginRequired.toLocaleString()}</p>
          </div>
        )}
        <div>
          <p className="text-xs text-slate-400">Current</p>
          <p className="font-semibold text-white">₹{Number.isFinite(currentValue) ? currentValue.toLocaleString() : '-'}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">P&L</p>
          <p className={`font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            ₹{Math.abs(pnl).toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">TP: {tp ?? '-'}</p>
          <p className={`font-semibold ${tpHit ? 'text-green-400 animate-pulse' : 'text-slate-300'}`}>
            {tpHit ? '✓ TP Hit' : '-'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">SL: {sl ?? '-'}</p>
          <p className={`font-semibold ${slHit ? 'text-red-400 animate-pulse' : 'text-slate-300'}`}>
            {slHit ? '✗ SL Hit' : '-'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Trailing SL: {trailingActive ? trailing : '-'}</p>
          <p className={`font-semibold ${trailingActive ? 'text-blue-400' : 'text-slate-300'}`}>
            {trailingActive ? 'Active' : '-'}
          </p>
        </div>
            {/* Edit TP/SL/Trailing Modal */}
            {editOpen && (
              <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50">
                <form onSubmit={handleEditSubmit} className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-80 space-y-4">
                  <h3 className="text-lg font-bold text-white mb-2">Edit TP / SL / Trailing</h3>
                  <div className="space-y-2">
                    <label className="block text-xs text-slate-300">Take Profit (TP)</label>
                    <input type="number" className="w-full px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm" value={editTp} onChange={e => setEditTp(e.target.value)} placeholder="e.g. 1000" />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs text-slate-300">Stop Loss (SL)</label>
                    <input type="number" className="w-full px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm" value={editSl} onChange={e => setEditSl(e.target.value)} placeholder="e.g. -1000" />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs text-slate-300">Trailing Stop</label>
                    <input type="number" className="w-full px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm" value={editTrailing} onChange={e => setEditTrailing(e.target.value)} placeholder="e.g. 500" />
                  </div>
                  <div className="flex gap-2 mt-4">
                    <button type="submit" disabled={editLoading} className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded font-semibold transition">{editLoading ? 'Saving...' : 'Save'}</button>
                    <button type="button" onClick={() => setEditOpen(false)} className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition">Cancel</button>
                  </div>
                </form>
              </div>
            )}
      </div>

      {/* Legs Section - Expandable */}
      {legs.length > 0 && (
        <div className="mt-3 border-t border-slate-700 pt-3">
          <button
            onClick={() => setShowLegs(!showLegs)}
            className="text-xs text-slate-400 hover:text-slate-300 transition flex items-center gap-2"
          >
            <span>{showLegs ? '▼' : '▶'}</span>
            <span>{legs.length} Leg{legs.length > 1 ? 's' : ''}</span>
          </button>
          
          {showLegs && (
            <div className="mt-2 space-y-1">
              {legs.map((leg: any, idx: number) => {
                const m = Array.isArray(legsMetrics) ? legsMetrics[idx] : undefined;
                const legPnl = m?.pnl_total ?? null;
                const legLtp = m?.ltp ?? null;
                const legEntry = m?.entry ?? leg.price ?? null;
                const isLegProfit = typeof legPnl === 'number' ? legPnl >= 0 : null;
                return (
                  <div key={idx} className="text-xs bg-slate-800/50 p-2 rounded flex justify-between items-center">
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded ${
                        leg.side === 'SELL' ? 'bg-red-500/20 text-red-300' : 'bg-green-500/20 text-green-300'
                      }`}>
                        {leg.side}
                      </span>
                      <span className="text-slate-300 font-mono">
                        {leg.strike} {leg.type}
                      </span>
                      {leg.symbol && (
                        <span className="text-slate-500 text-[10px]">{leg.symbol}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      {typeof legEntry === 'number' ? (
                        <span className="text-slate-400">Entry ₹{legEntry}</span>
                      ) : (
                        <span className="text-slate-600">Entry N/A</span>
                      )}
                      {typeof legLtp === 'number' && (
                        <span className="text-slate-400">LTP ₹{legLtp}</span>
                      )}
                      {typeof legPnl === 'number' ? (
                        <span className={`font-semibold ${isLegProfit ? 'text-green-400' : 'text-red-400'}`}>
                          P&L ₹{Math.abs(legPnl).toLocaleString()}
                        </span>
                      ) : (
                        <span className="text-slate-600">P&L N/A</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Position Actions */}
      <div className="mt-3 pt-3 border-t border-slate-700">
        <p className="text-xs text-slate-400 mb-2">Manage Position</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <button
            onClick={() => setHedgeOpen(true)}
            className="px-3 py-2 bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 text-xs border border-blue-500/30 rounded transition flex items-center justify-center gap-2"
          >
            <span>🛡️</span> Hedge
          </button>
          <button
            onClick={() => setAdjustOpen(true)}
            className="px-3 py-2 bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 text-xs border border-purple-500/30 rounded transition flex items-center justify-center gap-2"
          >
            <span>📊</span> Adjust
          </button>
          <button
            onClick={() => setAddOpen(true)}
            className="px-3 py-2 bg-green-600/20 hover:bg-green-600/30 text-green-300 text-xs border border-green-500/30 rounded transition flex items-center justify-center gap-2"
          >
            <span>➕</span> Add
          </button>
          <button
            onClick={() => setShareOpen(true)}
            className="px-3 py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 text-xs border border-amber-500/30 rounded transition flex items-center justify-center gap-2"
          >
            <span>📤</span> Share
          </button>
        </div>
      </div>

      {/* Hedge Position Modal */}
      {hedgeOpen && (
        <HedgeModal
          trade={trade}
          onClose={() => setHedgeOpen(false)}
          onSuccess={() => {
            setHedgeOpen(false);
            window.location.reload();
          }}
        />
      )}

      {/* Adjust Strikes Modal */}
      {adjustOpen && (
        <AdjustStrikesModal
          trade={trade}
          onClose={() => setAdjustOpen(false)}
          onSuccess={() => {
            setAdjustOpen(false);
            window.location.reload();
          }}
        />
      )}

      {/* Add to Position Modal */}
      {addOpen && (
        <AddToPositionModal
          trade={trade}
          onClose={() => setAddOpen(false)}
          onSuccess={() => {
            setAddOpen(false);
            window.location.reload();
          }}
        />
      )}

      {/* Share Strategy Modal */}
      {shareOpen && (
        <ShareStrategyModal
          trade={trade}
          onClose={() => setShareOpen(false)}
        />
      )}

      <div className="flex justify-between items-center mt-3">
        <div className="flex items-center gap-3">
          <p className={`text-sm font-medium ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
            {pnlPercentPremium === null ? '-' : `${isProfitable ? '+' : ''}${pnlPercentPremium.toFixed(2)}%`}
          </p>
          {isZerodhaMode && pnlPercentMargin !== null && (
            <p className="text-xs font-medium text-amber-400">
              ROM: {`${pnlPercentMargin >= 0 ? '+' : ''}${pnlPercentMargin.toFixed(2)}%`}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="btn-danger py-1 px-3 text-sm"
          disabled={loading}
        >
          {loading ? 'Closing...' : 'Close'}
        </button>
      </div>
    </div>
  );
};

const RiskMetric: React.FC<{ label: string; value: string; subtext?: string; status: 'good' | 'warning' | 'danger' }> = ({
  label,
  value,
  subtext,
  status,
}) => {
  const statusColor = {
    good: 'text-green-400',
    warning: 'text-orange-400',
    danger: 'text-red-400',
  }[status];

  return (
    <div className="bg-slate-900/50 p-4 rounded-lg border border-slate-700">
      <p className="text-xs text-slate-400 mb-2">{label}</p>
      <p className={`text-2xl font-bold ${statusColor}`}>{value}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  );
};

export default Positions;
