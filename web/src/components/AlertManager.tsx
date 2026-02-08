import React, { useState, useEffect } from 'react';
import { Bell, X, Plus, TrendingUp, TrendingDown } from 'lucide-react';
import { alertsAPI, type AlertOperator, type CreateAlertRequest } from '../lib/alertsAPI';

interface AlertManagerProps {
  symbol: string;
  currentPrice: number;
  onClose?: () => void;
  onAlertCreated?: () => void;
}

const AlertManager: React.FC<AlertManagerProps> = ({
  symbol,
  currentPrice,
  onClose,
  onAlertCreated,
}) => {
  const [operator, setOperator] = useState<AlertOperator>('above');
  const [targetPrice, setTargetPrice] = useState(currentPrice.toFixed(2));
  const [isRecurring, setIsRecurring] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Update target price when currentPrice changes (only if user hasn't modified it)
  useEffect(() => {
    if (!targetPrice || parseFloat(targetPrice) === 0) {
      setTargetPrice(currentPrice.toFixed(2));
    }
  }, [currentPrice]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    const price = parseFloat(targetPrice);
    if (isNaN(price) || price <= 0) {
      setError('Please enter a valid price');
      return;
    }

    setLoading(true);
    try {
      const request: CreateAlertRequest = {
        ticker: symbol.toUpperCase(),
        alert_type: 'PRICE',
        condition: {
          operator,
          price,
        },
        is_enabled: true,
        is_recurring: isRecurring,
      };

      await alertsAPI.create(request);
      setSuccess(true);
      
      // Reset form
      setTimeout(() => {
        setSuccess(false);
        setTargetPrice(currentPrice.toFixed(2));
        onAlertCreated?.();
      }, 1500);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create alert');
    } finally {
      setLoading(false);
    }
  };

  const getOperatorLabel = (op: AlertOperator) => {
    const labels = {
      above: 'Above',
      below: 'Below',
      above_or_equal: 'Above or Equal',
      below_or_equal: 'Below or Equal',
      equal: 'Equals',
    };
    return labels[op];
  };

  const getOperatorIcon = (op: AlertOperator) => {
    if (op === 'above' || op === 'above_or_equal') {
      return <TrendingUp className="w-4 h-4" />;
    }
    if (op === 'below' || op === 'below_or_equal') {
      return <TrendingDown className="w-4 h-4" />;
    }
    return <Bell className="w-4 h-4" />;
  };

  const percentDiff = ((parseFloat(targetPrice) - currentPrice) / currentPrice) * 100;

  return (
    <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700/50 rounded-lg p-6 w-full max-w-md">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <Bell className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Create Price Alert</h3>
            <p className="text-sm text-slate-400">{symbol}</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-800/50 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        )}
      </div>

      <div className="mb-4 p-3 bg-slate-800/50 rounded-lg border border-slate-700/30">
        <div className="text-sm text-slate-400 mb-1">Current Price</div>
        <div className="text-2xl font-bold text-white">₹{currentPrice.toFixed(2)}</div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Operator Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Alert When Price
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(['above', 'below', 'above_or_equal', 'below_or_equal'] as AlertOperator[]).map((op) => (
              <button
                key={op}
                type="button"
                onClick={() => setOperator(op)}
                className={`
                  flex items-center justify-center gap-2 px-4 py-3 rounded-lg border transition-all
                  ${
                    operator === op
                      ? 'bg-blue-500/20 border-blue-500/50 text-blue-400'
                      : 'bg-slate-800/50 border-slate-700/30 text-slate-400 hover:bg-slate-800 hover:border-slate-600'
                  }
                `}
              >
                {getOperatorIcon(op)}
                <span className="text-sm font-medium">{getOperatorLabel(op)}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Target Price Input */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Target Price
          </label>
          <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">₹</span>
            <input
              type="number"
              step="0.05"
              value={targetPrice}
              onChange={(e) => setTargetPrice(e.target.value)}
              className="w-full pl-8 pr-4 py-3 bg-slate-800/50 border border-slate-700/30 rounded-lg text-white focus:border-blue-500/50 focus:ring-2 focus:ring-blue-500/20 transition-all"
              placeholder="Enter target price"
              required
            />
          </div>
          {!isNaN(percentDiff) && Math.abs(percentDiff) > 0.01 && (
            <div className={`mt-2 text-sm ${percentDiff > 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {percentDiff > 0 ? '+' : ''}{percentDiff.toFixed(2)}% from current
            </div>
          )}
        </div>

        {/* Recurring Option */}
        <div className="flex items-center justify-between p-4 bg-slate-800/30 rounded-lg border border-slate-700/30">
          <div>
            <div className="text-sm font-medium text-slate-300">Recurring Alert</div>
            <div className="text-xs text-slate-500 mt-1">
              Keep alert active after triggering
            </div>
          </div>
          <button
            type="button"
            onClick={() => setIsRecurring(!isRecurring)}
            className={`
              relative w-11 h-6 rounded-full transition-colors
              ${isRecurring ? 'bg-blue-500' : 'bg-slate-700'}
            `}
          >
            <div
              className={`
                absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform
                ${isRecurring ? 'translate-x-5' : 'translate-x-0'}
              `}
            />
          </button>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {success && (
          <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg">
            <p className="text-sm text-emerald-400">✓ Alert created successfully!</p>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full px-6 py-3 bg-blue-500 hover:bg-blue-600 disabled:bg-slate-700 disabled:text-slate-500 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Creating...
            </>
          ) : (
            <>
              <Plus className="w-4 h-4" />
              Create Alert
            </>
          )}
        </button>
      </form>

      <div className="mt-4 p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
        <p className="text-xs text-slate-400 leading-relaxed">
          💡 <strong>Tip:</strong> Alerts are checked automatically every few minutes. 
          You'll receive a notification when your price target is reached.
        </p>
      </div>
    </div>
  );
};

export default AlertManager;
