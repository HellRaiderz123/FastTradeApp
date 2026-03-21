import React, { useState, useEffect, useMemo } from 'react';
import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { journalAPI } from '../lib/api';

interface RawIntent {
  id: number;
  intent_id: string;
  strategy: string;
  underlying: string;
  created_at: string;
  closed_at?: string | null;
  entry_credit?: number | null;
  pnl?: number | null;
  status: string;
  execution_result?: any;
  ticket?: any;
}

interface DayData {
  pnl: number;
  trades: number;
  wins: number;
  losses: number;
  items: { underlying: string; strategy: string; pnl: number }[];
}

const fmt = (v: number) => {
  const sign = v >= 0 ? '+' : '';
  return `${sign}₹${Math.abs(v).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
};

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const DAYS = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];

const TradeCalendar: React.FC = () => {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth()); // 0-indexed
  const [dayMap, setDayMap] = useState<Record<string, DayData>>({});
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    journalAPI.getExecutionIntents(500).then((res) => {
      const data: RawIntent[] = Array.isArray(res.data) ? res.data : [];
      const map: Record<string, DayData> = {};

      data.forEach((item) => {
        // Use closed_at for closed trades, created_at for open/dry-run
        const dateStr = item.closed_at || item.created_at;
        if (!dateStr) return;
        const pnl = Number(item.pnl ?? 0);
        const key = dateStr.slice(0, 10); // YYYY-MM-DD

        if (!map[key]) map[key] = { pnl: 0, trades: 0, wins: 0, losses: 0, items: [] };
        map[key].pnl += pnl;
        map[key].trades += 1;
        if (pnl > 0) map[key].wins += 1;
        else if (pnl < 0) map[key].losses += 1;
        map[key].items.push({ underlying: item.underlying, strategy: item.strategy, pnl });
      });

      setDayMap(map);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const prevMonth = () => {
    if (month === 0) { setMonth(11); setYear(y => y - 1); }
    else setMonth(m => m - 1);
    setSelectedDay(null);
  };
  const nextMonth = () => {
    if (month === 11) { setMonth(0); setYear(y => y + 1); }
    else setMonth(m => m + 1);
    setSelectedDay(null);
  };

  // Build calendar grid
  const { cells, monthStats } = useMemo(() => {
    const firstDay = new Date(year, month, 1).getDay(); // 0=Sun
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const cells: (string | null)[] = Array(firstDay).fill(null);
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push(`${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
    }
    // Pad to complete last row
    while (cells.length % 7 !== 0) cells.push(null);

    // Monthly summary
    let totalPnl = 0, totalTrades = 0, wins = 0, losses = 0;
    const prefix = `${year}-${String(month + 1).padStart(2, '0')}`;
    Object.entries(dayMap).forEach(([k, v]) => {
      if (k.startsWith(prefix)) {
        totalPnl += v.pnl;
        totalTrades += v.trades;
        wins += v.wins;
        losses += v.losses;
      }
    });

    return { cells, monthStats: { totalPnl, totalTrades, wins, losses } };
  }, [year, month, dayMap]);

  const selectedData = selectedDay ? dayMap[selectedDay] : null;
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

  return (
    <div className="space-y-4">
      {/* Header nav */}
      <div className="flex items-center justify-between">
        <button onClick={prevMonth} className="p-2 rounded-lg hover:bg-slate-800 transition text-slate-300">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <h2 className="text-xl font-bold text-white">{MONTHS[month]} {year}</h2>
        <button onClick={nextMonth} className="p-2 rounded-lg hover:bg-slate-800 transition text-slate-300">
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>

      {loading ? (
        <div className="text-center py-16 text-slate-400">Loading trades...</div>
      ) : (
        <>
          {/* Day-of-week headers */}
          <div className="grid grid-cols-7 gap-1 mb-1">
            {DAYS.map(d => (
              <div key={d} className="text-center text-xs font-semibold text-slate-500 py-1">{d}</div>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="grid grid-cols-7 gap-1">
            {cells.map((dateKey, i) => {
              if (!dateKey) return <div key={i} />;
              const day = parseInt(dateKey.slice(8), 10);
              const data = dayMap[dateKey];
              const isToday = dateKey === todayKey;
              const isSelected = dateKey === selectedDay;
              const hasTrades = !!data;
              const profit = hasTrades && data.pnl > 0;
              const loss = hasTrades && data.pnl < 0;

              return (
                <button
                  key={dateKey}
                  onClick={() => setSelectedDay(isSelected ? null : dateKey)}
                  className={`
                    relative rounded-lg p-1.5 min-h-[72px] flex flex-col text-left transition border
                    ${isSelected ? 'ring-2 ring-blue-400 border-blue-400/50' : 'border-slate-700/50'}
                    ${profit ? 'bg-emerald-950/60 hover:bg-emerald-900/60' : ''}
                    ${loss ? 'bg-rose-950/60 hover:bg-rose-900/60' : ''}
                    ${!hasTrades ? 'bg-slate-900/30 hover:bg-slate-800/40' : ''}
                    ${isToday ? 'ring-1 ring-blue-500/60' : ''}
                  `}
                >
                  <span className={`text-xs font-semibold mb-1 ${isToday ? 'text-blue-400' : 'text-slate-400'}`}>
                    {day}
                  </span>
                  {hasTrades && (
                    <>
                      <span className={`text-xs font-bold leading-tight ${profit ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {fmt(data.pnl)}
                      </span>
                      <span className="text-[10px] text-slate-500 mt-auto">
                        {data.trades} trade{data.trades !== 1 ? 's' : ''}
                      </span>
                    </>
                  )}
                </button>
              );
            })}
          </div>

          {/* Day detail popup */}
          {selectedDay && selectedData && (
            <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="font-semibold text-white">
                  {new Date(selectedDay + 'T00:00:00').toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })}
                </p>
                <button onClick={() => setSelectedDay(null)} className="text-slate-500 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex gap-4 text-sm">
                <span className={`font-bold text-lg ${selectedData.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {fmt(selectedData.pnl)}
                </span>
                <span className="text-slate-400">{selectedData.trades} trades</span>
                <span className="text-emerald-400">{selectedData.wins}W</span>
                <span className="text-rose-400">{selectedData.losses}L</span>
              </div>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {selectedData.items.map((t, i) => (
                  <div key={i} className="flex items-center justify-between text-sm bg-slate-800/60 rounded px-3 py-1.5">
                    <div>
                      <span className="text-white font-medium">{t.underlying}</span>
                      <span className="text-slate-500 ml-2 text-xs">{t.strategy}</span>
                    </div>
                    <span className={`font-semibold ${t.pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {fmt(t.pnl)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Monthly summary */}
          <div className="border-t border-slate-700 pt-4">
            <p className="text-xs text-slate-500 uppercase tracking-widest mb-3">Monthly Summary — {MONTHS[month]} {year}</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <SummaryCard label="Net P&L" value={fmt(monthStats.totalPnl)} color={monthStats.totalPnl >= 0 ? 'green' : 'red'} />
              <SummaryCard label="Total Trades" value={monthStats.totalTrades.toString()} />
              <SummaryCard label="Winning Days" value={monthStats.wins.toString()} color="green" />
              <SummaryCard label="Losing Days" value={monthStats.losses.toString()} color="red" />
            </div>
          </div>
        </>
      )}
    </div>
  );
};

const SummaryCard: React.FC<{ label: string; value: string; color?: 'green' | 'red' }> = ({ label, value, color }) => (
  <div className="bg-slate-900/60 border border-slate-700/50 rounded-lg p-3">
    <p className="text-xs text-slate-500 mb-1">{label}</p>
    <p className={`text-lg font-bold ${color === 'green' ? 'text-emerald-400' : color === 'red' ? 'text-rose-400' : 'text-white'}`}>
      {value}
    </p>
  </div>
);

export default TradeCalendar;
