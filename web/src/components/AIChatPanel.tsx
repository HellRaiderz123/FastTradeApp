/**
 * AIChatPanel — compact embeddable chat for the Terminal.
 * Stripped-down version of AIAssistant: no voice, no playbooks, no news radar.
 * Just the chat loop + quick suggestions.
 */
import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2, X, MessageSquare, Minimize2 } from 'lucide-react';
import api from '../lib/api';
import { cn } from '@/lib/utils';

interface Message {
  role: 'user' | 'bot';
  text: string;
}

const QUICK = [
  'Pre-market game plan',
  'AI signals for watchlist',
  'Today\'s market news',
  'Review my journal',
  'Scanner signals this week',
];

interface AIChatPanelProps {
  symbol?: string;
  onClose?: () => void;
  className?: string;
}

const AIChatPanel: React.FC<AIChatPanelProps> = ({ symbol, onClose, className }) => {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: 'Hi! Ask me anything about the market, your positions, or strategies.' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || loading) return;

    const contextText = symbol ? `[Context: viewing ${symbol}] ${trimmed}` : trimmed;
    const updated: Message[] = [...messages, { role: 'user', text: trimmed }];
    setMessages(updated);
    setInput('');
    setLoading(true);

    try {
      const history = updated.slice(1).map((m) => ({
        role: m.role === 'user' ? 'user' : 'assistant',
        content: m.text,
      }));
      const { data } = await api.post('/ai-chat/query', {
        message: contextText,
        history,
        voice_mode: false,
      });
      setMessages((prev) => [...prev, { role: 'bot', text: data.answer ?? 'No response.' }]);
    } catch {
      setMessages((prev) => [...prev, { role: 'bot', text: 'Could not reach AI backend. Check connection.' }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  return (
    <div className={cn('flex flex-col bg-card border border-border rounded-xl overflow-hidden', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border shrink-0 bg-muted/30">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/15">
            <Bot className="h-3.5 w-3.5 text-primary" />
          </div>
          <span className="text-sm font-semibold text-foreground">AI Assistant</span>
          {symbol && (
            <span className="text-[10px] font-mono bg-primary/10 text-primary rounded px-1.5 py-0.5">{symbol}</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0 no-scrollbar">
        {messages.map((m, i) => (
          <div key={i} className={cn('flex gap-2', m.role === 'user' ? 'justify-end' : 'justify-start')}>
            {m.role === 'bot' && (
              <div className="h-6 w-6 shrink-0 rounded-full bg-primary/15 flex items-center justify-center mt-0.5">
                <Bot className="h-3 w-3 text-primary" />
              </div>
            )}
            <div className={cn(
              'max-w-[85%] rounded-xl px-3 py-2 text-xs leading-relaxed',
              m.role === 'user'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted/60 text-foreground border border-border/60'
            )}>
              {m.text}
            </div>
            {m.role === 'user' && (
              <div className="h-6 w-6 shrink-0 rounded-full bg-muted flex items-center justify-center mt-0.5">
                <User className="h-3 w-3 text-muted-foreground" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-2 justify-start">
            <div className="h-6 w-6 shrink-0 rounded-full bg-primary/15 flex items-center justify-center mt-0.5">
              <Bot className="h-3 w-3 text-primary" />
            </div>
            <div className="bg-muted/60 border border-border/60 rounded-xl px-3 py-2 flex items-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Thinking…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick suggestions */}
      <div className="px-3 pb-2 shrink-0">
        <div className="flex gap-1.5 overflow-x-auto no-scrollbar pb-1">
          {QUICK.map((q) => (
            <button
              key={q}
              onClick={() => send(q)}
              disabled={loading}
              className="shrink-0 text-[10px] px-2.5 py-1 rounded-full border border-border bg-muted/40 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="px-3 pb-3 shrink-0">
        <div className="flex gap-2 items-center rounded-lg border border-border bg-background px-3 py-2 focus-within:ring-1 focus-within:ring-ring">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && send(input)}
            placeholder="Ask anything…"
            disabled={loading}
            className="flex-1 bg-transparent text-xs text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="shrink-0 p-1 rounded-md bg-primary text-primary-foreground disabled:opacity-40 hover:opacity-90 transition-opacity"
          >
            <Send className="h-3 w-3" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AIChatPanel;
