import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, RefreshCw, TrendingUp, BarChart3,
  Newspaper, BookOpen, AlertCircle, ExternalLink, Clock,
  Building2, Activity, ChevronDown, ChevronUp, FileText, Star
} from 'lucide-react';
import { fundamentalsAPI, FundamentalsData, PeerRow } from '../api/fundamentalsAPI';
import { authTokenStore } from '../lib/api';

interface NewsArticle {
  title: string;
  description: string;
  source: string;
  url: string;
  publishedAt: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
  imageUrl?: string;
}

type Tab = 'fundamentals' | 'news' | 'peers';

interface FundamentalsPanelProps {
  initialSymbol?: string;
  compact?: boolean;
}

const fmt = (v: number | null | undefined, digits = 2): string =>
  v == null ? 'N/A' : v.toLocaleString('en-IN', { maximumFractionDigits: digits });

const fmtCr = (v: number | null | undefined): string => {
  if (v == null) return 'N/A';
  if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L Cr`;
  if (v >= 1000) return `₹${(v / 1000).toFixed(1)}K Cr`;
  return `₹${v.toFixed(0)} Cr`;
};

const fmtNum = (v: string | number | null | undefined): string => {
  if (v == null) return 'N/A';
  const n = typeof v === 'string' ? parseFloat(v.replace(/,/g, '').replace('%', '')) : v;
  if (isNaN(n)) return String(v);
  return n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
};

const sentimentColor = (s?: string) => {
  if (s === 'positive') return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
  if (s === 'negative') return 'text-red-400 bg-red-500/10 border-red-500/20';
  return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
};

const MetricCard: React.FC<{ label: string; value: string; sub?: string; color?: string }> = ({
  label, value, sub, color = 'text-white'
}) => (
  <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4">
    <p className="text-xs text-slate-400 mb-1">{label}</p>
    <p className={`text-xl font-bold ${color}`}>{value}</p>
    {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
  </div>
);

const SectionHeader: React.FC<{ title: string; icon: React.ElementType }> = ({ title, icon: Icon }) => (
  <div className="flex items-center gap-2 mb-3">
    <Icon size={14} className="text-emerald-400" />
    <h3 className="text-sm font-semibold text-white">{title}</h3>
  </div>
);

const FundamentalsPanel: React.FC<FundamentalsPanelProps> = ({ initialSymbol = '', compact = false }) => {
  const [inputSymbol, setInputSymbol] = useState(initialSymbol);
  const [activeSymbol, setActiveSymbol] = useState(initialSymbol);
  const [tab, setTab] = useState<Tab>('fundamentals');
  const [data, setData] = useState<FundamentalsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [aboutExpanded, setAboutExpanded] = useState(false);
  const [showAllQuarters, setShowAllQuarters] = useState(false);

  const fetchFundamentals = useCallback(async (sym: string, force = false) => {
    if (!sym) return;
    setLoading(true);
    setError(null);
    try {
      const res = force ? await fundamentalsAPI.refresh(sym) : await fundamentalsAPI.get(sym);
      setData(res.data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load fundamentals');
      setData(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  const fetchNews = useCallback(async (sym: string) => {
    setNewsLoading(true);
    try {
      const token = authTokenStore.get();
      const res = await fetch(`/api/stock-news/${sym}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const json = await res.json();
      setNews(json.articles || []);
    } catch {
      setNews([]);
    } finally {
      setNewsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (activeSymbol) {
      fetchFundamentals(activeSymbol);
      fetchNews(activeSymbol);
    }
  }, [activeSymbol, fetchFundamentals, fetchNews]);

  useEffect(() => {
    if (initialSymbol && initialSymbol !== activeSymbol) {
      setInputSymbol(initialSymbol);
      setActiveSymbol(initialSymbol);
    }
  }, [initialSymbol]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const sym = inputSymbol.trim().toUpperCase();
    if (sym) setActiveSymbol(sym);
  };

  const handleRefresh = async () => {
    if (!activeSymbol) return;
    setRefreshing(true);
    await fetchFundamentals(activeSymbol, true);
  };

  const Range52w = ({ data }: { data: FundamentalsData }) => {
    const { week52_low, week52_high, current_price } = data;
    if (!week52_low || !week52_high || !current_price) return null;
    const pct = Math.min(100, Math.max(0,
      ((current_price - week52_low) / (week52_high - week52_low)) * 100
    ));
    return (
      <div className="bg-slate-800/60 border border-slate-700/50 rounded-xl p-4 col-span-2">
        <p className="text-xs text-slate-400 mb-3">52-Week Range</p>
        <div className="relative h-2 bg-slate-700 rounded-full">
          <div className="absolute h-full bg-gradient-to-r from-red-500 to-emerald-500 rounded-full" style={{ width: '100%', opacity: 0.3 }} />
          <div className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg border-2 border-emerald-400"
            style={{ left: `calc(${pct}% - 6px)` }} />
        </div>
        <div className="flex justify-between mt-2 text-xs text-slate-400">
          <span>₹{fmt(week52_low)}</span>
          <span className="text-white font-semibold">₹{fmt(current_price)} ({pct.toFixed(0)}%)</span>
          <span>₹{fmt(week52_high)}</span>
        </div>
      </div>
    );
  };

  // Build quarterly results columns (last 8 quarters)
  const getQtrCols = () => {
    if (!data?.quarterly_results?.length) return [];
    return Object.keys(data.quarterly_results[0]).filter(k => k !== 'line_item');
  };

  // Build annual P&L columns
  const getPnlCols = () => {
    if (!data?.pnl_annual?.length) return [];
    return Object.keys(data.pnl_annual[0]).filter(k => k !== 'line_item').reverse();
  };

  // Key P&L rows to show
  const KEY_QTR_ROWS = ['Sales', 'Operating Profit', 'OPM %', 'Net Profit', 'EPS in Rs'];
  const KEY_PNL_ROWS = ['Sales', 'Operating Profit', 'OPM %', 'Net Profit', 'EPS in Rs', 'Dividend Payout %'];

  const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
    { id: 'fundamentals', label: 'Fundamentals', icon: BarChart3 },
    { id: 'news', label: 'News', icon: Newspaper },
    { id: 'peers', label: 'Peers', icon: TrendingUp },
  ];

  return (
    <div className={compact ? '' : 'min-h-screen bg-slate-950 p-6'}>
      {!compact && (
        <form onSubmit={handleSearch} className="flex gap-3 mb-6">
          <div className="relative flex-1 max-w-md">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              value={inputSymbol}
              onChange={e => setInputSymbol(e.target.value.toUpperCase())}
              placeholder="Enter symbol e.g. TCS, RELIANCE"
              className="w-full pl-9 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 text-sm focus:outline-none focus:border-emerald-500"
            />
          </div>
          <button type="submit" className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition">
            Search
          </button>
        </form>
      )}

      {!activeSymbol && (
        <div className="text-center py-16 text-slate-500">
          <BookOpen size={48} className="mx-auto mb-3 opacity-40" />
          <p>Enter a stock symbol to view fundamentals and news</p>
        </div>
      )}

      {activeSymbol && (
        <>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-white">{activeSymbol}</h2>
              {data?.company_name && <p className="text-sm text-slate-400">{data.company_name}</p>}
              {data?.sector && (
                <div className="flex items-center gap-2 mt-1">
                  <Building2 size={12} className="text-slate-500" />
                  <span className="text-xs text-slate-500">{data.sector} · {data.industry}</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              {data?.from_cache && (
                <span className="text-xs text-slate-500 flex items-center gap-1">
                  <Clock size={11} />
                  Cached {data.cached_at ? new Date(data.cached_at).toLocaleDateString() : ''}
                </span>
              )}
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
                title="Force refresh (use after quarterly results)"
              >
                <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          <div className="flex gap-2 mb-5">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  tab === id
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                }`}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-lg mb-4">
              <AlertCircle size={16} className="text-red-400" />
              <span className="text-sm text-red-400">{error}</span>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Activity size={28} className="text-emerald-400 animate-pulse" />
            </div>
          ) : (
            <>
              {/* ── Fundamentals Tab ── */}
              {tab === 'fundamentals' && data && (
                <div className="space-y-5">

                  {/* Key metrics grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <MetricCard label="Market Cap" value={fmtCr(data.market_cap)} />
                    <MetricCard label="Current Price" value={data.current_price ? `₹${fmt(data.current_price)}` : 'N/A'} />
                    <MetricCard
                      label="Stock P/E"
                      value={fmt(data.pe_ratio)}
                      color={data.pe_ratio && data.pe_ratio < 20 ? 'text-emerald-400' : data.pe_ratio && data.pe_ratio > 40 ? 'text-red-400' : 'text-white'}
                    />
                    <MetricCard label="Book Value" value={data.book_value ? `₹${fmt(data.book_value)}` : 'N/A'} />
                    <MetricCard
                      label="ROE %"
                      value={fmt(data.roe)}
                      color={data.roe && data.roe > 15 ? 'text-emerald-400' : 'text-white'}
                    />
                    <MetricCard
                      label="ROCE %"
                      value={fmt(data.roce)}
                      color={data.roce && data.roce > 15 ? 'text-emerald-400' : 'text-white'}
                    />
                    <MetricCard label="Dividend Yield %" value={fmt(data.dividend_yield)} />
                    <MetricCard label="Face Value" value={data.face_value ? `₹${fmt(data.face_value)}` : 'N/A'} />
                    {data.eps != null && (
                      <MetricCard label="EPS (Annual)" value={`₹${fmt(data.eps)}`} />
                    )}
                    {data.opm_pct != null && (
                      <MetricCard
                        label="OPM %"
                        value={`${fmt(data.opm_pct)}%`}
                        color={data.opm_pct > 20 ? 'text-emerald-400' : data.opm_pct < 10 ? 'text-red-400' : 'text-white'}
                      />
                    )}
                    {data.npm_pct != null && (
                      <MetricCard
                        label="NPM %"
                        value={`${fmt(data.npm_pct)}%`}
                        color={data.npm_pct > 15 ? 'text-emerald-400' : data.npm_pct < 5 ? 'text-red-400' : 'text-white'}
                      />
                    )}
                    {data.debt_to_equity != null && (
                      <MetricCard
                        label="Debt / Equity"
                        value={fmt(data.debt_to_equity)}
                        color={data.debt_to_equity < 0.5 ? 'text-emerald-400' : data.debt_to_equity > 2 ? 'text-red-400' : 'text-white'}
                      />
                    )}
                    <Range52w data={data} />
                  </div>

                  {/* About */}
                  {data.about && (
                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                      <SectionHeader title="About" icon={BookOpen} />
                      <p className={`text-sm text-slate-300 leading-relaxed ${aboutExpanded ? '' : 'line-clamp-3'}`}>
                        {data.about}
                      </p>
                      <button
                        onClick={() => setAboutExpanded(v => !v)}
                        className="mt-2 flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        {aboutExpanded ? <><ChevronUp size={12} /> Show less</> : <><ChevronDown size={12} /> Show more</>}
                      </button>
                    </div>
                  )}

                  {/* Key Points */}
                  {data.key_points && (
                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                      <SectionHeader title="Key Points" icon={Star} />
                      <pre className="text-xs text-slate-300 leading-relaxed whitespace-pre-wrap font-sans">
                        {data.key_points}
                      </pre>
                    </div>
                  )}

                  {/* Quarterly Results */}
                  {data.quarterly_results && data.quarterly_results.length > 0 && (() => {
                    const cols = getQtrCols();
                    const rows = data.quarterly_results.filter(r =>
                      showAllQuarters ? true : KEY_QTR_ROWS.includes(String(r.line_item))
                    );
                    return (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                        <div className="flex items-center justify-between mb-3">
                          <SectionHeader title="Quarterly Results (₹ Cr)" icon={BarChart3} />
                          <button
                            onClick={() => setShowAllQuarters(v => !v)}
                            className="text-xs text-slate-400 hover:text-white"
                          >
                            {showAllQuarters ? 'Show less' : 'Show all rows'}
                          </button>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-slate-700/50 text-slate-400">
                                <th className="text-left py-2 pr-4 font-medium">Item</th>
                                {cols.map(c => <th key={c} className="text-right py-2 px-2 font-medium">{c}</th>)}
                              </tr>
                            </thead>
                            <tbody>
                              {rows.map((row, i) => (
                                <tr key={i} className="border-b border-slate-700/20 hover:bg-slate-700/20">
                                  <td className="py-2 pr-4 text-slate-300 font-medium whitespace-nowrap">{String(row.line_item)}</td>
                                  {cols.map(c => (
                                    <td key={c} className="text-right py-2 px-2 text-slate-300">
                                      {fmtNum(row[c])}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Annual P&L */}
                  {data.pnl_annual && data.pnl_annual.length > 0 && (() => {
                    const cols = getPnlCols();
                    const rows = data.pnl_annual.filter(r => KEY_PNL_ROWS.includes(String(r.line_item)));
                    return (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                        <SectionHeader title="Annual P&L (₹ Cr)" icon={BarChart3} />
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-slate-700/50 text-slate-400">
                                <th className="text-left py-2 pr-4 font-medium">Item</th>
                                {cols.map(c => <th key={c} className="text-right py-2 px-2 font-medium">{c}</th>)}
                              </tr>
                            </thead>
                            <tbody>
                              {rows.map((row, i) => (
                                <tr key={i} className="border-b border-slate-700/20 hover:bg-slate-700/20">
                                  <td className="py-2 pr-4 text-slate-300 font-medium whitespace-nowrap">{String(row.line_item)}</td>
                                  {cols.map(c => (
                                    <td key={c} className="text-right py-2 px-2 text-slate-300">
                                      {fmtNum(row[c])}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Shareholding Pattern */}
                  {data.shareholding_quarterly && data.shareholding_quarterly.length > 0 && (() => {
                    const sh = data.shareholding_quarterly;
                    const cols = Object.keys(sh[0]).filter(k => k !== 'holder_type').slice(-6);
                    return (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                        <SectionHeader title="Shareholding Pattern (%)" icon={Activity} />
                        <div className="overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-slate-700/50 text-slate-400">
                                <th className="text-left py-2 pr-4 font-medium">Holder</th>
                                {cols.map(c => <th key={c} className="text-right py-2 px-2 font-medium">{c}</th>)}
                              </tr>
                            </thead>
                            <tbody>
                              {sh.map((row, i) => (
                                <tr key={i} className="border-b border-slate-700/20 hover:bg-slate-700/20">
                                  <td className="py-2 pr-4 text-slate-300 font-medium">{row.holder_type}</td>
                                  {cols.map(c => (
                                    <td key={c} className="text-right py-2 px-2 text-slate-300">{row[c] ?? '—'}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Annual Reports & Credit Ratings */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {data.annual_reports && data.annual_reports.length > 0 && (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                        <SectionHeader title="Annual Reports" icon={FileText} />
                        <div className="space-y-2">
                          {data.annual_reports.slice(0, 5).map((r, i) => (
                            <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                              className="flex items-center justify-between text-xs text-slate-300 hover:text-emerald-400 transition">
                              <span>{r.title}</span>
                              <ExternalLink size={11} className="shrink-0 ml-2" />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                    {data.credit_ratings && data.credit_ratings.length > 0 && (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                        <SectionHeader title="Credit Ratings" icon={Star} />
                        <div className="space-y-2">
                          {data.credit_ratings.slice(0, 5).map((r, i) => (
                            <a key={i} href={r.url} target="_blank" rel="noopener noreferrer"
                              className="flex items-center justify-between text-xs text-slate-300 hover:text-emerald-400 transition">
                              <span>{r.detail}</span>
                              <ExternalLink size={11} className="shrink-0 ml-2" />
                            </a>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <p className="text-xs text-slate-600 text-right">
                    Source: Screener.in via yashsarawgi.me · Cache TTL: {data.cache_ttl_days} days
                    {data.from_cache ? ' · Serving from cache' : ' · Fresh fetch'}
                  </p>
                </div>
              )}

              {/* ── News Tab ── */}
              {tab === 'news' && (
                <div className="space-y-3">
                  {newsLoading ? (
                    <div className="flex items-center justify-center py-10">
                      <Activity size={24} className="text-emerald-400 animate-pulse" />
                    </div>
                  ) : news.length > 0 ? (
                    news.map((article, idx) => (
                      <div key={idx} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4 hover:bg-slate-800/70 transition">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-start gap-2 mb-1">
                              <h4 className="text-white text-sm font-semibold leading-snug">{article.title}</h4>
                              {article.sentiment && (
                                <span className={`shrink-0 text-xs px-2 py-0.5 rounded-full border ${sentimentColor(article.sentiment)}`}>
                                  {article.sentiment}
                                </span>
                              )}
                            </div>
                            {article.description && (
                              <p className="text-slate-400 text-xs mb-2 line-clamp-2">{article.description}</p>
                            )}
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-slate-500">{article.source} · {new Date(article.publishedAt).toLocaleDateString()}</span>
                              <a href={article.url} target="_blank" rel="noopener noreferrer"
                                className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300">
                                Read <ExternalLink size={11} />
                              </a>
                            </div>
                          </div>
                          {article.imageUrl && (
                            <img src={article.imageUrl} alt="" className="w-16 h-16 object-cover rounded-lg shrink-0" />
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-10">
                      <Newspaper size={40} className="mx-auto text-slate-600 mb-2" />
                      <p className="text-slate-400 text-sm">No news found for {activeSymbol}</p>
                    </div>
                  )}
                </div>
              )}

              {/* ── Peers Tab ── */}
              {tab === 'peers' && (
                <div>
                  {data?.peer_comparison && data.peer_comparison.length > 0 ? (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-slate-700/50 text-slate-400 text-xs">
                            <th className="text-left py-3 px-3">Company</th>
                            <th className="text-right py-3 px-3">CMP</th>
                            <th className="text-right py-3 px-3">P/E</th>
                            <th className="text-right py-3 px-3">ROCE %</th>
                            <th className="text-right py-3 px-3">Mkt Cap</th>
                            <th className="text-right py-3 px-3">Qtr Profit ▲%</th>
                            <th className="text-right py-3 px-3">Qtr Sales ▲%</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(data.peer_comparison as PeerRow[]).map((peer, idx) => {
                            const isMain = peer.Company === activeSymbol || idx === 0;
                            return (
                              <tr key={idx} className={`border-b border-slate-700/30 ${isMain ? 'bg-emerald-500/5' : 'hover:bg-slate-800/30'} transition`}>
                                <td className="py-3 px-3">
                                  <span className={`font-semibold ${isMain ? 'text-emerald-400' : 'text-white'}`}>{peer.Company}</span>
                                </td>
                                <td className="text-right py-3 px-3 text-white">₹{fmt(peer['CMP  Rs.'])}</td>
                                <td className="text-right py-3 px-3 text-slate-300">{fmt(peer['P/E'])}</td>
                                <td className={`text-right py-3 px-3 ${(peer['ROCE  %'] ?? 0) > 15 ? 'text-emerald-400' : 'text-slate-300'}`}>
                                  {fmt(peer['ROCE  %'])}
                                </td>
                                <td className="text-right py-3 px-3 text-slate-300">{fmtCr(peer['Mar Cap  Rs.Cr.'])}</td>
                                <td className={`text-right py-3 px-3 ${(peer['Qtr Profit Var  %'] ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                  {peer['Qtr Profit Var  %'] != null ? `${peer['Qtr Profit Var  %'] >= 0 ? '+' : ''}${fmt(peer['Qtr Profit Var  %'])}%` : 'N/A'}
                                </td>
                                <td className={`text-right py-3 px-3 ${(peer['Qtr Sales Var  %'] ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                  {peer['Qtr Sales Var  %'] != null ? `${peer['Qtr Sales Var  %'] >= 0 ? '+' : ''}${fmt(peer['Qtr Sales Var  %'])}%` : 'N/A'}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="text-center py-10">
                      <TrendingUp size={40} className="mx-auto text-slate-600 mb-2" />
                      <p className="text-slate-400 text-sm">No peer data available</p>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
};

export default FundamentalsPanel;
