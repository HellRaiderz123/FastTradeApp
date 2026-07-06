import React, { useState, useEffect, useMemo } from 'react';
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
  Calendar,
  Building2,
  Info,
  Bell,
  List,
  SlidersHorizontal,
} from 'lucide-react';
import CandleChart from '../components/CandleChart';
import NewsFeed from '../components/NewsFeed';
import ErrorBoundary from '../components/ErrorBoundary';
import StockDetailModal from '../components/StockDetailModal';
import AlertManager from '../components/AlertManager';
import AlertList from '../components/AlertList';
import ComparisonChart from '../components/ComparisonChart';
import MarketDepthViewer from '../components/MarketDepthViewer';
import { useRealtimeQuotes } from '../hooks/useRealtimeQuotes';
import { alertsAPI, mlAPI } from '../lib/api';
import { 
  marketDashboardAPI,
  swingScannerAPI,
  sentimentAPI,
  type TopMover,
  type SectorPerformance,
  type SwingOpportunity,
  type SentimentData 
} from '../lib/marketDashboardAPI';
import { getTodayEvents, type CalendarEvent } from '../api/calendarAPI';

const Terminal: React.FC = () => {
  const [selectedSymbol, setSelectedSymbol] = useState('RELIANCE');
  const [searchInput, setSearchInput] = useState('');
  const [timeframe, setTimeframe] = useState<'1m' | '5m' | '15m' | '30m' | '1h' | '1d'>('15m');
  const [universe, setUniverse] = useState<string>('NIFTY50');
  const [detailModalSymbol, setDetailModalSymbol] = useState<string | null>(null);
  const [showAdvancedPanels, setShowAdvancedPanels] = useState(false);
  
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
  const [todayEvents, setTodayEvents] = useState<CalendarEvent[]>([]);
  const [showCommandPalette, setShowCommandPalette] = useState(false);
  const [commandInput, setCommandInput] = useState('');
  
  // Alert modals
  const [showAlertManager, setShowAlertManager] = useState(false);
  const [showAlertList, setShowAlertList] = useState(false);
  const [alertRefreshTrigger, setAlertRefreshTrigger] = useState(0);
  
  // ML Predictions
  const [mlPredictions, setMlPredictions] = useState<Record<string, {
    signal: string; confidence: number; bias: string; reason: string; model_type?: string;
  }>>({});
  const [mlModelStatus, setMlModelStatus] = useState<string>('unknown');
  const [mlModelType, setMlModelType] = useState<string>('none');
  
  // Watchlist - Universe aware (top stocks by weight for real-time WS streaming)
  const universeWatchlist: Record<string, string[]> = {
    'NIFTY50': [
      'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
      'HINDUNILVR', 'ITC', 'SBIN', 'BHARTIARTL', 'BAJFINANCE',
      'KOTAKBANK', 'LT',
    ],
    'BANKNIFTY': [
      'HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK',
      'INDUSINDBK', 'BANDHANBNK', 'FEDERALBNK', 'IDFCFIRSTB', 'PNB',
      'BANKBARODA', 'AUBANK',
    ],
    'FINNIFTY': [
      'HDFCBANK', 'ICICIBANK', 'SBIN', 'KOTAKBANK', 'AXISBANK',
      'BAJFINANCE', 'BAJAJFINSV', 'HDFCLIFE', 'SBILIFE', 'ICICIGI',
      'BAJAJHLDNG', 'PFC', 'RECLTD', 'MUTHOOTFIN', 'CHOLAFIN',
    ],
    'NIFTY_IT': [
      'TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM',
      'LTIM', 'COFORGE', 'PERSISTENT', 'MPHASIS',
    ],
  };
  
  // Memoize watchlist symbols to prevent unnecessary WebSocket reconnections
  const watchlistSymbols = useMemo(
    () => universeWatchlist[universe] || ['RELIANCE', 'TCS', 'INFY', 'HDFCBANK', 'ICICIBANK', 'SBIN'],
    [universe]
  );

  const allSymbols = useMemo(() => {
    const joined = Object.values(universeWatchlist).flat();
    return [...new Set(joined)].sort();
  }, []);

  const filteredSymbols = useMemo(() => {
    if (!commandInput.trim()) return allSymbols.slice(0, 10);
    const input = commandInput.toUpperCase().trim();
    return allSymbols.filter((s) => s.includes(input)).slice(0, 10);
  }, [allSymbols, commandInput]);

  const { quotes, loading: quotesLoading, connected: quotesConnected } = useRealtimeQuotes(watchlistSymbols, true);

  // Fetch market data
  useEffect(() => {
    const fetchMarketData = async () => {
      if (document.visibilityState === 'hidden') return;

      const [moversRes, sectorsRes, sentimentRes, breadthRes] = await Promise.allSettled([
        marketDashboardAPI.getTopMovers(5, universe),
        marketDashboardAPI.getSectorPerformance(),
        sentimentAPI.getOverallSentiment(),
        marketDashboardAPI.getMarketBreadth(universe),
      ]);

      if (moversRes.status === 'fulfilled') {
        const movers = moversRes.value;
        setTopMovers({
          gainers: Array.isArray(movers?.gainers) ? movers.gainers : [],
          losers: Array.isArray(movers?.losers) ? movers.losers : [],
          most_active: Array.isArray(movers?.most_active) ? movers.most_active : [],
        });
      }

      if (sectorsRes.status === 'fulfilled') {
        setSectors((sectorsRes.value?.sectors ?? []).slice(0, 6));
      }

      if (sentimentRes.status === 'fulfilled') {
        setSentiment(sentimentRes.value);
      }

      if (breadthRes.status === 'fulfilled') {
        setMarketBreadth(breadthRes.value);
      }

      if (showAdvancedPanels) {
        const [swingRes, calendarRes] = await Promise.allSettled([
          swingScannerAPI.scan('all', 50, universe),
          getTodayEvents(),
        ]);

        if (swingRes.status === 'fulfilled') {
          setSwingOpportunities((swingRes.value?.opportunities ?? []).slice(0, 5));
          setSwingDataSource(swingRes.value?.data_source || 'unknown');
        } else {
          setSwingOpportunities([]);
          setSwingDataSource('error');
        }

        if (calendarRes.status === 'fulfilled') {
          const highImpactEvents = (calendarRes.value?.events ?? [])
            .filter((e) => e.impact === 'high')
            .slice(0, 4);
          setTodayEvents(highImpactEvents);
        }
      } else {
        setSwingOpportunities([]);
        setTodayEvents([]);
      }

      // ML predictions — fire and forget (don't block market data rendering)
      mlAPI.getMetrics().then((metricsRes) => {
        const status = metricsRes?.data?.model_status || 'not_trained';
        setMlModelStatus(status);
        setMlModelType(metricsRes?.data?.model_type || 'none');
        if (status === 'ready') {
          mlAPI.predictBulk(watchlistSymbols).then((mlRes) => {
            if (mlRes?.data?.predictions) {
              setMlPredictions(mlRes.data.predictions);
            }
          }).catch(() => {});
        } else {
          setMlPredictions({});
        }
      }).catch(() => {
        setMlModelStatus('unknown');
        setMlPredictions({});
      });
    };

    fetchMarketData();
    const interval = setInterval(fetchMarketData, 60000);

    return () => clearInterval(interval);
  }, [showAdvancedPanels, universe, watchlistSymbols]);

  // Keyboard shortcuts handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in search input
      const isInputFocused = document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA';
      
      // Ctrl/Cmd + K: Open command palette
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setShowCommandPalette(true);
        setCommandInput('');
        return;
      }
      
      // Esc: Close command palette or clear selection
      if (e.key === 'Escape') {
        if (showCommandPalette) {
          setShowCommandPalette(false);
          setCommandInput('');
        } else {
          setSearchInput('');
        }
        return;
      }
      
      if (isInputFocused) return;
      
      // 1-5: Quick timeframe switching
      const timeframeMap: Record<string, typeof timeframe> = {
        '1': '1m',
        '2': '5m',
        '3': '15m',
        '4': '1h',
        '5': '1d'
      };
      
      if (timeframeMap[e.key]) {
        e.preventDefault();
        setTimeframe(timeframeMap[e.key]);
      }
    };
    
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showCommandPalette]);

  const handleSymbolSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchInput.trim()) {
      setSelectedSymbol(searchInput.toUpperCase().trim());
      setSearchInput('');
    }
  };

  const handleCommandPaletteSubmit = (symbol: string) => {
    setSelectedSymbol(symbol.toUpperCase());
    setShowCommandPalette(false);
    setCommandInput('');
  };

  const candleTimeframe: '1m' | '5m' | '15m' | '1h' | 'daily' =
    timeframe === '1d' ? 'daily' : timeframe === '30m' ? '15m' : timeframe;
  
  return (
    <div className="h-full flex flex-col gap-4 terminal-pattern overflow-y-auto pb-6">
      {/* Command Palette Overlay */}
      {showCommandPalette && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-start justify-center pt-20">
          <div className="w-full max-w-2xl">
            <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-2xl overflow-hidden">
              {/* Command Palette Input */}
              <div className="border-b border-slate-700 p-4">
                <input
                  autoFocus
                  value={commandInput}
                  onChange={(e) => setCommandInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && filteredSymbols.length > 0) {
                      handleCommandPaletteSubmit(filteredSymbols[0]);
                    }
                  }}
                  className="w-full bg-transparent text-lg text-white focus:outline-none"
                  placeholder="Search stocks... (type TCS, INFY, etc.)"
                />
              </div>

              {/* Command Palette Results */}
              <div className="max-h-96 overflow-y-auto">
                {filteredSymbols.length > 0 ? (
                  filteredSymbols.map((symbol, idx) => (
                    <button
                      key={symbol}
                      onClick={() => handleCommandPaletteSubmit(symbol)}
                      className={`w-full text-left px-4 py-3 border-b border-slate-800 hover:bg-slate-800/50 transition flex items-center justify-between ${
                        idx === 0 ? 'bg-slate-800/50' : ''
                      }`}
                    >
                      <div>
                        <div className="text-white font-semibold">{symbol}</div>
                        <div className="text-xs text-slate-400 mt-1">
                          Press Enter to load chart
                        </div>
                      </div>
                      <Search size={16} className="text-slate-500" />
                    </button>
                  ))
                ) : (
                  <div className="px-4 py-8 text-center text-slate-400">
                    No stocks found matching "{commandInput}"
                  </div>
                )}
              </div>

              {/* Help Footer */}
              <div className="border-t border-slate-700 bg-slate-900/50 px-4 py-2 text-xs text-slate-500">
                <span className="mr-4">Press <kbd className="bg-slate-800 px-2 py-1 rounded">ESC</kbd> to close</span>
                <span>Press <kbd className="bg-slate-800 px-2 py-1 rounded">↑↓</kbd> to navigate</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Header with Market Overview */}
      <header className="terminal-panel rounded-2xl px-6 py-4 flex flex-col gap-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Bloomberg-Style Terminal</p>
              <h1 className="terminal-title text-3xl text-white">
                {universe === 'NIFTY50' ? 'NIFTY 50' : 
                 universe === 'BANKNIFTY' ? 'BANK NIFTY' : 
                 universe === 'FINNIFTY' ? 'FIN NIFTY' : 
                 universe === 'NIFTY_IT' ? 'NIFTY IT' : 'MARKET'} Command Center
              </h1>
            </div>
            
            {/* Universe Switcher */}
            <select 
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              title="Universe"
              className="bg-slate-900/80 border border-slate-700/50 rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:border-emerald-400/50 hover:border-slate-500/70 transition cursor-pointer"
            >
              <option value="NIFTY50">NIFTY 50 (50 stocks)</option>
              <option value="BANKNIFTY">BANK NIFTY (12 stocks)</option>
              <option value="FINNIFTY">FIN NIFTY (15 stocks)</option>
              <option value="NIFTY_IT">NIFTY IT (9 stocks)</option>
            </select>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Connection Status */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-900/70 border border-slate-700/50">
              <Activity size={14} className={quotesConnected ? 'text-emerald-400' : 'text-orange-400'} />
              <span className="text-xs text-slate-300">{quotesConnected ? 'Live' : 'Connecting...'}</span>
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
            
            {/* Keyboard Shortcuts Hint */}
            <div className="flex items-center gap-2 px-3 py-2 rounded-full bg-slate-900/70 border border-slate-700/50 text-xs text-slate-400">
              <span>⌘K</span>
              <span className="text-slate-600">•</span>
              <span>1-5</span>
              <span className="text-slate-600">•</span>
              <span>ESC</span>
            </div>

            <button
              onClick={() => setShowAdvancedPanels((v) => !v)}
              className={`flex items-center gap-2 px-3 py-2 rounded-full border text-xs transition ${
                showAdvancedPanels
                  ? 'bg-blue-500/20 border-blue-400/50 text-blue-200'
                  : 'bg-slate-900/70 border-slate-700/50 text-slate-300 hover:border-slate-500/70'
              }`}
            >
              <SlidersHorizontal size={14} />
              {showAdvancedPanels ? 'Advanced ON' : 'Advanced OFF'}
            </button>
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
              placeholder={`Search ${universe === 'NIFTY50' ? 'NIFTY 50' : universe === 'BANKNIFTY' ? 'BANK NIFTY' : universe === 'FINNIFTY' ? 'FIN NIFTY' : 'NIFTY IT'} stocks (e.g., TCS, RELIANCE)`}
            />
          </div>

          <div className="flex items-center gap-2">
            {(['1m', '5m', '15m', '30m', '1h', '1d'] as const).map((tf) => (
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
            {/* ML Signal Badge for selected symbol */}
            {mlModelStatus === 'ready' && mlPredictions[selectedSymbol] && mlPredictions[selectedSymbol].signal !== 'NO_TRADE' && (
              <div className="mb-2 flex items-center gap-2">
                <span className={`text-xs font-bold px-3 py-1 rounded-lg ${
                  mlPredictions[selectedSymbol].signal === 'BULLISH'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                    : 'bg-red-500/20 text-red-300 border border-red-500/30'
                }`}>
                  {(mlPredictions[selectedSymbol] as any).model_type === 'ensemble' ? '🧠 Ensemble' : '🤖 ML'}: {mlPredictions[selectedSymbol].signal} ({mlPredictions[selectedSymbol].confidence}%)
                </span>
                <span className="text-xs text-slate-500">{mlPredictions[selectedSymbol].reason}</span>
              </div>
            )}
            <ErrorBoundary>
              <CandleChart symbol={selectedSymbol} defaultTimeframe={candleTimeframe} height={630} showTimeframeSelector={true} />
            </ErrorBoundary>
          </div>

          {showAdvancedPanels && (
            <ErrorBoundary>
              <div className="terminal-panel rounded-2xl p-5">
                <MarketDepthViewer symbol={selectedSymbol} />
              </div>
            </ErrorBoundary>
          )}

          {showAdvancedPanels && (
            <ErrorBoundary>
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
                  {swingDataSource.includes('real') && (
                    <span className="px-2 py-1 rounded text-xs font-semibold bg-blue-500/20 text-blue-300 border border-blue-500/40">
                      REAL DATA
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
                      className="flex items-center justify-between bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3 hover:bg-slate-800/60 transition group"
                    >
                      <div 
                        onClick={() => setSelectedSymbol(opp.symbol)}
                        className="flex-1 cursor-pointer"
                      >
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
                      <div className="flex items-center gap-3">
                        <div 
                          onClick={() => setSelectedSymbol(opp.symbol)}
                          className="text-right cursor-pointer"
                        >
                          <div className="text-sm font-semibold text-white">₹{opp.ltp}</div>
                          <div className={`text-xs ${opp.change_percent >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            {opp.change_percent >= 0 ? '+' : ''}{opp.change_percent.toFixed(2)}%
                          </div>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDetailModalSymbol(opp.symbol);
                          }}
                          className="opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-slate-700/50 rounded-lg"
                          title="More Details"
                        >
                          <Info size={16} className="text-blue-400" />
                        </button>
                      </div>
                    </div>
                  ))
                ) : swingDataSource === 'error' ? (
                  <p className="text-xs text-red-400">Scanner unavailable — check backend connection</p>
                ) : (
                  <div className="space-y-3">
                    {[1,2,3].map(i => (
                      <div key={i} className="animate-pulse flex items-center justify-between bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3">
                        <div className="space-y-2">
                          <div className="h-3 w-20 bg-slate-700 rounded" />
                          <div className="h-2 w-32 bg-slate-800 rounded" />
                        </div>
                        <div className="h-4 w-14 bg-slate-700 rounded" />
                      </div>
                    ))}
                  </div>
                )}
              </div>
              </div>
            </ErrorBoundary>
          )}

          {/* Top Movers Tabs */}
          <ErrorBoundary>
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
                        className="flex items-center justify-between text-xs hover:bg-slate-800/40 rounded px-2 py-1 transition group"
                      >
                        <span 
                          onClick={() => setSelectedSymbol(stock.symbol)}
                          className="text-slate-200 font-medium cursor-pointer"
                        >
                          {stock.symbol}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-emerald-400 font-semibold">+{stock.change_percent.toFixed(2)}%</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDetailModalSymbol(stock.symbol);
                            }}
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-slate-700/50 rounded"
                            title="More Details"
                          >
                            <Info size={12} className="text-blue-400" />
                          </button>
                        </div>
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
                        className="flex items-center justify-between text-xs hover:bg-slate-800/40 rounded px-2 py-1 transition group"
                      >
                        <span 
                          onClick={() => setSelectedSymbol(stock.symbol)}
                          className="text-slate-200 font-medium cursor-pointer"
                        >
                          {stock.symbol}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-red-400 font-semibold">{stock.change_percent.toFixed(2)}%</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDetailModalSymbol(stock.symbol);
                            }}
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-slate-700/50 rounded"
                            title="More Details"
                          >
                            <Info size={12} className="text-blue-400" />
                          </button>
                        </div>
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
                        className="flex items-center justify-between text-xs hover:bg-slate-800/40 rounded px-2 py-1 transition group"
                      >
                        <span 
                          onClick={() => setSelectedSymbol(stock.symbol)}
                          className="text-slate-200 font-medium cursor-pointer"
                        >
                          {stock.symbol}
                        </span>
                        <div className="flex items-center gap-2">
                          <span className="text-slate-400">{(stock.volume / 1000000).toFixed(2)}M</span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDetailModalSymbol(stock.symbol);
                            }}
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-slate-700/50 rounded"
                            title="More Details"
                          >
                            <Info size={12} className="text-blue-400" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </ErrorBoundary>
          {showAdvancedPanels && todayEvents.length > 0 && (
            <div className="terminal-panel rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Today's Events</p>
                  <h2 className="terminal-title text-xl text-white">Key Calendar</h2>
                </div>
                <Calendar size={16} className="text-orange-300" />
              </div>

              <div className="space-y-2">
                {todayEvents.map((event, idx) => (
                  <div
                    key={idx}
                    className="bg-slate-900/60 border border-slate-700/40 rounded-lg px-3 py-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          {event.type === 'earnings' && <Building2 size={12} className="text-emerald-400" />}
                          {event.type === 'rbi' && <Building2 size={12} className="text-orange-400" />}
                          {event.type === 'ipo' && <TrendingUp size={12} className="text-blue-400" />}
                          <span className="text-xs font-semibold text-white">{event.title}</span>
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {event.time ? `${event.time} • ` : ''}{event.description || ''}
                        </div>
                        <span className={`inline-block mt-1 px-2 py-0.5 rounded text-[9px] font-semibold ${
                          event.impact === 'high'
                            ? 'bg-red-500/20 text-red-300'
                            : event.impact === 'medium'
                            ? 'bg-orange-500/20 text-orange-300'
                            : 'bg-slate-500/20 text-slate-300'
                        }`}>
                          {event.impact.toUpperCase()}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-3 pt-3 border-t border-slate-700/40">
                <a
                  href="/calendar"
                  className="text-xs text-blue-400 hover:text-blue-300 transition"
                >
                  View full calendar →
                </a>
              </div>
            </div>
          )}
        </div>

        {/* Right Column - Watchlist, Sectors, Sentiment */}
        <div className="flex flex-col gap-4">
          {/* Watchlist with Live Prices */}
          <ErrorBoundary>
            <div className="terminal-panel rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Live Watchlist</p>
                  <h2 className="terminal-title text-xl text-white">Blue Chips</h2>
                </div>
                <div className="flex items-center gap-2">
                  {!quotesConnected && !quotesLoading && (
                    <span className="text-xs text-yellow-400">Reconnecting...</span>
                  )}
                  {quotesLoading && <Activity size={14} className="text-blue-400 animate-pulse" />}
                </div>
              </div>

              <div className="space-y-3">
                {watchlistSymbols.map((symbol) => {
                  const quote = quotes[symbol];
                  if (!quote) {
                    return (
                      <div key={symbol} className="bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="text-sm font-semibold text-white">{symbol}</div>
                            <div className="text-xs text-slate-500 animate-pulse">Fetching quote…</div>
                          </div>
                          <div className="text-right">
                            <div className="h-5 bg-slate-700/50 rounded w-24 mb-1 animate-pulse"></div>
                            <div className="h-3 bg-slate-700/50 rounded w-16 animate-pulse"></div>
                          </div>
                        </div>
                      </div>
                    );
                  }

                  return (
                    <div
                      key={symbol}
                      className="bg-slate-900/60 border border-slate-700/40 rounded-xl px-4 py-3 hover:bg-slate-800/60 transition group"
                    >
                      <div className="flex items-center justify-between">
                        <div 
                          onClick={() => setSelectedSymbol(symbol)}
                          className="flex-1 cursor-pointer"
                        >
                          <div className="text-sm font-semibold text-white">{symbol}</div>
                          <div className={`text-xs flex items-center gap-1 ${
                            quote.change_percent >= 0 ? 'text-emerald-400' : 'text-red-400'
                          }`}>
                            {quote.change_percent >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                            {quote.change_percent >= 0 ? '+' : ''}{quote.change_percent}%
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div 
                            onClick={() => setSelectedSymbol(symbol)}
                            className="text-right cursor-pointer"
                          >
                            <div className="text-lg font-bold text-white">₹{quote.ltp}</div>
                            <div className={`text-xs ${quote.change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                              {quote.change >= 0 ? '+' : ''}{quote.change.toFixed(2)}
                            </div>
                          </div>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedSymbol(symbol);
                              setShowAlertManager(true);
                            }}
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-blue-500/10 rounded-lg"
                            title="Create Alert"
                          >
                            <Bell size={14} className="text-blue-400" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDetailModalSymbol(symbol);
                            }}
                            className="opacity-0 group-hover:opacity-100 transition-opacity p-2 hover:bg-slate-700/50 rounded-lg"
                            title="More Details"
                          >
                            <Info size={16} className="text-blue-400" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </ErrorBoundary>

          {/* Price Alert */}
          <ErrorBoundary>
            <div className="terminal-panel rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Alerts</p>
                  <h2 className="terminal-title text-xl text-white">Price Alerts</h2>
                </div>
                <Bell size={16} className="text-blue-400" />
              </div>

              <div className="space-y-3">
                <p className="text-xs text-slate-400 mb-4">
                  Set price alerts to get notified when targets are reached
                </p>

                <button
                  onClick={() => {
                    const currentQuote = quotes[selectedSymbol];
                    if (currentQuote?.ltp) {
                      setShowAlertManager(true);
                    }
                  }}
                  disabled={!quotes[selectedSymbol]?.ltp}
                  className="w-full bg-blue-500/20 hover:bg-blue-500/30 text-blue-200 border border-blue-400/40 rounded-lg px-4 py-3 text-sm font-semibold transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <Bell size={16} />
                  Create Alert for {selectedSymbol}
                </button>

                <button
                  onClick={() => setShowAlertList(true)}
                  className="w-full bg-slate-800/50 hover:bg-slate-800 text-slate-300 border border-slate-700/40 rounded-lg px-4 py-3 text-sm font-semibold transition flex items-center justify-center gap-2"
                >
                  <List size={16} />
                  View All Alerts
                </button>
              </div>
            </div>
          </ErrorBoundary>

          {/* ML Predictions Panel */}
          <ErrorBoundary>
            <div className="terminal-panel rounded-2xl p-5">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-400">ML Engine</p>
                  <h2 className="terminal-title text-xl text-white">AI Signals</h2>
                </div>
                <div className="flex items-center gap-3">
                  {mlModelType === 'ensemble' && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">ENSEMBLE</span>
                  )}
                  {mlModelType === 'single' && (
                    <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">GBM</span>
                  )}
                  <div className="flex items-center gap-1.5">
                    <span className={`inline-block w-2 h-2 rounded-full ${
                      mlModelStatus === 'ready' ? 'bg-emerald-400' :
                      mlModelStatus === 'training' ? 'bg-yellow-400 animate-pulse' : 'bg-slate-500'
                    }`} />
                    <span className="text-xs text-slate-400 capitalize">{mlModelStatus === 'not_trained' ? 'Not Trained' : mlModelStatus}</span>
                  </div>
                </div>
              </div>

              {mlModelStatus === 'ready' && Object.keys(mlPredictions).length > 0 ? (
                <div className="space-y-2">
                  {Object.entries(mlPredictions)
                    .filter(([, p]) => p.signal !== 'NO_TRADE')
                    .sort((a, b) => b[1].confidence - a[1].confidence)
                    .slice(0, 8)
                    .map(([symbol, pred]) => (
                      <div
                        key={symbol}
                        onClick={() => setSelectedSymbol(symbol)}
                        className="flex items-center justify-between px-3 py-2 rounded-lg bg-slate-900/60 border border-slate-700/30 hover:bg-slate-800/60 cursor-pointer transition"
                      >
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                            pred.signal === 'BULLISH'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : pred.signal === 'BEARISH'
                              ? 'bg-red-500/20 text-red-300'
                              : 'bg-slate-500/20 text-slate-300'
                          }`}>
                            {pred.signal === 'BULLISH' ? '▲' : pred.signal === 'BEARISH' ? '▼' : '─'} {pred.signal}
                          </span>
                          <span className="text-sm text-white font-medium">{symbol}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full bg-slate-700 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                pred.confidence >= 70 ? 'bg-emerald-400' :
                                pred.confidence >= 55 ? 'bg-yellow-400' : 'bg-slate-400'
                              }`}
                              style={{ width: `${pred.confidence}%` }}
                            />
                          </div>
                          <span className="text-xs text-slate-400 min-w-[32px] text-right">{pred.confidence}%</span>
                        </div>
                      </div>
                    ))}
                  {Object.values(mlPredictions).every(p => p.signal === 'NO_TRADE') && (
                    <p className="text-xs text-slate-500 text-center py-2">No actionable signals at this time</p>
                  )}
                </div>
              ) : mlModelStatus === 'not_trained' || mlModelStatus === 'unknown' ? (
                <div className="text-center py-4">
                  <p className="text-sm text-slate-400 mb-2">ML model not yet trained</p>
                  <a
                    href="/ml"
                    className="text-xs text-blue-400 hover:text-blue-300 transition"
                  >
                    Go to ML Center → Backfill data & Train
                  </a>
                </div>
              ) : (
                <p className="text-xs text-slate-500 text-center py-2">Loading predictions...</p>
              )}
            </div>
          </ErrorBoundary>

          {/* Sector Performance */}
          <ErrorBoundary>
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
          </ErrorBoundary>

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
            <NewsFeed height={480} />
          </div>
        </div>
      </section>

      {showAdvancedPanels && (
        <section className="w-full">
          <ErrorBoundary>
            <ComparisonChart
              initialSymbols={[selectedSymbol, 'TCS', 'INFY']}
              timeframe="3M"
            />
          </ErrorBoundary>
        </section>
      )}

      {/* Stock Detail Modal */}
      {detailModalSymbol && (
        <StockDetailModal
          symbol={detailModalSymbol}
          onClose={() => setDetailModalSymbol(null)}
          currentPrice={quotes[detailModalSymbol]?.ltp || 0}
          change={quotes[detailModalSymbol]?.change || 0}
          changePercent={quotes[detailModalSymbol]?.change_percent || 0}
        />
      )}

      {/* Alert Manager Modal */}
      {showAlertManager && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <AlertManager
            symbol={selectedSymbol}
            currentPrice={quotes[selectedSymbol]?.ltp || 0}
            onClose={() => setShowAlertManager(false)}
            onAlertCreated={() => {
              setAlertRefreshTrigger(prev => prev + 1);
              setTimeout(() => setShowAlertManager(false), 2000);
            }}
          />
        </div>
      )}

      {/* Alert List Modal */}
      {showAlertList && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <AlertList
            onClose={() => setShowAlertList(false)}
            refreshTrigger={alertRefreshTrigger}
          />
        </div>
      )}
    </div>
  );
};

export default Terminal;
