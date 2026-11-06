import React, { useEffect, useRef, useState, useCallback } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X, TrendingUp, TrendingDown, Zap, ExternalLink, Volume2 } from 'lucide-react';
import { authTokenStore } from '../lib/api';

interface FlashAlert {
  id: string;
  symbol: string;
  company: string;
  headline: string;
  category: string;
  impact: 'HIGH' | 'MEDIUM';
  pdf_url?: string;
  published_at?: string;
  ltp?: number | null;
  change_pct?: number | null;
  volume?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  prev_close?: number | null;
  ts: number;
}

const MAX_VISIBLE = 4;
const AUTO_DISMISS_MS = 14000;

function fmt(n: number | null | undefined, decimals = 2): string {
  if (n == null) return '—';
  return n.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtVol(v: number | null | undefined): string {
  if (v == null) return '—';
  if (v >= 1_00_00_000) return `${(v / 1_00_00_000).toFixed(1)}Cr`;
  if (v >= 1_00_000) return `${(v / 1_00_000).toFixed(1)}L`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return String(v);
}

function AlertCard({
  alert,
  onDismiss,
}: {
  alert: FlashAlert;
  onDismiss: (id: string) => void;
}) {
  const isHigh = alert.impact === 'HIGH';
  const changeUp = (alert.change_pct ?? 0) >= 0;

  // Auto-dismiss timer bar
  const [progress, setProgress] = useState(100);
  useEffect(() => {
    const start = Date.now();
    const tick = setInterval(() => {
      const elapsed = Date.now() - start;
      const pct = Math.max(0, 100 - (elapsed / AUTO_DISMISS_MS) * 100);
      setProgress(pct);
      if (pct === 0) {
        clearInterval(tick);
        onDismiss(alert.id);
      }
    }, 80);
    return () => clearInterval(tick);
  }, [alert.id, onDismiss]);

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 80, scale: 0.94 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 80, scale: 0.9 }}
      transition={{ type: 'spring', stiffness: 340, damping: 28 }}
      className={`relative w-80 rounded-2xl border shadow-2xl overflow-hidden backdrop-blur-sm ${
        isHigh
          ? 'bg-gradient-to-br from-red-950/95 to-slate-900/95 border-red-600'
          : 'bg-gradient-to-br from-amber-950/95 to-slate-900/95 border-amber-600'
      }`}
    >
      {/* Glow pulse on HIGH */}
      {isHigh && (
        <motion.div
          className="absolute inset-0 rounded-2xl pointer-events-none"
          animate={{ boxShadow: ['0 0 0px rgba(239,68,68,0)', '0 0 22px rgba(239,68,68,0.35)', '0 0 0px rgba(239,68,68,0)'] }}
          transition={{ duration: 1.8, repeat: Infinity }}
        />
      )}

      {/* Header */}
      <div className={`flex items-center justify-between px-3 py-2 border-b ${isHigh ? 'border-red-800/60' : 'border-amber-800/60'}`}>
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ scale: [1, 1.3, 1] }}
            transition={{ duration: 1.2, repeat: Infinity }}
          >
            <Zap className={`w-3.5 h-3.5 ${isHigh ? 'text-red-400' : 'text-amber-400'}`} />
          </motion.div>
          <span className={`text-[10px] font-bold uppercase tracking-widest ${isHigh ? 'text-red-300' : 'text-amber-300'}`}>
            NSE Flash · {alert.impact}
          </span>
        </div>
        <button
          onClick={() => onDismiss(alert.id)}
          className="p-0.5 rounded text-slate-500 hover:text-slate-200 transition"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Body */}
      <div className="px-3 py-2.5">
        {/* Symbol + company */}
        <div className="flex items-start justify-between gap-2 mb-1.5">
          <div>
            <span className={`text-base font-bold ${isHigh ? 'text-red-200' : 'text-amber-200'}`}>
              {alert.symbol}
            </span>
            <span className="text-[11px] text-slate-400 ml-1.5 truncate max-w-[140px] inline-block align-bottom">
              {alert.company}
            </span>
          </div>
          {/* LTP + change */}
          {alert.ltp != null && (
            <div className="text-right flex-shrink-0">
              <div className="text-sm font-bold text-white">₹{fmt(alert.ltp)}</div>
              {alert.change_pct != null && (
                <div className={`flex items-center justify-end gap-0.5 text-[11px] font-semibold ${changeUp ? 'text-emerald-400' : 'text-red-400'}`}>
                  {changeUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {changeUp ? '+' : ''}{fmt(alert.change_pct, 2)}%
                </div>
              )}
            </div>
          )}
        </div>

        {/* Headline */}
        <p className="text-[11px] text-slate-200 leading-relaxed line-clamp-2 mb-2">
          {alert.headline}
        </p>

        {/* Market stats row */}
        {(alert.volume != null || alert.high != null || alert.low != null) && (
          <div className="flex items-center gap-3 text-[10px] text-slate-400 mb-2">
            {alert.volume != null && (
              <span className="flex items-center gap-1">
                <Volume2 className="w-2.5 h-2.5" /> Vol: <span className="text-slate-200">{fmtVol(alert.volume)}</span>
              </span>
            )}
            {alert.high != null && (
              <span>H: <span className="text-emerald-400">₹{fmt(alert.high)}</span></span>
            )}
            {alert.low != null && (
              <span>L: <span className="text-red-400">₹{fmt(alert.low)}</span></span>
            )}
          </div>
        )}

        {/* Category + PDF link */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-slate-500 truncate max-w-[180px]">{alert.category}</span>
          {alert.pdf_url && (
            <a
              href={alert.pdf_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[10px] text-blue-400 hover:text-blue-300 transition"
            >
              <ExternalLink className="w-2.5 h-2.5" /> Filing
            </a>
          )}
        </div>
      </div>

      {/* Auto-dismiss progress bar */}
      <div className="h-0.5 bg-slate-800">
        <motion.div
          className={`h-full ${isHigh ? 'bg-red-500' : 'bg-amber-500'}`}
          style={{ width: `${progress}%` }}
          transition={{ ease: 'linear' }}
        />
      </div>
    </motion.div>
  );
}

export default function NSEFlashAlerts() {
  const [alerts, setAlerts] = useState<FlashAlert[]>([]);
  const seenRef = useRef<Set<string>>(new Set());
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const addAlert = useCallback((raw: Omit<FlashAlert, 'id'>) => {
    const key = `${raw.symbol}|${raw.headline.slice(0, 80)}`;
    if (seenRef.current.has(key)) return;
    seenRef.current.add(key);
    const alert: FlashAlert = { ...raw, id: `${key}-${Date.now()}` };
    setAlerts(prev => [alert, ...prev].slice(0, MAX_VISIBLE));
  }, []);

  const dismiss = useCallback((id: string) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
  }, []);

  // REST poll fallback
  const pollRest = useCallback(async () => {
    try {
      const token = authTokenStore.get();
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const res = await fetch('/api/nse/flash-alerts/poll', { headers });
      if (!res.ok) return;
      const data = await res.json();
      for (const a of data.alerts ?? []) addAlert(a);
    } catch { /* silent */ }
  }, [addAlert]);

  useEffect(() => {
    // Try SSE first
    const token = authTokenStore.get();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const es = new EventSource(`/api/nse/flash-alerts${tokenParam}`);
    esRef.current = es;

    es.addEventListener('flash', (e: MessageEvent) => {
      try { addAlert(JSON.parse(e.data)); } catch { /* ignore */ }
    });

    es.onerror = () => {
      es.close();
      esRef.current = null;
      // Fall back to polling every 35s
      pollRest();
      pollRef.current = setInterval(pollRest, 35_000);
    };

    // Initial REST poll regardless (catches alerts before SSE connects)
    pollRest();

    return () => {
      es.close();
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [addAlert, pollRest]);

  if (alerts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {alerts.map(alert => (
          <div key={alert.id} className="pointer-events-auto">
            <AlertCard alert={alert} onDismiss={dismiss} />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}
