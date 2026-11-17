import React, { useState, useEffect, useCallback } from 'react';
import { Brain, RefreshCcw, AlertTriangle, TrendingDown, Zap, Wind, Clock, Newspaper } from 'lucide-react';
import api from '../lib/api';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Reflection {
  id: number;
  intent_id: string;
  symbol: string;
  strategy: string;
  pnl: number;
  primary_cause: string;
  weights: { news: number; technical: number; macro: number; iv: number; timing: number };
  entry_rsi: number | null;
  entry_vix: number | null;
  entry_iv_regime: string | null;
  entry_market_mode: string | null;
  news_filing_found: boolean;
  news_sentiment: string | null;
  news_tags: string[];
  reflection_text: string | null;
  reflected_at: string;
}

interface Pattern {
  strategy: string;
  primary_cause: string;
  sl_count: number;
  avg_loss: number;
  avg_entry_rsi: number | null;
  avg_entry_vix: number | null;
}

interface DiagSummary {
  trades: number; wins: number; losses: number;
  win_rate_pct: number; net_pnl: number; profit_factor: number | null;
}

interface Diagnostics {
  summary: DiagSummary;
  by_signal_bias: Record<string, DiagSummary>;
  by_strategy: Record<string, DiagSummary>;
  by_market_mode: Record<string, DiagSummary>;
  by_iv_regime: Record<string, DiagSummary>;
}

// ── Cause config ──────────────────────────────────────────────────────────────

const CAUSE_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  NEWS:      { label: 'News / Filing',   color: 'text-orange-400 bg-orange-500/10 border-orange-500/30', icon: <Newspaper size={13} /> },
  TECHNICAL: { label: 'Technical Miss',  color: 'text-red-400 bg-red-500/10 border-red-500/30',         icon: <TrendingDown size={13} /> },
  MACRO:     { label: 'Macro / VIX',     color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30', icon: <Wind size={13} /> },
  IV:        { label: 'IV Regime',       color: 'text-violet-400 bg-violet-500/10 border-violet-500/30', icon: <Zap size={13} /> },
  TIMING:    { label: 'Timing / Noise',  color: 'text-slate-400 bg-slate-500/10 border-slate-500/30',   icon: <Clock size={13} /> },
};

const causeColor = (c: string) => CAUSE_CONFIG[c]?.color ?? 'text-slate-400 bg-slate-500/10 border-slate-500/30';
const causeIcon  = (c: string) => CAUSE_CONFIG[c]?.icon ?? <AlertTriangle size={13} />;
const causeLabel = (c: string) => CAUSE_CONFIG[c]?.label ?? c;

// ── Weight bar ────────────────────────────────────────────────────────────────

const WeightBar: React.FC<{ weights: Reflection['weights'] }> = ({ weights }) => {
  const segments = [
    { key: 'news',      pct: weights.news * 100,      color: 'bg-orange-500' },
    { key: 'technical', pct: weights.technical * 100, color: 'bg-red-500' },
    { key: 'macro',     pct: weights.macro * 100,     color: 'bg-yellow-500' },
    { key: 'iv',        pct: weights.iv * 100,        color: 'bg-violet-500' },
    { key: 'timing',    pct: weights.timing * 100,    color: 'bg-slate-500' },
  ].filter(s => s.pct > 0);

  return (
    <div className="flex h-1.5 w-full rounded-full overflow-hidden gap-px">
      {segments.map(s => (
        <div key={s.key} className={`${s.color} rounded-full`} style={{ width: `${s.pct}%` }} />
      ))}
    </div>
  );
};

// ── Diag table ────────────────────────────────────────────────────────────────

const DiagTable: React.FC<{ title: string; data: Record<string, DiagSummary> }> = ({ title, data }) => {
  const rows = Object.entries(data)
    .map(([k, v]) => ({ key: k.replace(/\|/g, ' / '), ...v }))
    .sort((a, b) => b.trades - a.trades)
    .slice(0, 6);

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <div className="text-sm font-semibold text-foreground mb-3">{title}</div>
      {rows.length === 0 ? (
        <div className="text-xs text-muted-foreground">No data yet</div>
      ) : (
        <div className="space-y-2">
          {rows.map(r => (
            <div key={r.key} className="flex items-center justify-between gap-2">
              <div>
                <div className="text-xs text-foreground">{r.key}</div>
                <div className="text-[10px] text-muted-foreground">
                  {r.trades} trades · Win {r.win_rate_pct.toFixed(1)}%
                  {r.profit_factor != null ? ` · PF ${r.profit_factor.toFixed(2)}` : ''}
                </div>
              </div>
              <div className={`text-xs font-semibold ${r.net_pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {r.net_pnl >= 0 ? '+' : ''}₹{Math.abs(r.net_pnl).toLocaleString('en-IN')}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ── Main page ─────────────────────────────────────────────────────────────────

const StrategyIntelligence: React.FC = () => {
  const [reflections, setReflections] = useState<Reflection[]>([]);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [diagnostics, setDiagnostics] = useState<Diagnostics | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Reflection | null>(null);
  const [filterCause, setFilterCause] = useState('');
  const [reflecting, setReflecting] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [rRes, pRes, dRes] = await Promise.all([
        api.get('/learning/reflections', { params: { limit: 100 } }),
        api.get('/learning/patterns', { params: { min_trades: 2 } }),
        api.get('/learning/diagnostics', { params: { lookback_days: 30, limit: 200 } }),
      ]);
      setReflections(rRes.data.data ?? []);
      setPatterns(pRes.data.patterns ?? []);
      setDiagnostics(dRes.data ?? null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const triggerReflect = async (intentId: string) => {
    setReflecting(intentId);
    try {
      await api.post(`/learning/reflect/${intentId}`);
      await fetchAll();
    } catch (e) {
      console.error(e);
    } finally {
      setReflecting(null);
    }
  };

  const filtered = filterCause
    ? reflections.filter(r => r.primary_cause === filterCause)
    : reflections;

  const causeCounts = reflections.reduce<Record<string, number>>((acc, r) => {
    acc[r.primary_cause] = (acc[r.primary_cause] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="min-h-screen bg-background p-6 space-y-6">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Brain className="text-violet-400" size={28} />
          <div>
            <h1 className="text-2xl font-bold text-foreground">Strategy Intelligence</h1>
            <p className="text-sm text-muted-foreground">Self-learning post-mortem engine — why did the SL hit?</p>
          </div>
        </div>
        <button
          onClick={fetchAll}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-muted rounded-lg text-white text-sm transition-colors"
        >
          <RefreshCcw size={15} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Cause breakdown pills */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => setFilterCause('')}
          className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
            filterCause === '' ? 'bg-foreground text-background border-foreground' : 'bg-card border-border text-muted-foreground hover:text-foreground'
          }`}
        >
          All ({reflections.length})
        </button>
        {Object.entries(causeCounts).map(([cause, count]) => (
          <button
            key={cause}
            onClick={() => setFilterCause(filterCause === cause ? '' : cause)}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border transition-colors ${
              filterCause === cause ? causeColor(cause) + ' ring-2 ring-offset-1 ring-offset-background ring-current' : causeColor(cause)
            }`}
          >
            {causeIcon(cause)}
            {causeLabel(cause)} ({count})
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

        {/* Left: Failure patterns */}
        <div className="space-y-4">
          <div className="text-sm font-semibold text-foreground">Failure Patterns</div>
          {patterns.length === 0 ? (
            <div className="bg-card border border-border rounded-xl p-6 text-center text-sm text-muted-foreground">
              No patterns yet — need ≥2 SL hits per combination
            </div>
          ) : (
            patterns.map((p, i) => (
              <div key={i} className="bg-card border border-border rounded-xl p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-foreground">{p.strategy}</span>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium ${causeColor(p.primary_cause)}`}>
                    {causeIcon(p.primary_cause)}
                    {causeLabel(p.primary_cause)}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                  <div>SL hits<br /><span className="text-red-400 font-semibold">{p.sl_count}</span></div>
                  <div>Avg loss<br /><span className="text-red-400 font-semibold">₹{p.avg_loss.toLocaleString('en-IN')}</span></div>
                  <div>Avg RSI<br /><span className="text-foreground font-semibold">{p.avg_entry_rsi ?? '—'}</span></div>
                </div>
                {p.avg_entry_vix && (
                  <div className="text-[11px] text-muted-foreground">
                    Avg VIX at entry: <span className="text-yellow-400">{p.avg_entry_vix}</span>
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Middle: Reflections list */}
        <div className="space-y-3">
          <div className="text-sm font-semibold text-foreground">Recent Reflections ({filtered.length})</div>
          {filtered.length === 0 ? (
            <div className="bg-card border border-border rounded-xl p-6 text-center text-sm text-muted-foreground">
              No reflections yet. They are generated automatically when a trade hits SL.
            </div>
          ) : (
            filtered.map(r => (
              <button
                key={r.id}
                onClick={() => setSelected(selected?.id === r.id ? null : r)}
                className={`w-full text-left bg-card border rounded-xl p-4 space-y-2 transition-colors hover:bg-accent/40 ${
                  selected?.id === r.id ? 'border-violet-500/50' : 'border-border'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground text-sm">{r.symbol}</span>
                    <span className="text-xs text-muted-foreground">{r.strategy}</span>
                  </div>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[11px] font-medium ${causeColor(r.primary_cause)}`}>
                    {causeIcon(r.primary_cause)}
                    {causeLabel(r.primary_cause)}
                  </span>
                </div>
                <WeightBar weights={r.weights} />
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span className="text-red-400 font-medium">₹{Math.abs(r.pnl).toLocaleString('en-IN')} loss</span>
                  <span>{r.reflected_at?.slice(0, 16)}</span>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Right: Detail panel */}
        <div className="space-y-4">
          {selected ? (
            <>
              <div className="text-sm font-semibold text-foreground">Post-Mortem Detail</div>
              <div className="bg-card border border-border rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-lg font-bold text-foreground">{selected.symbol}</div>
                    <div className="text-xs text-muted-foreground">{selected.strategy}</div>
                  </div>
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${causeColor(selected.primary_cause)}`}>
                    {causeIcon(selected.primary_cause)}
                    {causeLabel(selected.primary_cause)}
                  </span>
                </div>

                {/* Cause weights */}
                <div>
                  <div className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Cause Attribution</div>
                  <div className="space-y-1.5">
                    {Object.entries(selected.weights).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-2">
                        <div className="w-20 text-xs text-muted-foreground capitalize">{k}</div>
                        <div className="flex-1 bg-muted rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${
                              k === 'news' ? 'bg-orange-500' :
                              k === 'technical' ? 'bg-red-500' :
                              k === 'macro' ? 'bg-yellow-500' :
                              k === 'iv' ? 'bg-violet-500' : 'bg-slate-500'
                            }`}
                            style={{ width: `${(v as number) * 100}%` }}
                          />
                        </div>
                        <div className="w-10 text-xs text-right text-foreground">{((v as number) * 100).toFixed(0)}%</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Entry conditions */}
                <div>
                  <div className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Entry Conditions</div>
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      { label: 'RSI', value: selected.entry_rsi?.toFixed(1) ?? '—', warn: (selected.entry_rsi ?? 0) > 70 },
                      { label: 'VIX', value: selected.entry_vix?.toFixed(1) ?? '—', warn: (selected.entry_vix ?? 0) > 16 },
                      { label: 'IV Regime', value: selected.entry_iv_regime ?? '—', warn: selected.entry_iv_regime === 'HIGH' },
                      { label: 'Market Mode', value: selected.entry_market_mode ?? '—', warn: false },
                    ].map(item => (
                      <div key={item.label} className="bg-muted rounded-lg p-2 border border-border">
                        <div className="text-[10px] text-muted-foreground">{item.label}</div>
                        <div className={`text-sm font-semibold ${item.warn ? 'text-red-400' : 'text-foreground'}`}>
                          {item.value}
                          {item.warn && <span className="ml-1 text-[10px]">⚠</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* News */}
                {selected.news_filing_found && (
                  <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3">
                    <div className="text-xs font-semibold text-orange-400 mb-1">Filing / News Found Near SL</div>
                    <div className="text-xs text-muted-foreground">
                      Sentiment: <span className="text-foreground">{selected.news_sentiment}</span>
                    </div>
                    {selected.news_tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {selected.news_tags.map(t => (
                          <span key={t} className="px-1.5 py-0.5 bg-orange-500/20 text-orange-300 rounded text-[10px]">{t}</span>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Reflection text */}
                {selected.reflection_text && (
                  <div>
                    <div className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wide">Reflection</div>
                    <p className="text-sm text-foreground leading-relaxed">{selected.reflection_text}</p>
                  </div>
                )}

                <button
                  onClick={() => triggerReflect(selected.intent_id)}
                  disabled={reflecting === selected.intent_id}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-muted rounded-lg text-xs text-white transition-colors"
                >
                  <RefreshCcw size={13} className={reflecting === selected.intent_id ? 'animate-spin' : ''} />
                  Re-reflect
                </button>
              </div>
            </>
          ) : (
            <>
              <div className="text-sm font-semibold text-foreground">Signal Diagnostics (30d)</div>
              {diagnostics ? (
                <div className="space-y-4">
                  {/* Summary */}
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: 'Trades', value: diagnostics.summary.trades.toString() },
                      { label: 'Win Rate', value: `${diagnostics.summary.win_rate_pct.toFixed(1)}%` },
                      { label: 'Net P&L', value: `₹${diagnostics.summary.net_pnl.toLocaleString('en-IN')}`, color: diagnostics.summary.net_pnl >= 0 ? 'text-emerald-400' : 'text-red-400' },
                      { label: 'Profit Factor', value: diagnostics.summary.profit_factor?.toFixed(2) ?? 'N/A' },
                    ].map(s => (
                      <div key={s.label} className="bg-card border border-border rounded-xl p-3">
                        <div className="text-[10px] text-muted-foreground">{s.label}</div>
                        <div className={`text-lg font-bold ${(s as any).color ?? 'text-foreground'}`}>{s.value}</div>
                      </div>
                    ))}
                  </div>
                  <DiagTable title="By IV Regime" data={diagnostics.by_iv_regime} />
                  <DiagTable title="By Market Mode" data={diagnostics.by_market_mode} />
                  <DiagTable title="By Strategy" data={diagnostics.by_strategy} />
                </div>
              ) : (
                <div className="bg-card border border-border rounded-xl p-6 text-center text-sm text-muted-foreground">
                  Select a reflection to see details, or wait for diagnostics to load.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default StrategyIntelligence;
