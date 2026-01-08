import React, { useState, useEffect } from 'react';
import { Bell, X, Check } from 'lucide-react';
import api from '../lib/api';

interface Notification {
  id: number;
  type: string;
  title: string;
  message: string;
  priority: string;
  read: boolean;
  created_at: string;
}

export const NotificationBell: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');

  // Fetch unread notifications
  const fetchNotifications = async () => {
    try {
      const response = await api.get('/notifications/unread');
      const data = response.data;
      setNotifications(data.notifications || []);
      setUnreadCount(data.count || 0);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    }
  };

  // Mark notification as read
  const markAsRead = async (notificationId: number) => {
    try {
      await api.post('/notifications/mark-read', {
        notification_ids: [notificationId]
      });
      
      // Update local state
      setNotifications(prev => 
        prev.map(n => n.id === notificationId ? {...n, read: true} : n)
      );
      setUnreadCount(prev => Math.max(0, prev - 1));
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  // Mark all as read
  const markAllAsRead = async () => {
    setLoading(true);
    try {
      await api.post('/notifications/mark-all-read');
      setNotifications(prev => prev.map(n => ({...n, read: true})));
      setUnreadCount(0);
      setStatusMsg('All marked read');
    } catch (error) {
      console.error('Failed to mark all as read:', error);
      setStatusMsg('Failed to mark all');
    } finally {
      setLoading(false);
      setTimeout(() => setStatusMsg(''), 2000);
    }
  };

  // Clear old notifications (30 days by default)
  const clearOld = async () => {
    setLoading(true);
    try {
      await api.delete('/notifications/clear-old', { params: { days: 30 } });
      await fetchNotifications();
      setStatusMsg('Cleared old');
    } catch (error) {
      console.error('Failed to clear notifications:', error);
      setStatusMsg('Clear failed');
    } finally {
      setLoading(false);
      setTimeout(() => setStatusMsg(''), 2000);
    }
  };

  // Fetch on mount and every 2 minutes
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 120000);
    return () => clearInterval(interval);
  }, []);

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-red-400';
      case 'high': return 'text-orange-400';
      case 'medium': return 'text-yellow-400';
      default: return 'text-blue-400';
    }
  };

  const getTypeEmoji = (type: string) => {
    if (type.includes('executed')) return '✅';
    if (type.includes('failed')) return '❌';
    if (type.includes('tp')) return '🎯';
    if (type.includes('sl')) return '🛑';
    if (type.includes('pnl')) return '📊';
    if (type.includes('error')) return '🚨';
    if (type.includes('margin')) return '⚠️';
    return '🔔';
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="relative">
      {/* Bell Icon */}
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="relative text-slate-400 hover:text-white transition"
      >
        <Bell className="w-6 h-6" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center font-bold">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {showDropdown && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-40"
            onClick={() => setShowDropdown(false)}
          />
          
          {/* Notification Panel */}
          <div className="absolute right-0 mt-2 w-96 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 max-h-[600px] flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-slate-700 flex items-center justify-between">
              <div>
                <h3 className="text-white font-semibold">Notifications</h3>
                <p className="text-slate-400 text-sm">{unreadCount} unread</p>
                {statusMsg && <p className="text-xs text-slate-400">{statusMsg}</p>}
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={fetchNotifications}
                  disabled={loading}
                  className="text-slate-300 hover:text-white text-sm"
                >
                  Refresh
                </button>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllAsRead}
                    disabled={loading}
                    className="text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1"
                  >
                    <Check className="w-4 h-4" />
                    Mark all
                  </button>
                )}
                <button
                  onClick={clearOld}
                  disabled={loading}
                  className="text-slate-300 hover:text-white text-sm"
                >
                  Clear 30d
                </button>
              </div>
            </div>

            {/* Notification List */}
            <div className="overflow-y-auto flex-1">
              {notifications.length === 0 ? (
                <div className="p-8 text-center text-slate-400">
                  <Bell className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No notifications</p>
                </div>
              ) : (
                <div className="divide-y divide-slate-700">
                  {notifications.map((notification) => (
                    <div
                      key={notification.id}
                      className={`p-4 hover:bg-slate-750 transition cursor-pointer ${
                        !notification.read ? 'bg-slate-800/50' : ''
                      }`}
                      onClick={() => markAsRead(notification.id)}
                    >
                      <div className="flex items-start gap-3">
                        {/* Icon */}
                        <span className="text-2xl flex-shrink-0">
                          {getTypeEmoji(notification.type)}
                        </span>

                        {/* Content */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <h4 className={`font-medium ${getPriorityColor(notification.priority)}`}>
                              {notification.title}
                            </h4>
                            {!notification.read && (
                              <div className="w-2 h-2 bg-blue-500 rounded-full flex-shrink-0 mt-2" />
                            )}
                          </div>
                          
                          <p className="text-slate-300 text-sm mt-1 whitespace-pre-wrap">
                            {notification.message.slice(0, 150)}
                            {notification.message.length > 150 ? '...' : ''}
                          </p>
                          
                          <p className="text-slate-500 text-xs mt-2">
                            {formatTime(notification.created_at)}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            {notifications.length > 0 && (
              <div className="p-3 border-t border-slate-700 text-center">
                <button
                  onClick={() => {
                    setShowDropdown(false);
                    // Navigate to notifications page if you have one
                  }}
                  className="text-blue-400 hover:text-blue-300 text-sm"
                >
                  View all notifications
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};
