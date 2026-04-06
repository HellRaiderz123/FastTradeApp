import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, CheckCircle, XCircle, Zap, BarChart3, ClipboardList, Target, ArrowRight, Mic, MicOff, Volume2, VolumeX, ShieldAlert } from 'lucide-react';
import axios from 'axios';

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
  close_position: 'Position Closed',
  place_trade: 'Trade Placed',
  trade_confirmation_required: 'Confirmation Required',
};

function ActionCard({ action }: { action: ActionResult }) {
  const ok = action.result.success;
  const label = ACTION_LABELS[action.tool] ?? action.tool.replace(/_/g, ' ');
  return (
    <div className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs mt-1 border ${
      ok ? 'bg-emerald-950 border-emerald-700 text-emerald-300' : 'bg-red-950 border-red-700 text-red-300'
    }`}>
      {ok
        ? <CheckCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-emerald-400" />
        : <XCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-red-400" />}
      <div>
        <span className="font-semibold">{label}</span>
        {ok ? (
          <span className="ml-2 opacity-80">
            {Object.entries(action.result)
              .filter(([k]) => !['success', 'action', 'id', 'requires_confirmation', 'order_preview', 'message', 'priorities', 'summary', 'trade', 'coaching_flags', 'notes', 'watchlist', 'market_sentiment', 'by_strategy', 'by_time_block', 'by_day_of_week', 'strengths', 'top_exit_reasons', 'best_trade', 'worst_trade'].includes(k))
              .map(([k, v]) => `${k.replace(/_/g, ' ')}: ${v}`)
              .join(' · ')}
          </span>
        ) : (
          <span className="ml-2">{action.result.error}</span>
        )}
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

  return null;
}

const buildTradeConfirmationPrompt = (action: ActionResult) => {
  const preview = (action.result.order_preview as Record<string, unknown> | undefined) ?? {};
  const parts = [preview.trade_action, preview.quantity, preview.symbol, preview.order_type, preview.product].filter(Boolean);
  return `Confirm and place that live order now: ${parts.join(' ')}.`;
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
  const preview = (action.result.order_preview as Record<string, unknown> | undefined) ?? {};
  if (!requiresConfirmation) return null;

  const summary = [preview.trade_action, preview.quantity, preview.symbol, preview.order_type, preview.product]
    .filter(Boolean)
    .join(' · ');

  return (
    <div className="mt-2 rounded-xl border border-amber-700 bg-amber-950/30 p-3">
      <div className="flex items-center gap-2 text-amber-300 text-xs font-semibold mb-2">
        <ShieldAlert className="w-4 h-4" /> Live trade confirmation required
      </div>
      <div className="text-xs text-slate-200 mb-3">{summary || 'Review the order preview before placing the live order.'}</div>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onConfirm(action)}
          disabled={disabled}
          className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-500 disabled:opacity-50"
        >
          Confirm & Place
        </button>
        <button
          onClick={onCancel}
          disabled={disabled}
          className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-200 text-xs font-semibold border border-slate-700 hover:bg-slate-700 disabled:opacity-50"
        >
          Cancel
        </button>
      </div>
    </div>
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
  'What is my profit factor?',
];

export default function AIAssistant() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: 'Jarvis mode is online. I can speak replies, manage FastTrade actions, and keep live trade placement behind explicit confirmation. Try: "Build my pre-market game plan" or "Buy 1 share of TCS as a dry run".' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [jarvisMode, setJarvisMode] = useState(true);
  const [isListening, setIsListening] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  useEffect(() => {
    if (!voiceEnabled || typeof window === 'undefined' || !('speechSynthesis' in window)) {
      return;
    }
    const last = messages[messages.length - 1];
    if (!last || last.role !== 'bot') return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(last.text);
    utterance.lang = 'en-IN';
    utterance.rate = jarvisMode ? 1.02 : 1;
    utterance.pitch = 0.95;
    window.speechSynthesis.speak(utterance);

    return () => window.speechSynthesis.cancel();
  }, [messages, voiceEnabled, jarvisMode]);

  const startListening = () => {
    if (typeof window === 'undefined') return;
    const SpeechRecognitionCtor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognitionCtor) {
      window.alert('Speech recognition is not supported in this browser. Use Chrome/Edge, or type your command.');
      return;
    }

    try {
      const recognition = new SpeechRecognitionCtor();
      recognitionRef.current = recognition;
      recognition.lang = 'en-IN';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onstart = () => setIsListening(true);
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => {
        setIsListening(false);
        window.alert('I could not catch that clearly. Please try again.');
      };
      recognition.onresult = (event: any) => {
        const transcript = Array.from(event?.results || [])
          .map((result: any) => result?.[0]?.transcript || '')
          .join(' ')
          .trim();
        if (transcript) {
          setInput(transcript);
          void send(transcript);
        }
      };
      recognition.start();
    } catch {
      setIsListening(false);
      window.alert('Voice recognition could not be started.');
    }
  };

  const stopListening = () => {
    recognitionRef.current?.stop?.();
    setIsListening(false);
  };

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const updatedMessages = [...messages, { role: 'user' as const, text }];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);
    try {
      const history = updatedMessages
        .slice(1)
        .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text }));
      const { data } = await axios.post('/api/ai-chat/query', {
        message: text,
        history,
        voice_mode: voiceEnabled || jarvisMode,
        assistant_style: jarvisMode ? 'jarvis' : undefined,
      });
      setMessages(prev => [...prev, {
        role: 'bot',
        text: data.answer,
        table: data.table,
        actions: data.actions?.length ? data.actions : undefined,
      }]);
    } catch {
      setMessages(prev => [...prev, { role: 'bot', text: 'Failed to reach server.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-3xl mx-auto">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-white flex items-center gap-2">
          <Bot className="w-6 h-6 text-blue-400" /> AI Trade Assistant
          <span className="ml-2 flex items-center gap-1 text-xs font-normal text-emerald-400 bg-emerald-950 border border-emerald-700 px-2 py-0.5 rounded-full">
            <Zap className="w-3 h-3" /> Agentic
          </span>
        </h1>
        <p className="text-slate-400 text-sm mt-1">Jarvis-style voice copilot with full FastTrade actions and confirmation-gated live orders.</p>
        <div className="flex flex-wrap gap-2 mt-3">
          <button
            onClick={() => setJarvisMode(prev => !prev)}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border ${jarvisMode ? 'bg-blue-600/20 border-blue-500 text-blue-200' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
          >
            {jarvisMode ? '🤖 Jarvis ON' : '🤖 Jarvis OFF'}
          </button>
          <button
            onClick={() => {
              if (voiceEnabled && typeof window !== 'undefined' && 'speechSynthesis' in window) window.speechSynthesis.cancel();
              setVoiceEnabled(prev => !prev);
            }}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border flex items-center gap-1 ${voiceEnabled ? 'bg-emerald-600/20 border-emerald-500 text-emerald-200' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
          >
            {voiceEnabled ? <Volume2 className="w-3.5 h-3.5" /> : <VolumeX className="w-3.5 h-3.5" />}
            {voiceEnabled ? 'Voice ON' : 'Voice OFF'}
          </button>
          <button
            onClick={isListening ? stopListening : startListening}
            className={`px-3 py-1.5 rounded-full text-xs font-semibold border flex items-center gap-1 ${isListening ? 'bg-amber-600/20 border-amber-500 text-amber-200' : 'bg-slate-800 border-slate-700 text-slate-300'}`}
          >
            {isListening ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
            {isListening ? 'Listening…' : 'Speak'}
          </button>
        </div>
      </div>

      {/* AI Playbooks */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
        {PLAYBOOKS.map((playbook) => {
          const Icon = playbook.icon;
          return (
            <button
              key={playbook.title}
              onClick={() => send(playbook.prompt)}
              disabled={loading}
              className={`text-left rounded-2xl border bg-gradient-to-br ${playbook.accent} p-4 hover:scale-[1.01] hover:border-slate-500 transition disabled:opacity-60`}
            >
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="w-10 h-10 rounded-xl bg-slate-900/70 border border-slate-700 flex items-center justify-center">
                  <Icon className="w-5 h-5 text-white" />
                </div>
                <ArrowRight className="w-4 h-4 text-slate-400 flex-shrink-0" />
              </div>
              <h3 className="text-sm font-semibold text-white">{playbook.title}</h3>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">{playbook.description}</p>
              <div className="mt-3 text-[11px] text-blue-300">{playbook.prompt}</div>
            </button>
          );
        })}
      </div>

      {/* Chat window */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0" style={{ maxHeight: 'calc(100vh - 360px)' }}>
        {messages.map((m, i) => (
          <div key={i} className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {m.role === 'bot' && (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                <Bot className="w-4 h-4 text-white" />
              </div>
            )}
            <div className={`max-w-xl ${m.role === 'user' ? 'order-first' : ''}`}>
              <div className={`rounded-xl px-4 py-3 text-sm whitespace-pre-wrap ${
                m.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-100'
              }`}>
                {m.text}
              </div>
              {m.actions && m.actions.length > 0 && (
                <div className="mt-2 space-y-1">
                  {m.actions.map((a, ai) => (
                    <React.Fragment key={ai}>
                      <ActionCard action={a} />
                      <TradeConfirmationCard
                        action={a}
                        onConfirm={(action) => send(buildTradeConfirmationPrompt(action))}
                        onCancel={() => send('Cancel that pending trade. Do not place the live order.')}
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
                      <tr>{Object.keys(m.table[0]).map(k => <th key={k} className="px-3 py-2 text-left capitalize">{k.replace(/_/g, ' ')}</th>)}</tr>
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
          </div>
        ))}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div className="bg-slate-800 rounded-xl px-4 py-3">
              <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Suggestions */}
      <div className="mb-3">
        <div className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">More quick actions</div>
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map(s => (
            <button key={s} onClick={() => send(s)}
              className="text-xs px-3 py-1.5 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 transition">
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          placeholder="Ask a question or give a command..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send(input)}
          disabled={loading}
        />
        <button
          onClick={isListening ? stopListening : startListening}
          disabled={loading}
          className="px-4 py-3 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 rounded-xl transition border border-slate-700"
          title={isListening ? 'Stop listening' : 'Speak a command'}
        >
          {isListening ? <MicOff className="w-4 h-4 text-amber-300" /> : <Mic className="w-4 h-4 text-slate-200" />}
        </button>
        <button onClick={() => send(input)} disabled={loading || !input.trim()}
          className="px-4 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-xl transition">
          <Send className="w-4 h-4 text-white" />
        </button>
      </div>
    </div>
  );
}
