import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { SHORTCUT_LIST } from '../hooks/useKeyboardShortcuts';

interface CommandItem {
  label: string;
  path: string;
  keywords: string;
}

const COMMANDS: CommandItem[] = [
  { label: 'Terminal', path: '/', keywords: 'terminal bloomberg' },
  { label: 'Dashboard', path: '/dashboard', keywords: 'dashboard overview' },
  { label: 'Screener', path: '/screener', keywords: 'screener filter stocks' },
  { label: 'Heatmap', path: '/heatmap', keywords: 'heatmap sector' },
  { label: 'Watchlists', path: '/watchlists', keywords: 'watchlist symbols' },
  { label: 'Multi-Timeframe', path: '/multi-timeframe', keywords: 'timeframe candles' },
  { label: 'Options Chain', path: '/options', keywords: 'options chain strikes' },
  { label: 'Calendar', path: '/calendar', keywords: 'calendar events expiry' },
  { label: 'Strategies', path: '/strategies', keywords: 'strategies manage' },
  { label: 'Marketplace', path: '/marketplace', keywords: 'marketplace templates' },
  { label: 'Create Scanner', path: '/create-scanner', keywords: 'scanner condition' },
  { label: 'Auto Trader', path: '/auto-trader', keywords: 'auto trader bot' },
  { label: 'Positions', path: '/positions', keywords: 'positions open' },
  { label: 'Reconciliation', path: '/reconciliation', keywords: 'reconcile broker' },
  { label: 'Strategy P&L', path: '/strategy-pnl', keywords: 'pnl analytics equity' },
  { label: 'Journal', path: '/journal', keywords: 'journal trades history' },
  { label: 'Backtest', path: '/backtest', keywords: 'backtest historical' },
  { label: 'Compare Backtests', path: '/backtest-comparison', keywords: 'compare backtest' },
  { label: 'Trade Costs', path: '/trade-costs', keywords: 'costs brokerage charges' },
  { label: 'ML Center', path: '/ml', keywords: 'ml machine learning signals' },
  { label: 'Finance', path: '/finance', keywords: 'finance budget goals' },
  { label: 'Settings', path: '/settings', keywords: 'settings zerodha api' },
];

interface Props {
  open: boolean;
  onClose: () => void;
}

const CommandPalette: React.FC<Props> = ({ open, onClose }) => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const filtered = query.trim()
    ? COMMANDS.filter((c) =>
        `${c.label} ${c.keywords}`.toLowerCase().includes(query.toLowerCase())
      )
    : COMMANDS;

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelected(0);
  }, [query]);

  const go = (path: string) => {
    navigate(path);
    onClose();
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelected((s) => Math.min(s + 1, filtered.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setSelected((s) => Math.max(s - 1, 0)); }
    if (e.key === 'Enter' && filtered[selected]) go(filtered[selected].path);
    if (e.key === 'Escape') onClose();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-700">
          <Search size={18} className="text-slate-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Search pages..."
            className="flex-1 bg-transparent text-white placeholder-slate-500 focus:outline-none text-sm"
          />
          <button onClick={onClose} className="text-slate-500 hover:text-white transition">
            <X size={16} />
          </button>
        </div>

        {/* Results */}
        <div className="max-h-72 overflow-y-auto">
          {filtered.length === 0 ? (
            <p className="text-center text-slate-500 py-8 text-sm">No results</p>
          ) : (
            filtered.map((cmd, i) => (
              <button
                key={cmd.path}
                onClick={() => go(cmd.path)}
                onMouseEnter={() => setSelected(i)}
                className={`w-full text-left px-4 py-2.5 text-sm transition flex items-center gap-3 ${
                  i === selected ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                {cmd.label}
              </button>
            ))
          )}
        </div>

        {/* Shortcuts reference */}
        <div className="border-t border-slate-700 px-4 py-3">
          <p className="text-xs text-slate-500 mb-2 font-semibold uppercase tracking-wide">Keyboard Shortcuts</p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1">
            {SHORTCUT_LIST.map((s) => (
              <div key={s.key} className="flex items-center justify-between">
                <span className="text-xs text-slate-400">{s.label}</span>
                <kbd className="text-xs bg-slate-800 border border-slate-600 rounded px-1.5 py-0.5 text-slate-300 font-mono">{s.key}</kbd>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CommandPalette;
