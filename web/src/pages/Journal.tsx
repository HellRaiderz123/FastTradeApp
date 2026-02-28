import React, { useState, useEffect } from 'react';
import { ChevronDown, Download } from 'lucide-react';
import { journalAPI } from '../lib/api';

interface JournalEntry {
  id: number;
  strategy: string;
  underlying: string;
  created_at: string;
  closed_at?: string | null;
  entry_price: number;
  exit_price?: number | null;
  pnl: number;
  pnl_percent: number;
  status: string;
  execution_mode?: string;
  execution_result?: any; // Preserve execution result for deduplication logic
}

interface DiagnosticsSummary {
  trades: number;
  wins: number;
  losses: number;
  breakeven: number;
  win_rate_pct: number;
  gross_profit: number;
  gross_loss: number;
  profit_factor: number | null;
  avg_pnl: number;
  net_pnl: number;
}

type DiagnosticsGroup = Record<string, DiagnosticsSummary>;

interface SignalDiagnostics {
  summary: DiagnosticsSummary;
  by_signal_bias: DiagnosticsGroup;
  by_strategy: DiagnosticsGroup;
  by_bias_strategy: DiagnosticsGroup;
  by_market_mode: DiagnosticsGroup;
  by_iv_regime: DiagnosticsGroup;
  count: number;
  lookback_days: number | null;
  limit: number;
}

type PnLFilter = 'all' | 'profit' | 'loss';
type ExecutionTypeFilter = 'all' | 'paper' | 'zerodha_dry' | 'zerodha_live';

const Journal: React.FC = () => {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [pnlFilter, setPnlFilter] = useState<PnLFilter>('all');
  const [executionTypeFilter, setExecutionTypeFilter] = useState<ExecutionTypeFilter>('all');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [diagnostics, setDiagnostics] = useState<SignalDiagnostics | null>(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null);
  const [diagnosticsLookback, setDiagnosticsLookback] = useState(30);
  const [diagnosticsLimit, setDiagnosticsLimit] = useState(200);

  useEffect(() => {
    fetchJournal();
    fetchDiagnostics();
  }, []);

  const fetchJournal = async () => {
    try {
      const response = await journalAPI.getExecutionIntents(100);
      const data = Array.isArray(response.data) ? response.data : [];
      const mapped: JournalEntry[] = data.map((item: any) => {
        const entryPrice = Number(item?.entry_credit ?? 0) || 0;
        const pnl = Number(item?.pnl ?? 0) || 0;
        const exitPrice = entryPrice ? entryPrice - pnl : null;
        const pnlPercent = entryPrice !== 0 ? (pnl / entryPrice) * 100 : 0;
        const execution_result = item?.execution_result || {};
        const execution_mode = (execution_result && execution_result.mode) || 'UNKNOWN';
        return {
          id: item?.id ?? item?.intent_id ?? Math.random(),
          strategy: item?.strategy || 'Unknown',
          underlying: item?.underlying || '-',
          created_at: item?.created_at,
          closed_at: item?.closed_at,
          entry_price: entryPrice,
          exit_price: exitPrice,
          pnl,
          pnl_percent: pnlPercent,
          status: item?.status || 'UNKNOWN',
          execution_mode,
          execution_result, // Preserve for deduplication
        };
      });
      
      // Deduplicate ZERODHA_LIVE entries: keep only the most recent record per strategy/underlying combo
      const deduplicated = deduplicateZerodhaLive(mapped);
      setEntries(deduplicated);
    } catch (error) {
      console.error('Failed to fetch journal:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchDiagnostics = async () => {
    setDiagnosticsLoading(true);
    setDiagnosticsError(null);
    try {
      const response = await journalAPI.getSignalDiagnostics({
        limit: diagnosticsLimit,
        lookback_days: diagnosticsLookback,
      });
      setDiagnostics(response.data || null);
    } catch (error) {
      console.error('Failed to fetch diagnostics:', error);
      setDiagnosticsError('Diagnostics unavailable');
      setDiagnostics(null);
    } finally {
      setDiagnosticsLoading(false);
    }
  };

  const deduplicateZerodhaLive = (entries: JournalEntry[]): JournalEntry[] => {
    const zerodhaLiveMap = new Map<string, JournalEntry>();
    const nonZerodhaLive: JournalEntry[] = [];

    entries.forEach((entry) => {
      const mode = entry.execution_mode || '';
      const isZerodhaLive = mode === 'ZERODHA_LIVE' || mode === 'ZERODHA_LIVE_DIRECT';
      
      if (isZerodhaLive) {
        const key = `${entry.strategy}|${entry.underlying}`;
        const existing = zerodhaLiveMap.get(key);
        
        if (!existing) {
          zerodhaLiveMap.set(key, entry);
        } else {
          // Prefer app-executed (source !== 'zerodha_api_sync') over synced from API
          const existingSource = existing.execution_result?.source || '';
          const currentSource = entry.execution_result?.source || '';
          const existingIsSynced = existingSource === 'zerodha_api_sync';
          const currentIsSynced = currentSource === 'zerodha_api_sync';
          
          if (currentIsSynced && !existingIsSynced) {
            // Keep existing (app-executed) over synced
            return;
          } else if (!currentIsSynced && existingIsSynced) {
            // Replace with app-executed (current)
            zerodhaLiveMap.set(key, entry);
          } else {
            // Both same type: keep most recent
            if (new Date(entry.created_at) > new Date(existing.created_at)) {
              zerodhaLiveMap.set(key, entry);
            }
          }
        }
      } else {
        nonZerodhaLive.push(entry);
      }
    });

    // Combine dedup'ed Zerodha live + all non-live entries
    return [...Array.from(zerodhaLiveMap.values()), ...nonZerodhaLive];
  };

  const getExecutionTypeFromMode = (mode?: string): ExecutionTypeFilter => {
    if (!mode) return 'paper';
    if (mode.includes('ZERODHA_LIVE_DIRECT')) return 'zerodha_live';
    if (mode.includes('ZERODHA_LIVE')) return 'zerodha_live';
    if (mode.includes('ZERODHA')) return 'zerodha_dry';
    return 'paper';
  };

  const filteredEntries = entries.filter((entry) => {
    // Apply P&L filter
    if (pnlFilter === 'profit' && entry.pnl <= 0) return false;
    if (pnlFilter === 'loss' && entry.pnl >= 0) return false;

    // Apply execution type filter
    if (executionTypeFilter !== 'all') {
      const entryType = getExecutionTypeFromMode(entry.execution_mode);
      if (entryType !== executionTypeFilter) return false;
    }

    return true;
  });

  // Calculate stats based on FILTERED entries (not all entries)
  const stats = {
    totalTrades: filteredEntries.length,
    wins: filteredEntries.filter((e) => e.pnl > 0).length,
    losses: filteredEntries.filter((e) => e.pnl < 0).length,
    totalPnL: filteredEntries.reduce((sum, e) => sum + e.pnl, 0),
    avgWin: filteredEntries.filter((e) => e.pnl > 0).length > 0
      ? filteredEntries.filter((e) => e.pnl > 0).reduce((sum, e) => sum + e.pnl, 0) /
      filteredEntries.filter((e) => e.pnl > 0).length
      : 0,
    avgLoss: filteredEntries.filter((e) => e.pnl < 0).length > 0
      ? filteredEntries.filter((e) => e.pnl < 0).reduce((sum, e) => sum + e.pnl, 0) /
      filteredEntries.filter((e) => e.pnl < 0).length
      : 0,
  };

  // Show all-time stats for reference
  const allTimeStats = {
    totalTrades: entries.length,
    wins: entries.filter((e) => e.pnl > 0).length,
    losses: entries.filter((e) => e.pnl < 0).length,
    totalPnL: entries.reduce((sum, e) => sum + e.pnl, 0),
  };

  // Check if filters are active
  const hasActiveFilters = pnlFilter !== 'all' || executionTypeFilter !== 'all';

  const formatMoney = (value?: number | null) => {
    if (value === null || value === undefined) return 'N/A';
    return `₹${Number(value).toLocaleString()}`;
  };

  const formatPercent = (value?: number | null) => {
    if (value === null || value === undefined) return 'N/A';
    return `${Number(value).toFixed(1)}%`;
  };

  const toGroupRows = (
    group?: DiagnosticsGroup,
    max: number = 6,
    order: 'asc' | 'desc' = 'asc'
  ) => {
    if (!group) return [];
    const rows = Object.entries(group).map(([key, value]) => ({
      key: key.split('|').join(' / '),
      trades: value.trades,
      win_rate_pct: value.win_rate_pct,
      net_pnl: value.net_pnl,
      profit_factor: value.profit_factor,
    }));
    rows.sort((a, b) => order === 'asc' ? a.net_pnl - b.net_pnl : b.net_pnl - a.net_pnl);
    return rows.slice(0, max);
  };

  const diagnosticsSummary = diagnostics?.summary;
  const lossDrivers = toGroupRows(diagnostics?.by_bias_strategy, 5, 'asc');
  const marketModeRows = toGroupRows(diagnostics?.by_market_mode, 5, 'desc');
  const ivRegimeRows = toGroupRows(diagnostics?.by_iv_regime, 5, 'desc');
  const biasRows = toGroupRows(diagnostics?.by_signal_bias, 5, 'desc');

  return (
    <div className="space-y-6">
      {/* Filter Status Indicator */}
      {hasActiveFilters && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
          <p className="text-sm text-blue-300">
            🔍 <span className="font-semibold">Filters Active:</span> Showing {filteredEntries.length} of {entries.length} trades
            {pnlFilter !== 'all' && <span className="ml-2">• P&L: {pnlFilter}</span>}
            {executionTypeFilter !== 'all' && <span className="ml-2">• Type: {executionTypeFilter.replace('_', ' ')}</span>}
          </p>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard 
          label="Total Trades" 
          value={stats.totalTrades.toString()} 
          subtext={hasActiveFilters ? `of ${allTimeStats.totalTrades} total` : undefined}
        />
        <StatCard 
          label="Wins" 
          value={stats.wins.toString()} 
          subtext={`Avg: ₹${Math.round(stats.avgWin)}`} 
          color="green" 
        />
        <StatCard 
          label="Losses" 
          value={stats.losses.toString()} 
          subtext={`Avg: ₹${Math.round(stats.avgLoss)}`} 
          color="red" 
        />
        <StatCard 
          label="Total P&L" 
          value={`₹${stats.totalPnL.toLocaleString()}`} 
          subtext={hasActiveFilters ? `(All-time: ₹${allTimeStats.totalPnL.toLocaleString()})` : undefined}
          color={stats.totalPnL >= 0 ? 'green' : 'red'} 
        />
      </div>

      {/* Diagnostics */}
      <div className="terminal-panel terminal-pattern p-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-6">
          <div>
            <p className="terminal-title text-2xl text-white">Signal Diagnostics</p>
            <p className="text-sm text-slate-400">
              Loss drivers by signal bias, strategy, and regime for the selected window.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400">Lookback (days)</label>
              <input
                type="number"
                min={1}
                max={365}
                value={diagnosticsLookback}
                onChange={(event) => setDiagnosticsLookback(Math.max(1, Number(event.target.value) || 1))}
                className="w-24 bg-slate-900/80 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200"
              />
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400">Limit</label>
              <input
                type="number"
                min={10}
                max={1000}
                value={diagnosticsLimit}
                onChange={(event) => setDiagnosticsLimit(Math.max(10, Number(event.target.value) || 10))}
                className="w-24 bg-slate-900/80 border border-slate-700 rounded-md px-3 py-2 text-sm text-slate-200"
              />
            </div>
            <button
              onClick={fetchDiagnostics}
              className="px-4 py-2 bg-slate-900/80 border border-slate-700 rounded-md text-sm text-slate-200 hover:text-white hover:border-slate-500 transition"
            >
              Refresh
            </button>
          </div>
        </div>

        {diagnosticsLoading ? (
          <div className="text-center py-10 text-slate-400">Loading diagnostics...</div>
        ) : diagnosticsError ? (
          <div className="text-center py-10 text-rose-300">{diagnosticsError}</div>
        ) : !diagnosticsSummary ? (
          <div className="text-center py-10 text-slate-400">No diagnostics data yet</div>
        ) : (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <StatCard label="Trades" value={diagnosticsSummary.trades.toString()} />
              <StatCard label="Win Rate" value={formatPercent(diagnosticsSummary.win_rate_pct)} />
              <StatCard
                label="Net P&L"
                value={formatMoney(diagnosticsSummary.net_pnl)}
                color={diagnosticsSummary.net_pnl >= 0 ? 'green' : 'red'}
              />
              <StatCard
                label="Profit Factor"
                value={diagnosticsSummary.profit_factor === null ? 'N/A' : diagnosticsSummary.profit_factor.toFixed(2)}
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <DiagnosticsPanel title="Loss Drivers (Bias + Strategy)" rows={lossDrivers} />
              <DiagnosticsPanel title="Signal Bias Performance" rows={biasRows} />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <DiagnosticsPanel title="Market Mode Performance" rows={marketModeRows} />
              <DiagnosticsPanel title="IV Regime Performance" rows={ivRegimeRows} />
            </div>
          </div>
        )}
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

        {/* Filters */}
        <div className="space-y-4 mb-6">
          {/* P&L Filter */}
          <div>
            <p className="text-xs text-slate-400 mb-2 font-semibold">P&L Filter</p>
            <div className="flex gap-2">
              {(['all', 'profit', 'loss'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setPnlFilter(f)}
                  className={`px-4 py-2 rounded-lg font-medium transition ${
                    pnlFilter === f
                      ? 'bg-blue-500 text-white'
                      : 'bg-slate-900 text-slate-400 hover:text-white'
                  }`}
                >
                  {f.charAt(0).toUpperCase() + f.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* Execution Type Filter */}
          <div>
            <p className="text-xs text-slate-400 mb-2 font-semibold">Execution Type</p>
            <div className="flex flex-wrap gap-2">
              {(['all', 'paper', 'zerodha_dry', 'zerodha_live'] as const).map((f) => {
                const labels = {
                  all: 'All',
                  paper: 'Paper',
                  zerodha_dry: 'Zerodha DRY',
                  zerodha_live: 'Zerodha LIVE',
                };
                return (
                  <button
                    key={f}
                    onClick={() => setExecutionTypeFilter(f)}
                    className={`px-4 py-2 rounded-lg font-medium transition ${
                      executionTypeFilter === f
                        ? f === 'zerodha_live'
                          ? 'bg-red-500 text-white'
                          : f === 'zerodha_dry'
                          ? 'bg-blue-500 text-white'
                          : 'bg-blue-500 text-white'
                        : 'bg-slate-900 text-slate-400 hover:text-white'
                    }`}
                  >
                    {labels[f]}
                  </button>
                );
              })}
            </div>
          </div>
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
        <AnalysisCard 
          title="Win Rate" 
          value={`${stats.totalTrades > 0 ? ((stats.wins / stats.totalTrades) * 100).toFixed(1) : '0'}%`} 
        />
        <AnalysisCard 
          title="Profit Factor" 
          value={stats.avgLoss !== 0 ? Math.abs(stats.avgWin / stats.avgLoss).toFixed(2) : 'N/A'} 
        />
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

const getModeLabel = (mode?: string) => {
  if (!mode) return 'Unknown';
  if (mode.includes('ZERODHA_LIVE_DIRECT')) return 'Executed Direct on Zerodha';
  if (mode.includes('ZERODHA_LIVE')) return 'Executed as Zerodha LIVE RUN';
  if (mode.includes('ZERODHA_DRY_RUN')) return 'Executed as DRY RUN (Zerodha)';
  if (mode.includes('PAPER')) return 'Executed as DRY RUN (Paper)';
  return 'Executed as DRY RUN';
};

const getModeColor = (mode?: string) => {
  if (!mode) return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
  if (mode.includes('ZERODHA_LIVE_DIRECT')) return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
  if (mode.includes('ZERODHA_LIVE')) return 'bg-red-500/20 text-red-300 border-red-500/30';
  if (mode.includes('ZERODHA')) return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
  return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
};

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
            <div className="flex items-center gap-2 mt-1">
              <p className="text-xs text-slate-400">{entry.underlying}</p>
              <span className={`inline-block px-2 py-0.5 rounded text-xs border ${getModeColor(entry.execution_mode)}`}>
                {getModeLabel(entry.execution_mode)}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-8 text-right">
          <div>
            <p className="text-xs text-slate-400">Created Time</p>
            <p className="text-sm font-medium text-white">{new Date(entry.created_at).toLocaleString()}</p>
          </div>
          {entry.closed_at && (
            <div>
              <p className="text-xs text-slate-400">Closed Time</p>
              <p className="text-sm font-medium text-white">{new Date(entry.closed_at).toLocaleString()}</p>
            </div>
          )}
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
        <div className="bg-slate-950/50 p-4 border-t border-slate-700 grid grid-cols-2 md:grid-cols-5 gap-4">
          <DetailItem label="Entry Price" value={entry.entry_price ? `₹${entry.entry_price.toLocaleString()}` : 'N/A'} />
          <DetailItem label="Exit Price" value={entry.exit_price !== null && entry.exit_price !== undefined ? `₹${entry.exit_price.toLocaleString()}` : 'N/A'} />
          <DetailItem label="Return %" value={`${entry.pnl_percent.toFixed(2)}%`} color={isProfitable ? 'green' : 'red'} />
          <DetailItem label="Status" value={entry.status} />
          <DetailItem label="Execution Mode" value={getModeLabel(entry.execution_mode)} />
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

interface DiagnosticsRow {
  key: string;
  trades: number;
  win_rate_pct: number;
  net_pnl: number;
  profit_factor: number | null;
}

const formatCompactMoney = (value: number) => {
  const sign = value >= 0 ? '+' : '-';
  return `${sign}₹${Math.abs(value).toLocaleString()}`;
};

const DiagnosticsPanel: React.FC<{ title: string; rows: DiagnosticsRow[] }> = ({ title, rows }) => (
  <div className="card-glass p-4">
    <div className="flex items-center justify-between mb-3">
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      <span className="text-xs text-slate-500">{rows.length} buckets</span>
    </div>
    {rows.length === 0 ? (
      <p className="text-sm text-slate-500">No data yet</p>
    ) : (
      <div className="space-y-3">
        {rows.map((row) => (
          <div key={row.key} className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm text-white">{row.key}</p>
              <p className="text-xs text-slate-500">
                {row.trades} trades · Win {row.win_rate_pct.toFixed(1)}% · PF {row.profit_factor === null ? 'N/A' : row.profit_factor.toFixed(2)}
              </p>
            </div>
            <div className={`text-sm font-semibold ${row.net_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {formatCompactMoney(row.net_pnl)}
            </div>
          </div>
        ))}
      </div>
    )}
  </div>
);

export default Journal;
