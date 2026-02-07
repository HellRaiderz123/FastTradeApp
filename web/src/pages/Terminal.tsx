import React, { useState, useEffect } from 'react';
import {
  Search,
  Activity,
  Zap,
  Clock,
  BarChart3,
  Triangle,
  TrendingUp,
  TrendingDown,
} from 'lucide-react';
import ChartPanel from '../components/ChartPanel';
import QuotePanel from '../components/QuotePanel';
import { useRealtimeQuotes } from '../hooks/useRealtimeQuotes';
import { marketAPI } from '../lib/api';

interface SectorData {
  name: string;
  change_percent: number;
  trending: 'up' | 'down' | 'neutral';
}

const Terminal: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('RELIANCE');
  const [searchInput, setSearchInput] = useState('');
  const [timeframe, setTimeframe] = useState<'1m' | '5m' | '15m' | '30m' | '1h' | '1d'>('15m');
  const [sectors, setSectors] = useState<SectorData[]>([]);

  // Watchlist stocks
  const watchlistSymbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK'];
  
  // Real-time quotes for watchlist
  const { quotes, loading: quotesLoading, connected } = useRealtimeQuotes(watchlistSymbols, true);

  // Fetch sector performance
  useEffect(() => {
    const fetchSectors = async () => {
      try {
        const response = await marketAPI.getSectorPerformance();
        setSectors(response.data.sectors.slice(0, 6)); // Top 6 sectors
      } catch (error) {
        console.error('Failed to fetch sector performance:', error);
      }
    };

    fetchSectors();
    const interval = setInterval(fetchSectors, 60000); // Refresh every minute

    return () => clearInterval(interval);
  }, []);

  // Mock signals (will be replaced with real signal generation in Phase 3)
  const signals = [
    { label: 'Momentum', status: 'BUY', score: 78 },
    { label: 'Mean Reversion', status: 'HOLD', score: 54 },
    { label: 'Trend', status: 'BUY', score: 81 },
    { label: 'IV Regime', status: 'HIGH', score: 62 },
  ];

  // Mock news headlines (will be replaced with real news feed in Phase 3)
  const headlines = [
    { title: 'RBI policy watch: rate commentary shifts to neutral', source: 'MacroPulse', time: '2m ago' },
    { title: 'Reliance retail sales beat street estimates', source: 'StreetEdge', time: '14m ago' },
    { title: 'NIFTY IT leads as rupee weakens', source: 'MarketWire', time: '22m ago' },
    { title: 'Banking stocks pause after strong rally', source: 'DealDesk', time: '35m ago' },
  ];

  const handleSymbolSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchInput.trim()) {
      setSelectedSymbol(searchInput.toUpperCase().trim());
      setSearchInput('');
    }
  };

  return (
    <div className="h-full flex flex-col gap-6 terminal-pattern overflow-y-auto pb-6">
      {/* Header */}
      <header className="terminal-panel rounded-2xl px-6 py-4 flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">FastTrade Terminal</p>
            <h1 className="terminal-title text-3xl text-white">Market Control Center</h1>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-300">
            <div className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-900/70 border border-slate-700/50">
              <Activity size={14} className={connected ? 'text-emerald-400' : 'text-orange-400'} />
              <span>{connected ? 'Live' : 'Connecting...'}</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-900/70 border border-slate-700/50">
              <Clock size={14} className="text-orange-300" />
              <span>Asia Session</span>
            </div>
          </div>
        </div>

        {/* Search and Timeframe Selector */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-2 min-w-[280px]">
            <Search size={16} className="text-slate-400" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleSymbolSearch}
              className="bg-transparent w-full text-sm text-slate-200 focus:outline-none"
              placeholder="Search NIFTY 50 stocks (e.g., TCS, INFY)"
            />
          </div>

          <div className="flex items-center gap-2">
            {(['1m', '5m', '15m', '1h', '1d'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-2 rounded-lg text-xs uppercase tracking-wide border transition ${
                  timeframe === tf
                    ? 'bg-emerald-500/20 text-emerald-200 border-emerald-400/40'
                    : 'border-slate-700/60 text-slate-400 hover:text-white hover:border-slate-400/60'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </header>

      {/* Main Content Grid */}
      <section className="grid grid-cols-1 xl:grid-cols-[1.2fr_0.8fr] gap-6">
        {/* Left Column - Chart and Signals */}
        <div className="flex flex-col gap-6">
          {/* Chart Panel */}
          <div className="h-[500px]">
            <ChartPanel symbol={selectedSymbol} timeframe={timeframe} height={450} />
          </div>

          {/* Signals Panel */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Signal Lab</p>
                <h2 className="terminal-title text-xl text-white">Strategy Signals</h2>
              </div>
              <Zap size={18} className="text-emerald-300" />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {signals.map((sig) => (
                <div
                  key={sig.label}
                  className="flex items-center justify-between bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3"
                >
                  <div>
                    <p className="text-sm text-white font-medium">{sig.label}</p>
                    <p className="text-xs text-slate-400">Confidence: {sig.score}%</p>
                  </div>
                  <span
                    className={`text-xs font-semibold px-3 py-1 rounded-full ${
                      sig.status === 'BUY'
                        ? 'bg-emerald-500/20 text-emerald-200'
                        : sig.status === 'HOLD'
                        ? 'bg-slate-600/30 text-slate-200'
                        : 'bg-orange-500/20 text-orange-200'
                    }`}
                  >
                    {sig.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column - Watchlist, Sectors, News */}
        <div className="flex flex-col gap-6">
          {/* Watchlist */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Watchlist</p>
                <h2 className="terminal-title text-xl text-white">Top Tickers</h2>
              </div>
              {quotesLoading && <Activity size={14} className="text-blue-400 animate-pulse" />}
            </div>

            <div className="grid grid-cols-1 gap-3">
              {watchlistSymbols.map((symbol) => (
                <QuotePanel
                  key={symbol}
                  symbol={symbol}
                  quote={quotes[symbol] || null}
                  onClick={() => setSelectedSymbol(symbol)}
                />
              ))}
            </div>
          </div>

          {/* Sector Pulse */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Sector Pulse</p>
                <h2 className="terminal-title text-xl text-white">Heat Snapshot</h2>
              </div>
              <BarChart3 size={16} className="text-orange-300" />
            </div>

            <div className="space-y-3">
              {sectors.length > 0 ? (
                sectors.map((sector) => (
                  <div key={sector.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {sector.trending === 'up' ? (
                        <TrendingUp size={14} className="text-emerald-400" />
                      ) : sector.trending === 'down' ? (
                        <TrendingDown size={14} className="text-red-400" />
                      ) : (
                        <Activity size={14} className="text-slate-400" />
                      )}
                      <span className="text-sm text-slate-200">{sector.name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-32 h-2 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            sector.change_percent >= 0 ? 'bg-emerald-400' : 'bg-red-400'
                          }`}
                          style={{ width: `${Math.min(100, Math.abs(sector.change_percent) * 40)}%` }}
                        />
                      </div>
                      <span
                        className={`text-xs font-medium min-w-[50px] text-right ${
                          sector.change_percent >= 0 ? 'text-emerald-300' : 'text-red-300'
                        }`}
                      >
                        {sector.change_percent >= 0 ? '+' : ''}
                        {sector.change_percent.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500">Loading sectors...</p>
              )}
            </div>
          </div>

          {/* Newsflow */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Newsflow</p>
                <h2 className="terminal-title text-xl text-white">Market Headlines</h2>
              </div>
              <Triangle size={16} className="text-emerald-300" />
            </div>

            <div className="space-y-4">
              {headlines.map((item, idx) => (
                <div key={idx} className="border-b border-slate-800/60 pb-3 last:border-0">
                  <p className="text-sm text-slate-200 leading-relaxed">{item.title}</p>
                  <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                    <span>{item.source}</span>
                    <span>•</span>
                    <span>{item.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Terminal;
