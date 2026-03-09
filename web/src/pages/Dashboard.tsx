import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { TrendingUp, DollarSign, Activity, Target, Lock, Unlock, Save } from 'lucide-react';
import { useTradeStore } from '../lib/store';
import { accountAPI, journalAPI, marketAPI, watchlistAPI } from '../lib/api';
import GridLayout from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import CandleChart from '../components/CandleChart';
import TwitterSentimentWidget from '../components/TwitterSentimentWidget';

const AnyGridLayout = GridLayout as any;

interface DailyCapitalData {
  date: string;
  opening_capital: number;
  closing_capital: number;
  daily_pnl: number;
  daily_return_pct: number;
}

interface QuoteItem {
  symbol: string;
  ltp: number;
  change?: number;
  change_percent?: number;
}

const DEFAULT_LAYOUT = [
  { i: 'metrics', x: 0, y: 0, w: 12, h: 2 },
  { i: 'nifty', x: 0, y: 2, w: 4, h: 4 },
  { i: 'banknifty', x: 4, y: 2, w: 4, h: 4 },
  { i: 'finnifty', x: 8, y: 2, w: 4, h: 4 },
  { i: 'portfolio', x: 0, y: 6, w: 8, h: 4 },
  { i: 'account', x: 8, y: 6, w: 4, h: 4 },
  { i: 'marketstats', x: 0, y: 10, w: 4, h: 3 },
  { i: 'watchlist', x: 4, y: 10, w: 4, h: 3 },
  { i: 'stats', x: 8, y: 10, w: 4, h: 3 },
  { i: 'twitter', x: 0, y: 13, w: 6, h: 4 },
  { i: 'trades', x: 6, y: 13, w: 6, h: 4 },
];

const Dashboard: React.FC = () => {
  const { capital, trades, accountProfile, setTrades, setCapital, setAccountProfile, setLoading } = useTradeStore();
  const [dailyCapitalHistory, setDailyCapitalHistory] = useState<DailyCapitalData[]>([]);
  const [locked, setLocked] = useState(true);
  const [layout, setLayout] = useState(() => {
    const saved = localStorage.getItem('dashboard_layout');
    if (!saved) return DEFAULT_LAYOUT;
    try {
      return JSON.parse(saved);
    } catch {
      return DEFAULT_LAYOUT;
    }
  });
  const [marketQuotes, setMarketQuotes] = useState<QuoteItem[]>([]);
  const [watchlistQuotes, setWatchlistQuotes] = useState<QuoteItem[]>([]);
  const [gridWidth, setGridWidth] = useState<number>(() => Math.max(980, window.innerWidth - 360));

  useEffect(() => {
    const fetchAll = async () => {
      await Promise.allSettled([
        fetchAccountData(),
        fetchDailyCapitalHistory(),
        fetchAllTrades(),
        fetchMarketStats(),
        fetchWatchlistQuotes(),
      ]);
    };

    fetchAll();
    const interval = setInterval(fetchAll, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const onResize = () => {
      setGridWidth(Math.max(980, window.innerWidth - 360));
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const fetchAccountData = async () => {
    try {
      const response = await accountAPI.getProfile();
      setAccountProfile(response.data);
      setCapital(response.data?.capital || 0);
    } catch (error) {
      console.error('Failed to fetch account data:', error);
    }
  };

  const fetchAllTrades = async () => {
    try {
      setLoading(true);
      const response = await journalAPI.getExecutionIntents(100);
      const data = Array.isArray(response?.data) ? response.data : [];
      const allTrades = data.filter((trade: any) => trade.status === 'EXECUTED' || trade.status === 'CLOSED');
      setTrades(allTrades);
    } catch (error) {
      console.error('Failed to fetch trades:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchDailyCapitalHistory = async () => {
    try {
      const response = await accountAPI.getDailyCapital(30);
      setDailyCapitalHistory(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Failed to fetch daily capital history:', error);
    }
  };

  const fetchMarketStats = async () => {
    try {
      const response = await marketAPI.getBulkQuotes(['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'SENSEX']);
      const quotes = Array.isArray(response.data?.quotes) ? response.data.quotes : [];
      setMarketQuotes(quotes);
    } catch (error) {
      console.error('Failed to fetch market stats:', error);
      setMarketQuotes([]);
    }
  };

  const fetchWatchlistQuotes = async () => {
    try {
      const response = await watchlistAPI.getQuotes(1);
      const quotes = Array.isArray(response.data?.quotes) ? response.data.quotes : [];
      setWatchlistQuotes(quotes);
    } catch (error) {
      console.error('Failed to fetch watchlist quotes:', error);
      setWatchlistQuotes([]);
    }
  };

  const saveLayout = () => {
    localStorage.setItem('dashboard_layout', JSON.stringify(layout));
  };

  const resetLayout = () => {
    localStorage.removeItem('dashboard_layout');
    setLayout(DEFAULT_LAYOUT);
  };

  const displayCapital = accountProfile?.capital || capital || 0;
  const today = new Date();
  const isToday = (dateStr?: string) => {
    if (!dateStr) return false;
    const date = new Date(dateStr);
    return date.getFullYear() === today.getFullYear() && date.getMonth() === today.getMonth() && date.getDate() === today.getDate();
  };

  const tradesToday = trades.filter((trade: any) => isToday(trade.created_at) || isToday(trade.closed_at));
  const todayPnL = tradesToday.reduce((sum: number, trade: any) => sum + Number(trade.pnl || 0), 0);
  const pnlPercent = displayCapital > 0 ? ((todayPnL / displayCapital) * 100).toFixed(2) : '0.00';
  const winCount = tradesToday.filter((trade: any) => Number(trade.pnl) > 0).length;
  const winRate = tradesToday.length > 0 ? ((winCount / tradesToday.length) * 100).toFixed(1) : '0.0';

  const chartData = dailyCapitalHistory.map((item) => ({
    time: new Date(item.date).toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
    balance: Number(item.closing_capital || 0),
  }));

  const tradeStats = {
    totalTrades: tradesToday.length,
    wins: tradesToday.filter((trade: any) => Number(trade.pnl) > 0).length,
    losses: tradesToday.filter((trade: any) => Number(trade.pnl) < 0).length,
    averageWin: (() => {
      const wins = tradesToday.filter((trade: any) => Number(trade.pnl) > 0);
      if (!wins.length) return 0;
      return wins.reduce((sum: number, trade: any) => sum + Number(trade.pnl || 0), 0) / wins.length;
    })(),
    averageLoss: (() => {
      const losses = tradesToday.filter((trade: any) => Number(trade.pnl) < 0);
      if (!losses.length) return 0;
      return losses.reduce((sum: number, trade: any) => sum + Number(trade.pnl || 0), 0) / losses.length;
    })(),
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white">Dashboard</h1>
          <p className="text-slate-400 mt-1">{locked ? 'Layout is locked' : 'Drag and resize widgets to customize'}</p>
        </div>

        <div className="flex items-center gap-2">
          <button onClick={resetLayout} className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg transition-colors">Reset Layout</button>
          <button onClick={saveLayout} className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors">
            <Save className="w-4 h-4" /> Save Layout
          </button>
          <button
            onClick={() => setLocked((current) => !current)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${locked ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-green-600 hover:bg-green-700 text-white'}`}
          >
            {locked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
            {locked ? 'Locked' : 'Unlocked'}
          </button>
        </div>
      </div>

      <AnyGridLayout
        className="layout"
        layout={layout}
        cols={12}
        rowHeight={80}
        width={gridWidth}
        isDraggable={!locked}
        isResizable={!locked}
        onLayoutChange={(newLayout: any) => setLayout(newLayout)}
        draggableHandle=".drag-handle"
      >
        <Widget key="metrics" title="Key Metrics" locked={locked} keyName="metrics">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 p-4">
            <MetricCard icon={DollarSign} label="Capital" value={`₹${displayCapital.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`} change={accountProfile ? 'From Zerodha' : 'Loading...'} color="blue" />
            <MetricCard icon={TrendingUp} label="Today's P&L" value={`₹${todayPnL.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`} change={`${pnlPercent}%`} color={todayPnL >= 0 ? 'green' : 'red'} />
            <MetricCard icon={Activity} label="Total Trades" value={tradeStats.totalTrades.toString()} change={`${tradeStats.totalTrades} today`} color="purple" />
            <MetricCard icon={Target} label="Win Rate" value={`${winRate}%`} change={`${winCount}/${tradeStats.totalTrades} wins`} color={parseFloat(winRate) >= 50 ? 'green' : 'orange'} />
          </div>
        </Widget>

        <Widget key="nifty" title="NIFTY" locked={locked} keyName="nifty" padding="p-2">
          <CandleChart symbol="NIFTY" defaultTimeframe="15m" height={250} showTimeframeSelector={false} />
        </Widget>

        <Widget key="banknifty" title="BANKNIFTY" locked={locked} keyName="banknifty" padding="p-2">
          <CandleChart symbol="BANKNIFTY" defaultTimeframe="15m" height={250} showTimeframeSelector={false} />
        </Widget>

        <Widget key="finnifty" title="FINNIFTY" locked={locked} keyName="finnifty" padding="p-2">
          <CandleChart symbol="FINNIFTY" defaultTimeframe="15m" height={250} showTimeframeSelector={false} />
        </Widget>

        <Widget key="portfolio" title="Portfolio Growth" locked={locked} keyName="portfolio">
          <div className="p-6 h-full">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="time" stroke="#94a3b8" />
                  <YAxis stroke="#94a3b8" />
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px' }} labelStyle={{ color: '#f1f5f9' }} />
                  <Area type="monotone" dataKey="balance" stroke="#10B981" fillOpacity={1} fill="url(#colorBalance)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-center text-slate-400 py-16">No portfolio history available yet</p>
            )}
          </div>
        </Widget>

        <Widget key="account" title="Account Info" locked={locked} keyName="account">
          <div className="p-6 space-y-3">
            {accountProfile ? (
              <>
                <StatItem label="User ID" value={accountProfile.user_id || 'N/A'} />
                <StatItem label="Email" value={accountProfile.email || 'N/A'} />
                <StatItem label="Equity" value={`₹${Math.round(accountProfile.equity || 0).toLocaleString('en-IN')}`} />
                <StatItem label="Net Worth" value={`₹${Math.round(accountProfile.net_worth || 0).toLocaleString('en-IN')}`} />
                <StatItem label="Available Margin" value={`₹${Math.round(accountProfile.margins_available || 0).toLocaleString('en-IN')}`} />
              </>
            ) : (
              <p className="text-slate-400 text-sm">Loading account data...</p>
            )}
          </div>
        </Widget>

        <Widget key="marketstats" title="Market Stats" locked={locked} keyName="marketstats">
          <div className="p-4 grid grid-cols-2 gap-3">
            {marketQuotes.length > 0 ? marketQuotes.slice(0, 4).map((quote) => (
              <div key={quote.symbol} className="bg-slate-800 rounded p-3">
                <p className="text-slate-400 text-xs">{quote.symbol}</p>
                <p className={`text-xl font-bold mt-1 ${(quote.change_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>₹{Number(quote.ltp || 0).toFixed(2)}</p>
                <p className={`text-xs ${(quote.change_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{(quote.change_percent || 0) >= 0 ? '+' : ''}{Number(quote.change_percent || 0).toFixed(2)}%</p>
              </div>
            )) : <p className="text-center text-slate-400 col-span-2 py-8">No market stats available</p>}
          </div>
        </Widget>

        <Widget key="watchlist" title="Quick Watchlist" locked={locked} keyName="watchlist">
          <div className="p-4 space-y-2 text-sm custom-scrollbar overflow-y-auto max-h-[220px]">
            {watchlistQuotes.length > 0 ? watchlistQuotes.slice(0, 8).map((quote) => (
              <div key={quote.symbol} className="flex items-center justify-between py-2 border-b border-slate-800">
                <span className="text-white">{quote.symbol}</span>
                <span className={(quote.change_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}>
                  {(quote.change_percent || 0) >= 0 ? '+' : ''}{Number(quote.change_percent || 0).toFixed(2)}%
                </span>
              </div>
            )) : <p className="text-center text-slate-400 py-8">No watchlist data</p>}
          </div>
        </Widget>

        <Widget key="stats" title="Trade Statistics" locked={locked} keyName="stats">
          <div className="p-4 grid grid-cols-2 gap-3">
            <StatCard label="Trades" value={tradeStats.totalTrades.toString()} valueClass="text-white" />
            <StatCard label="Wins" value={tradeStats.wins.toString()} valueClass="text-green-400" />
            <StatCard label="Losses" value={tradeStats.losses.toString()} valueClass="text-red-400" />
            <StatCard label="Avg Win" value={`₹${Math.round(tradeStats.averageWin).toLocaleString('en-IN')}`} valueClass="text-green-400" />
          </div>
        </Widget>

        <Widget key="twitter" title="" locked={locked} keyName="twitter" padding="p-0">
          <TwitterSentimentWidget timeframe="1h" />
        </Widget>

        <Widget key="trades" title="Recent Trades" locked={locked} keyName="trades">
          <div className="p-6 space-y-2">
            {trades.slice(0, 6).map((trade: any, idx: number) => (
              <TradeRow key={idx} trade={trade} />
            ))}
            {trades.length === 0 && <p className="text-center text-slate-400 py-8">No trades available</p>}
          </div>
        </Widget>
      </AnyGridLayout>
    </div>
  );
};

const Widget: React.FC<{ title: string; locked: boolean; keyName: string; children: React.ReactNode; padding?: string }> = ({ title, locked, keyName, children, padding = 'p-0' }) => (
  <div className="bg-slate-900 rounded-lg border border-slate-800 overflow-hidden">
    <div className="drag-handle bg-slate-800 px-4 py-2 cursor-move border-b border-slate-700 flex items-center justify-between">
      <span className="text-white font-semibold">{title}</span>
      {!locked && <span className="text-slate-500 text-xs">Drag to move</span>}
    </div>
    <div className={padding}>{children}</div>
  </div>
);

const StatCard: React.FC<{ label: string; value: string; valueClass: string }> = ({ label, value, valueClass }) => (
  <div className="bg-slate-800 rounded-lg p-3">
    <p className="text-slate-400 text-xs">{label}</p>
    <p className={`text-lg font-bold ${valueClass}`}>{value}</p>
  </div>
);

interface MetricCardProps {
  icon: React.ElementType;
  label: string;
  value: string;
  change: string;
  color: 'blue' | 'green' | 'red' | 'purple' | 'orange';
}

const MetricCard: React.FC<MetricCardProps> = ({ icon: Icon, label, value, change, color }) => {
  const colorClasses = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    red: 'from-red-500 to-red-600',
    purple: 'from-purple-500 to-purple-600',
    orange: 'from-orange-500 to-orange-600',
  };

  return (
    <div className="bg-slate-800 rounded-lg p-4">
      <div className={`w-12 h-12 bg-gradient-to-br ${colorClasses[color]} rounded-lg flex items-center justify-center mb-4`}>
        <Icon className="w-6 h-6 text-white" />
      </div>
      <p className="text-sm text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-xs text-slate-500 mt-2">{change}</p>
    </div>
  );
};

const StatItem: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex justify-between items-center">
    <span className="text-sm text-slate-400">{label}</span>
    <span className="font-semibold text-white">{value}</span>
  </div>
);

const TradeRow: React.FC<{ trade: any }> = ({ trade }) => (
  <div className="flex justify-between items-center p-3 bg-slate-900/50 rounded-lg">
    <div>
      <p className="font-medium text-white">{trade.strategy || '-'}</p>
      <p className="text-xs text-slate-400">{trade.underlying || '-'}</p>
    </div>
    <div className="text-right">
      <p className={`font-bold ${Number(trade.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
        ₹{Math.abs(Number(trade.pnl || 0)).toLocaleString('en-IN')}
      </p>
      <p className={`text-xs ${Number(trade.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
        {Number(trade.pnl || 0) >= 0 ? '+' : ''}{Number(trade.pnl_percent || 0).toFixed(2)}%
      </p>
    </div>
  </div>
);

export default Dashboard;
