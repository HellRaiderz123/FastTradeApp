import React, { useState, useEffect } from 'react';
import { ChevronDown, Download } from 'lucide-react';
import { journalAPI } from '../lib/api';

interface JournalEntry {
  id: number;
  strategy: string;
  underlying: string;
  entry_time: string;
  exit_time?: string;
  entry_price: number;
  exit_price?: number;
  pnl: number;
  pnl_percent: number;
  status: string;
  created_at: string;
}

const Journal: React.FC = () => {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    fetchJournal();
  }, []);

  const fetchJournal = async () => {
    try {
      const response = await journalAPI.getStrategyRuns(100);
      setEntries(response.data || []);
    } catch (error) {
      console.error('Failed to fetch journal:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredEntries = entries.filter((entry) => {
    if (filter === 'profit') return entry.pnl > 0;
    if (filter === 'loss') return entry.pnl < 0;
    return true;
  });

  const stats = {
    totalTrades: entries.length,
    wins: entries.filter((e) => e.pnl > 0).length,
    losses: entries.filter((e) => e.pnl < 0).length,
    totalPnL: entries.reduce((sum, e) => sum + e.pnl, 0),
    avgWin: entries.filter((e) => e.pnl > 0).length > 0
      ? entries.filter((e) => e.pnl > 0).reduce((sum, e) => sum + e.pnl, 0) /
      entries.filter((e) => e.pnl > 0).length
      : 0,
    avgLoss: entries.filter((e) => e.pnl < 0).length > 0
      ? entries.filter((e) => e.pnl < 0).reduce((sum, e) => sum + e.pnl, 0) /
      entries.filter((e) => e.pnl < 0).length
      : 0,
  };

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard label="Total Trades" value={stats.totalTrades.toString()} />
        <StatCard label="Wins" value={stats.wins.toString()} subtext={`Avg: ₹${Math.round(stats.avgWin)}`} color="green" />
        <StatCard label="Losses" value={stats.losses.toString()} subtext={`Avg: ₹${Math.round(stats.avgLoss)}`} color="red" />
        <StatCard label="Total P&L" value={`₹${stats.totalPnL.toLocaleString()}`} color={stats.totalPnL >= 0 ? 'green' : 'red'} />
      </div>

      {/* Journal */}
      <div className="card-glass p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-white">Trade Journal</h2>
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-900 rounded-lg hover:bg-slate-800 transition text-slate-300">
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>

        {/* Filter */}
        <div className="flex gap-2 mb-6">
          {['all', 'profit', 'loss'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg font-medium transition ${
                filter === f
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-900 text-slate-400 hover:text-white'
              }`}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>

        {/* Entries */}
        {loading ? (
          <div className="text-center py-12 text-slate-400">Loading...</div>
        ) : filteredEntries.length === 0 ? (
          <div className="text-center py-12 text-slate-400">No trades yet</div>
        ) : (
          <div className="space-y-2">
            {filteredEntries.map((entry) => (
              <JournalEntryRow
                key={entry.id}
                entry={entry}
                expanded={expandedId === entry.id}
                onToggle={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Analysis */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <AnalysisCard title="Win Rate" value={`${((stats.wins / stats.totalTrades) * 100).toFixed(1)}%`} />
        <AnalysisCard title="Profit Factor" value={Math.abs(stats.avgWin / stats.avgLoss).toFixed(2)} />
      </div>
    </div>
  );
};

const StatCard: React.FC<{ label: string; value: string; subtext?: string; color?: string }> = ({
  label,
  value,
  subtext,
  color,
}) => {
  const colorClass = {
    green: 'text-green-400',
    red: 'text-red-400',
  }[color || 'white'];

  return (
    <div className="card-glass p-4">
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${colorClass || 'text-white'}`}>{value}</p>
      {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
    </div>
  );
};

interface JournalEntryRowProps {
  entry: JournalEntry;
  expanded: boolean;
  onToggle: () => void;
}

const JournalEntryRow: React.FC<JournalEntryRowProps> = ({ entry, expanded, onToggle }) => {
  const isProfitable = entry.pnl >= 0;

  return (
    <div className="border border-slate-700 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full bg-slate-900/50 hover:bg-slate-900 p-4 flex items-center justify-between transition"
      >
        <div className="flex items-center gap-4 flex-1 text-left">
          <div>
            <p className="font-semibold text-white">{entry.strategy}</p>
            <p className="text-xs text-slate-400">{entry.underlying}</p>
          </div>
        </div>

        <div className="flex items-center gap-8 text-right">
          <div>
            <p className="text-xs text-slate-400">Created Time</p>
            <p className="text-sm font-medium text-white">{new Date(entry.created_at).toLocaleString()}</p>
          </div>
          <div>
            <p className="text-xs text-slate-400">P&L</p>
            <p className={`text-lg font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
              {isProfitable ? '+' : ''}₹{Math.abs(entry.pnl).toLocaleString()}
            </p>
          </div>
          <div className="w-6 h-6 text-slate-400">
            <ChevronDown className={`w-6 h-6 transition ${expanded ? 'rotate-180' : ''}`} />
          </div>
        </div>
      </button>

      {expanded && (
        <div className="bg-slate-950/50 p-4 border-t border-slate-700 grid grid-cols-2 md:grid-cols-4 gap-4">
          <DetailItem label="Entry Price" value={`₹${entry.entry_price.toLocaleString()}`} />
          <DetailItem label="Exit Price" value={entry.exit_price ? `₹${entry.exit_price.toLocaleString()}` : 'N/A'} />
          <DetailItem label="Return %" value={`${entry.pnl_percent.toFixed(2)}%`} color={isProfitable ? 'green' : 'red'} />
          <DetailItem label="Status" value={entry.status} />
        </div>
      )}
    </div>
  );
};

const DetailItem: React.FC<{ label: string; value: string; color?: string }> = ({ label, value, color }) => {
  const colorClass = {
    green: 'text-green-400',
    red: 'text-red-400',
  }[color || 'white'];

  return (
    <div>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className={`font-semibold ${colorClass || 'text-white'}`}>{value}</p>
    </div>
  );
};

const AnalysisCard: React.FC<{ title: string; value: string }> = ({ title, value }) => (
  <div className="card-glass p-6">
    <p className="text-slate-400 mb-2">{title}</p>
    <p className="text-3xl font-bold text-white">{value}</p>
  </div>
);

export default Journal;
