import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCcw, FileText, TrendingUp, TrendingDown, Minus, Filter, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import api from '../lib/api';

interface FilingRow {
  id: number;
  symbol: string;
  company: string;
  headline: string;
  category: string;
  impact: string;
  pdf_url: string;
  published_at: string;
  pdf_extracted: boolean;
  sentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  sentiment_score: number;
  summary: string;
  key_numbers: Record<string, number>;
  signal_tags: string[];
  passed_filter: boolean;
  avg_volume: number;
  filter_reason: string;
  analysed_at: string;
  pdf_text?: string;
}

interface Stats {
  total_analysed: number;
  sentiment_breakdown: { BULLISH: number; BEARISH: number; NEUTRAL: number };
  top_signal_tags: { tag: string; count: number }[];
  most_active_symbols: { symbol: string; count: number }[];
}

const SENTIMENT_COLORS = {
  BULLISH: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30',
  BEARISH: 'text-red-400 bg-red-500/10 border-red-500/30',
  NEUTRAL: 'text-slate-400 bg-slate-500/10 border-slate-500/30',
};

const TAG_COLORS: Record<string, string> = {
  BEAT: 'bg-emerald-500/20 text-emerald-300',
  MISS: 'bg-red-500/20 text-red-300',
  ORDER_WIN: 'bg-blue-500/20 text-blue-300',
  REGULATORY_ACTION: 'bg-orange-500/20 text-orange-300',
  SHAREHOLDER_RETURN: 'bg-violet-500/20 text-violet-300',
  'M&A': 'bg-yellow-500/20 text-yellow-300',
  LOSS_REPORTED: 'bg-red-500/20 text-red-300',
  EXPANSION: 'bg-cyan-500/20 text-cyan-300',
  FUNDRAISE: 'bg-indigo-500/20 text-indigo-300',
  INSIDER_BUY: 'bg-emerald-500/20 text-emerald-300',
  INSIDER_SELL: 'bg-red-500/20 text-red-300',
};

const SentimentIcon = ({ s }: { s: string }) =>
  s === 'BULLISH' ? <TrendingUp size={14} /> : s === 'BEARISH' ? <TrendingDown size={14} /> : <Minus size={14} />;

const FilingAnalysis: React.FC = () => {
  const [rows, setRows] = useState<FilingRow[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const LIMIT = 50;

  // Filters
  const [filterSentiment, setFilterSentiment] = useState('');
  const [filterSymbol, setFilterSymbol] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const [passedOnly, setPassedOnly] = useState(true);

  // Detail modal
  const [detail, setDetail] = useState<FilingRow | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [showPdfText, setShowPdfText] = useState(false);

  const fetchData = useCallback(async (off = 0) => {
    setLoading(true);
    try {
      const params: Record<string, any> = { limit: LIMIT, offset: off, passed_only: passedOnly };
      if (filterSentiment) params.sentiment = filterSentiment;
      if (filterSymbol) params.symbol = filterSymbol.toUpperCase();
      if (filterTag) params.tag = filterTag;

      const [listRes, statsRes] = await Promise.all([
        api.get('/nse/filing-analysis', { params }),
        api.get('/nse/filing-analysis/stats', { params: { days: 30 } }),
      ]);
      setRows(listRes.data.data);
      setTotal(listRes.data.total);
      setStats(statsRes.data);
      setOffset(off);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [filterSentiment, filterSymbol, filterTag, passedOnly]);

  useEffect(() => { fetchData(0); }, [fetchData]);

  const openDetail = async (id: number) => {
    setDetailLoading(true);
    setShowPdfText(false);
    try {
      const res = await api.get(`/nse/filing-analysis/${id}`);
      setDetail(res.data);
    } catch (e) { console.error(e); }
    finally { setDetailLoading(false); }
  };

  const rerun = async (id: number) => {
    try {
      await api.post(`/nse/filing-analysis/rerun/${id}`);
      openDetail(id);
    } catch (e) { console.error(e); }
  };

  const fmt = (n: number) => n >= 1e5 ? `${(n / 1e5).toFixed(1)}L` : n.toLocaleString('en-IN');

  return (
    <div className="min-h-screen bg-background p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">NSE Filing Analysis</h1>
          <p className="text-muted-foreground text-sm mt-1">
            HIGH-impact filings on NIFTY500 stocks — PDF extracted, sentiment classified, operator-trap filtered
          </p>
        </div>
        <button
          onClick={() => fetchData(0)}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-muted rounded-lg text-white text-sm transition-colors"
        >
          <RefreshCcw size={16} className={loading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </div>

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="text-muted-foreground text-xs mb-1">Analysed (30d)</div>
            <div className="text-2xl font-bold text-foreground">{stats.total_analysed}</div>
          </div>
          {(['BULLISH', 'BEARISH', 'NEUTRAL'] as const).map((s) => (
            <div key={s} className="bg-card border border-border rounded-xl p-4">
              <div className="text-muted-foreground text-xs mb-1">{s}</div>
              <div className={`text-2xl font-bold ${s === 'BULLISH' ? 'text-emerald-400' : s === 'BEARISH' ? 'text-red-400' : 'text-slate-400'}`}>
                {stats.sentiment_breakdown[s]}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Top tags + symbols */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="text-sm font-semibold text-foreground mb-3">Top Signal Tags (30d)</div>
            <div className="flex flex-wrap gap-2">
              {stats.top_signal_tags.map(({ tag, count }) => (
                <button
                  key={tag}
                  onClick={() => setFilterTag(filterTag === tag ? '' : tag)}
                  className={`px-2 py-1 rounded text-xs font-medium border transition-colors ${
                    filterTag === tag ? 'ring-2 ring-blue-500' : ''
                  } ${TAG_COLORS[tag] || 'bg-muted text-foreground border-border'}`}
                >
                  {tag} <span className="opacity-70">×{count}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="text-sm font-semibold text-foreground mb-3">Most Active Symbols (30d)</div>
            <div className="flex flex-wrap gap-2">
              {stats.most_active_symbols.map(({ symbol, count }) => (
                <button
                  key={symbol}
                  onClick={() => setFilterSymbol(filterSymbol === symbol ? '' : symbol)}
                  className={`px-2 py-1 rounded text-xs font-medium bg-muted border border-border text-foreground transition-colors ${
                    filterSymbol === symbol ? 'ring-2 ring-blue-500' : ''
                  }`}
                >
                  {symbol} <span className="opacity-60">×{count}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center bg-card border border-border rounded-xl p-4">
        <Filter size={16} className="text-muted-foreground" />
        <input
          placeholder="Symbol (e.g. RELIANCE)"
          value={filterSymbol}
          onChange={(e) => setFilterSymbol(e.target.value)}
          className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-blue-500 w-40"
        />
        <select
          value={filterSentiment}
          onChange={(e) => setFilterSentiment(e.target.value)}
          className="px-3 py-1.5 bg-background border border-border rounded-lg text-sm text-foreground focus:outline-none"
        >
          <option value="">All Sentiments</option>
          <option value="BULLISH">Bullish</option>
          <option value="BEARISH">Bearish</option>
          <option value="NEUTRAL">Neutral</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-foreground cursor-pointer">
          <input type="checkbox" checked={passedOnly} onChange={(e) => setPassedOnly(e.target.checked)} className="w-4 h-4" />
          NIFTY500 + Volume filter only
        </label>
        {(filterSymbol || filterSentiment || filterTag) && (
          <button
            onClick={() => { setFilterSymbol(''); setFilterSentiment(''); setFilterTag(''); }}
            className="text-xs text-muted-foreground hover:text-foreground underline"
          >
            Clear filters
          </button>
        )}
        <span className="ml-auto text-xs text-muted-foreground">{total} filings</span>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Symbol</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Headline</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Sentiment</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Tags</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Avg Vol</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">PDF</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted-foreground">Published</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => openDetail(row.id)}
                  className="hover:bg-accent/40 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3">
                    <div className="font-semibold text-foreground">{row.symbol}</div>
                    <div className="text-xs text-muted-foreground truncate max-w-[120px]">{row.company}</div>
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <div className="text-foreground text-xs leading-relaxed line-clamp-2">{row.summary || row.headline}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs font-medium ${SENTIMENT_COLORS[row.sentiment]}`}>
                      <SentimentIcon s={row.sentiment} />
                      {row.sentiment}
                    </span>
                    <div className="text-xs text-muted-foreground mt-1">score {row.sentiment_score?.toFixed(2)}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {row.signal_tags.slice(0, 3).map((t) => (
                        <span key={t} className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${TAG_COLORS[t] || 'bg-muted text-foreground'}`}>
                          {t}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{fmt(row.avg_volume || 0)}</td>
                  <td className="px-4 py-3">
                    {row.pdf_extracted
                      ? <span className="text-emerald-400 text-xs">✓ Extracted</span>
                      : <span className="text-muted-foreground text-xs">Headline only</span>}
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground whitespace-nowrap">{row.published_at?.slice(0, 16)}</td>
                </tr>
              ))}
              {rows.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-muted-foreground">
                    No filings found. Filings are analysed automatically every 2 minutes during market hours.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > LIMIT && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-border">
            <button
              disabled={offset === 0}
              onClick={() => fetchData(Math.max(0, offset - LIMIT))}
              className="px-3 py-1.5 text-sm bg-muted rounded-lg disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-xs text-muted-foreground">
              {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
            </span>
            <button
              disabled={offset + LIMIT >= total}
              onClick={() => fetchData(offset + LIMIT)}
              className="px-3 py-1.5 text-sm bg-muted rounded-lg disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Detail modal */}
      {(detail || detailLoading) && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setDetail(null)}>
          <div
            className="bg-card border border-border rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {detailLoading ? (
              <div className="p-12 text-center text-muted-foreground">Loading...</div>
            ) : detail && (
              <div className="p-6 space-y-4">
                {/* Modal header */}
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xl font-bold text-foreground">{detail.symbol}</span>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-medium ${SENTIMENT_COLORS[detail.sentiment]}`}>
                        <SentimentIcon s={detail.sentiment} />
                        {detail.sentiment}
                      </span>
                    </div>
                    <div className="text-sm text-muted-foreground mt-0.5">{detail.company}</div>
                  </div>
                  <button onClick={() => setDetail(null)} className="text-muted-foreground hover:text-foreground text-xl leading-none">×</button>
                </div>

                {/* Headline */}
                <div className="bg-muted rounded-lg p-3 text-sm text-foreground">{detail.headline}</div>

                {/* Summary */}
                {detail.summary && detail.summary !== detail.headline && (
                  <div className="text-sm text-muted-foreground">{detail.summary}</div>
                )}

                {/* Key numbers */}
                {Object.keys(detail.key_numbers || {}).length > 0 && (
                  <div>
                    <div className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Key Numbers</div>
                    <div className="grid grid-cols-2 gap-2">
                      {Object.entries(detail.key_numbers).map(([k, v]) => (
                        <div key={k} className="bg-muted rounded-lg p-2 border border-border">
                          <div className="text-xs text-muted-foreground capitalize">{k.replace(/_/g, ' ')}</div>
                          <div className="text-sm font-semibold text-foreground">₹{(v as number).toLocaleString('en-IN')} Cr</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Signal tags */}
                {detail.signal_tags.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {detail.signal_tags.map((t) => (
                      <span key={t} className={`px-2 py-1 rounded text-xs font-medium ${TAG_COLORS[t] || 'bg-muted text-foreground'}`}>{t}</span>
                    ))}
                  </div>
                )}

                {/* Meta */}
                <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                  <div>Avg Volume: <span className="text-foreground">{fmt(detail.avg_volume || 0)}</span></div>
                  <div>Score: <span className="text-foreground">{detail.sentiment_score?.toFixed(3)}</span></div>
                  <div>Filter: <span className="text-foreground">{detail.filter_reason}</span></div>
                  <div>Published: <span className="text-foreground">{detail.published_at}</span></div>
                </div>

                {/* PDF text toggle */}
                {detail.pdf_text && (
                  <div>
                    <button
                      onClick={() => setShowPdfText(!showPdfText)}
                      className="flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300"
                    >
                      {showPdfText ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      {showPdfText ? 'Hide' : 'Show'} extracted PDF text
                    </button>
                    {showPdfText && (
                      <pre className="mt-2 bg-muted rounded-lg p-3 text-xs text-muted-foreground overflow-x-auto whitespace-pre-wrap max-h-64">
                        {detail.pdf_text}
                      </pre>
                    )}
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-2 border-t border-border">
                  {detail.pdf_url && (
                    <a
                      href={detail.pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-muted rounded-lg text-xs text-foreground hover:bg-accent transition-colors"
                    >
                      <FileText size={14} />
                      Open PDF
                      <ExternalLink size={12} />
                    </a>
                  )}
                  <button
                    onClick={() => rerun(detail.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 rounded-lg text-xs text-white transition-colors"
                  >
                    <RefreshCcw size={14} />
                    Re-analyse
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default FilingAnalysis;
