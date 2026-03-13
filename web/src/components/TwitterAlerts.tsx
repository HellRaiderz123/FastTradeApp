import React, { useEffect, useState, useRef } from 'react';
import { Twitter, AlertTriangle, TrendingUp, TrendingDown, Target, X } from 'lucide-react';
import { twitterAPI } from '../lib/api';
import { useToast } from './Toast';

interface TwitterAlert {
  id: number;
  tweet_id: string;
  symbol: string;
  alert_type: string;
  title: string;
  message: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  username: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  engagement_score: number;
  read: boolean;
  created_at: string;
}

const TwitterAlertsMonitor: React.FC = () => {
  const [alerts, setAlerts] = useState<TwitterAlert[]>([]);
  const { showToast } = useToast();
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const lastAlertIdRef = useRef<number>(0);
  const hasInitializedRef = useRef<boolean>(false);

  useEffect(() => {
    // Initial fetch
    fetchAlerts();

    // Poll for new alerts every 30 seconds
    pollingInterval.current = setInterval(fetchAlerts, 30000);

    return () => {
      if (pollingInterval.current) {
        clearInterval(pollingInterval.current);
      }
    };
  }, []);

  const fetchAlerts = async () => {
    try {
      const response = await twitterAPI.getAlerts(true, 20); // Unread only
      const newAlerts: TwitterAlert[] = response.data.alerts || [];

      const newestAlertId = newAlerts.length > 0 ? Math.max(...newAlerts.map(a => a.id)) : lastAlertIdRef.current;

      if (!hasInitializedRef.current) {
        lastAlertIdRef.current = newestAlertId;
        hasInitializedRef.current = true;
        setAlerts(newAlerts);
        return;
      }

      // Check for new high-impact alerts
      const unseenAlerts = newAlerts.filter(alert => alert.id > lastAlertIdRef.current);

      if (unseenAlerts.length > 0) {
        // Show toast notifications for new alerts
        unseenAlerts.forEach(alert => {
          if (alert.severity === 'critical' || alert.severity === 'high') {
            const toastType = alert.sentiment === 'bullish' ? 'success' : 
                            alert.sentiment === 'bearish' ? 'warning' : 'info';
            
            showToast(
              toastType,
              `🐦 ${alert.symbol}: ${alert.sentiment.toUpperCase()}`,
              `@${alert.username}: ${alert.message.substring(0, 100)}...`,
              10000 // 10 seconds
            );
          }
        });

        // Update last alert ID
        lastAlertIdRef.current = newestAlertId;
      }

      if (newAlerts.length > 0 && newestAlertId > lastAlertIdRef.current) {
        lastAlertIdRef.current = newestAlertId;
      }

      setAlerts(newAlerts);
    } catch (err) {
      // Silently fail if Twitter API not configured
      console.debug('Twitter alerts not available:', err);
    }
  };

  const markAsRead = async (alertId: number) => {
    try {
      await twitterAPI.markAlertRead(alertId);
      setAlerts(prev => prev.filter(a => a.id !== alertId));
    } catch (err) {
      console.error('Failed to mark alert as read:', err);
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'bearish': return <TrendingDown className="w-4 h-4 text-red-400" />;
      default: return <Target className="w-4 h-4 text-slate-400" />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'border-red-500 bg-red-900/20';
      case 'high': return 'border-orange-500 bg-orange-900/20';
      case 'medium': return 'border-yellow-500 bg-yellow-900/20';
      default: return 'border-slate-600 bg-slate-800';
    }
  };

  // This component runs silently in the background
  // It doesn't render any UI - it just shows toast notifications
  return null;
};

export default TwitterAlertsMonitor;

// Optional: Standalone alerts panel component for displaying alerts in a sidebar
export const TwitterAlertsPanel: React.FC = () => {
  const [alerts, setAlerts] = useState<TwitterAlert[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 60000); // Update every minute
    return () => clearInterval(interval);
  }, []);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const response = await twitterAPI.getAlerts(true, 10);
      setAlerts(response.data.alerts || []);
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    } finally {
      setLoading(false);
    }
  };

  const markAsRead = async (alertId: number) => {
    try {
      await twitterAPI.markAlertRead(alertId);
      setAlerts(prev => prev.filter(a => a.id !== alertId));
    } catch (err) {
      console.error('Failed to mark alert as read:', err);
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'bearish': return <TrendingDown className="w-4 h-4 text-red-400" />;
      default: return <Target className="w-4 h-4 text-slate-400" />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'border-red-500 bg-red-900/20';
      case 'high': return 'border-orange-500 bg-orange-900/20';
      case 'medium': return 'border-yellow-500 bg-yellow-900/20';
      default: return 'border-slate-600 bg-slate-800';
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  if (loading) {
    return (
      <div className="bg-slate-900 rounded-lg border border-slate-800 p-4">
        <div className="flex items-center gap-2 mb-4">
          <Twitter className="w-5 h-5 text-blue-400" />
          <h3 className="text-lg font-semibold text-white">High Impact Alerts</h3>
        </div>
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500 mx-auto"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 rounded-lg border border-slate-800 p-4">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="w-5 h-5 text-orange-400" />
        <h3 className="text-lg font-semibold text-white">High Impact Alerts</h3>
        {alerts.length > 0 && (
          <span className="ml-auto bg-orange-500 text-white text-xs px-2 py-1 rounded-full">
            {alerts.length}
          </span>
        )}
      </div>

      {alerts.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-slate-400">No active alerts</p>
          <p className="text-xs text-slate-500 mt-1">High-impact tweets will appear here</p>
        </div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {alerts.map(alert => (
            <div 
              key={alert.id}
              className={`p-3 rounded-lg border ${getSeverityColor(alert.severity)} relative`}
            >
              <button
                onClick={() => markAsRead(alert.id)}
                className="absolute top-2 right-2 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="flex items-start gap-2 mb-2">
                {getSentimentIcon(alert.sentiment)}
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-white">{alert.symbol}</span>
                    <span className="text-xs text-slate-400">@{alert.username}</span>
                  </div>
                  <p className="text-sm text-slate-300 line-clamp-2">{alert.message}</p>
                </div>
              </div>

              <div className="flex items-center justify-between mt-2 text-xs">
                <span className="text-slate-500">{formatTime(alert.created_at)}</span>
                <span className="text-slate-400 capitalize">{alert.alert_type.replace('_', ' ')}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
