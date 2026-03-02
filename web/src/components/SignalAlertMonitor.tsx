/**
 * SignalAlertMonitor — Background component that polls ML predictions
 * and shows actionable BUY/SELL alert popups with sound.
 *
 * Renders:
 *  1. Floating alert popups (bottom-left) for new BUY/SELL signals
 *  2. Inline settings gear in the Header (via props callback)
 *
 * Mount once in App.tsx inside <ToastProvider> so it persists across pages.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  TrendingUp,
  TrendingDown,
  X,
  Bell,
  BellOff,
  Settings,
  Volume2,
  VolumeX,
  Brain,
  Zap,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { alertsAPI } from '../lib/api';

// ── Types ──────────────────────────────────────────────────────────────
interface MLAlert {
  id: string;
  symbol: string;
  signal: 'BULLISH' | 'BEARISH';
  action: 'BUY' | 'SELL';
  confidence: number;
  bias: string;
  reason: string;
  model_type: string;
  timestamp: string;
  dismissed: boolean;
}

interface AlertSettings {
  enabled: boolean;
  soundEnabled: boolean;
  minConfidence: number;
  pollIntervalSec: number;
  cooldownMinutes: number;
  maxVisibleAlerts: number;
}

// Default watchlist — same stocks as Terminal NIFTY50
const DEFAULT_SYMBOLS = [
  'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
  'HINDUNILVR', 'ITC', 'SBIN', 'BHARTIARTL', 'BAJFINANCE',
  'KOTAKBANK', 'LT', 'AXISBANK', 'TITAN', 'SUNPHARMA',
];

// ── Helpers ────────────────────────────────────────────────────────────
const SETTINGS_KEY = 'fasttrade_signal_alert_settings';

function loadSettings(): AlertSettings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) return { ...defaultSettings(), ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return defaultSettings();
}

function saveSettings(s: AlertSettings) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

function defaultSettings(): AlertSettings {
  return {
    enabled: true,
    soundEnabled: true,
    minConfidence: 60,
    pollIntervalSec: 60,
    cooldownMinutes: 15,
    maxVisibleAlerts: 5,
  };
}

// Simple beep using Web Audio API (no external file needed)
function playAlertSound(type: 'buy' | 'sell') {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);

    if (type === 'buy') {
      // Ascending chirp for BUY
      osc.type = 'sine';
      osc.frequency.setValueAtTime(600, ctx.currentTime);
      osc.frequency.linearRampToValueAtTime(900, ctx.currentTime + 0.15);
    } else {
      // Descending chirp for SELL
      osc.type = 'sine';
      osc.frequency.setValueAtTime(900, ctx.currentTime);
      osc.frequency.linearRampToValueAtTime(500, ctx.currentTime + 0.15);
    }

    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);

    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch {
    // Audio not available — silent fallback
  }
}

function timeAgo(ts: string): string {
  const diff = Date.now() - new Date(ts).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return 'Just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  return `${hr}h ago`;
}

// ── Component ──────────────────────────────────────────────────────────
export const SignalAlertMonitor: React.FC = () => {
  const [settings, setSettings] = useState<AlertSettings>(loadSettings);
  const [alerts, setAlerts] = useState<MLAlert[]>([]);
  const [showSettings, setShowSettings] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [scanning, setScanning] = useState(false);

  const seenIds = useRef(new Set<string>());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Persist settings
  useEffect(() => {
    saveSettings(settings);
  }, [settings]);

  // ── Poll for ML signals ─────────────────────────────────────────────
  const scanSignals = useCallback(async () => {
    if (!settings.enabled || scanning) return;
    setScanning(true);

    try {
      const res = await alertsAPI.scanMLSignals({
        symbols: DEFAULT_SYMBOLS,
        min_confidence: settings.minConfidence,
        cooldown_minutes: settings.cooldownMinutes,
      });

      const data = res.data;
      if (data?.alerts?.length) {
        const newAlerts: MLAlert[] = [];
        for (const a of data.alerts) {
          const id = `${a.symbol}:${a.signal}:${a.timestamp}`;
          if (seenIds.current.has(id)) continue;
          seenIds.current.add(id);

          const alert: MLAlert = {
            id,
            symbol: a.symbol,
            signal: a.signal,
            action: a.action,
            confidence: a.confidence,
            bias: a.bias,
            reason: a.reason || '',
            model_type: a.model_type || 'ml',
            timestamp: a.timestamp,
            dismissed: false,
          };
          newAlerts.push(alert);

          // Play sound
          if (settings.soundEnabled) {
            playAlertSound(a.action === 'BUY' ? 'buy' : 'sell');
          }
        }

        if (newAlerts.length) {
          setAlerts(prev => [...newAlerts, ...prev].slice(0, 50));
          setCollapsed(false); // Auto-expand when new alerts arrive
        }
      }
    } catch (err) {
      console.warn('Signal scan failed:', err);
    } finally {
      setScanning(false);
    }
  }, [settings.enabled, settings.minConfidence, settings.cooldownMinutes, settings.soundEnabled, scanning]);

  // Set up polling interval
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);

    if (settings.enabled) {
      // Initial scan after 5 seconds (let app load first)
      const timeout = setTimeout(() => {
        scanSignals();
      }, 5000);

      intervalRef.current = setInterval(scanSignals, settings.pollIntervalSec * 1000);

      return () => {
        clearTimeout(timeout);
        if (intervalRef.current) clearInterval(intervalRef.current);
      };
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [settings.enabled, settings.pollIntervalSec, scanSignals]);

  // ── Handlers ────────────────────────────────────────────────────────
  const dismissAlert = (id: string) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
  };

  const dismissAll = () => {
    setAlerts([]);
  };

  const updateSetting = <K extends keyof AlertSettings>(key: K, value: AlertSettings[K]) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const visibleAlerts = alerts.filter(a => !a.dismissed).slice(0, settings.maxVisibleAlerts);
  const hiddenCount = Math.max(0, alerts.filter(a => !a.dismissed).length - settings.maxVisibleAlerts);

  // ── Render ──────────────────────────────────────────────────────────
  return (
    <>
      {/* ── Floating Alert Popups (bottom-right) ────────────────── */}
      <div className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 max-w-sm items-end">
        {/* Controls bar */}
        <div className="flex items-center gap-2 mb-1">
          {/* Toggle on/off */}
          <button
            onClick={() => updateSetting('enabled', !settings.enabled)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
              settings.enabled
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
                : 'bg-slate-800/80 text-slate-500 border border-slate-700/50 hover:bg-slate-700/50'
            }`}
            title={settings.enabled ? 'Signal alerts ON' : 'Signal alerts OFF'}
          >
            {settings.enabled ? <Bell size={13} /> : <BellOff size={13} />}
            {settings.enabled ? 'Alerts ON' : 'Alerts OFF'}
          </button>

          {/* Sound toggle */}
          <button
            onClick={() => updateSetting('soundEnabled', !settings.soundEnabled)}
            className={`p-1.5 rounded-lg text-xs transition-all border ${
              settings.soundEnabled
                ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                : 'bg-slate-800/80 text-slate-500 border-slate-700/50'
            }`}
            title={settings.soundEnabled ? 'Sound ON' : 'Sound OFF'}
          >
            {settings.soundEnabled ? <Volume2 size={13} /> : <VolumeX size={13} />}
          </button>

          {/* Settings gear */}
          <button
            onClick={() => setShowSettings(!showSettings)}
            className={`p-1.5 rounded-lg text-xs transition-all border ${
              showSettings
                ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                : 'bg-slate-800/80 text-slate-400 border-slate-700/50 hover:text-white'
            }`}
            title="Alert Settings"
          >
            <Settings size={13} />
          </button>

          {/* Scanning indicator */}
          {scanning && (
            <span className="text-[10px] text-slate-500 flex items-center gap-1">
              <span className="w-1.5 h-1.5 bg-yellow-400 rounded-full animate-pulse" />
              Scanning...
            </span>
          )}

          {/* Alert count & collapse */}
          {alerts.length > 0 && (
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-white ml-auto"
            >
              {alerts.length} alert{alerts.length !== 1 ? 's' : ''}
              {collapsed ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            </button>
          )}

          {alerts.length > 0 && (
            <button
              onClick={dismissAll}
              className="text-[10px] text-slate-500 hover:text-red-400"
              title="Dismiss all"
            >
              Clear
            </button>
          )}
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="bg-slate-900/95 border border-slate-700 rounded-xl p-4 backdrop-blur-sm shadow-2xl">
            <h4 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Brain size={14} className="text-purple-400" />
              Signal Alert Settings
            </h4>

            <div className="space-y-3">
              {/* Min Confidence */}
              <div>
                <label className="text-xs text-slate-400 block mb-1">
                  Min Confidence: <span className="text-white font-mono">{settings.minConfidence}%</span>
                </label>
                <input
                  type="range"
                  min={30}
                  max={95}
                  step={5}
                  value={settings.minConfidence}
                  onChange={e => updateSetting('minConfidence', parseInt(e.target.value))}
                  className="w-full h-1.5 rounded-full appearance-none bg-slate-700 accent-purple-500"
                  title="Minimum confidence threshold"
                />
                <div className="flex justify-between text-[9px] text-slate-600 mt-0.5">
                  <span>30%</span>
                  <span>95%</span>
                </div>
              </div>

              {/* Poll Interval */}
              <div>
                <label className="text-xs text-slate-400 block mb-1">
                  Check every: <span className="text-white font-mono">{settings.pollIntervalSec}s</span>
                </label>
                <input
                  type="range"
                  min={30}
                  max={300}
                  step={15}
                  value={settings.pollIntervalSec}
                  onChange={e => updateSetting('pollIntervalSec', parseInt(e.target.value))}
                  className="w-full h-1.5 rounded-full appearance-none bg-slate-700 accent-purple-500"
                  title="Polling interval in seconds"
                />
                <div className="flex justify-between text-[9px] text-slate-600 mt-0.5">
                  <span>30s</span>
                  <span>5m</span>
                </div>
              </div>

              {/* Cooldown */}
              <div>
                <label className="text-xs text-slate-400 block mb-1">
                  Cooldown: <span className="text-white font-mono">{settings.cooldownMinutes}m</span>
                </label>
                <input
                  type="range"
                  min={5}
                  max={120}
                  step={5}
                  value={settings.cooldownMinutes}
                  onChange={e => updateSetting('cooldownMinutes', parseInt(e.target.value))}
                  className="w-full h-1.5 rounded-full appearance-none bg-slate-700 accent-purple-500"
                  title="Cooldown between repeated alerts"
                />
                <div className="flex justify-between text-[9px] text-slate-600 mt-0.5">
                  <span>5m</span>
                  <span>2h</span>
                </div>
              </div>
            </div>

            <div className="mt-3 pt-3 border-t border-slate-700/50">
              <p className="text-[10px] text-slate-500">
                Scans {DEFAULT_SYMBOLS.length} NIFTY50 stocks for ML BUY/SELL signals.
                Alerts are deduplicated via a server-side cooldown window.
              </p>
            </div>
          </div>
        )}

        {/* Alert Cards (shown when not collapsed) */}
        {!collapsed && visibleAlerts.map(alert => (
          <AlertCard key={alert.id} alert={alert} onDismiss={dismissAlert} />
        ))}

        {!collapsed && hiddenCount > 0 && (
          <div className="text-[10px] text-slate-500 text-center py-1">
            +{hiddenCount} more alert{hiddenCount !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </>
  );
};

// ── Individual Alert Card ──────────────────────────────────────────────
const AlertCard: React.FC<{ alert: MLAlert; onDismiss: (id: string) => void }> = ({
  alert,
  onDismiss,
}) => {
  const isBuy = alert.action === 'BUY';

  return (
    <div
      className={`relative rounded-xl border p-4 shadow-2xl backdrop-blur-sm animate-slideInLeft ${
        isBuy
          ? 'bg-emerald-950/90 border-emerald-500/40'
          : 'bg-red-950/90 border-red-500/40'
      }`}
      style={{ minWidth: '320px' }}
    >
      {/* Dismiss button */}
      <button
        onClick={() => onDismiss(alert.id)}
        className="absolute top-2 right-2 text-slate-500 hover:text-white transition"
        title="Dismiss alert"
      >
        <X size={14} />
      </button>

      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <div
          className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isBuy ? 'bg-emerald-500/20' : 'bg-red-500/20'
          }`}
        >
          {isBuy ? (
            <TrendingUp size={20} className="text-emerald-400" />
          ) : (
            <TrendingDown size={20} className="text-red-400" />
          )}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-white font-bold text-base">{alert.symbol}</span>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                isBuy
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                  : 'bg-red-500/20 text-red-300 border border-red-500/30'
              }`}
            >
              {alert.action}
            </span>
            <span
              className={`text-[9px] font-semibold px-1.5 py-0.5 rounded ${
                alert.model_type === 'ensemble'
                  ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                  : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
              }`}
            >
              {alert.model_type === 'ensemble' ? 'ENSEMBLE' : 'GBM'}
            </span>
          </div>
          <p className="text-slate-400 text-[10px] mt-0.5">
            {timeAgo(alert.timestamp)}
          </p>
        </div>
      </div>

      {/* Confidence bar */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-slate-400 text-xs">Confidence</span>
        <div className="flex-1 h-2 rounded-full bg-slate-700/50 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              alert.confidence >= 75
                ? isBuy ? 'bg-emerald-400' : 'bg-red-400'
                : 'bg-yellow-400'
            }`}
            style={{ width: `${alert.confidence}%` }}
          />
        </div>
        <span className="text-white text-xs font-bold font-mono">{alert.confidence}%</span>
      </div>

      {/* Reason */}
      {alert.reason && (
        <p className="text-slate-400 text-[11px] leading-relaxed line-clamp-2">
          {alert.reason}
        </p>
      )}

      {/* Action hint */}
      <div className={`mt-2 pt-2 border-t flex items-center gap-2 ${
        isBuy ? 'border-emerald-500/20' : 'border-red-500/20'
      }`}>
        <Zap size={11} className={isBuy ? 'text-emerald-400' : 'text-red-400'} />
        <span className={`text-[10px] font-medium ${
          isBuy ? 'text-emerald-400' : 'text-red-400'
        }`}>
          {isBuy ? 'Consider buying' : 'Consider selling'} {alert.symbol}
        </span>
      </div>
    </div>
  );
};

// ── CSS animation (add via Tailwind or style tag) ──────────────────────
// If not using Tailwind JIT arbitrary, inject a small style
const styleId = 'signal-alert-animations';
if (typeof document !== 'undefined' && !document.getElementById(styleId)) {
  const style = document.createElement('style');
  style.id = styleId;
  style.textContent = `
    @keyframes slideInLeft {
      from { opacity: 0; transform: translateX(-30px) scale(0.95); }
      to   { opacity: 1; transform: translateX(0) scale(1); }
    }
    .animate-slideInLeft {
      animation: slideInLeft 0.35s ease-out;
    }
  `;
  document.head.appendChild(style);
}

export default SignalAlertMonitor;
