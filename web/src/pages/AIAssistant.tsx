import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import axios from 'axios';

const API = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

interface TableRow { [key: string]: string }
interface Message {
  role: 'user' | 'bot';
  text: string;
  table?: TableRow[];
}

const SUGGESTIONS = [
  'Show my open positions',
  'Which strategy is performing best?',
  'Analyze my losing trades',
  'What is my win rate?',
  'Should I hold or exit my current positions?',
  'What is my total P&L this month?',
  'Which symbol made me the most money?',
  'Explain iron condor strategy',
];

export default function AIAssistant() {
  const [messages, setMessages] = useState<Message[]>([
    { role: 'bot', text: 'Hi! I have full access to your trade data and can answer anything.\nAsk me about your positions, P&L, strategy performance, or any trading concept.' },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const updatedMessages = [...messages, { role: 'user' as const, text }];
    setMessages(updatedMessages);
    setInput('');
    setLoading(true);
    try {
      // Build history for multi-turn context (exclude initial bot greeting)
      const history = updatedMessages
        .slice(1)
        .map(m => ({ role: m.role === 'user' ? 'user' : 'assistant', content: m.text }));
      const { data } = await axios.post(`${API}/ai-chat/query`, { message: text, history });
      setMessages(prev => [...prev, { role: 'bot', text: data.answer, table: data.table }]);
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
        </h1>
        <p className="text-slate-400 text-sm mt-1">Ask questions about your trades in plain English.</p>
      </div>

      {/* Chat window */}
      <div className="flex-1 overflow-y-auto space-y-4 mb-4 min-h-0" style={{ maxHeight: 'calc(100vh - 280px)' }}>
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
      <div className="flex flex-wrap gap-2 mb-3">
        {SUGGESTIONS.map(s => (
          <button key={s} onClick={() => send(s)}
            className="text-xs px-3 py-1.5 rounded-full bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700 transition">
            {s}
          </button>
        ))}
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          className="flex-1 bg-slate-800 border border-slate-700 rounded-xl px-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          placeholder="Ask about your trades..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send(input)}
          disabled={loading}
        />
        <button onClick={() => send(input)} disabled={loading || !input.trim()}
          className="px-4 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-xl transition">
          <Send className="w-4 h-4 text-white" />
        </button>
      </div>
    </div>
  );
}
