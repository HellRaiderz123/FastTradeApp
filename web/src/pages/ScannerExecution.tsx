import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Loader2, CheckCircle, Clock, TrendingUp,
  TrendingDown, AlertCircle, Zap, RefreshCw, X, Minus, Plus
} from 'lucide-react';
import { useToast } from '../components/Toast';
import api, { mlAPI, marketAPI } from '../lib/api';

interface ScanSignal {
  symbol: string;
  ltp: number;
  change_percent: number;
  indicators: Record<string, number>;
  conditions_met: number;
  htf_confirmed?: boolean;
  htf_timeframe?: string | null;
  atr?: number | null;
  suggested_quantity?: number;
  capital_used?: number;
  position_sizing?: string;
}

interface ScanResult {
  strategy_id: number;
  strategy_name: string;
  direction: string;
  signals: ScanSignal[];
  total_scanned: number;
  matches_found: number;
  execution_mode: string;
  exit_config: Record<string, any>;
}

interface ExecutionEvent {
  time: string;
  label: string;
  sublabel: string;
  status: 'done' | 'active' | 'pending';
  cycle: string;
}

interface ExecutedSignal {
  symbol: string;
  ltp: number;
  change_percent: number;
  quantity: number;
  direction: string;
  status: 'idle' | 'executing' | 'done' | 'failed';
  order?: {
    status: string;
    order_id?: string;
    fill_price?: number;
    error?: string;
  };
  events: ExecutionEvent[];
}

const MODE_BADGE: Record<string, { label: string; cls: string }> = {
  ZERODHA_LIVE: { label: '🔴 LIVE', cls: 'bg-red-500/20 text-red-300 border-red-500/40' },
  PAPER_TRADING: { label: '🟢 PAPER', cls: 'bg-green-500/20 text-green-300 border-green-500/40' },
  ZERODHA_DRY_RUN: { label: '🟡 DRY RUN', cls: 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40' },
};

function buildInitialEvents(direction: string): ExecutionEvent[] {
  const now = new Date().toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true, day: '2-digit', month: 'short', year: 'numeric' });
  return [
    { time: '', label: direction === 'BUY' ? 'Sold' : 'Bought', sublabel: 'Order Placed', status: 'pending', cycle: 'C1' },
    { time: '', label: 'Exit Triggered', sublabel: 'Condition has been met', status: 'pending', cycle: 'C1' },
    { time: '', label: direction === 'BUY' ? 'Bought' : 'Sold', sublabel: 'Order Placed', status: 'pending', cycle: 'C1' },
    { time: now, label: `${direction === 'BUY' ? 'BUY' : 'SELL'} alert`, sublabel: 'Signal detected', status: 'active', cycle: 'C1' },
    { time: now, label: 'Waiting for entry', sublabel: 'Waiting for entry', status: 'done', cycle: 'C1' },
  ];
}

function buildExecutedEvents(direction: string, fillPrice: number, orderId: string): ExecutionEvent[] {
  const now = new Date().toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true, day: '2-digit', month: 'short', year: 'numeric' });
  const priceStr = fillPrice ? `₹${fillPrice.toLocaleString('en-IN')}` : '';
  return [
    { time: '', label: direction === 'BUY' ? 'Sold' : 'Bought', sublabel: 'Order Placed', status: 'pending', cycle: 'C1' },
    { time: '', label: 'Exit Triggered', sublabel: 'Condition has been met', status: 'pending', cycle: 'C1' },
    { time: now, label: direction === 'BUY' ? 'Bought' : 'Sold', sublabel: `Order ${orderId}`, status: 'active', cycle: 'C1' },
    { time: now, label: `${direction === 'BUY' ? 'BUY' : 'SELL'} alert${priceStr ? ` at ${priceStr}` : ''}`, sublabel: 'Signal detected', status: 'done', cycle: 'C1' },
    { time: now, label: 'Waiting for entry', sublabel: 'Waiting for entry', status: 'done', cycle: 'C1' },
  ];
}

interface TradeModalProps {
  symbol: string;
  direction: string;
  ltp: number;
  defaultQty: number;
  onConfirm: (symbol: string, qty: number) => void;
  onClose: () => void;
}

const TradeModal: React.FC<TradeModalProps> = ({ symbol, direction, ltp, defaultQty, onConfirm, onClose }) => {
  const [qty, setQty] = useState(defaultQty);
  const [price, setPrice] = useState(ltp);
  const [ml, setMl] = useState<any>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Poll LTP every 5s
    const poll = async () => {
      try {
        const res = await marketAPI.getLTP(symbol);
        setPrice(res.data?.ltp ?? res.data?.price ?? price);
      } catch {}
    };
    poll();
    intervalRef.current = setInterval(poll, 5000);
    // Fetch ML signal once
    mlAPI.getSignalWithNews(symbol).then(res => setMl(res.data)).catch(() => {});
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  const mlSignal = ml?.ml_signal ?? ml?.signal ?? null;
  const confidence = ml?.confidence ?? ml?.ml_confidence ?? null;
  const sentiment = ml?.news_sentiment ?? ml?.sentiment ?? null;
  const indicators: Record<string, any> = ml?.indicators ?? {};

  const signalColor = mlSignal === 'BUY' ? 'text-green-400' : mlSignal === 'SELL' ? 'text-red-400' : 'text-yellow-400';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-[420px] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
          <div>
            <p className="text-base font-bold text-white">{symbol}</p>
            <p className="text-xs text-slate-400">NSE • {direction === 'BUY' ? 'Long' : 'Short'}</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-slate-800 rounded-lg">
            <X className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Live price */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-500">LTP</span>
            <span className="text-xl font-bold text-white">₹{price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
          </div>

          {/* Quantity editor */}
          <div>
            <p className="text-xs text-slate-500 mb-2">Quantity</p>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setQty(q => Math.max(1, q - 1))}
                className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center"
              >
                <Minus className="w-3.5 h-3.5 text-slate-300" />
              </button>
              <input
                type="number"
                min={1}
                value={qty}
                onChange={e => setQty(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-20 text-center bg-slate-800 border border-slate-700 rounded-lg py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={() => setQty(q => q + 1)}
                className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center"
              >
                <Plus className="w-3.5 h-3.5 text-slate-300" />
              </button>
              <span className="text-xs text-slate-500">≈ ₹{(price * qty).toLocaleString('en-IN', { maximumFractionDigits: 0 })} total</span>
            </div>
          </div>

          {/* ML + News */}
          {ml && (
            <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">ML Signal</span>
                <span className={`text-sm font-bold ${signalColor}`}>
                  {mlSignal ?? '—'}{confidence != null ? ` • ${(confidence * 100).toFixed(0)}%` : ''}
                </span>
              </div>
              {sentiment && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">News Sentiment</span>
                  <span className="text-xs text-slate-300">{sentiment}</span>
                </div>
              )}
              {Object.keys(indicators).length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {Object.entries(indicators).slice(0, 6).map(([k, v]) => (
                    <span key={k} className="px-2 py-0.5 rounded bg-slate-700 text-[10px] text-slate-300">
                      {k}: {typeof v === 'number' ? v.toFixed(2) : String(v)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Confirm */}
        <div className="px-5 pb-5">
          <button
            onClick={() => onConfirm(symbol, qty)}
            className={`w-full py-3 rounded-xl text-sm font-bold transition ${
              direction === 'BUY'
                ? 'bg-green-600 hover:bg-green-700 text-white'
                : 'bg-red-600 hover:bg-red-700 text-white'
            }`}
          >
            Confirm {direction === 'BUY' ? 'Buy' : 'Sell'} • {qty} × ₹{price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
          </button>
        </div>
      </div>
    </div>
  );
};

const ScannerExecution: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const state = location.state as { scanResult: ScanResult; autoExecute?: boolean } | null;
  const scanResult = state?.scanResult;
  const autoExecute = state?.autoExecute ?? false;

  const [signals, setSignals] = useState<ExecutedSignal[]>(() =>
    (scanResult?.signals || []).map(sig => ({
      symbol: sig.symbol,
      ltp: sig.ltp,
      change_percent: sig.change_percent,
      quantity: sig.suggested_quantity || 1,
      direction: scanResult?.direction || 'BUY',
      status: 'idle',
      events: buildInitialEvents(scanResult?.direction || 'BUY'),
    }))
  );

  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(
    scanResult?.signals?.[0]?.symbol || null
  );

  const [executingAll, setExecutingAll] = useState(false);
  const [tradeModal, setTradeModal] = useState<string | null>(null);

  const executeOne = useCallback(async (symbol: string, quantityOverride?: number) => {
    if (!scanResult) return;
    const sig = scanResult.signals.find(s => s.symbol === symbol);
    if (!sig) return;

    setSignals(prev => prev.map(s =>
      s.symbol === symbol ? { ...s, status: 'executing' } : s
    ));

    try {
      const qty = quantityOverride ?? sig.suggested_quantity ?? 1;
      const res = await api.post('/condition-scanner/execute-signal', {
        symbol,
        direction: scanResult.direction,
        strategy_id: scanResult.strategy_id,
        strategy_name: scanResult.strategy_name,
        exit_config: scanResult.exit_config,
        quantity: qty,
        suggested_quantity: qty,
      });

      const order = res.data.order;
      const failed = order.status?.includes('FAILED');
      const skipped = order.status === 'SKIPPED';

      setSignals(prev => prev.map(s =>
        s.symbol === symbol
          ? {
              ...s,
              status: failed ? 'failed' : 'done',
              order,
              events: (failed || skipped)
                ? s.events
                : buildExecutedEvents(scanResult.direction, order.fill_price || sig.ltp, order.order_id || ''),
            }
          : s
      ));

      showToast(failed ? 'error' : 'success', res.data.message);
    } catch (err: any) {
      setSignals(prev => prev.map(s =>
        s.symbol === symbol ? { ...s, status: 'failed' } : s
      ));
      showToast('error', err?.response?.data?.detail || 'Execution failed');
    }
  }, [scanResult, showToast]);

  // Auto-execute all on mount if requested
  useEffect(() => {
    if (!autoExecute || !scanResult?.signals?.length) return;
    const run = async () => {
      setExecutingAll(true);
      for (const sig of scanResult.signals) {
        await executeOne(sig.symbol);
      }
      setExecutingAll(false);
    };
    run();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!scanResult) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-4">
        <AlertCircle className="w-12 h-12 text-slate-600" />
        <p className="text-slate-400">No scan result. Go back and run a scan first.</p>
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm"
        >
          Back to Scanner
        </button>
      </div>
    );
  }

  const modeBadge = MODE_BADGE[scanResult.execution_mode] || MODE_BADGE['ZERODHA_DRY_RUN'];
  const selectedSig = signals.find(s => s.symbol === selectedSymbol);
  const originalSig = scanResult.signals.find(s => s.symbol === selectedSymbol);

  return (
    <>
    <div className="flex h-[calc(100vh-4rem)] bg-slate-950">
      {/* ── Left: Instrument List (Streak-style) ── */}
      <div className="w-[420px] flex-shrink-0 border-r border-slate-800 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center gap-3 mb-3">
            <button
              onClick={() => navigate(-1)}
              className="p-1.5 hover:bg-slate-800 rounded-lg transition"
            >
              <ArrowLeft className="w-4 h-4 text-slate-400" />
            </button>
            <div className="flex-1 min-w-0">
              <h1 className="text-base font-bold text-white truncate">{scanResult.strategy_name}</h1>
              <p className="text-xs text-slate-500">
                {scanResult.matches_found} signal{scanResult.matches_found !== 1 ? 's' : ''} • {scanResult.total_scanned} scanned
              </p>
            </div>
            <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${modeBadge.cls}`}>
              {modeBadge.label}
            </span>
          </div>

          {/* Execute All button */}
          <button
            onClick={async () => {
              setExecutingAll(true);
              for (const sig of scanResult.signals) {
                const s = signals.find(x => x.symbol === sig.symbol);
                if (s?.status === 'idle') await executeOne(sig.symbol);
              }
              setExecutingAll(false);
            }}
            disabled={executingAll || signals.every(s => s.status !== 'idle')}
            className="w-full py-2.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition disabled:opacity-50 bg-blue-600 hover:bg-blue-700 text-white"
          >
            {executingAll
              ? <><Loader2 className="w-4 h-4 animate-spin" /> Executing…</>
              : <><Zap className="w-4 h-4" /> Execute All Signals</>
            }
          </button>
        </div>

        {/* Strategy / Instrument table header */}
        <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-2 px-4 py-2 text-[10px] text-slate-500 uppercase tracking-wider border-b border-slate-800">
          <span>Strategy / Instrument</span>
          <span className="text-right">Avg Price</span>
          <span className="text-right">LTP</span>
          <span className="text-right">Day Chg</span>
          <span className="text-right w-24">Status</span>
        </div>

        {/* Strategy row */}
        <div className="px-4 py-2 border-b border-slate-800/50 bg-slate-900/30">
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-2 items-center">
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500">▼</span>
              <span className="text-sm font-semibold text-white">{scanResult.strategy_name}</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                {scanResult.direction === 'BUY' ? 'equity' : 'equity'}
              </span>
            </div>
            <span className="text-xs text-slate-500 text-right">-</span>
            <span className="text-xs text-slate-500 text-right">-</span>
            <span className="text-xs text-slate-500 text-right">-</span>
            <div className="text-right w-24">
              <span className="text-[10px] text-slate-400">
                {signals.filter(s => s.status === 'done').length}/{signals.length} Running
              </span>
            </div>
          </div>
        </div>

        {/* Instrument rows */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {signals.map(sig => {
            const isSelected = sig.symbol === selectedSymbol;
            const origSig = scanResult.signals.find(s => s.symbol === sig.symbol);
            return (
              <div
                key={sig.symbol}
                onClick={() => setSelectedSymbol(sig.symbol)}
                className={`grid grid-cols-[1fr_auto_auto_auto_auto] gap-2 items-center px-4 py-3 cursor-pointer border-b border-slate-800/40 transition ${
                  isSelected ? 'bg-blue-600/10 border-l-2 border-l-blue-500' : 'hover:bg-slate-900/50'
                }`}
              >
                {/* Symbol */}
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-sm font-semibold text-white truncate">{sig.symbol}</span>
                  <span className="text-[10px] text-slate-500">NSE</span>
                  {origSig?.suggested_quantity && (
                    <span className="text-[10px] text-blue-400">x{origSig.suggested_quantity}</span>
                  )}
                </div>

                {/* Avg Price */}
                <span className="text-xs text-slate-400 text-right">0</span>

                {/* LTP */}
                <span className="text-xs text-white text-right font-medium">
                  {sig.ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>

                {/* Day Change */}
                <span className={`text-xs text-right ${sig.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {sig.change_percent >= 0 ? '+' : ''}{sig.change_percent.toFixed(2)} %
                </span>

                {/* Status */}
                <div className="flex items-center justify-end gap-1.5 w-24">
                  {sig.status === 'executing' && (
                    <Loader2 className="w-3 h-3 animate-spin text-blue-400" />
                  )}
                  {sig.status === 'done' && (
                    <span className="flex items-center gap-1 text-[10px] text-green-400">
                      <CheckCircle className="w-3 h-3" />
                      {sig.direction === 'BUY' ? 'BUY' : 'SELL'} Done
                    </span>
                  )}
                  {sig.status === 'failed' && (
                    <span className="flex items-center gap-1 text-[10px] text-red-400">
                      <X className="w-3 h-3" /> Failed
                    </span>
                  )}
                  {sig.status === 'idle' && (
                    <span className="flex items-center gap-1 text-[10px] text-blue-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-400 inline-block" />
                      {sig.direction === 'BUY' ? 'BUY' : 'SELL'} Alert
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Right: Streak-style Timeline ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {selectedSig ? (
          <>
            {/* Header */}
            <div className="p-5 border-b border-slate-800 bg-slate-950/80">
              <div className="flex items-center justify-between mb-1">
                <div>
                  <h2 className="text-lg font-bold text-white">{scanResult.strategy_name}</h2>
                  <div className="flex items-center gap-3 mt-1">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-blue-600/30 border border-blue-500/40 flex items-center justify-center text-xs font-bold text-blue-300">
                        {selectedSig.symbol.slice(0, 2)}
                      </div>
                      <span className="text-sm font-semibold text-white">{selectedSig.symbol}</span>
                      <span className="text-xs text-slate-500">NSE</span>
                    </div>
                    <span className="text-xs text-slate-400">
                      Avg Price: <span className="text-white font-medium">
                        ₹{selectedSig.order?.fill_price?.toFixed(2) || '0.00'} x {selectedSig.quantity}
                      </span>
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedSymbol(null)}
                  className="p-1.5 hover:bg-slate-800 rounded-lg"
                >
                  <X className="w-4 h-4 text-slate-500" />
                </button>
              </div>

              {/* Cycle tabs */}
              <div className="flex items-center gap-2 mt-3">
                <span className="text-xs text-slate-500">Cycles</span>
                <button className="px-3 py-1 rounded-md text-xs font-semibold bg-blue-600 text-white">C1</button>
              </div>
            </div>

            {/* Timeline */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
              <div className="max-w-lg mx-auto">
                <div className="relative">
                  {/* Vertical line */}
                  <div className="absolute left-[18px] top-0 bottom-0 w-px bg-slate-800" />

                  <div className="space-y-0">
                    {selectedSig.events.map((event, idx) => (
                      <div key={idx} className={`relative flex gap-4 pb-6 ${event.status === 'active' ? 'bg-blue-600/5 -mx-3 px-3 rounded-xl border border-blue-500/20' : ''}`}>
                        {/* Circle */}
                        <div className="relative z-10 flex-shrink-0 mt-1">
                          {event.status === 'done' ? (
                            <div className="w-9 h-9 rounded-full bg-slate-900 border-2 border-slate-700 flex items-center justify-center">
                              <CheckCircle className="w-4 h-4 text-slate-500" />
                            </div>
                          ) : event.status === 'active' ? (
                            <div className="w-9 h-9 rounded-full bg-blue-600/20 border-2 border-blue-500 flex items-center justify-center">
                              {selectedSig.status === 'executing'
                                ? <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                                : selectedSig.direction === 'BUY'
                                  ? <TrendingUp className="w-4 h-4 text-blue-400" />
                                  : <TrendingDown className="w-4 h-4 text-red-400" />
                              }
                            </div>
                          ) : (
                            <div className="w-9 h-9 rounded-full bg-slate-900 border-2 border-slate-800 flex items-center justify-center">
                              <Clock className="w-4 h-4 text-slate-700" />
                            </div>
                          )}
                        </div>

                        {/* Content */}
                        <div className="flex-1 min-w-0 pt-1">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <p className={`text-sm font-semibold ${
                                event.status === 'active' ? 'text-white' :
                                event.status === 'done' ? 'text-slate-400' : 'text-slate-600'
                              }`}>
                                {event.label}
                              </p>
                              <p className={`text-xs mt-0.5 ${
                                event.status === 'active' ? 'text-slate-400' : 'text-slate-600'
                              }`}>
                                {event.sublabel}
                              </p>
                            </div>
                            <div className="text-right flex-shrink-0">
                              {event.time && (
                                <p className="text-[10px] text-slate-500">{event.time}</p>
                              )}
                              <span className="text-[10px] text-slate-600">{event.cycle}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Execute button for this symbol */}
                {selectedSig.status === 'idle' && (
                  <div className="mt-6 p-4 rounded-xl border border-blue-500/30 bg-blue-600/5">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <p className="text-sm font-semibold text-white">
                          {selectedSig.direction === 'BUY' ? 'Buy' : 'Sell'} {selectedSig.symbol}
                        </p>
                        <p className="text-xs text-slate-400 mt-0.5">
                          LTP ₹{selectedSig.ltp.toLocaleString('en-IN')} • Qty {selectedSig.quantity}
                        </p>
                      </div>
                      <button
                        onClick={() => setTradeModal(selectedSig.symbol)}
                        className={`px-5 py-2 rounded-xl text-sm font-semibold transition ${
                          selectedSig.direction === 'BUY'
                            ? 'bg-green-600 hover:bg-green-700 text-white'
                            : 'bg-red-600 hover:bg-red-700 text-white'
                        }`}
                      >
                        {selectedSig.direction === 'BUY' ? 'Buy' : 'Sell'}
                      </button>
                    </div>

                    {/* Indicator values */}
                    {originalSig && Object.keys(originalSig.indicators).length > 0 && (
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(originalSig.indicators).map(([k, v]) => (
                          <span key={k} className="px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 border border-slate-700">
                            {k}: {v}
                          </span>
                        ))}
                        {originalSig.atr != null && (
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-[10px] text-slate-300 border border-slate-700">
                            ATR: {originalSig.atr}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Order result */}
                {selectedSig.status === 'done' && selectedSig.order && (
                  <div className="mt-6 p-4 rounded-xl border border-green-500/30 bg-green-500/5">
                    <div className="flex items-center gap-2 mb-2">
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <span className="text-sm font-semibold text-green-300">Order Placed</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="text-slate-500">Order ID</span>
                        <p className="text-white font-mono text-[11px] mt-0.5">{selectedSig.order.order_id}</p>
                      </div>
                      <div>
                        <span className="text-slate-500">Fill Price</span>
                        <p className="text-white font-semibold mt-0.5">₹{selectedSig.order.fill_price?.toLocaleString('en-IN')}</p>
                      </div>
                      <div>
                        <span className="text-slate-500">Status</span>
                        <p className="text-green-400 font-medium mt-0.5">{selectedSig.order.status}</p>
                      </div>
                      <div>
                        <span className="text-slate-500">Qty</span>
                        <p className="text-white font-medium mt-0.5">{selectedSig.quantity}</p>
                      </div>
                    </div>
                  </div>
                )}

                {selectedSig.status === 'failed' && (
                  <div className="mt-6 p-4 rounded-xl border border-red-500/30 bg-red-500/5">
                    <div className="flex items-center gap-2 mb-1">
                      <AlertCircle className="w-4 h-4 text-red-400" />
                      <span className="text-sm font-semibold text-red-300">Execution Failed</span>
                    </div>
                    <p className="text-xs text-slate-400">{selectedSig.order?.error || 'Unknown error'}</p>
                    <button
                      onClick={() => {
                        setSignals(prev => prev.map(s =>
                          s.symbol === selectedSig.symbol
                            ? { ...s, status: 'idle', events: buildInitialEvents(s.direction) }
                            : s
                        ));
                      }}
                      className="mt-2 flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                    >
                      <RefreshCw className="w-3 h-3" /> Retry
                    </button>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <Zap className="w-12 h-12 text-slate-700 mx-auto mb-3" />
              <p className="text-slate-400 text-sm">Select an instrument to view its execution timeline</p>
            </div>
          </div>
        )}
      </div>
    </div>

    {tradeModal && (() => {
      const modalSig = signals.find(s => s.symbol === tradeModal);
      const origModalSig = scanResult.signals.find(s => s.symbol === tradeModal);
      if (!modalSig) return null;
      return (
        <TradeModal
          symbol={tradeModal}
          direction={scanResult.direction}
          ltp={modalSig.ltp}
          defaultQty={origModalSig?.suggested_quantity ?? modalSig.quantity}
          onConfirm={(sym, qty) => {
            setTradeModal(null);
            executeOne(sym, qty);
          }}
          onClose={() => setTradeModal(null)}
        />
      );
    })()}
    </>
  );
};

export default ScannerExecution;
