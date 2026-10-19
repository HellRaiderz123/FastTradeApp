import React, { useEffect, useRef, useState } from 'react';
import {
  createChart, AreaSeries, ColorType,
  type IChartApi, type Time,
} from 'lightweight-charts';
import {
  TrendingUp, TrendingDown, Activity,
  ArrowUpRight, ArrowDownRight, RefreshCw,
  Wallet, Target,
} from 'lucide-react';
import { useTradeStore } from '../lib/store';
import { accountAPI, journalAPI, marketAPI, watchlistAPI } from '../lib/api';
import TradingChart from '../components/TradingChart';
import TwitterSentimentWidget from '../components/TwitterSentimentWidget';
import { cn } from '@/lib/utils';

interface DailyCapitalData {
  date: string;
  closing_capital: number;
  daily_pnl: number;
}

interface QuoteItem {
  symbol: string;
  ltp: number;
  change?: number;
  change_percent?: number;
}

const fmt = (n: number) => n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
const fmtDec = (n: number, d = 2) => n.toLocaleString('en-IN', { minimumFractionDigits: d, maximumFractionDigits: d });

const Dashboard: React.FC = () => {
  const { capital, trades, accountProfile, setTrades, setCapital, setAccountProfile, setLoading } = useTradeStore();
  const [dailyCapitalHistory, setDailyCapitalHistory] = useState<DailyCapitalData[]>([]);
  const [marketQuotes, setMarketQuotes] = useState<QuoteItem[]>([]);
  const [watchlistQuotes, setWatchlistQuotes] = useState<QuoteItem[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchAll = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    await Promise.allSettled([
      fetchAccountData(),
      fetchDailyCapitalHistory(),
      fetchAllTrades(),
      fetchMarketStats(),
      fetchWatchlistQuotes(),
    ]);
    setLastUpdated(new Date());
    if (showRefresh) setRefreshing(false);
  };

  useEffect(() => {
    fetchAll();
    const interval = setInterval(() => fetchAll(), 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchAccountData = async () => {
    try {
      const response = await accountAPI.getProfile();
      setAccountProfile(response.data);
      setCapital(response.data?.capital || 0);
    } catch { /* silent */ }
  };

  const fetchAllTrades = async () => {
    try {
      setLoading(true);
      const response = await journalAPI.getExecutionIntents(100);
      const data = Array.isArray(response?.data) ? response.data : [];
      setTrades(data.filter((t: any) => t.status === 'EXECUTED' || t.status === 'CLOSED'));
    } catch { /* silent */ }
    finally { setLoading(false); }
  };

  const fetchDailyCapitalHistory = async () => {
    try {
      const response = await accountAPI.getDailyCapital(30);
      setDailyCapitalHistory(Array.isArray(response.data) ? response.data : []);
    } catch { /* silent */ }
  };

  const fetchMarketStats = async () => {
    try {
      const response = await marketAPI.getBulkQuotes(['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']);
      setMarketQuotes(Array.isArray(response.data?.quotes) ? response.data.quotes : []);
    } catch { setMarketQuotes([]); }
  };

  const fetchWatchlistQuotes = async () => {
    try {
      const response = await watchlistAPI.getQuotes(1);
      setWatchlistQuotes(Array.isArray(response.data?.quotes) ? response.data.quotes : []);
    } catch { setWatchlistQuotes([]); }
  };

  // Derived stats
  const displayCapital = accountProfile?.capital || capital || 0;
  const today = new Date();
  const isToday = (d?: string) => {
    if (!d) return false;
    const dt = new Date(d);
    return dt.getFullYear() === today.getFullYear() && dt.getMonth() === today.getMonth() && dt.getDate() === today.getDate();
  };
  const tradesToday = trades.filter((t: any) => isToday(t.created_at) || isToday(t.closed_at));
  const todayPnL = tradesToday.reduce((s: number, t: any) => s + Number(t.pnl || 0), 0);
  const pnlPct = displayCapital > 0 ? (todayPnL / displayCapital) * 100 : 0;
  const wins = tradesToday.filter((t: any) => Number(t.pnl) > 0).length;
  const winRate = tradesToday.length > 0 ? (wins / tradesToday.length) * 100 : 0;
  const avgWin = (() => {
    const w = tradesToday.filter((t: any) => Number(t.pnl) > 0);
    return w.length ? w.reduce((s: number, t: any) => s + Number(t.pnl), 0) / w.length : 0;
  })();
  const avgLoss = (() => {
    const l = tradesToday.filter((t: any) => Number(t.pnl) < 0);
    return l.length ? Math.abs(l.reduce((s: number, t: any) => s + Number(t.pnl), 0) / l.length) : 0;
  })();

  const chartData = dailyCapitalHistory.map((item) => ({
    date: new Date(item.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
    capital: Number(item.closing_capital || 0),
    pnl: Number(item.daily_pnl || 0),
  }));

  return (
    <div className="space-y-5">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground tracking-tight">Dashboard</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {lastUpdated
              ? `Updated ${lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}`
              : 'Loading…'}
          </p>
        </div>
        <button
          onClick={() => fetchAll(true)}
          className={cn(
            'flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors',
            refreshing && 'opacity-60 pointer-events-none'
          )}
        >
          <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
          Refresh
        </button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard
          icon={Wallet}
          label="Portfolio Value"
          value={`₹${fmt(displayCapital)}`}
          sub={accountProfile ? 'From broker' : 'Loading…'}
          accent="blue"
        />
        <KpiCard
          icon={todayPnL >= 0 ? TrendingUp : TrendingDown}
          label="Today's P&L"
          value={`${todayPnL >= 0 ? '+' : ''}₹${fmt(Math.abs(todayPnL))}`}
          sub={`${todayPnL >= 0 ? '+' : ''}${fmtDec(pnlPct)}% today`}
          accent={todayPnL >= 0 ? 'green' : 'red'}
          highlight
        />
        <KpiCard
          icon={Activity}
          label="Trades Today"
          value={tradesToday.length.toString()}
          sub={`${wins}W · ${tradesToday.length - wins}L`}
          accent="purple"
        />
        <KpiCard
          icon={Target}
          label="Win Rate"
          value={`${fmtDec(winRate, 1)}%`}
          sub={`Avg win ₹${fmt(avgWin)}`}
          accent={winRate >= 50 ? 'green' : 'orange'}
        />
      </div>

      {/* Charts row — index candles */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {(['NIFTY', 'BANKNIFTY', 'FINNIFTY'] as const).map((sym) => (
          <TradingChart
            key={sym}
            symbol={sym}
            defaultTimeframe="15m"
            height={200}
            showTimeframeSelector={false}
            className="overflow-hidden"
          />
        ))}
      </div>

      {/* Middle row — portfolio chart + account + watchlist */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        {/* Portfolio growth */}
        <Panel className="lg:col-span-7">
          <PanelHeader title="Portfolio Growth" sub="30-day capital curve" />
          <PortfolioChart data={chartData} />
        </Panel>

        {/* Account info */}
        <Panel className="lg:col-span-5">
          <PanelHeader title="Account" sub="Broker snapshot" />
          <div className="px-4 pb-4 space-y-1">
            {accountProfile ? (
              <>
                <AccountRow label="User ID" value={accountProfile.user_id || '—'} />
                <AccountRow label="Email" value={accountProfile.email || '—'} mono={false} />
                <AccountRow label="Equity" value={`₹${fmt(accountProfile.equity || 0)}`} />
                <AccountRow label="Net Worth" value={`₹${fmt(accountProfile.net_worth || 0)}`} />
                <AccountRow label="Available Margin" value={`₹${fmt(accountProfile.margins_available || 0)}`} highlight />
              </>
            ) : (
              <EmptyState text="Loading account…" height={160} />
            )}
          </div>

          {/* Mini trade stats */}
          <div className="mx-4 mb-4 grid grid-cols-2 gap-2 pt-3 border-t border-border">
            <MiniStat label="Avg Win" value={`₹${fmt(avgWin)}`} color="text-emerald-500" />
            <MiniStat label="Avg Loss" value={`₹${fmt(avgLoss)}`} color="text-red-500" />
            <MiniStat label="Total Trades" value={tradesToday.length.toString()} color="text-foreground" />
            <MiniStat label="Win Rate" value={`${fmtDec(winRate, 1)}%`} color={winRate >= 50 ? 'text-emerald-500' : 'text-amber-500'} />
          </div>
        </Panel>
      </div>

      {/* Bottom row — market stats + watchlist + recent trades + sentiment */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
        {/* Market indices */}
        <Panel className="lg:col-span-3">
          <PanelHeader title="Indices" sub="Live quotes" />
          <div className="px-3 pb-3 space-y-1.5">
            {marketQuotes.length > 0 ? marketQuotes.slice(0, 4).map((q) => (
              <IndexRow key={q.symbol} quote={q} />
            )) : <EmptyState text="No market data" height={120} />}
          </div>
        </Panel>

        {/* Watchlist */}
        <Panel className="lg:col-span-3">
          <PanelHeader title="Watchlist" sub="Top movers" />
          <div className="px-3 pb-3 space-y-0.5 max-h-[220px] overflow-y-auto no-scrollbar">
            {watchlistQuotes.length > 0 ? watchlistQuotes.slice(0, 10).map((q) => (
              <WatchRow key={q.symbol} quote={q} />
            )) : <EmptyState text="No watchlist data" height={120} />}
          </div>
        </Panel>

        {/* Recent trades */}
        <Panel className="lg:col-span-3">
          <PanelHeader title="Recent Trades" sub="Today's activity" />
          <div className="px-3 pb-3 space-y-1.5 max-h-[220px] overflow-y-auto no-scrollbar">
            {trades.slice(0, 6).map((trade: any, i: number) => (
              <TradeRow key={i} trade={trade} />
            ))}
            {trades.length === 0 && <EmptyState text="No trades yet" height={120} />}
          </div>
        </Panel>

        {/* Sentiment */}
        <Panel className="lg:col-span-3 overflow-hidden">
          <TwitterSentimentWidget timeframe="1h" />
        </Panel>
      </div>
    </div>
  );
};

/* ── Sub-components ─────────────────────────────────────────── */

const Panel: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
  <div className={cn('rounded-xl border border-border bg-card', className)}>
    {children}
  </div>
);

const PanelHeader: React.FC<{ title: string; sub?: string }> = ({ title, sub }) => (
  <div className="flex items-baseline justify-between px-4 pt-3.5 pb-2">
    <p className="text-sm font-semibold text-foreground">{title}</p>
    {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
  </div>
);

const EmptyState: React.FC<{ text: string; height?: number }> = ({ text, height = 80 }) => (
  <div className={cn('flex items-center justify-center text-xs text-muted-foreground')} style={{ height }}>
    {text}
  </div>
);

type Accent = 'blue' | 'green' | 'red' | 'purple' | 'orange';
const accentIcon: Record<Accent, string> = {
  blue: 'bg-blue-500/15 text-blue-500',
  green: 'bg-emerald-500/15 text-emerald-500',
  red: 'bg-red-500/15 text-red-500',
  purple: 'bg-violet-500/15 text-violet-500',
  orange: 'bg-amber-500/15 text-amber-500',
};
const accentValue: Record<Accent, string> = {
  blue: 'text-foreground',
  green: 'text-emerald-500',
  red: 'text-red-500',
  purple: 'text-foreground',
  orange: 'text-amber-500',
};

const KpiCard: React.FC<{
  icon: React.ElementType;
  label: string;
  value: string;
  sub: string;
  accent: Accent;
  highlight?: boolean;
}> = ({ icon: Icon, label, value, sub, accent, highlight }) => (
  <div className={cn(
    'rounded-xl border border-border bg-card px-4 py-3.5 flex items-start gap-3',
    highlight && 'ring-1 ring-inset ring-border'
  )}>
    <div className={cn('mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', accentIcon[accent])}>
      <Icon className="h-4 w-4" />
    </div>
    <div className="min-w-0">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn('text-lg font-bold leading-tight tracking-tight', accentValue[accent])}>{value}</p>
      <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>
    </div>
  </div>
);

const AccountRow: React.FC<{ label: string; value: string; mono?: boolean; highlight?: boolean }> = ({
  label, value, mono = true, highlight = false,
}) => (
  <div className="flex items-center justify-between py-1.5 border-b border-border/50 last:border-0">
    <span className="text-xs text-muted-foreground">{label}</span>
    <span className={cn('text-xs font-medium', mono && 'font-mono', highlight ? 'text-primary' : 'text-foreground')}>
      {value}
    </span>
  </div>
);

const MiniStat: React.FC<{ label: string; value: string; color: string }> = ({ label, value, color }) => (
  <div className="rounded-lg bg-muted/40 px-3 py-2">
    <p className="text-[10px] text-muted-foreground">{label}</p>
    <p className={cn('text-sm font-bold', color)}>{value}</p>
  </div>
);

const IndexRow: React.FC<{ quote: QuoteItem }> = ({ quote }) => {
  const pct = quote.change_percent ?? 0;
  const up = pct >= 0;
  return (
    <div className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-accent/50 transition-colors">
      <div>
        <p className="text-xs font-semibold text-foreground">{quote.symbol}</p>
        <p className="text-[10px] text-muted-foreground font-mono">₹{fmtDec(quote.ltp)}</p>
      </div>
      <span className={cn(
        'flex items-center gap-0.5 text-[10px] font-semibold',
        up ? 'text-emerald-500' : 'text-red-500'
      )}>
        {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
        {Math.abs(pct).toFixed(2)}%
      </span>
    </div>
  );
};

const WatchRow: React.FC<{ quote: QuoteItem }> = ({ quote }) => {
  const pct = quote.change_percent ?? 0;
  const up = pct >= 0;
  return (
    <div className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-accent/40 transition-colors">
      <span className="text-xs font-medium text-foreground truncate max-w-[100px]">{quote.symbol}</span>
      <span className={cn('text-xs font-mono font-semibold', up ? 'text-emerald-500' : 'text-red-500')}>
        {up ? '+' : ''}{fmtDec(pct)}%
      </span>
    </div>
  );
};

const TradeRow: React.FC<{ trade: any }> = ({ trade }) => {
  const pnl = Number(trade.pnl || 0);
  const up = pnl >= 0;
  return (
    <div className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-accent/50 transition-colors">
      <div className="min-w-0">
        <p className="text-xs font-medium text-foreground truncate">{trade.strategy || '—'}</p>
        <p className="text-[10px] text-muted-foreground">{trade.underlying || '—'}</p>
      </div>
      <div className="text-right shrink-0 ml-2">
        <p className={cn('text-xs font-bold font-mono', up ? 'text-emerald-500' : 'text-red-500')}>
          {up ? '+' : '-'}₹{fmt(Math.abs(pnl))}
        </p>
        <p className={cn('text-[10px]', up ? 'text-emerald-500' : 'text-red-500')}>
          {up ? '+' : ''}{fmtDec(Number(trade.pnl_percent || 0))}%
        </p>
      </div>
    </div>
  );
};

/* ── PortfolioChart — lightweight-charts area line ─────────── */
interface PortfolioChartProps {
  data: { date: string; capital: number }[];
}

function isDark() {
  return !document.documentElement.classList.contains('light-mode');
}

const PortfolioChart: React.FC<PortfolioChartProps> = ({ data }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const dark = isDark();
    const bg   = dark ? '#0b1222' : '#ffffff';
    const text = dark ? '#94a3b8' : '#64748b';
    const grid = dark ? 'rgba(148,163,184,0.07)' : 'rgba(100,116,139,0.1)';
    const bdr  = dark ? 'rgba(148,163,184,0.12)' : 'rgba(100,116,139,0.18)';

    const chart = createChart(el, {
      width: el.clientWidth,
      height: 220,
      layout: { background: { type: ColorType.Solid, color: bg }, textColor: text, fontSize: 11 },
      grid: { vertLines: { color: grid }, horzLines: { color: grid } },
      rightPriceScale: { borderColor: bdr },
      timeScale: { borderColor: bdr, timeVisible: false },
      crosshair: {
        vertLine: { color: 'rgba(148,163,184,0.35)', labelBackgroundColor: dark ? '#1e293b' : '#f1f5f9' },
        horzLine: { color: 'rgba(148,163,184,0.35)', labelBackgroundColor: dark ? '#1e293b' : '#f1f5f9' },
      },
      handleScroll: false,
      handleScale: false,
    });
    chartRef.current = chart;

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#10b981',
      topColor: 'rgba(16,185,129,0.22)',
      bottomColor: 'rgba(16,185,129,0)',
      lineWidth: 2,
      priceFormat: { type: 'price', precision: 0, minMove: 1 },
    });

    if (data.length > 0) {
      // Use sequential integer times since we only have date strings
      const bars = data.map((d, i) => ({ time: (i + 1) as Time, value: d.capital }));
      series.setData(bars);
      chart.timeScale().fitContent();
    }

    const ro = new ResizeObserver(() => {
      chartRef.current?.applyOptions({ width: el.clientWidth });
    });
    ro.observe(el);

    // Theme observer
    const mo = new MutationObserver(() => {
      const d2 = isDark();
      chartRef.current?.applyOptions({
        layout: { background: { type: ColorType.Solid, color: d2 ? '#0b1222' : '#ffffff' }, textColor: d2 ? '#94a3b8' : '#64748b' },
      });
    });
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });

    return () => { ro.disconnect(); mo.disconnect(); chart.remove(); chartRef.current = null; };
  }, [data]);

  if (data.length === 0) {
    return <div className="flex items-center justify-center h-[220px] text-xs text-muted-foreground">No portfolio history yet</div>;
  }

  return <div className="px-4 pb-4"><div ref={containerRef} style={{ height: 220 }} /></div>;
};

export default Dashboard;
