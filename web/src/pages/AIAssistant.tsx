import AIAnalysis from './AIAnalysis';
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Send, Bot, User, Loader2, CheckCircle, XCircle, Zap, BarChart3, ClipboardList, Target, ArrowRight, Mic, MicOff, Volume2, VolumeX, ShieldAlert, Newspaper, TrendingUp, ChevronDown, ChevronUp, RefreshCw, Radio, Activity, Cpu, Gauge, Sparkles } from 'lucide-react';
import axios from 'axios';
import { AnimatePresence, motion } from 'framer-motion';

interface TableRow { [key: string]: string }

interface ActionResult {
  tool: string;
  args: Record<string, unknown>;
  result: { success: boolean; action?: string; error?: string; [key: string]: unknown };
}

interface Message {
  role: 'user' | 'bot';
  text: string;
  table?: TableRow[];
  actions?: ActionResult[];
}

interface PlaybookItem {
  title: string;
  description: string;
  prompt: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: string;
}

type InteractionMode = 'general' | 'news' | 'trade';

const ACTION_LABELS: Record<string, string> = {
  create_budget: 'Budget Created',
  update_budget: 'Budget Updated',
  delete_budget: 'Budget Deleted',
  create_savings_goal: 'Savings Goal Created',
  update_savings_goal_progress: 'Savings Goal Updated',
  create_bill_reminder: 'Bill Reminder Added',
  mark_bill_paid: 'Bill Marked Paid',
  add_transaction: 'Transaction Added',
  get_watchlist_gameplan: 'Pre-Market Plan Ready',
  review_trade_journal: 'Journal Review Ready',
  trade_autopsy: 'Trade Autopsy Ready',
  run_scanner: 'Scanner Ran',
  get_recent_scanner_signals: 'Scanner Signals Ready',
  get_trade_cost_summary: 'Brokerage Summary Ready',
  get_market_news_summary: 'Market News Ready',
  close_position: 'Position Closed',
  place_trade: 'Trade Placed',
  trade_confirmation_required: 'Confirmation Required',
  created_watchlist: 'Watchlist Created',
  watchlist_symbol_added: 'Symbol Added',
  watchlist_symbol_removed: 'Symbol Removed',
  watchlist_remove_confirmation_required: 'Confirmation Required',
};

const OMIT_ACTION_KEYS = [
  'success', 'action', 'id', 'requires_confirmation', 'order_preview', 'confirmation_preview', 'message', 'priorities', 'summary', 'trade',
  'coaching_flags', 'notes', 'watchlist', 'market_sentiment', 'by_strategy', 'by_time_block', 'by_day_of_week',
  'strengths', 'top_exit_reasons', 'best_trade', 'worst_trade', 'headlines', 'signals', 'top_symbols', 'top_strategies',
  'sentiment_summary', 'trending_topics',
];

const formatActionValue = (value: unknown): string => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.length ? `${value.length} items` : '0 items';
  if (typeof value === 'object') {
    const rec = value as Record<string, unknown>;
    const quickOrder = [rec.trade_action, rec.quantity, rec.symbol, rec.order_type, rec.product].filter(Boolean).join(' ');
    if (quickOrder) return quickOrder;
    try {
      return JSON.stringify(value);
    } catch {
      return '[data]';
    }
  }
  return String(value);
};

const buildActionDetail = (action: ActionResult): string => {
  const result = action.result;
  if (!result.success) return String(result.error || 'Action failed.');

  if (result.action === 'simulated_trade') {
    const preview = (result.would_place as Record<string, unknown> | undefined) || {};
    const summary = [preview.trade_action, preview.quantity, preview.symbol, preview.order_type, preview.product].filter(Boolean).join(' ');
    return `dry run: true${summary ? ` · ${summary}` : ''}`;
  }

  if (action.tool === 'get_trade_cost_summary') {
    return `₹${result.total_brokerage ?? 0} brokerage in last ${result.days ?? 30}d · total costs ₹${result.total_costs ?? 0}`;
  }

  if (action.tool === 'get_recent_scanner_signals') {
    return `${result.signal_count ?? 0} signals in last ${result.days ?? 7}d`;
  }

  if (action.tool === 'get_market_news_summary') {
    return `${result.headline_count ?? 0} headlines fetched`;
  }

  const details = Object.entries(result)
    .filter(([k]) => !OMIT_ACTION_KEYS.includes(k))
    .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${formatActionValue(v)}`)
    .filter(Boolean)
    .join(' · ');

  return details || String(result.message || 'Completed.');
};

function ActionCard({ action }: { action: ActionResult }) {
  const ok = action.result.success;
  const requiresConfirmation = Boolean(action.result?.requires_confirmation);
  const baseLabel = requiresConfirmation
    ? 'Confirmation Required — click below to execute live'
    : (ACTION_LABELS[action.tool] ?? action.tool.replace(/_/g, ' '));
  const label = ok ? baseLabel : `${baseLabel} Failed`;
  const detail = requiresConfirmation ? '' : buildActionDetail(action);

  return (
    <div className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs mt-1 border ${
      requiresConfirmation
        ? 'bg-amber-950/40 border-amber-600 text-amber-300'
        : ok
          ? 'bg-emerald-950 border-emerald-700 text-emerald-300'
          : 'bg-red-950 border-red-700 text-red-300'
    }`}>
      {requiresConfirmation
        ? <ShieldAlert className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-amber-400" />
        : ok
          ? <CheckCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-emerald-400" />
          : <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-red-400" />}
      <div>
        <span className="font-semibold">{label}</span>
        {!!detail && <span className="ml-2 opacity-85">{detail}</span>}
      </div>
    </div>
  );
}

function PlaybookResultCard({ action }: { action: ActionResult }) {
  if (!action.result.success) return null;

  if (action.tool === 'get_watchlist_gameplan') {
    const watchlist = action.result.watchlist as { name?: string; symbol_count?: number } | undefined;
    const sentiment = action.result.market_sentiment as { sentiment?: string; sentiment_score?: number | string } | undefined;
    const priorities = (action.result.priorities as Array<Record<string, unknown>> | undefined) ?? [];
    const notes = (action.result.notes as string[] | undefined) ?? [];

    return (
      <div className="mt-2 rounded-xl border border-blue-800 bg-slate-900/80 p-3">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-sm font-semibold text-white">Pre-Market Summary</div>
            <div className="text-xs text-slate-400">{watchlist?.name ?? 'Watchlist'} • {watchlist?.symbol_count ?? priorities.length} symbols</div>
          </div>
          <div className="text-xs px-2 py-1 rounded-full bg-blue-950 text-blue-300 border border-blue-800">
            {sentiment?.sentiment ?? 'sentiment N/A'}{sentiment?.sentiment_score !== undefined ? ` • ${sentiment.sentiment_score}` : ''}
          </div>
        </div>
        {priorities.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="text-xs w-full">
              <thead className="bg-slate-800 text-slate-300">
                <tr>
                  <th className="px-3 py-2 text-left">Symbol</th>
                  <th className="px-3 py-2 text-left">Signals</th>
                  <th className="px-3 py-2 text-left">Direction</th>
                  <th className="px-3 py-2 text-left">Strategy</th>
                </tr>
              </thead>
              <tbody>
                {priorities.slice(0, 5).map((row, idx) => (
                  <tr key={idx} className="border-t border-slate-800 text-slate-200">
                    <td className="px-3 py-2 font-medium">{String(row.symbol ?? '-')}</td>
                    <td className="px-3 py-2">{String(row.recent_signal_count ?? 0)}</td>
                    <td className="px-3 py-2">{String(row.latest_direction ?? '-')}</td>
                    <td className="px-3 py-2">{String(row.latest_strategy ?? '-')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {notes.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-slate-300 list-disc pl-4">
            {notes.map((note, idx) => <li key={idx}>{note}</li>)}
          </ul>
        )}
      </div>
    );
  }

  if (action.tool === 'review_trade_journal') {
    const summary = (action.result.summary as Record<string, unknown> | undefined) ?? {};
    const coaching = (action.result.coaching_flags as string[] | undefined) ?? [];
    const byStrategy = (action.result.by_strategy as Array<Record<string, unknown>> | undefined) ?? [];

    const metrics: Array<[string, unknown]> = [
      ['Trades', summary.total_trades],
      ['Win Rate', summary.win_rate !== undefined ? `${summary.win_rate}%` : '-'],
      ['Expectancy', summary.expectancy !== undefined ? `₹${summary.expectancy}` : '-'],
      ['Profit Factor', summary.profit_factor ?? '-'],
    ];

    return (
      <div className="mt-2 rounded-xl border border-violet-800 bg-slate-900/80 p-3">
        <div className="text-sm font-semibold text-white mb-2">Journal Review Snapshot</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
          {metrics.map(([label, value]) => (
            <div key={String(label)} className="rounded-lg bg-slate-800 border border-slate-700 px-3 py-2">
              <div className="text-[11px] text-slate-400">{String(label)}</div>
              <div className="text-sm font-semibold text-white">{String(value)}</div>
            </div>
          ))}
        </div>
        {byStrategy.length > 0 && (
          <div className="text-xs text-slate-300 mb-2">
            <span className="text-slate-400">Top strategy:</span> {String(byStrategy[0]?.strategy ?? '-')}
            {' · '}
            <span className="text-slate-400">P&L:</span> ₹{String(byStrategy[0]?.pnl ?? '-')}
          </div>
        )}
        {coaching.length > 0 && (
          <ul className="space-y-1 text-xs text-slate-300 list-disc pl-4">
            {coaching.map((note, idx) => <li key={idx}>{note}</li>)}
          </ul>
        )}
      </div>
    );
  }

  if (action.tool === 'trade_autopsy') {
    const trade = (action.result.trade as Record<string, unknown> | undefined) ?? {};
    const strengths = (action.result.strengths as string[] | undefined) ?? [];
    const coaching = (action.result.coaching_flags as string[] | undefined) ?? [];

    return (
      <div className="mt-2 rounded-xl border border-emerald-800 bg-slate-900/80 p-3">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-sm font-semibold text-white">Trade Autopsy</div>
            <div className="text-xs text-slate-400">{String(trade.symbol ?? '-')} • {String(trade.strategy ?? '-')}</div>
          </div>
          <div className={`text-xs px-2 py-1 rounded-full border ${Number(trade.pnl ?? 0) >= 0 ? 'bg-emerald-950 text-emerald-300 border-emerald-800' : 'bg-red-950 text-red-300 border-red-800'}`}>
            P&L: ₹{String(trade.pnl ?? '-')}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
          <div className="rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-slate-300">Exit: {String(trade.exit_reason ?? '-')}</div>
          <div className="rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-slate-300">Hold: {String(trade.holding_minutes ?? '-')} min</div>
        </div>
        {strengths.length > 0 && (
          <div className="mb-2">
            <div className="text-[11px] uppercase tracking-wide text-emerald-400 mb-1">Strengths</div>
            <ul className="space-y-1 text-xs text-slate-300 list-disc pl-4">
              {strengths.map((item, idx) => <li key={idx}>{item}</li>)}
            </ul>
          </div>
        )}
        {coaching.length > 0 && (
          <div>
            <div className="text-[11px] uppercase tracking-wide text-amber-400 mb-1">Coaching notes</div>
            <ul className="space-y-1 text-xs text-slate-300 list-disc pl-4">
              {coaching.map((item, idx) => <li key={idx}>{item}</li>)}
            </ul>
          </div>
        )}
      </div>
    );
  }

  if (action.tool === 'get_market_news_summary') {
    const headlines = (action.result.headlines as Array<Record<string, unknown>> | undefined) ?? [];
    const sentiment = (action.result.sentiment_summary as Record<string, unknown> | undefined) ?? {};

    return (
      <div className="mt-2 rounded-xl border border-amber-800 bg-slate-900/80 p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-semibold text-white">Today's Market News</div>
          <div className="text-xs px-2 py-1 rounded-full bg-amber-950 text-amber-300 border border-amber-800">
            {String(action.result.headline_count ?? headlines.length)} headlines
          </div>
        </div>
        <div className="text-xs text-slate-400 mb-2">
          Bullish: {String(sentiment.bullish ?? 0)} · Bearish: {String(sentiment.bearish ?? 0)} · Neutral: {String(sentiment.neutral ?? 0)}
        </div>
        <ul className="space-y-1 text-xs text-slate-200 list-disc pl-4">
          {headlines.slice(0, 5).map((h, idx) => (
            <li key={idx}>{String(h.title ?? '-')} {h.source ? `(${String(h.source)})` : ''}</li>
          ))}
        </ul>
      </div>
    );
  }

  if (action.tool === 'get_recent_scanner_signals') {
    const signals = (action.result.signals as Array<Record<string, unknown>> | undefined) ?? [];
    return (
      <div className="mt-2 rounded-xl border border-cyan-800 bg-slate-900/80 p-3">
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-semibold text-white">Scanner Activity</div>
          <div className="text-xs px-2 py-1 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-800">
            {String(action.result.signal_count ?? signals.length)} signals
          </div>
        </div>
        <ul className="space-y-1 text-xs text-slate-300 list-disc pl-4">
          {signals.slice(0, 5).map((s, idx) => (
            <li key={idx}>{String(s.symbol ?? '-')} · {String(s.strategy ?? '-')} · {String(s.direction ?? '-')}</li>
          ))}
        </ul>
      </div>
    );
  }

  return null;
}

const buildTradeConfirmationPrompt = (action: ActionResult) => {
  const orderPreview = (action.result.order_preview as Record<string, unknown> | undefined) ?? {};
  const genericPreview = (action.result.confirmation_preview as Record<string, unknown> | undefined) ?? {};

  if (orderPreview.trade_action) {
    const parts = [orderPreview.trade_action, orderPreview.quantity, orderPreview.symbol, orderPreview.order_type, orderPreview.product].filter(Boolean);
    return `Confirm and place that live order now: ${parts.join(' ')}.`;
  }

  const op = String(genericPreview.operation || action.result.action || '').toLowerCase();
  const symbol = String(genericPreview.symbol || '').toUpperCase();
  const wl = String(genericPreview.watchlist || '').trim();
  if (op.includes('remove_watchlist_symbol') && symbol) {
    return wl
      ? `Yes, confirm remove ${symbol} from watchlist ${wl}.`
      : `Yes, confirm remove ${symbol} from the watchlist.`;
  }
  return 'Yes, confirmed. Please proceed.';
};

function TradeConfirmationCard({
  action,
  onConfirm,
  onCancel,
  disabled,
}: {
  action: ActionResult;
  onConfirm: (action: ActionResult) => void;
  onCancel: () => void;
  disabled: boolean;
}) {
  const requiresConfirmation = Boolean(action.result?.requires_confirmation);
  const preview = ((action.result.order_preview as Record<string, unknown> | undefined)
    ?? (action.result.confirmation_preview as Record<string, unknown> | undefined)
    ?? {});
  if (!requiresConfirmation) return null;

  const isTrade = Boolean(preview.trade_action);
  const summary = isTrade
    ? [preview.trade_action, preview.quantity, preview.symbol, preview.order_type, preview.product].filter(Boolean).join(' · ')
    : [preview.operation, preview.symbol, preview.watchlist].filter(Boolean).join(' · ');

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      className="mt-3 rounded-2xl border-2 border-amber-500 bg-gradient-to-br from-amber-950/60 to-orange-950/40 p-4 shadow-[0_0_24px_rgba(245,158,11,0.25)]"
    >
      <div className="flex items-center gap-2 mb-1">
        <motion.div
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        >
          <ShieldAlert className="w-5 h-5 text-amber-400" />
        </motion.div>
        <span className="text-amber-300 text-sm font-bold">Confirmation Required</span>
      </div>
      <p className="text-xs text-amber-200/80 mb-3">
        {isTrade
          ? 'This order has NOT been placed yet. Click Confirm & Place Live below to execute on Zerodha. Make sure Zerodha is connected in Settings.'
          : 'This action has not been applied yet. Click Confirm to proceed.'}
      </p>
      {summary && (
        <div className="rounded-xl border border-amber-700/60 bg-black/30 px-3 py-2 text-sm font-mono text-amber-100 mb-3">
          {summary}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <motion.button
          onClick={() => onConfirm(action)}
          disabled={disabled}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          className="px-4 py-2 rounded-xl bg-amber-500 text-slate-950 text-sm font-bold hover:bg-amber-400 disabled:opacity-50 shadow-lg"
        >
          {isTrade ? '✓ Confirm & Place Live' : '✓ Confirm'}
        </motion.button>
        <button
          onClick={onCancel}
          disabled={disabled}
          className="px-4 py-2 rounded-xl bg-slate-800 text-slate-200 text-sm font-semibold border border-slate-600 hover:bg-slate-700 disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </motion.div>
  );
}

const PLAYBOOKS: PlaybookItem[] = [
  {
    title: 'Pre-Market Plan',
    description: 'Rank your watchlist using signals, sentiment, and current exposure.',
    prompt: 'Build my pre-market game plan',
    icon: BarChart3,
    accent: 'from-blue-600/20 to-cyan-600/10 border-blue-500/30',
  },
  {
    title: 'Journal Review',
    description: 'Summarize the last 30 days and highlight strengths and repeated mistakes.',
    prompt: 'Review my journal for the last 30 days',
    icon: ClipboardList,
    accent: 'from-violet-600/20 to-fuchsia-600/10 border-violet-500/30',
  },
  {
    title: 'Trade Autopsy',
    description: 'Coach a recent trade with exit-discipline and risk-control notes.',
    prompt: 'Do a trade autopsy on my last closed trade',
    icon: Target,
    accent: 'from-emerald-600/20 to-teal-600/10 border-emerald-500/30',
  },
];

const SUGGESTIONS = [
  'Analyze my strategy performance',
  'Build my pre-market game plan',
  'Buy 1 share of TCS at market price as a dry run',
  'What scanner signals fired this week?',
  'How much am I spending on brokerage?',
  "today's market news summary",
  'Show me trending market topics',
  'What is my profit factor?',
  'Give me geopolitical impact on NIFTY and crude',
  'Which open positions should be hedged first?',
  'Generate a 3-step pre-open execution checklist',
  'Create my capital-at-risk plan for today',
];

const detectInteractionMode = (text: string): InteractionMode => {
  const q = (text || '').toLowerCase();
  if (/(news|headline|sentiment|market update|breaking|macro|rbi|fed|fii|dii)/i.test(q)) {
    return 'news';
  }
  if (/(buy|sell|trade|position|exit|order|hedge|pnl|sl|tp)/i.test(q)) {
    return 'trade';
  }
  return 'general';
};

const MODE_STYLES: Record<InteractionMode, { ring: string; badge: string; title: string; subtitle: string }> = {
  general: {
    ring: 'from-blue-500/20 via-cyan-500/10 to-transparent',
    badge: 'border-blue-700 bg-blue-950/40 text-blue-200',
    title: 'Jarvis Core',
    subtitle: 'Context synthesis and response generation',
  },
  news: {
    ring: 'from-orange-500/20 via-amber-500/10 to-transparent',
    badge: 'border-amber-700 bg-amber-950/40 text-amber-200',
    title: 'News Intelligence Mode',
    subtitle: 'Scanning sentiment, headlines, and market catalysts',
  },
  trade: {
    ring: 'from-emerald-500/20 via-teal-500/10 to-transparent',
    badge: 'border-emerald-700 bg-emerald-950/40 text-emerald-200',
    title: 'Execution Control Mode',
    subtitle: 'Validating risk gates and order intent',
  },
};

function JarvisThinkingCard({ mode, prompt }: { mode: InteractionMode; prompt: string }) {
  const style = MODE_STYLES[mode];
  const phases =
    mode === 'news'
      ? ['Pulling latest feeds', 'Scoring market sentiment', 'Building concise briefing']
      : mode === 'trade'
        ? ['Validating intent details', 'Checking risk and broker state', 'Preparing action response']
        : ['Understanding your request', 'Linking account context', 'Composing Jarvis response'];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      className={`relative overflow-hidden rounded-2xl border border-slate-700 bg-gradient-to-br ${style.ring} p-4`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] border ${style.badge}`}>{style.title}</div>
          <div className="text-sm text-slate-100 mt-2 font-medium">{style.subtitle}</div>
          {prompt && <div className="text-xs text-slate-400 mt-1 truncate max-w-[460px]">Query: {prompt}</div>}
        </div>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'linear' }}
          className="h-8 w-8 rounded-full border border-slate-600 flex items-center justify-center"
        >
          <Loader2 className="w-4 h-4 text-slate-300" />
        </motion.div>
      </div>

      <div className="mt-3 space-y-2">
        {phases.map((phase, idx) => (
          <motion.div
            key={phase}
            initial={{ opacity: 0.2, x: -8 }}
            animate={{ opacity: [0.35, 1, 0.35], x: [0, 2, 0] }}
            transition={{ duration: 1.8, repeat: Infinity, delay: idx * 0.25 }}
            className="h-8 rounded-lg border border-slate-700 bg-slate-900/60 px-3 flex items-center text-xs text-slate-300"
          >
            {phase}
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}

// ─── Typewriter hook ────────────────────────────────────────────────────────
function useTypewriter(text: string, speed = 14): string {
  const [displayed, setDisplayed] = useState('');
  useEffect(() => {
    if (!text) { setDisplayed(''); return; }
    setDisplayed('');
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) clearInterval(interval);
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);
  return displayed;
}

// ─── BotMessage with typewriter on latest message ───────────────────────────
function BotMessageText({ text, isLatest }: { text: string; isLatest: boolean }) {
  const displayed = useTypewriter(isLatest ? text : '', 12);
  return <span className="whitespace-pre-wrap">{isLatest ? displayed : text}</span>;
}

// ─── News Radar Panel ────────────────────────────────────────────────────────
interface NewsHeadline { title: string; source?: string; sentiment?: string; link?: string; description?: string }
interface TrendingTopic { keyword: string; sentiment?: string | number; count?: number; mentions?: number }
interface NewsAlert { type?: string; message?: string; priority?: string }

function NewsRadarPanel() {
  const [headlines, setHeadlines] = useState<NewsHeadline[]>([]);
  const [trending, setTrending] = useState<TrendingTopic[]>([]);
  const [alerts, setAlerts] = useState<NewsAlert[]>([]);
  const [fetching, setFetching] = useState(true);
  const [liveConnected, setLiveConnected] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchNews = useCallback(async () => {
    setFetching(true);
    try {
      const [feedResp, trendResp, alertResp] = await Promise.all([
        axios.get('/api/news/feed').catch(() => ({ data: {} })),
        axios.get('/api/news/trending').catch(() => ({ data: {} })),
        axios.get('/api/news/alerts').catch(() => ({ data: {} })),
      ]);
      const newsItems: NewsHeadline[] = feedResp.data.news || [];
      const trendItems: TrendingTopic[] = trendResp.data.topics || [];
      const alertItems: NewsAlert[] = alertResp.data.alerts || [];
      if (newsItems.length) setHeadlines(newsItems.slice(0, 12));
      if (trendItems.length) setTrending(trendItems.slice(0, 8));
      if (alertItems.length) setAlerts(alertItems.slice(0, 8));
      setLastUpdated(new Date());
    } catch { /* silent */ } finally {
      setFetching(false);
    }
  }, []);

  useEffect(() => {
    fetchNews();
    const t = setInterval(fetchNews, 3 * 60 * 1000);
    return () => clearInterval(t);
  }, [fetchNews]);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof EventSource === 'undefined') return;

    const stream = new EventSource('/api/news/stream?limit=12&interval_seconds=15');

    const onNews = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data || '{}');
        const newsItems: NewsHeadline[] = Array.isArray(payload.news) ? payload.news : [];
        const alertItems: NewsAlert[] = Array.isArray(payload.alerts) ? payload.alerts : [];
        if (newsItems.length) {
          setHeadlines(newsItems.slice(0, 12));
          setFetching(false);
        }
        if (alertItems.length) {
          setAlerts(alertItems.slice(0, 8));
        }
        setLastUpdated(new Date());
        setLiveConnected(true);
      } catch {
        setLiveConnected(false);
      }
    };

    const onError = () => {
      setLiveConnected(false);
    };

    stream.addEventListener('news', onNews as EventListener);
    stream.onerror = onError;

    return () => {
      stream.removeEventListener('news', onNews as EventListener);
      stream.close();
      setLiveConnected(false);
    };
  }, []);

  // Auto-rotate active headline
  useEffect(() => {
    if (headlines.length === 0) return;
    const t = setInterval(() => setActiveIdx((i) => (i + 1) % Math.min(headlines.length, 8)), 5000);
    return () => clearInterval(t);
  }, [headlines.length]);

  const sentimentColor = (s?: string | number) => {
    if (s === null || s === undefined) return 'text-slate-400';
    if (typeof s === 'number') {
      if (s > 0.1) return 'text-emerald-400';
      if (s < -0.1) return 'text-red-400';
      return 'text-amber-400';
    }
    const sl = String(s).toLowerCase();
    if (sl.includes('bull') || sl.includes('positive')) return 'text-emerald-400';
    if (sl.includes('bear') || sl.includes('negative')) return 'text-red-400';
    return 'text-amber-400';
  };

  const sentimentBg = (s?: string | number) => {
    if (s === null || s === undefined) return 'border-slate-700 bg-slate-800/60';
    if (typeof s === 'number') {
      if (s > 0.1) return 'border-emerald-800 bg-emerald-950/40';
      if (s < -0.1) return 'border-red-900 bg-red-950/40';
      return 'border-amber-800 bg-amber-950/40';
    }
    const sl = String(s).toLowerCase();
    if (sl.includes('bull') || sl.includes('positive')) return 'border-emerald-800 bg-emerald-950/40';
    if (sl.includes('bear') || sl.includes('negative')) return 'border-red-900 bg-red-950/40';
    return 'border-amber-800 bg-amber-950/40';
  };

  const marqueeAlerts = alerts.length > 0 ? alerts : headlines.slice(0, 4).map((h) => ({ message: h.title, priority: 'medium', type: 'headline' }));

  return (
    <div className="rounded-2xl border border-amber-900/60 bg-gradient-to-br from-slate-900 to-amber-950/20 p-3 overflow-hidden shadow-[0_0_45px_rgba(245,158,11,0.08)]">
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ scale: [1, 1.25, 1] }}
            transition={{ duration: 1.6, repeat: Infinity }}
          >
            <Radio className="w-4 h-4 text-amber-400" />
          </motion.div>
          <span className="text-xs font-bold text-amber-300 uppercase tracking-widest">News Radar</span>
          {fetching && <Loader2 className="w-3 h-3 text-amber-400 animate-spin" />}
          <span className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] border ${liveConnected ? 'border-emerald-700 bg-emerald-950/50 text-emerald-300' : 'border-slate-700 bg-slate-900 text-slate-400'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${liveConnected ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
            {liveConnected ? 'Live' : 'Polling'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-[10px] text-slate-500">
              {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          )}
          <button
            onClick={fetchNews}
            disabled={fetching}
            className="p-1 rounded text-slate-500 hover:text-amber-300 transition disabled:opacity-40"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {marqueeAlerts.length > 0 && (
        <div className="mb-3 rounded-lg border border-red-900/60 bg-red-950/20 overflow-hidden">
          <div className="px-2 py-1 text-[10px] uppercase tracking-widest text-red-300 border-b border-red-900/50">Breaking Tape</div>
          <div className="relative h-7 overflow-hidden">
            <motion.div
              className="absolute whitespace-nowrap flex items-center gap-8 text-[11px] text-red-100/90 px-3 h-7"
              animate={{ x: ['0%', '-50%'] }}
              transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
            >
              {[...marqueeAlerts, ...marqueeAlerts].map((a, idx) => (
                <span key={idx} className="inline-flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
                  {a.message || '-'}
                </span>
              ))}
            </motion.div>
          </div>
        </div>
      )}

      {/* Featured headline ticker */}
      {headlines.length > 0 && (
        <div className={`relative rounded-xl border px-3 py-2 mb-3 overflow-hidden ${sentimentBg(headlines[activeIdx]?.sentiment)}`}>
          <div className="absolute top-2 right-2 flex gap-1">
            {headlines.slice(0, Math.min(headlines.length, 8)).map((_, idx) => (
              <button
                key={idx}
                onClick={() => setActiveIdx(idx)}
                className={`w-1.5 h-1.5 rounded-full transition ${idx === activeIdx ? 'bg-amber-400' : 'bg-slate-600'}`}
              />
            ))}
          </div>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeIdx}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.35 }}
            >
              <div className="text-xs text-slate-100 font-medium pr-16 leading-relaxed">
                {headlines[activeIdx]?.title}
              </div>
              {headlines[activeIdx]?.description && (
                <div className="text-[11px] text-slate-300/80 mt-1 line-clamp-2">
                  {headlines[activeIdx]?.description}
                </div>
              )}
              <div className="flex items-center gap-2 mt-1.5">
                {headlines[activeIdx]?.source && (
                  <span className="text-[10px] text-slate-400">{headlines[activeIdx].source}</span>
                )}
                {headlines[activeIdx]?.sentiment && (
                  <span className={`text-[10px] font-semibold ${sentimentColor(headlines[activeIdx].sentiment)}`}>
                    {headlines[activeIdx].sentiment}
                  </span>
                )}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      )}

      {/* Trending topics */}
      {trending.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-2">
            <TrendingUp className="w-3 h-3 text-slate-400" />
            <span className="text-[10px] uppercase tracking-widest text-slate-500">Trending</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {trending.map((t, i) => (
              <motion.span
                key={`${t.keyword}-${i}`}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.04 }}
                className={`text-[11px] px-2 py-0.5 rounded-full border cursor-default ${sentimentBg(t.sentiment)}`}
              >
                <span className={sentimentColor(t.sentiment)}>{t.keyword}</span>
                {(t.count !== undefined || t.mentions !== undefined) && ((t.count ?? t.mentions ?? 0) > 1) && (
                  <span className="ml-1 text-slate-500">×{String(t.count ?? t.mentions ?? 0)}</span>
                )}
              </motion.span>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!fetching && headlines.length === 0 && (
        <div className="flex items-center gap-2 text-xs text-slate-500 py-2">
          <Activity className="w-3.5 h-3.5" />
          No news data available. Make sure the news feed service is running.
        </div>
      )}
    </div>
  );
}

function FutureOpsPanel({
  activeMode,
  isListening,
  loading,
  onRun,
}: {
  activeMode: InteractionMode;
  isListening: boolean;
  loading: boolean;
  onRun: (prompt: string) => void;
}) {
  const [pulse, setPulse] = useState(64);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setPulse((prev) => {
        const drift = Math.round((Math.random() - 0.5) * 9);
        return Math.max(28, Math.min(96, prev + drift));
      });
    }, 2400);
    return () => window.clearInterval(timer);
  }, []);

  const modeBoost = activeMode === 'trade' ? 10 : activeMode === 'news' ? 6 : 3;
  const liveScore = Math.max(10, Math.min(100, pulse + modeBoost + (isListening ? 6 : 0) - (loading ? 3 : 0)));
  const macros = [
    'Build my risk map for today with key threats',
    'Give me geopolitical impact on NIFTY and crude',
    'Which open positions should be hedged first?',
    'Generate a 3-step pre-open execution checklist',
  ];

  return (
    <div className="rounded-2xl border border-cyan-900/50 bg-gradient-to-br from-slate-900 via-slate-900 to-cyan-950/20 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5">
          <Sparkles className="w-4 h-4 text-cyan-300" />
          <span className="text-xs font-bold text-cyan-200 uppercase tracking-widest">Future Ops Deck</span>
        </div>
        <span className="text-[10px] text-slate-500">live telemetry</span>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2">
          <div className="flex items-center justify-between text-[10px] text-slate-400">
            <span className="flex items-center gap-1"><Gauge className="w-3 h-3" /> Market Pulse</span>
            <span>{liveScore}/100</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-slate-800 overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-cyan-400 to-emerald-400"
              animate={{ width: `${liveScore}%` }}
              transition={{ duration: 0.7, ease: 'easeOut' }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-slate-700 bg-slate-900/80 px-3 py-2">
          <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
            <span className="flex items-center gap-1"><Cpu className="w-3 h-3" /> Core State</span>
            <span className={loading ? 'text-amber-300' : isListening ? 'text-emerald-300' : 'text-slate-300'}>
              {loading ? 'Thinking' : isListening ? 'Listening' : 'Ready'}
            </span>
          </div>
          <div className="flex items-center gap-1">
            {[0, 1, 2, 3, 4].map((i) => (
              <motion.span
                key={i}
                className={`h-1.5 w-1.5 rounded-full ${loading || isListening ? 'bg-cyan-300' : 'bg-slate-600'}`}
                animate={loading || isListening ? { opacity: [0.3, 1, 0.3] } : { opacity: 0.4 }}
                transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.12 }}
              />
            ))}
          </div>
        </div>
      </div>

      <div>
        <div className="text-[10px] uppercase tracking-widest text-slate-500 mb-2">High-value macros</div>
        <div className="space-y-1.5">
          {macros.map((macro) => (
            <button
              key={macro}
              onClick={() => onRun(macro)}
              disabled={loading}
              className="w-full text-left rounded-lg border border-slate-700 bg-slate-900/70 hover:bg-slate-800/80 px-2.5 py-1.5 text-[11px] text-slate-200 transition disabled:opacity-50"
            >
              {macro}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function AIAssistant() {
  const [activeTab, setActiveTab] = useState<'chat' | 'agents'>('chat');
  const readPref = (key: string, fallback: boolean): boolean => {
    if (typeof window === 'undefined') return fallback;
    const raw = window.localStorage.getItem(key);
    if (raw === null) return fallback;
    return raw === '1';
  };

  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: 'Jarvis mode is online. I can speak replies, execute FastTrade actions, and keep live orders behind explicit confirmation. Press Engage Jarvis and speak naturally.' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(() => readPref('jarvis_voice_enabled', true));
  const [jarvisMode, setJarvisMode] = useState(() => readPref('jarvis_mode_enabled', true));
  const [handsFreeMode, setHandsFreeMode] = useState(() => readPref('jarvis_hands_free_enabled', true));
  const [continuousConversation, setContinuousConversation] = useState(() => readPref('jarvis_continuous_conversation', true));
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [voiceSessionArmed, setVoiceSessionArmed] = useState(() => readPref('jarvis_voice_session_armed', true));
  const [voiceStatus, setVoiceStatus] = useState('Tap Engage Jarvis and speak your command.');
  const [activeMode, setActiveMode] = useState<InteractionMode>('general');
  const [currentPrompt, setCurrentPrompt] = useState('');
  const [responseTick, setResponseTick] = useState(0);
  const [panelTab, setPanelTab] = useState<'playbooks' | 'voice'>('playbooks');
  const [panelOpen, setPanelOpen] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);
  const manualStopRef = useRef(false);
  const lastTranscriptRef = useRef('');
  const lastSpokenMessageIndexRef = useRef(-1);
  const speechPrimedRef = useRef(false);

  const voiceStatusTone = !voiceSupported
    ? 'border-amber-800 bg-amber-950/30 text-amber-200'
    : isListening
      ? 'border-emerald-700 bg-emerald-950/30 text-emerald-200'
      : 'border-slate-700 bg-slate-950/70 text-slate-200';

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const SpeechRecognitionCtor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const supported = Boolean(SpeechRecognitionCtor);
    setVoiceSupported(supported);
    if (!supported) {
      setVoiceStatus('Voice recognition is unavailable in this browser. Use Chrome or Edge for full Jarvis mode.');
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('jarvis_voice_enabled', voiceEnabled ? '1' : '0');
    window.localStorage.setItem('jarvis_mode_enabled', jarvisMode ? '1' : '0');
    window.localStorage.setItem('jarvis_hands_free_enabled', handsFreeMode ? '1' : '0');
    window.localStorage.setItem('jarvis_continuous_conversation', continuousConversation ? '1' : '0');
    window.localStorage.setItem('jarvis_voice_session_armed', voiceSessionArmed ? '1' : '0');
  }, [voiceEnabled, jarvisMode, handsFreeMode, continuousConversation, voiceSessionArmed]);

  const primeSpeechSynthesis = () => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window) || speechPrimedRef.current) {
      return;
    }
    try {
      const seed = new SpeechSynthesisUtterance(' ');
      seed.volume = 0;
      window.speechSynthesis.speak(seed);
      speechPrimedRef.current = true;
    } catch {
      // no-op
    }
  };

  const stopListening = (manual = true) => {
    manualStopRef.current = manual;
    recognitionRef.current?.stop?.();
    setIsListening(false);
    if (manual) {
      setVoiceStatus('Jarvis is on standby. Tap Engage Jarvis to talk again.');
    }
  };

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    primeSpeechSynthesis();
    if (jarvisMode && voiceEnabled && handsFreeMode && continuousConversation) {
      setVoiceSessionArmed(true);
    }
    const mode = detectInteractionMode(text);
    setActiveMode(mode);
    setCurrentPrompt(text);
    setResponseTick((prev) => prev + 1);

    const updatedMessages = [...messages, { role: 'user' as const, text }];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);
    setVoiceStatus(`Processing: “${text}”`);
    try {
      const history = updatedMessages
        .slice(1)
        .map((m) => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text }));
      const { data } = await axios.post('/api/ai-chat/query', {
        message: text,
        history,
        voice_mode: voiceEnabled || jarvisMode,
        assistant_style: jarvisMode ? 'jarvis' : undefined,
      });
      setMessages((prev) => [...prev, {
        role: 'bot',
        text: data.answer,
        table: data.table,
        actions: data.actions?.length ? data.actions : undefined,
      }]);
      setVoiceStatus(mode === 'news' ? 'News briefing generated. Ready for the next question.' : 'Response ready. Awaiting your next command.');
    } catch {
      setMessages((prev) => [...prev, { role: 'bot', text: 'I could not reach the FastTrade AI core. Please check the backend connection and try again.' }]);
      setVoiceStatus('Connection issue. Please verify the backend is reachable.');
    } finally {
      setLoading(false);
    }
  };

  const startListening = (auto = false) => {
    primeSpeechSynthesis();
    if (typeof window === 'undefined') return;
    const SpeechRecognitionCtor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      setVoiceSupported(false);
      setVoiceStatus('Voice recognition is unavailable in this browser. Use Chrome or Edge for full Jarvis mode.');
      return;
    }
    if (loading) {
      setVoiceStatus('Hold on — I am still processing the previous request.');
      return;
    }

    if (!auto) {
      setVoiceSessionArmed(true);
    }

    manualStopRef.current = false;
    lastTranscriptRef.current = '';

    try {
      recognitionRef.current?.stop?.();
      const recognition = new SpeechRecognitionCtor();
      recognitionRef.current = recognition;
      recognition.lang = 'en-IN';
      recognition.interimResults = true;
      recognition.continuous = handsFreeMode;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => {
        setIsListening(true);
        setVoiceStatus(auto ? 'Listening for the next command…' : 'Listening… speak your FastTrade command.');
      };
      recognition.onresult = (event: any) => {
        const results = Array.from(event?.results || []);
        const transcript = results
          .map((result: any) => result?.[0]?.transcript || '')
          .join(' ')
          .trim();

        if (!transcript) return;

        lastTranscriptRef.current = transcript;
        setInput(transcript);

        const isFinal = results.some((result: any) => result?.isFinal);
        setVoiceStatus(isFinal ? `Heard: “${transcript}”` : `Listening: “${transcript}”`);

        if (isFinal) {
          recognition.stop();
          void send(transcript);
        }
      };
      recognition.onerror = (event: any) => {
        setIsListening(false);
        const code = String(event?.error || 'unknown');
        if (code === 'not-allowed' || code === 'service-not-allowed') {
          setVoiceStatus('Microphone permission is blocked. Allow microphone access in the browser.');
        } else if (code === 'no-speech') {
          setVoiceStatus('No speech detected. Try again.');
        } else {
          setVoiceStatus('Voice recognition had a problem. Try again in Chrome or Edge.');
        }
      };
      recognition.onend = () => {
        setIsListening(false);
        if (manualStopRef.current) return;

        if (voiceSessionArmed && handsFreeMode && jarvisMode && voiceSupported && continuousConversation && !loading) {
          setVoiceStatus('Conversation mode active. Listening again…');
          window.setTimeout(() => startListening(true), 380);
          return;
        }

        if (!lastTranscriptRef.current) {
          setVoiceStatus('I did not catch that. Tap Engage Jarvis and try again.');
        }
      };
      recognition.start();
    } catch {
      setIsListening(false);
      setVoiceStatus('Voice recognition could not be started.');
    }
  };

  useEffect(() => {
    if (!voiceEnabled || typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }

    const index = messages.length - 1;
    if (index < 0 || index === lastSpokenMessageIndexRef.current) return;
    const last = messages[index];
    if (!last || last.role !== 'bot') return;

    const synth = window.speechSynthesis;
    const speakText = () => {
      const utterance = new SpeechSynthesisUtterance(last.text);
      const voices = synth.getVoices?.() ?? [];
      const preferredVoice =
        voices.find((voice) => /en[-_]IN/i.test(voice.lang)) ||
        voices.find((voice) => /david|mark|daniel|male/i.test(voice.name)) ||
        voices[0];

      if (preferredVoice) {
        utterance.voice = preferredVoice;
        utterance.lang = preferredVoice.lang || 'en-IN';
      } else {
        utterance.lang = 'en-IN';
      }

      utterance.rate = jarvisMode ? 1.02 : 1;
      utterance.pitch = jarvisMode ? 0.9 : 1;
      utterance.onstart = () => setVoiceStatus('Jarvis is speaking…');
      utterance.onend = () => {
        if (voiceSessionArmed && handsFreeMode && jarvisMode && voiceSupported && continuousConversation && !manualStopRef.current) {
          setVoiceStatus('Standing by for the next command…');
          window.setTimeout(() => startListening(true), 320);
        } else {
          setVoiceStatus('Ready. Tap Engage Jarvis to speak.');
        }
      };
      utterance.onerror = () => {
        setVoiceStatus('Voice playback failed. Re-engage Jarvis to reinitialize audio.');
      };

      synth.cancel();
      synth.speak(utterance);
      lastSpokenMessageIndexRef.current = index;
    };

    const availableVoices = synth.getVoices?.() ?? [];
    if (availableVoices.length > 0) {
      speakText();
      return;
    }

    const onVoicesChanged = () => {
      synth.removeEventListener?.('voiceschanged', onVoicesChanged);
      speakText();
    };
    synth.addEventListener?.('voiceschanged', onVoicesChanged);

    const fallbackTimer = window.setTimeout(() => {
      synth.removeEventListener?.('voiceschanged', onVoicesChanged);
      speakText();
    }, 450);

    return () => {
      window.clearTimeout(fallbackTimer);
      synth.removeEventListener?.('voiceschanged', onVoicesChanged);
    };
  }, [messages, voiceEnabled, jarvisMode, handsFreeMode, voiceSupported, voiceSessionArmed, continuousConversation, loading]);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop?.();
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const engageJarvis = () => {
    primeSpeechSynthesis();
    if (isListening) {
      stopListening(true);
      return;
    }
    if (continuousConversation) {
      setVoiceSessionArmed(true);
    }
    startListening(false);
  };

  return (
    <div className="flex flex-col h-full max-w-5xl mx-auto overflow-hidden">

      {/* ── Compact header bar ── */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex-none rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 mb-3 shadow-[0_0_40px_rgba(37,99,235,0.08)]"
      >
        <div className="flex items-center gap-3 flex-wrap">
          {/* Jarvis orb */}
          <div className="relative h-10 w-10 rounded-full border border-slate-700 bg-slate-950/80 flex items-center justify-center flex-shrink-0">
            <motion.div
              className={`absolute inset-0 rounded-full bg-gradient-to-br ${MODE_STYLES[activeMode].ring}`}
              animate={{ opacity: [0.3, 0.9, 0.3], scale: [0.88, 1.1, 0.88] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
            />
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 9, repeat: Infinity, ease: 'linear' }}
              className="relative z-10 h-7 w-7 rounded-full border border-slate-500/80"
            />
            <span className="absolute z-20 h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(56,189,248,0.9)]" />
          </div>

          {/* Title + badge */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-base font-bold text-white flex items-center gap-1.5">
                <Bot className="w-4 h-4 text-blue-400" /> Jarvis Command Deck
              </h1>
              <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 bg-emerald-950 border border-emerald-700 px-1.5 py-0.5 rounded-full">
                <Zap className="w-3 h-3" /> Agentic
              </span>
              <span className={`text-[11px] px-1.5 py-0.5 rounded-full border ${MODE_STYLES[activeMode].badge}`}>
                {MODE_STYLES[activeMode].title}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 truncate">Voice-first FastTrade copilot · confirmation-gated live orders</p>
          </div>

          {/* Voice status - compact */}
          <div className={`hidden md:flex items-center gap-2 px-2 py-1 rounded-lg border text-xs max-w-[220px] truncate ${voiceStatusTone}`}>
            <span className="truncate">{voiceStatus}</span>
          </div>

          {/* Engage button */}
          <button
            onClick={engageJarvis}
            className={`flex-shrink-0 flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold transition border ${isListening ? 'bg-amber-600 border-amber-400 text-slate-950' : 'bg-blue-600 border-blue-500 text-white hover:bg-blue-500'}`}
          >
            {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            {isListening ? 'Stop Jarvis' : 'Engage Jarvis'}
          </button>

          {/* Tab switcher */}
          <div className="flex-shrink-0 flex items-center rounded-xl border border-slate-700 bg-slate-900 overflow-hidden">
            <button
              onClick={() => setActiveTab('chat')}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold transition ${activeTab === 'chat' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            >
              <Bot className="w-3.5 h-3.5" />
              Jarvis
            </button>
            <button
              onClick={() => setActiveTab('agents')}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold transition ${activeTab === 'agents' ? 'bg-blue-600 text-white' : 'text-slate-400 hover:text-slate-200'}`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              AI Agents
            </button>
          </div>

          {/* Panel toggle */}
          <button
            onClick={() => setPanelOpen((v) => !v)}
            className="flex-shrink-0 p-2 rounded-lg border border-slate-700 bg-slate-800/60 text-slate-400 hover:text-slate-200 transition"
            title={panelOpen ? 'Collapse panels' : 'Expand panels'}
          >
            {panelOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </motion.div>

      {/* ── AI Agents tab ── */}
      {activeTab === 'agents' && (
        <div className="flex-1 overflow-y-auto pr-1">
          <AIAnalysis />
        </div>
      )}

      {/* ── Chat tab content ── */}
      {activeTab === 'chat' && (
      <>
      <AnimatePresence initial={false}>
        {panelOpen && (
          <motion.div
            key="panel"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="flex-none overflow-hidden mb-3"
          >
            {/* Tab row */}
            <div className="flex gap-1 mb-2">
              {([
                { key: 'playbooks', label: 'Playbooks', icon: BarChart3 },
                { key: 'voice', label: 'Voice', icon: Mic },
              ] as const).map(({ key, label, icon: Icon }) => (
                <button
                  key={key}
                  onClick={() => setPanelTab(key)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                    panelTab === key
                      ? 'bg-slate-700 border-slate-600 text-white'
                      : 'bg-slate-900 border-slate-800 text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </button>
              ))}
            </div>

            {/* Tab: Playbooks */}
            {panelTab === 'playbooks' && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {PLAYBOOKS.map((playbook) => {
                  const Icon = playbook.icon;
                  return (
                    <motion.button
                      key={playbook.title}
                      onClick={() => send(playbook.prompt)}
                      disabled={loading}
                      whileHover={{ y: -2, scale: 1.01 }}
                      whileTap={{ scale: 0.99 }}
                      className={`text-left rounded-2xl border bg-gradient-to-br ${playbook.accent} p-3 hover:border-slate-500 transition disabled:opacity-60`}
                    >
                      <div className="flex items-start justify-between gap-3 mb-2">
                        <div className="w-8 h-8 rounded-xl bg-slate-900/70 border border-slate-700 flex items-center justify-center">
                          <Icon className="w-4 h-4 text-white" />
                        </div>
                        <ArrowRight className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
                      </div>
                      <h3 className="text-xs font-semibold text-white">{playbook.title}</h3>
                      <p className="text-[11px] text-slate-300 mt-0.5 leading-relaxed">{playbook.description}</p>
                      <div className="mt-2 text-[10px] text-blue-300">{playbook.prompt}</div>
                    </motion.button>
                  );
                })}
              </div>
            )}

            {/* Tab: Voice */}
            {panelTab === 'voice' && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-4">
                <div className="flex gap-4 flex-wrap items-center">
                  <button
                    onClick={engageJarvis}
                    className={`relative h-16 w-16 rounded-full border flex items-center justify-center transition-all shadow-lg flex-shrink-0 ${isListening ? 'border-amber-400 bg-amber-500/15 text-amber-200 shadow-amber-500/20 scale-105' : 'border-blue-500 bg-blue-500/15 text-blue-100 hover:scale-105 shadow-blue-500/20'}`}
                  >
                    <span className={`absolute inset-0 rounded-full ${isListening ? 'animate-ping bg-amber-500/20' : 'bg-blue-500/5'}`} />
                    {isListening ? <MicOff className="w-6 h-6 relative z-10" /> : <Mic className="w-6 h-6 relative z-10" />}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] uppercase tracking-widest text-slate-400 mb-1">Voice status</div>
                    <div className={`rounded-xl border px-3 py-2 text-xs ${voiceStatusTone} mb-2`}>{voiceStatus}</div>
                    <div className="flex flex-wrap gap-2">
                      <button onClick={() => setJarvisMode((p) => !p)} className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${jarvisMode ? 'bg-blue-600/20 border-blue-500 text-blue-200' : 'bg-slate-800 border-slate-700 text-slate-300'}`}>
                        {jarvisMode ? '🤖 Jarvis ON' : '🤖 Jarvis OFF'}
                      </button>
                      <button
                        onClick={() => { if (voiceEnabled && typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel(); setVoiceEnabled((p) => !p); }}
                        className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border flex items-center gap-1 ${voiceEnabled ? 'bg-emerald-600/20 border-emerald-500 text-emerald-200' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
                      >
                        {voiceEnabled ? <Volume2 className="w-3 h-3" /> : <VolumeX className="w-3 h-3" />}
                        {voiceEnabled ? 'Replies Spoken' : 'Replies Muted'}
                      </button>
                      <button onClick={() => setHandsFreeMode((p) => !p)} className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${handsFreeMode ? 'bg-violet-600/20 border-violet-500 text-violet-200' : 'bg-slate-800 border-slate-700 text-slate-300'}`}>
                        {handsFreeMode ? '🎙️ Hands-Free ON' : '🎙️ Hands-Free OFF'}
                      </button>
                      <button
                        onClick={() => setContinuousConversation((p) => !p)}
                        className={`px-2.5 py-1 rounded-full text-[11px] font-semibold border ${continuousConversation ? 'bg-cyan-600/20 border-cyan-500 text-cyan-200' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
                      >
                        {continuousConversation ? '🧠 Conversation ON' : '🧠 Conversation OFF'}
                      </button>
                    </div>
                  </div>
                  <div className="w-full md:w-auto rounded-xl border border-slate-800 bg-slate-900/80 p-3 text-xs text-slate-300">
                    <div className="font-semibold text-white mb-1">Full Jarvis flow</div>
                    <ul className="space-y-1 list-disc pl-4 text-slate-400">
                      <li>Press <span className="text-blue-300 font-semibold">Engage Jarvis</span> and speak</li>
                      <li>Replies spoken aloud, hands-free loops</li>
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Dedicated Radar + Future Deck ── */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, delay: 0.06 }}
        className="flex-none grid grid-cols-1 xl:grid-cols-[1.3fr_0.7fr] gap-3 mb-3"
      >
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Newspaper className="w-4 h-4 text-amber-300" />
            <span className="text-[11px] uppercase tracking-widest text-amber-300">Dedicated News Radar</span>
          </div>
          <NewsRadarPanel />
        </div>
        <FutureOpsPanel
          activeMode={activeMode}
          isListening={isListening}
          loading={loading}
          onRun={(prompt) => send(prompt)}
        />
      </motion.div>

      {/* ── Chat window — takes all remaining space ── */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-1 pb-2">
        {(currentPrompt || loading) && (
          <motion.div
            key={`mission-${responseTick}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className={`rounded-xl border px-3 py-2 text-xs ${MODE_STYLES[activeMode].badge}`}
          >
            <span className="uppercase tracking-[0.18em] mr-2 opacity-85">Mission feed</span>
            <span className="opacity-95">{loading ? MODE_STYLES[activeMode].subtitle : 'Last query processed successfully'}</span>
          </motion.div>
        )}

        <AnimatePresence initial={false}>
          {messages.map((m, i) => {
            const isLatestBot = m.role === 'bot' && i === messages.length - 1;
            return (
              <motion.div
                key={`${m.role}-${i}-${m.text.slice(0, 24)}`}
                initial={{ opacity: 0, y: 16, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.25 }}
                className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.role === 'bot' && (
                  <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                    <Bot className="w-4 h-4 text-white" />
                  </div>
                )}
                <div className={`max-w-xl ${m.role === 'user' ? 'order-first' : ''}`}>
                  <motion.div
                    initial={m.role === 'bot' ? { filter: 'blur(4px)', opacity: 0.7 } : false}
                    animate={m.role === 'bot' ? { filter: 'blur(0px)', opacity: 1 } : { opacity: 1 }}
                    transition={{ duration: 0.22 }}
                    className={`rounded-xl px-4 py-3 text-sm border ${
                      m.role === 'user'
                        ? 'bg-blue-600 text-white border-blue-500/60'
                        : 'bg-slate-800 text-slate-100 border-slate-700 shadow-[0_0_0_1px_rgba(51,65,85,0.15)]'
                    }`}
                  >
                    {m.role === 'bot'
                      ? <BotMessageText text={m.text} isLatest={isLatestBot} />
                      : <span className="whitespace-pre-wrap">{m.text}</span>
                    }
                  </motion.div>
                  {m.actions && m.actions.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {m.actions.map((a, ai) => (
                        <React.Fragment key={ai}>
                          <ActionCard action={a} />
                          <TradeConfirmationCard
                            action={a}
                            onConfirm={(action) => send(buildTradeConfirmationPrompt(action))}
                            onCancel={() => send('Cancel that pending action. Do not execute it.')}
                            disabled={loading}
                          />
                          <PlaybookResultCard action={a} />
                        </React.Fragment>
                      ))}
                    </div>
                  )}
                  {m.table && m.table.length > 0 && (
                    <div className="mt-2 overflow-x-auto rounded-lg border border-slate-700">
                      <table className="text-xs w-full">
                        <thead className="bg-slate-700 text-slate-300">
                          <tr>{Object.keys(m.table[0]).map((k) => <th key={k} className="px-3 py-2 text-left capitalize">{k.replace(/_/g, ' ')}</th>)}</tr>
                        </thead>
                        <tbody>
                          {m.table.map((row, ri) => (
                            <tr key={ri} className="border-t border-slate-700 hover:bg-slate-750">
                              {Object.values(row).map((v, vi) => (
                                <td key={vi} className={`px-3 py-2 ${String(v).startsWith('₹-') || String(v).startsWith('-') ? 'text-red-400' : String(v).startsWith('₹') ? 'text-green-400' : 'text-slate-300'}`}>
                                  {String(v)}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
                {m.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-slate-600 flex items-center justify-center flex-shrink-0">
                    <User className="w-4 h-4 text-white" />
                  </div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>

        <AnimatePresence>
          {loading && (
            <div className="flex gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="flex-1 max-w-xl">
                <JarvisThinkingCard mode={activeMode} prompt={currentPrompt} />
              </div>
            </div>
          )}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      {/* ── Suggestions (horizontal scroll) ── */}
      <div className="flex-none mt-2">
        <div className="flex items-center justify-between gap-3 mb-1.5">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Quick actions + AI protocols</div>
          <div className={`text-[10px] px-2 py-0.5 rounded-full border ${MODE_STYLES[activeMode].badge}`}>
            {MODE_STYLES[activeMode].title}
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
          {SUGGESTIONS.map((s) => (
            <motion.button
              key={s}
              onClick={() => send(s)}
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              className="flex-shrink-0 text-xs px-3 py-1.5 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 transition"
            >
              {s}
            </motion.button>
          ))}
        </div>
      </div>

      {/* ── Input bar ── */}
      <div className="flex-none mt-2">
        <div className="text-[10px] uppercase tracking-wide text-slate-500 mb-1.5">
          {activeMode === 'news' ? 'Ask for news insight' : 'Type or use voice above'}
        </div>
        <div className="flex gap-2">
          <input
            className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            placeholder={activeMode === 'news' ? 'Ask: what is latest market news for my watchlist?' : 'Optional typed command...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send(input)}
            disabled={loading}
          />
          <button
            onClick={engageJarvis}
            disabled={loading}
            className={`px-3 py-2.5 rounded-xl transition border ${isListening ? 'bg-amber-600/20 border-amber-500' : 'bg-slate-800 hover:bg-slate-700 border-slate-700'} disabled:opacity-40`}
          >
            {isListening ? <MicOff className="w-4 h-4 text-amber-300" /> : <Mic className="w-4 h-4 text-slate-200" />}
          </button>
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="px-3 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-xl transition"
          >
            <Send className="w-4 h-4 text-white" />
          </button>
        </div>
      </div>

      </>
      )}

      {/* ── Floating mic FAB (always visible) ── */}
      <motion.button
        onClick={engageJarvis}
        disabled={loading}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.92 }}
        animate={isListening ? { scale: [1, 1.12, 1] } : {}}
        transition={isListening ? { duration: 1, repeat: Infinity } : {}}
        className={`fixed bottom-6 right-6 z-30 h-14 w-14 rounded-full border shadow-2xl flex items-center justify-center transition ${isListening ? 'bg-amber-500 text-slate-950 border-amber-300' : 'bg-blue-600 text-white border-blue-400 hover:bg-blue-500'} disabled:opacity-50`}
        title={isListening ? 'Stop Jarvis' : 'Engage Jarvis'}
      >
        {isListening ? <MicOff className="w-6 h-6" /> : <Mic className="w-6 h-6" />}
      </motion.button>
    </div>
  );
}
