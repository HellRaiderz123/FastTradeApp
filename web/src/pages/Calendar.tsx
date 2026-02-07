import React from 'react';
import EconomicCalendar from '../components/EconomicCalendar';
import { Calendar as CalendarIcon } from 'lucide-react';

const Calendar: React.FC = () => {
  return (
    <div className="h-full flex flex-col gap-6">
      {/* Page Header */}
      <div className="terminal-panel rounded-2xl px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Market Events</p>
            <h1 className="terminal-title text-3xl text-white">Economic Calendar</h1>
          </div>
          <CalendarIcon size={24} className="text-emerald-400" />
        </div>
        <p className="text-sm text-slate-400 mt-2">
          Track earnings, RBI policy, economic data, IPOs, dividends, and corporate actions
        </p>
      </div>

      {/* Economic Calendar Component */}
      <div className="terminal-panel rounded-2xl p-6 overflow-hidden">
        <EconomicCalendar height={800} />
      </div>
    </div>
  );
};

export default Calendar;
