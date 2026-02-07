import React, { useState, useEffect } from 'react';
import {
  Search,
  Activity,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Eye,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  Target,
  AlertTriangle,
} from 'lucide-react';
import TechnicalChart from '../components/TechnicalChart';
import NewsFeed from '../components/NewsFeed';
import { useRealtimeQuotes } from '../hooks/useRealtimeQuotes';
import { marketAPI } from '../lib/api';
import { 
  marketDashboardAPI,
  swingScannerAPI,
  sentimentAPI,
  type TopMover,
  type SectorPerformance,
  type SwingOpportunity,
  type SentimentData 
} from '../lib/marketDashboardAPI';

const Terminal: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('RELIANCE');
  const [searchInput, setSearchInput] = useState('');
  const [timeframe, setTimeframe] = useState<'1m' | '5m' | '15m' | '30m' | '1h' | '1d'>('15m');
  
  // Market data
  const [topMovers, setTopMovers] = useState<{
    gainers: TopMover[];
    losers: TopMover[];
    most_active: TopMover[];
  }>({ gainers: [], losers: [], most_active: [] });
  
  const [sectors, setSectors] = useState<SectorPerformance[]>([]);
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [swingOpportunities, setSwingOpportunities] = useState<SwingOpportunity[]>([]);
  const [swingDataSource, setSwingDataSource] = useState<string>('live');
  const [marketBreadth, setMarketBreadth] = useState<any>(null);
  
  // Watchlist
  const watchlistSymbols = ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN'];
  const { quotes, loading: quotesLoading, connected } = useRealtimeQuotes(watchlistSymbols, true);

  // Fetch market data
  useEffect(() => {
    const fetchMarketData = async () => {
      try {
        // Top movers
        const movers = await marketDashboardAPI.getTopMovers(5);
        setTopMovers(movers);

        // Sector performance
        const sectorData = await marketDashboardAPI.getSectorPerformance();
        setSectors(sectorData.sectors.slice(0, 6));

        // Overall sentiment
        const sentimentData = await sentimentAPI.getOverallSentiment();
        setSentiment(sentimentData);

        // Market breadth
        const breadth = await marketDashboardAPI.getMarketBreadth();
        setMarketBreadth(breadth);

        // Swing opportunities
        const opportunities = await swingScannerAPI.scan('all', 60);
        setSwingOpportunities(opportunities.opportunities.slice(0, 5));
        setSwingDataSource(opportunities.data_source || 'unknown');
      } catch (error) {
        console.error('Failed to fetch market data:', error);
      }
    };

    fetchMarketData();
    const interval = setInterval(fetchMarketData, 30000); // Refresh every 30s

    return () => clearInterval(interval);
  }, []);

  const handleSymbolSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchInput.trim()) {
      setSelectedSymbol(searchInput.toUpperCase().trim());
      setSearchInput('');
    }
  };

  return (
    <div className="h-full flex flex-col gap-4 terminal-pattern overflow-y-auto pb-6">
      {/* Header with Market Overview */}
      <header className="terminal-panel rounded-2xl px-6 py-4 flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Bloomberg-Style Terminal</p>
            <h1 className="terminal-title text-3xl text-white">NIFTY 50 Command Center</h1>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Connection Status */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-900/70 border border-slate-700/50">
              <Activity size={14} className={connected ? 'text-emerald-400' : 'text-orange-400'} />
              <span className="text-xs text-slate-300">{connected ? 'Live' : 'Connecting...'}</span>
            </div>
            
            {/* Session */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-900/70 border border-slate-700/50">
              <Clock size={14} className="text-orange-300" />
              <span className="text-xs text-slate-300">Asia Session</span>
            </div>
            
            {/* Market Sentiment */}
            {sentiment && (
              <div className={`flex items-center gap-2 px-4 py-2 rounded-full border ${
                sentiment.sentiment.includes('BULLISH') 
                  ? 'bg-emerald-500/20 border-emerald-400/50 text-emerald-200'
                  : sentiment.sentiment.includes('BEARISH')
                  ? 'bg-red-500/20 border-red-400/50 text-red-200'
                  : 'bg-slate-500/20 border-slate-400/50 text-slate-200'
              }`}>
                <Eye size={14} />
                <div className="flex flex-col">
                  <span className="text-[10px] uppercase tracking-wider opacity-70">Sentiment</span>
                  <span className="text-xs font-semibold">{sentiment.fear_greed_index}/100</span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Search and Timeframe */}
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2 bg-slate-900/80 border border-slate-700/50 rounded-xl px-4 py-2 min-w-[280px]">
            <Search size={16} className="text-slate-400" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleSymbolSearch}
              className="bg-transparent w-full text-sm text-slate-200 focus:outline-none"
              placeholder="Search NIFTY 50 stocks (e.g., TCS, RELIANCE)"
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

      {/* Market Breadth Banner */}
      {marketBreadth && (
        <div className="grid grid-cols-4 gap-4">
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Advancing</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-emerald-400">{marketBreadth.advancing}</span>
              <span className="text-xs text-slate-400">stocks</span>
            </div>
          </div>
          
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Declining</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-red-400">{marketBreadth.declining}</span>
              <span className="text-xs text-slate-400">stocks</span>
            </div>
          </div>
          
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">A/D Ratio</p>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-white">{marketBreadth.advance_decline_ratio}</span>
              <span className={`text-xs px-2 py-0.5 rounded ${
                marketBreadth.breadth_strength === 'STRONG' || marketBreadth.breadth_strength === 'VERY_STRONG'
                  ? 'bg-emerald-500/20 text-emerald-300'
                  : 'bg-slate-500/20 text-slate-300'
              }`}>
                {marketBreadth.breadth_strength}
              </span>
            </div>
          </div>
          
          <div className="terminal-panel rounded-xl px-4 py-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider">52W Highs/Lows</p>
            <div className="flex items-baseline gap-3">
              <div className="flex items-center gap-1">
                <span className="text-xl font-bold text-emerald-400">{marketBreadth.new_highs_52w}</span>
                <TrendingUp size={14} className="text-emerald-400" />
              </div>
              <div className="flex items-center gap-1">
                <span className="text-xl font-bold text-red-400">{marketBreadth.new_lows_52w}</span>
                <TrendingDown size={14} className="text-red-400" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Grid */}
      <section className="grid grid-cols-1 xl:grid-cols-[1fr_0.8fr] gap-4">
        {/* Left Column - Chart and Swing Opportunities */}
        <div className="flex flex-col gap-4">
          {/* Technical Chart Panel with Indicators */}
          <div className="h-[650px]">
            <TechnicalChart symbol={selectedSymbol} timeframe={timeframe} height={630} />
          </div>

          {/* Swing Trade Opportunities */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Swing Scanner</p>
                <h2 className="terminal-title text-xl text-white">Top Opportunities</h2>
              </div>
              <div className="flex items-center gap-2">
                {swingDataSource.includes('simulated') && (
                  <span className="px-2 py-1 rounded text-xs font-semibold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40">
                    SIMULATED
                  </span>
                )}
                {swingDataSource.includes('live') && (
                  <span className="px-2 py-1 rounded text-xs font-semibold bg-green-500/20 text-green-300 border border-green-500/40">
                    LIVE
                  </span>
                )}
                <Target size={18} className="text-orange-300" />
              </div>
            </div>

            <div className="space-y-3">
              {swingOpportunities.length > 0 ? (
                swingOpportunities.map((opp) => (
                  <div
                    key={opp.symbol}
                    onClick={() => setSelectedSymbol(opp.symbol)}
                    className="flex items-center justify-between bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3 cursor-pointer hover:bg-slate-800/60 transition"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-semibold text-white">{opp.symbol}</span>
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                          opp.signal === 'BULLISH'
                            ? 'bg-emerald-500/20 text-emerald-200'
                            : opp.signal === 'BEARISH'
                            ? 'bg-red-500/20 text-red-200'
                            : 'bg-slate-500/20 text-slate-200'
                        }`}>
                          {opp.signal}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-slate-400">
                          Strength: {opp.strength}% • RSI: {opp.indicators.rsi?.toFixed(1)}
                        </span>
                        {opp.indicators.volume_spike && (
                          <span className="text-xs bg-orange-500/20 text-orange-300 px-2 py-0.5 rounded">
                            VOL📈
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-white">₹{opp.ltp}</div>
                      <div className={`text-xs ${opp.change_percent >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {opp.change_percent >= 0 ? '+' : ''}{opp.change_percent.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500">Loading opportunities...</p>
              )}
            </div>
          </div>

          {/* Top Movers Tabs */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Top Movers</p>
                <h2 className="terminal-title text-xl text-white">Market Leaders</h2>
              </div>
              <BarChart3 size={18} className="text-emerald-300" />
            </div>

            <div className="grid grid-cols-3 gap-4">
              {/* Gainers */}
              <div>
                <h3 className="text-xs font-semibold text-emerald-400 mb-3 flex items-center gap-1">
                  <TrendingUp size={14} /> GAINERS
                </h3>
                <div className="space-y-2">
                  {topMovers.gainers.slice(0, 5).map((stock) => (
                    <div
                      key={stock.symbol}
                      onClick={() => setSelectedSymbol(stock.symbol)}
                      className="flex items-center justify-between text-xs cursor-pointer hover:bg-slate-800/40 rounded px-2 py-1 transition"
                    >
                      <span className="text-slate-200 font-medium">{stock.symbol}</span>
                      <span className="text-emerald-400 font-semibold">+{stock.change_percent.toFixed(2)}%</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Losers */}
              <div>
                <h3 className="text-xs font-semibold text-red-400 mb-3 flex items-center gap-1">
                  <TrendingDown size={14} /> LOSERS
                </h3>
                <div className="space-y-2">
                  {topMovers.losers.slice(0, 5).map((stock) => (
                    <div
                      key={stock.symbol}
                      onClick={() => setSelectedSymbol(stock.symbol)}
                      className="flex items-center justify-between text-xs cursor-pointer hover:bg-slate-800/40 rounded px-2 py-1 transition"
                    >
                      <span className="text-slate-200 font-medium">{stock.symbol}</span>
                      <span className="text-red-400 font-semibold">{stock.change_percent.toFixed(2)}%</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Most Active */}
              <div>
                <h3 className="text-xs font-semibold text-orange-400 mb-3 flex items-center gap-1">
                  <Activity size={14} /> MOST ACTIVE
                </h3>
                <div className="space-y-2">
                  {topMovers.most_active.slice(0, 5).map((stock) => (
                    <div
                      key={stock.symbol}
                      onClick={() => setSelectedSymbol(stock.symbol)}
                      className="flex items-center justify-between text-xs cursor-pointer hover:bg-slate-800/40 rounded px-2 py-1 transition"
                    >
                      <span className="text-slate-200 font-medium">{stock.symbol}</span>
                      <span className="text-slate-400">{(stock.volume / 1000000).toFixed(2)}M</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Watchlist, Sectors, Sentiment */}
        <div className="flex flex-col gap-4">
          {/* Watchlist with Live Prices */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Live Watchlist</p>
                <h2 className="terminal-title text-xl text-white">Blue Chips</h2>
              </div>
              {quotesLoading && <Activity size={14} className="text-blue-400 animate-pulse" />}
            </div>

            <div className="space-y-3">
              {watchlistSymbols.map((symbol) => {
                const quote = quotes[symbol];
                if (!quote) {
                  return (
                    <div key={symbol} className="bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3">
                      <span className="text-sm text-slate-500">Loading {symbol}...</span>
                    </div>
                  );
                }

                return (
                  <div
                    key={symbol}
                    onClick={() => setSelectedSymbol(symbol)}
                    className="bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3 cursor-pointer hover:bg-slate-800/60 transition"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm font-semibold text-white">{symbol}</div>
                        <div className={`text-xs flex items-center gap-1 ${
                          quote.change_percent >= 0 ? 'text-emerald-400' : 'text-red-400'
                        }`}>
                          {quote.change_percent >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                          {quote.change_percent >= 0 ? '+' : ''}{quote.change_percent}%
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold text-white">₹{quote.ltp}</div>
                        <div className={`text-xs ${quote.change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {quote.change >= 0 ? '+' : ''}{quote.change.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Sector Performance */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Sector Pulse</p>
                <h2 className="terminal-title text-xl text-white">Industry Heat</h2>
              </div>
              <BarChart3 size={16} className="text-orange-300" />
            </div>

            <div className="space-y-3">
              {sectors.length > 0 ? (
                sectors.map((sector) => (
                  <div key={sector.name} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {sector.change_percent >= 0 ? (
                        <TrendingUp size={14} className="text-emerald-400" />
                      ) : (
                        <TrendingDown size={14} className="text-red-400" />
                      )}
                      <span className="text-sm text-slate-200">{sector.name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="w-24 h-2 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full ${
                            sector.change_percent >= 0 ? 'bg-emerald-400' : 'bg-red-400'
                          }`}
                          style={{ width: `${Math.min(100, Math.abs(sector.change_percent) * 40)}%` }}
                        />
                      </div>
                      <span
                        className={`text-xs font-medium min-w-[55px] text-right ${
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

          {/* Market Sentiment */}
          {sentiment && (
            <div className="terminal-panel rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Market Sentiment</p>
                  <h2 className="terminal-title text-xl text-white">Fear & Greed</h2>
                </div>
                <Zap size={16} className="text-orange-300" />
              </div>

              {/* Sentiment Gauge */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-slate-400">Score</span>
                  <span className={`text-2xl font-bold ${
                    sentiment.fear_greed_index >= 55
                      ? 'text-emerald-400'
                      : sentiment.fear_greed_index >= 45
                      ? 'text-slate-300'
                      : 'text-red-400'
                  }`}>
                    {sentiment.fear_greed_index}/100
                  </span>
                </div>
                <div className="h-3 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      sentiment.fear_greed_index >= 55
                        ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                        : sentiment.fear_greed_index >= 45
                        ? 'bg-slate-500'
                        : 'bg-gradient-to-r from-red-500 to-red-400'
                    }`}
                    style={{ width: `${sentiment.fear_greed_index}%` }}
                  />
                </div>
                <div className="flex items-center justify-center mt-2">
                  <span className={`text-sm font-semibold px-3 py-1 rounded-full ${
                    sentiment.sentiment.includes('BULLISH')
                      ? 'bg-emerald-500/20 text-emerald-200'
                      : sentiment.sentiment.includes('BEARISH')
                      ? 'bg-red-500/20 text-red-200'
                      : 'bg-slate-500/20 text-slate-200'
                  }`}>
                    {sentiment.sentiment.replace('_', ' ')}
                  </span>
                </div>
              </div>

              {/* Components */}
              <div className="space-y-3">
                {sentiment.components.vix && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">VIX</span>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{sentiment.components.vix.level}</span>
                      <span className={`px-2 py-0.5 rounded ${
                        sentiment.components.vix.score > 60
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-slate-500/20 text-slate-300'
                      }`}>
                        {sentiment.components.vix.interpretation.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                )}

                {sentiment.components.pcr && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">Put/Call Ratio</span>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">{sentiment.components.pcr.value}</span>
                      <span className={`px-2 py-0.5 rounded ${
                        sentiment.components.pcr.interpretation.includes('BULLISH')
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-slate-500/20 text-slate-300'
                      }`}>
                        {sentiment.components.pcr.interpretation.replace(/_/g, ' ')}
                      </span>
                    </div>
                  </div>
                )}

                {sentiment.components.momentum && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">NIFTY Momentum</span>
                    <div className="flex items-center gap-2">
                      <span className={`font-medium ${
                        sentiment.components.momentum.nifty_change_percent >= 0
                          ? 'text-emerald-400'
                          : 'text-red-400'
                      }`}>
                        {sentiment.components.momentum.nifty_change_percent >= 0 ? '+' : ''}
                        {sentiment.components.momentum.nifty_change_percent.toFixed(2)}%
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* News Feed with Sentiment */}
          <div className="terminal-panel rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Market News</p>
                <h2 className="terminal-title text-xl text-white">Live Feed</h2>
              </div>
            </div>
            <NewsFeed height={800} />
          </div>
        </div>
      </section>
    </div>
  );
};

export default Terminal;
