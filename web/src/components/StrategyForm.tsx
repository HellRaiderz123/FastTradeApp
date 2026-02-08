import React, { useState, useEffect } from 'react';
import { X, Save, Plus, Trash2 } from 'lucide-react';
import { strategyAPI } from '../lib/api';

interface Leg {
  id?: string;
  type: 'BUY' | 'SELL';
  option_type: 'CE' | 'PE';
  strike: number;
  strike_type?: 'ABSOLUTE' | 'ATM_OFFSET' | 'PCT_OFFSET';
  strike_offset?: number;
  quantity: number;
  premium?: number;
}

interface StrategyFormProps {
  onClose: () => void;
  onSuccess: () => void;
  initialData?: any;
}

export const StrategyForm: React.FC<StrategyFormProps> = ({
  onClose,
  onSuccess,
  initialData,
}) => {
  const [loading, setLoading] = useState(false);
  const defaultParameters = {
    risk_mode: 'CONSERVATIVE',
    lots: 1,
    capital: 100000,
    min_confidence: 75,
    tp_pct: 0,
    sl_pct: 0,
    trailing_sl_pct: 0,
    entry_time: '09:20',
    exit_time: '15:20',
  };
  const [formData, setFormData] = useState({
    name: initialData?.name || '',
    description: initialData?.description || '',
    strategy_type: initialData?.strategy_type || 'option_spread_15m',
    underlying: initialData?.underlying || 'NIFTY',
    parameters: {
      ...defaultParameters,
      ...(initialData?.parameters || {}),
    },
  });

  // Extract legs from parameters if they exist
  const [legs, setLegs] = useState<Leg[]>(() => {
    const existingLegs = initialData?.parameters?.legs || [];
    return existingLegs.map((leg: any, idx: number) => ({
      id: `leg-${Date.now()}-${idx}`,
      type: leg.type || 'BUY',
      option_type: leg.option_type || 'CE',
      strike: leg.strike || 0,
      strike_type: leg.strike_type || 'ABSOLUTE',
      strike_offset: leg.strike_offset || 0,
      quantity: leg.quantity || 1,
      premium: leg.premium || 0,
    }));
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const addLeg = () => {
    setLegs([
      ...legs,
      {
        id: `leg-${Date.now()}`,
        type: 'BUY',
        option_type: 'CE',
        strike: 0,
        strike_type: 'ABSOLUTE',
        strike_offset: 0,
        quantity: 1,
        premium: 0,
      },
    ]);
  };

  const removeLeg = (id: string) => {
    setLegs(legs.filter((leg) => leg.id !== id));
  };

  const updateLeg = (id: string, field: keyof Leg, value: any) => {
    setLegs(
      legs.map((leg) =>
        leg.id === id ? { ...leg, [field]: value } : leg
      )
    );
  };

  const validate = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Strategy name is required';
    }

    if (!formData.description.trim()) {
      newErrors.description = 'Description is required';
    }

    if (!formData.underlying) {
      newErrors.underlying = 'Underlying is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    setLoading(true);
    try {
      // Include legs in parameters if they exist
      const dataToSubmit = {
        ...formData,
        parameters: {
          ...formData.parameters,
          ...(legs.length > 0 && {
            legs: legs.map(leg => ({
              type: leg.type,
              option_type: leg.option_type,
              strike: Number(leg.strike) || 0,
              strike_type: leg.strike_type || 'ABSOLUTE',
              strike_offset: Number(leg.strike_offset) || 0,
              quantity: Number(leg.quantity) || 1,
              premium: Number(leg.premium) || 0,
            })),
          }),
        },
      };

      if (initialData?.id) {
        await strategyAPI.updateStrategy(initialData.id, dataToSubmit);
      } else {
        await strategyAPI.createStrategy(dataToSubmit);
      }

      onSuccess();
      onClose();
    } catch (error) {
      console.error('Form submission failed:', error);
      alert('Failed to save strategy');
    } finally {
      setLoading(false);
    }
  };

  const underlyings = [
    { value: 'NIFTY', label: 'NIFTY50' },
    { value: 'BANKNIFTY', label: 'BANKNIFTY' },
    { value: 'FINNIFTY', label: 'FINNIFTY' },
  ];
  const riskModes = ['CONSERVATIVE', 'BALANCED', 'AGGRESSIVE'];

  return (
    <>
      {/* Header */}
      <div className="flex justify-between items-center p-6 border-b border-slate-700">
        <h2 className="text-2xl font-bold text-white">
          {initialData ? 'Edit Strategy' : 'Create New Strategy'}
        </h2>
        <button
          onClick={onClose}
          className="p-1 hover:bg-slate-800 rounded text-slate-300"
          title="Close"
          aria-label="Close"
        >
          <X size={24} />
        </button>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="p-6 space-y-4 flex-1 overflow-y-auto">
          {/* Name */}
          <div>
            <label htmlFor="strategy-name" className="block text-sm font-medium mb-1 text-slate-200">
              Strategy Name
            </label>
            <input
              id="strategy-name"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="e.g., NIFTY Conservative"
            />
            {errors.name && <p className="text-red-400 text-sm mt-1">{errors.name}</p>}
          </div>

          {/* Description */}
          <div>
            <label htmlFor="strategy-description" className="block text-sm font-medium mb-1 text-slate-200">
              Description
            </label>
            <textarea
              id="strategy-description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={3}
              className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="Strategy description..."
            />
            {errors.description && (
              <p className="text-red-400 text-sm mt-1">{errors.description}</p>
            )}
          </div>

          {/* Grid Row 1 */}
          <div className="grid grid-cols-2 gap-4">
            {/* Underlying */}
            <div>
              <label htmlFor="strategy-underlying" className="block text-sm font-medium mb-1 text-slate-200">
                Underlying
              </label>
              <select
                id="strategy-underlying"
                aria-label="Underlying"
                value={formData.underlying}
                onChange={(e) => setFormData({ ...formData, underlying: e.target.value })}
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                {underlyings.map((u) => (
                  <option key={u.value} value={u.value}>
                    {u.label}
                  </option>
                ))}
              </select>
              {errors.underlying && (
                <p className="text-red-400 text-sm mt-1">{errors.underlying}</p>
              )}
            </div>

            {/* Strategy Type */}
            <div>
              <label htmlFor="strategy-type" className="block text-sm font-medium mb-1 text-slate-200">
                Strategy Type
              </label>
              <select
                id="strategy-type"
                aria-label="Strategy type"
                value={formData.strategy_type}
                onChange={(e) =>
                  setFormData({ ...formData, strategy_type: e.target.value })
                }
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="option_spread_15m">Option Spread 15m</option>
              </select>
            </div>
          </div>

          {/* Parameters Section */}
          <div className="border-t border-slate-700 pt-4">
            <h3 className="font-semibold mb-3 text-slate-200">Strategy Parameters</h3>

            <div className="grid grid-cols-2 gap-4">
              {/* Risk Mode */}
              <div>
                <label htmlFor="strategy-risk-mode" className="block text-sm font-medium mb-1 text-slate-200">
                  Risk Mode
                </label>
                <select
                  id="strategy-risk-mode"
                  aria-label="Risk mode"
                  value={formData.parameters.risk_mode}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        risk_mode: e.target.value,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  {riskModes.map((rm) => (
                    <option key={rm} value={rm}>
                      {rm}
                    </option>
                  ))}
                </select>
              </div>

              {/* Lots */}
              <div>
                <label htmlFor="strategy-lots" className="block text-sm font-medium mb-1 text-slate-200">
                  Lots
                </label>
                <input
                  id="strategy-lots"
                  aria-label="Lots"
                  type="number"
                  min="1"
                  max="10"
                  value={formData.parameters.lots}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        lots: parseInt(e.target.value) || 1,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Capital */}
              <div>
                <label htmlFor="strategy-capital" className="block text-sm font-medium mb-1 text-slate-200">
                  Capital
                </label>
                <input
                  id="strategy-capital"
                  aria-label="Capital"
                  type="number"
                  min="50000"
                  step="10000"
                  value={formData.parameters.capital}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        capital: parseInt(e.target.value) || 100000,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Min Confidence */}
              <div>
                <label htmlFor="strategy-min-confidence" className="block text-sm font-medium mb-1 text-slate-200">
                  Min Confidence (%)
                </label>
                <input
                  id="strategy-min-confidence"
                  aria-label="Min confidence"
                  type="number"
                  min="50"
                  max="95"
                  value={formData.parameters.min_confidence}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        min_confidence: parseInt(e.target.value) || 75,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Take Profit */}
              <div>
                <label htmlFor="strategy-tp" className="block text-sm font-medium mb-1 text-slate-200">
                  Profit Target (%)
                </label>
                <input
                  id="strategy-tp"
                  aria-label="Profit target percent"
                  type="number"
                  min="0"
                  max="100"
                  step="1"
                  value={formData.parameters.tp_pct}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        tp_pct: Number(e.target.value) || 0,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Stop Loss */}
              <div>
                <label htmlFor="strategy-sl" className="block text-sm font-medium mb-1 text-slate-200">
                  Stop Loss (%)
                </label>
                <input
                  id="strategy-sl"
                  aria-label="Stop loss percent"
                  type="number"
                  min="0"
                  max="300"
                  step="1"
                  value={formData.parameters.sl_pct}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        sl_pct: Number(e.target.value) || 0,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Trailing Stop Loss */}
              <div>
                <label htmlFor="strategy-tsl" className="block text-sm font-medium mb-1 text-slate-200">
                  Trailing SL (%)
                </label>
                <input
                  id="strategy-tsl"
                  aria-label="Trailing stop loss percent"
                  type="number"
                  min="0"
                  max="300"
                  step="1"
                  value={formData.parameters.trailing_sl_pct}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        trailing_sl_pct: Number(e.target.value) || 0,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Entry Time */}
              <div>
                <label htmlFor="strategy-entry-time" className="block text-sm font-medium mb-1 text-slate-200">
                  Entry Time (HH:MM)
                </label>
                <input
                  id="strategy-entry-time"
                  aria-label="Entry time"
                  type="time"
                  value={formData.parameters.entry_time}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        entry_time: e.target.value,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Exit Time */}
              <div>
                <label htmlFor="strategy-exit-time" className="block text-sm font-medium mb-1 text-slate-200">
                  Exit Time (HH:MM)
                </label>
                <input
                  id="strategy-exit-time"
                  aria-label="Exit time"
                  type="time"
                  value={formData.parameters.exit_time}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      parameters: {
                        ...formData.parameters,
                        exit_time: e.target.value,
                      },
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
          </div>

          {/* Legs Section (for custom strategies) */}
          <div className="border-t border-slate-700 pt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="font-semibold text-slate-200">Option Legs</h3>
              <button
                type="button"
                onClick={addLeg}
                className="flex items-center space-x-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded transition-colors"
                title="Add new leg"
              >
                <Plus size={14} />
                <span>Add Leg</span>
              </button>
            </div>

            {legs.length === 0 ? (
              <div className="text-slate-400 text-sm bg-slate-900 border border-slate-700 rounded p-4 text-center">
                No legs defined. Click "Add Leg" to create option legs for this strategy.
              </div>
            ) : (
              <div className="space-y-3">
                {legs.map((leg, idx) => (
                  <div
                    key={leg.id}
                    className="bg-slate-900 border border-slate-700 rounded p-3 space-y-3"
                  >
                    {/* Header */}
                    <div className="flex items-center justify-between">
                      <div className="text-sm font-semibold text-slate-200">
                        Leg {idx + 1}
                      </div>
                      <button
                        type="button"
                        onClick={() => removeLeg(leg.id!)}
                        className="text-red-400 hover:text-red-300 transition-colors"
                        title="Remove leg"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>

                    {/* Leg Fields */}
                    <div className="grid grid-cols-2 gap-3">
                      {/* Side (BUY/SELL) */}
                      <div>
                        <label className="block text-xs font-medium mb-1 text-slate-300">
                          Side
                        </label>
                        <select
                          value={leg.type}
                          onChange={(e) =>
                            updateLeg(leg.id!, 'type', e.target.value)
                          }
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                          <option value="BUY">BUY</option>
                          <option value="SELL">SELL</option>
                        </select>
                      </div>

                      {/* Option Type (CE/PE) */}
                      <div>
                        <label className="block text-xs font-medium mb-1 text-slate-300">
                          Type
                        </label>
                        <select
                          value={leg.option_type}
                          onChange={(e) =>
                            updateLeg(leg.id!, 'option_type', e.target.value)
                          }
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                        >
                          <option value="CE">CE (Call)</option>
                          <option value="PE">PE (Put)</option>
                        </select>
                      </div>

                      {/* Strike */}
                      <div>
                        <label className="block text-xs font-medium mb-1 text-slate-300">
                          Strike
                        </label>
                        <input
                          type="number"
                          value={leg.strike}
                          onChange={(e) =>
                            updateLeg(leg.id!, 'strike', Number(e.target.value))
                          }
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="e.g., 48000"
                        />
                      </div>

                      {/* Quantity */}
                      <div>
                        <label className="block text-xs font-medium mb-1 text-slate-300">
                          Quantity
                        </label>
                        <input
                          type="number"
                          min="1"
                          value={leg.quantity}
                          onChange={(e) =>
                            updateLeg(leg.id!, 'quantity', Number(e.target.value))
                          }
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="Lots"
                        />
                      </div>

                      {/* Premium (Optional) */}
                      <div>
                        <label className="block text-xs font-medium mb-1 text-slate-300">
                          Premium (₹)
                        </label>
                        <input
                          type="number"
                          step="0.01"
                          value={leg.premium || 0}
                          onChange={(e) =>
                            updateLeg(leg.id!, 'premium', Number(e.target.value))
                          }
                          className="w-full px-2 py-1.5 bg-slate-800 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
                          placeholder="Optional"
                        />
                      </div>

                      {/* Display Summary */}
                      <div className="col-span-2 text-xs text-slate-400 bg-slate-800 px-2 py-1.5 rounded">
                        <span className={leg.type === 'BUY' ? 'text-green-400' : 'text-red-400'}>
                          {leg.type}
                        </span>
                        {' '}{leg.quantity}x {leg.strike} {leg.option_type}
                        {leg.premium > 0 && ` @ ₹${leg.premium.toFixed(2)}`}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {legs.length > 0 && (
              <div className="mt-2 text-xs text-slate-400">
                💡 Tip: Use Strategy Builder for visual leg creation with Greeks calculation
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end space-x-3 pt-4 border-t border-slate-700">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-slate-600 rounded text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={loading}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              <Save size={16} />
              <span>{loading ? 'Saving...' : 'Save Strategy'}</span>
            </button>
          </div>
        </form>
    </>
  );
};

export default StrategyForm;
