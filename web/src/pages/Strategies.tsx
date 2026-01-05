import React, { useState } from 'react';
import { AlertCircle, CheckCircle, Clock, X } from 'lucide-react';
import { strategyAPI, executionAPI } from '../lib/api';
import { useTradeStore } from '../lib/store';

const Strategies: React.FC = () => {
  const [underlying, setUnderlying] = useState('NIFTY');
  const [capital, setCapital] = useState(100000);
  const [lots, setLots] = useState(1);
  const [riskMode, setRiskMode] = useState('BALANCED');
  const [loading, setLoading] = useState(false);
  const [strategyResult, setStrategyResult] = useState<any>(null);
  const { addTrade } = useTradeStore();

  const underlyings = ['NIFTY', 'BANKNIFTY', 'FINNIFTY'];
  const riskModes = ['Conservative', 'Balanced', 'Aggressive'];

  const handleRunStrategy = async () => {
    setLoading(true);
    try {
      const payload = {
        underlying,
        interval: '15minute',
        use_ml: false,
        min_confidence: 75,
        risk_mode: riskMode,
        lots,
        capital,
      };

      const response = await strategyAPI.runStrategy(payload);
      setStrategyResult(response.data);
    } catch (error) {
      console.error('Strategy error:', error);
      alert('Failed to run strategy');
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!strategyResult || !strategyResult.run_id) return;

    try {
      // Create intent
      const intentRes = await executionAPI.createIntent(strategyResult.run_id);
      const intent = intentRes.data;

      // Confirm intent
      await executionAPI.confirmIntent(intent.intent_id);

      // Execute
      const execRes = await executionAPI.executeIntent(
        intent.intent_id,
        `exec_${Date.now()}`
      );

      // Add to store
      addTrade({
        id: intent.id,
        strategy: strategyResult.strategy,
        underlying,
        status: 'EXECUTED',
        entry_price: strategyResult.ticket?.legs?.[0]?.price || 0,
        current_price: strategyResult.ticket?.legs?.[0]?.price || 0,
        pnl: 0,
        pnl_percent: 0,
        tp: intent.tp || 2000,
        sl: intent.sl || -2000,
        entry_time: new Date().toISOString(),
      });

      setStrategyResult(null);
      alert('Trade executed successfully!');
    } catch (error) {
      console.error('Execution error:', error);
      alert('Failed to execute trade');
    }
  };

  return (
    <div className="space-y-6">
      {/* Strategy Generator */}
      <div className="card-glass p-6">
        <h2 className="text-2xl font-bold mb-6 text-white">Strategy Generator</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {/* Underlying */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Underlying
            </label>
            <select
              value={underlying}
              onChange={(e) => setUnderlying(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            >
              {underlyings.map((u) => (
                <option key={u} value={u}>
                  {u}
                </option>
              ))}
            </select>
          </div>

          {/* Capital */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Capital (₹)
            </label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(parseInt(e.target.value))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Lots */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Lots
            </label>
            <input
              type="number"
              value={lots}
              onChange={(e) => setLots(parseInt(e.target.value))}
              min="1"
              max="10"
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Risk Mode */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Risk Mode
            </label>
            <select
              value={riskMode}
              onChange={(e) => setRiskMode(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
            >
              {riskModes.map((mode) => (
                <option key={mode} value={mode}>
                  {mode}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={handleRunStrategy}
          disabled={loading}
          className="btn-primary w-full py-3"
        >
          {loading ? 'Analyzing...' : 'Run Strategy Analysis'}
        </button>
      </div>

      {/* Strategy Result */}
      {strategyResult && (
        <div className="card-glass p-6">
          <div className="flex items-start justify-between mb-6">
            <h3 className="text-xl font-bold text-white">Strategy Result</h3>
            <button
              onClick={() => setStrategyResult(null)}
              className="text-slate-400 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Status */}
            <div>
              <div className="flex items-center gap-3 mb-4">
                {strategyResult.approved ? (
                  <>
                    <CheckCircle className="w-6 h-6 text-green-400" />
                    <span className="text-lg font-bold text-green-400">Approved</span>
                  </>
                ) : (
                  <>
                    <AlertCircle className="w-6 h-6 text-red-400" />
                    <span className="text-lg font-bold text-red-400">Rejected</span>
                  </>
                )}
              </div>
              <p className="text-slate-300 mb-6">{strategyResult.reason}</p>

              {strategyResult.approved && (
                <button
                  onClick={handleExecute}
                  className="btn-primary w-full py-3"
                >
                  Execute Trade
                </button>
              )}
            </div>

            {/* Details */}
            <div className="space-y-3">
              <DetailRow label="Strategy" value={strategyResult.strategy} />
              <DetailRow label="Signal" value={strategyResult.signal?.signal || 'N/A'} />
              <DetailRow label="Confidence" value={`${strategyResult.signal?.confidence || 0}%`} />
              <DetailRow label="IV Regime" value={strategyResult.signal?.iv_regime || 'N/A'} />
              {strategyResult.risk_metrics && (
                <>
                  <DetailRow label="Max Risk %" value={`${strategyResult.risk_metrics.risk_pct || 0}%`} />
                  <DetailRow label="Max Loss" value={`₹${strategyResult.risk_metrics.max_loss || 0}`} />
                </>
              )}
            </div>
          </div>

          {/* Ticket Info */}
          {strategyResult.ticket && (
            <div className="mt-6 pt-6 border-t border-slate-700">
              <h4 className="font-semibold text-white mb-4">Trade Ticket</h4>
              <TicketPreview ticket={strategyResult.ticket} />
            </div>
          )}
        </div>
      )}

      {/* Coming Soon Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ComingSoon title="Backtester" description="Test strategies on historical data" />
        <ComingSoon title="Strategy Builder" description="Create custom strategies visually" />
      </div>
    </div>
  );
};

const DetailRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex justify-between items-center">
    <span className="text-slate-400">{label}</span>
    <span className="font-semibold text-white">{value}</span>
  </div>
);

const TicketPreview: React.FC<{ ticket: any }> = ({ ticket }) => (
  <div className="bg-slate-900/50 rounded-lg p-4 space-y-2">
    <div className="grid grid-cols-2 gap-4">
      <DetailRow label="Lot Size" value={ticket.lot_size?.toString() || '65'} />
      <DetailRow label="Lots" value={ticket.lots?.toString() || '1'} />
      <DetailRow label="Max Width" value={`${ticket.max_width || '100'} pts`} />
      <DetailRow label="Strategy" value={ticket.strategy || 'N/A'} />
    </div>
    {ticket.legs && ticket.legs.length > 0 && (
      <div className="mt-4 pt-4 border-t border-slate-700">
        <p className="text-sm font-semibold text-slate-300 mb-2">Legs:</p>
        {ticket.legs.map((leg: any, idx: number) => (
          <div key={idx} className="text-xs text-slate-400 py-1">
            {leg.side} {leg.type} {leg.strike}
          </div>
        ))}
      </div>
    )}
  </div>
);

const ComingSoon: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="card-glass p-6 opacity-50">
    <div className="flex items-center justify-center h-32">
      <div className="text-center">
        <Clock className="w-8 h-8 text-slate-400 mx-auto mb-2" />
        <h4 className="font-semibold text-slate-300">{title}</h4>
        <p className="text-sm text-slate-400 mt-1">{description}</p>
      </div>
    </div>
  </div>
);

export default Strategies;
