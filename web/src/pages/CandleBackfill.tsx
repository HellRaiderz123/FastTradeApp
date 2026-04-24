import { useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Database, Loader2, Play } from 'lucide-react';
import { candleBackfillAPI } from '../lib/api';
import { useToast } from '../components/Toast';

type BackfillTimeframe = '1 Min' | '5 Min' | '15 Min' | '1 Hour' | 'Day';

interface BackfillResult {
  message: string;
  timeframe: BackfillTimeframe;
  symbols_attempted: number;
  days: number;
  success: number;
  failed: number;
  aggregated_from_15m?: number | null;
  total_rows_in_table: number;
  errors: string[];
}

const TIMEFRAME_OPTIONS: Array<{ value: BackfillTimeframe; label: string; defaultDays: number }> = [
  { value: '1 Min', label: '1 Minute', defaultDays: 15 },
  { value: '5 Min', label: '5 Minutes', defaultDays: 45 },
  { value: '15 Min', label: '15 Minutes', defaultDays: 90 },
  { value: '1 Hour', label: '1 Hour', defaultDays: 365 },
  { value: 'Day', label: '1 Day', defaultDays: 900 },
];

export default function CandleBackfill() {
  const { showToast } = useToast();
  const [timeframe, setTimeframe] = useState<BackfillTimeframe>('15 Min');
  const [symbols, setSymbols] = useState('');
  const [days, setDays] = useState<number>(90);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BackfillResult | null>(null);

  const selectedDefaults = useMemo(
    () => TIMEFRAME_OPTIONS.find((opt) => opt.value === timeframe),
    [timeframe]
  );

  const handleUseRecommendedDays = () => {
    if (selectedDefaults) {
      setDays(selectedDefaults.defaultDays);
    }
  };

  const runBackfill = async () => {
    const safeDays = Math.min(900, Math.max(1, Math.floor(Number(days) || 0)));

    if (!safeDays) {
      showToast('error', 'Invalid days', 'Days must be between 1 and 900.');
      return;
    }

    setRunning(true);
    setResult(null);

    try {
      const res = await candleBackfillAPI.runManual({
        timeframe,
        symbols: symbols.trim(),
        days: safeDays,
      });

      const data = res.data as BackfillResult;
      setResult(data);

      if (data.success > 0) {
        showToast(
          'success',
          'Backfill complete',
          `${data.success}/${data.symbols_attempted} symbols loaded for ${data.timeframe}.`
        );
      } else {
        showToast('error', 'Backfill failed', data.errors?.[0] || 'No symbols were loaded.');
      }
    } catch (err: any) {
      showToast('error', 'Backfill failed', err?.response?.data?.detail || 'Request failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="card-glass p-6">
        <div className="flex items-center gap-3 mb-2">
          <Database className="w-6 h-6 text-cyan-400" />
          <h1 className="text-2xl font-bold text-white">Candle Backfill</h1>
        </div>
        <p className="text-slate-400 text-sm">
          Backfill candles directly from Zerodha for 1m, 5m, 15m, 1h, and daily timeframes.
          Leave symbols empty to use NIFTY50 universe.
        </p>
      </div>

      <div className="card-glass p-6 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-slate-300 mb-2">Timeframe</label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value as BackfillTimeframe)}
              disabled={running}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white"
            >
              {TIMEFRAME_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm text-slate-300 mb-2">Days (1-900)</label>
            <input
              type="number"
              min={1}
              max={900}
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              disabled={running}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white"
            />
          </div>

          <div className="flex items-end">
            <button
              onClick={handleUseRecommendedDays}
              disabled={running}
              className="w-full bg-slate-800 hover:bg-slate-700 disabled:bg-slate-700 text-slate-200 px-3 py-2 rounded-lg text-sm"
            >
              Use Recommended ({selectedDefaults?.defaultDays ?? '-'} days)
            </button>
          </div>
        </div>

        <div>
          <label className="block text-sm text-slate-300 mb-2">Symbols (Optional)</label>
          <textarea
            value={symbols}
            onChange={(e) => setSymbols(e.target.value)}
            disabled={running}
            rows={3}
            placeholder="NIFTY, BANKNIFTY, RELIANCE"
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white placeholder-slate-500"
          />
          <p className="text-xs text-slate-500 mt-1">
            Comma-separated symbols. Keep blank for default NIFTY50 backfill.
          </p>
        </div>

        <button
          onClick={runBackfill}
          disabled={running}
          className="w-full md:w-auto inline-flex items-center gap-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 text-white px-5 py-2.5 rounded-lg font-medium"
        >
          {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          {running ? 'Running Backfill...' : 'Run Backfill'}
        </button>

        <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-400/20 rounded-lg p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5" />
          <span>
            Requires valid Zerodha API credentials and access token in backend settings.
          </span>
        </div>
      </div>

      {result && (
        <div className="card-glass p-6 space-y-4">
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle2 className="w-5 h-5" />
            <h2 className="text-lg font-semibold text-white">Backfill Result</h2>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <StatCard label="Timeframe" value={result.timeframe} />
            <StatCard label="Days" value={String(result.days)} />
            <StatCard label="Symbols" value={String(result.symbols_attempted)} />
            <StatCard label="Total Rows" value={result.total_rows_in_table.toLocaleString()} />
            <StatCard label="Success" value={String(result.success)} success />
            <StatCard label="Failed" value={String(result.failed)} danger={result.failed > 0} />
            {result.aggregated_from_15m !== undefined && result.aggregated_from_15m !== null ? (
              <StatCard label="1H Aggregated" value={String(result.aggregated_from_15m)} />
            ) : null}
          </div>

          {result.errors?.length > 0 && (
            <div className="bg-rose-500/10 border border-rose-400/20 rounded-lg p-3">
              <p className="text-rose-300 text-sm font-medium mb-2">Errors</p>
              <ul className="text-xs text-rose-200 space-y-1 max-h-40 overflow-auto">
                {result.errors.map((err, idx) => (
                  <li key={`${idx}-${err}`}>- {err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  success,
  danger,
}: {
  label: string;
  value: string;
  success?: boolean;
  danger?: boolean;
}) {
  const valueClass = success ? 'text-green-300' : danger ? 'text-rose-300' : 'text-white';

  return (
    <div className="bg-slate-900/70 border border-slate-800 rounded-lg p-3">
      <p className="text-slate-400 text-xs">{label}</p>
      <p className={`text-base font-semibold ${valueClass}`}>{value}</p>
    </div>
  );
}
