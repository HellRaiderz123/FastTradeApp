import React, { useState, useEffect } from 'react';
import {
  Bell,
  BellOff,
  BellRing,
  Trash2,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  X,
} from 'lucide-react';
import { alertsAPI, type Alert, type AlertOperator } from '../lib/alertsAPI';

interface AlertListProps {
  ticker?: string;
  onClose?: () => void;
  refreshTrigger?: number;
}

const AlertList: React.FC<AlertListProps> = ({ ticker, onClose, refreshTrigger }) => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await alertsAPI.list(ticker);
      setAlerts(response.alerts);
    } catch (err: any) {
      setError('Failed to load alerts');
      console.error('Error fetching alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [ticker, refreshTrigger]);

  const handleToggle = async (alert: Alert) => {
    setActionLoading(alert.id);
    try {
      if (alert.is_enabled) {
        await alertsAPI.disable(alert.id);
      } else {
        await alertsAPI.enable(alert.id);
      }
      await fetchAlerts();
    } catch (err) {
      console.error('Failed to toggle alert:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (alertId: number) => {
    if (!confirm('Are you sure you want to delete this alert?')) return;

    setActionLoading(alertId);
    try {
      await alertsAPI.delete(alertId);
      await fetchAlerts();
    } catch (err) {
      console.error('Failed to delete alert:', err);
    } finally {
      setActionLoading(null);
    }
  };

  const getOperatorDisplay = (operator: AlertOperator) => {
    const displays = {
      above: { label: '>', icon: TrendingUp, color: 'text-emerald-400' },
      below: { label: '<', icon: TrendingDown, color: 'text-red-400' },
      above_or_equal: { label: '≥', icon: TrendingUp, color: 'text-emerald-400' },
      below_or_equal: { label: '≤', icon: TrendingDown, color: 'text-red-400' },
      equal: { label: '=', icon: Bell, color: 'text-blue-400' },
    };
    return displays[operator] || displays.equal;
  };

  const formatDateTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700/50 rounded-lg p-6">
        <div className="flex items-center justify-center py-8">
          <RefreshCw className="w-6 h-6 text-blue-400 animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/95 backdrop-blur-sm border border-slate-700/50 rounded-lg p-6 w-full max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/10 rounded-lg">
            <Bell className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Active Alerts</h3>
            <p className="text-sm text-slate-400">
              {ticker ? `For ${ticker}` : 'All symbols'} · {alerts.length} total
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchAlerts}
            className="p-2 hover:bg-slate-800/50 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-5 h-5 text-slate-400" />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-slate-800/50 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-slate-400" />
            </button>
          )}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="mb-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Alerts List */}
      {alerts.length === 0 ? (
        <div className="py-12 text-center">
          <BellOff className="w-12 h-12 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400">No alerts configured</p>
          <p className="text-sm text-slate-500 mt-1">Create an alert to get started</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {alerts.map((alert) => {
            const operatorInfo = getOperatorDisplay(alert.condition.operator);
            const Icon = operatorInfo.icon;
            const isActionLoading = actionLoading === alert.id;

            return (
              <div
                key={alert.id}
                className={`
                  p-4 rounded-lg border transition-all
                  ${
                    alert.is_enabled
                      ? 'bg-slate-800/50 border-slate-700/30 hover:bg-slate-800'
                      : 'bg-slate-800/20 border-slate-700/20 opacity-60'
                  }
                `}
              >
                <div className="flex items-start justify-between gap-4">
                  {/* Alert Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="font-semibold text-white">{alert.ticker}</span>
                      <Icon className={`w-4 h-4 ${operatorInfo.color}`} />
                      <span className="text-slate-400 text-sm">
                        {operatorInfo.label} ₹{alert.condition.price.toFixed(2)}
                      </span>
                      {alert.is_recurring && (
                        <span className="px-2 py-0.5 bg-blue-500/10 border border-blue-500/30 rounded text-xs text-blue-400">
                          Recurring
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <div className="flex items-center gap-1">
                        <BellRing className="w-3 h-3" />
                        Triggered {alert.trigger_count}×
                      </div>
                      {alert.last_triggered_at && (
                        <div>Last: {formatDateTime(alert.last_triggered_at)}</div>
                      )}
                      <div>Created: {formatDateTime(alert.created_at)}</div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleToggle(alert)}
                      disabled={isActionLoading}
                      className={`
                        p-2 rounded-lg transition-colors
                        ${
                          alert.is_enabled
                            ? 'hover:bg-slate-700/50 text-blue-400'
                            : 'hover:bg-slate-700/30 text-slate-500'
                        }
                      `}
                      title={alert.is_enabled ? 'Disable alert' : 'Enable alert'}
                    >
                      {isActionLoading ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : alert.is_enabled ? (
                        <Bell className="w-4 h-4" />
                      ) : (
                        <BellOff className="w-4 h-4" />
                      )}
                    </button>

                    <button
                      onClick={() => handleDelete(alert.id)}
                      disabled={isActionLoading}
                      className="p-2 hover:bg-red-500/10 text-slate-500 hover:text-red-400 rounded-lg transition-colors"
                      title="Delete alert"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Footer Info */}
      <div className="mt-4 p-3 bg-slate-800/30 rounded-lg border border-slate-700/30">
        <p className="text-xs text-slate-400">
          💡 Alerts are evaluated automatically. Disable recurring alerts after they trigger once.
        </p>
      </div>
    </div>
  );
};

export default AlertList;
