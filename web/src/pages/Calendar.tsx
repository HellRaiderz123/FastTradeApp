import React, { useState } from 'react';
import EconomicCalendar from '../components/EconomicCalendar';
import TradeCalendar from '../components/TradeCalendar';
import { Calendar as CalendarIcon, TrendingUp } from 'lucide-react';

type Tab = 'trades' | 'economic';

const Calendar: React.FC = () => {
  const [tab, setTab] = useState<Tab>('trades');

  return (
    <div className="h-full flex flex-col gap-6">
      {/* Header */}
      <div className="terminal-panel rounded-2xl px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Calendar</p>
            <h1 className="terminal-title text-3xl text-white">
              {tab === 'trades' ? 'Trade P&L Calendar' : 'Economic Calendar'}
            </h1>
          </div>
          {tab === 'trades' ? (
            <TrendingUp size={24} className="text-emerald-400" />
          ) : (
            <CalendarIcon size={24} className="text-emerald-400" />
          )}
        </div>
        <p className="text-sm text-slate-400 mt-2">
          {tab === 'trades'
            ? 'Daily P&L, trade count, and monthly performance at a glance'
            : 'Earnings, RBI policy, economic data, IPOs, dividends, and corporate actions'}
        </p>

        {/* Tabs */}
        <div className="flex gap-2 mt-4">
          {(['trades', 'economic'] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
                tab === t
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              {t === 'trades' ? '📈 Trade Calendar' : '📅 Economic Calendar'}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="terminal-panel rounded-2xl p-6 overflow-auto flex-1">
        {tab === 'trades' ? (
          <TradeCalendar />
        ) : (
          <EconomicCalendar height={800} />
        )}
      </div>
    </div>
  );
};

export default Calendar;
