import React, { useState, useEffect } from 'react';
import {
  X,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Newspaper,
  Activity,
  Clock,
  Target,
  AlertCircle,
  ExternalLink,
  ArrowUpRight,
  ArrowDownRight,
  Eye,
  Zap,
  Brain,
  TrendingUp as TrendIcon
} from 'lucide-react';
import { mlAPI } from '../lib/api';
import TechnicalChart from './TechnicalChart';
import HistoricalReturns from './HistoricalReturns';
import PeerComparison from './PeerComparison';
import StockStrategyPanel from './StockStrategyPanel';

interface StockDetailModalProps {
  symbol: string;
  onClose: () => void;
  currentPrice?: number;
  change?: number;
  changePercent?: number;
}

interface NewsArticle {
  title: string;
  description: string;
  source: string;
  url: string;
  publishedAt: string;
  sentiment?: 'positive' | 'negative' | 'neutral';
  imageUrl?: string;
}

interface TechnicalAnalysis {
  rsi: number | null;
  macd: {
    macd: number;
    signal: number;
    histogram: number;
  } | null;
  adx: {
    adx: number;
    plus_di: number;
    minus_di: number;
  } | null;
  signal: string;
  trend: string;
  recommendation: string;
}

interface TimeframeSuggestion {
  timeframe: string;
  score: number;
  reason: string;
  suitability: 'excellent' | 'good' | 'moderate' | 'poor';
}

const StockDetailModal: React.FC<StockDetailModalProps> = ({
  symbol,
  onClose,
  currentPrice = 0,
  change = 0,
  changePercent = 0
}) => {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'news' | 'technicals' | 'timeframes' | 'peers' | 'strategies'>('overview');
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [technicals, setTechnicals] = useState<TechnicalAnalysis | null>(null);
  const [timeframeSuggestions, setTimeframeSuggestions] = useState<TimeframeSuggestion[]>([]);
  const [newsLoading, setNewsLoading] = useState(false);
  const [mlSignal, setMlSignal] = useState<{
    signal: string; confidence: number; bias: string; reason: string;
    model_type?: string; indicators?: any;
  } | null>(null);
  const [mlLoading, setMlLoading] = useState(false);

  // Calculate sentiment summary from news articles
  const calculateNewsSentiment = () => {
    if (news.length === 0) return { positive: 0, negative: 0, neutral: 0, dominant: 'neutral' as const };
    
    const counts = {
      positive: news.filter(a => a.sentiment === 'positive').length,
      negative: news.filter(a => a.sentiment === 'negative').length,
      neutral: news.filter(a => a.sentiment === 'neutral').length,
    };
    
    let dominant: 'positive' | 'negative' | 'neutral' = 'neutral';
    if (counts.positive > counts.negative && counts.positive > counts.neutral) {
      dominant = 'positive';
    } else if (counts.negative > counts.positive && counts.negative > counts.neutral) {
      dominant = 'negative';
    }
    
    return { ...counts, dominant };
  };

  useEffect(() => {
    loadStockDetails();
  }, [symbol]);

  const loadStockDetails = async () => {
    setLoading(true);
    try {
      // Keep modal snappy: wait only for core overview data, load the rest in background.
      await Promise.allSettled([
        loadTechnicals(),
        loadMLSignal(),
      ]);

      void loadNews();
      void loadTimeframeSuggestions();
    } catch (error) {
      console.error('Failed to load stock details:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadNews = async () => {
    setNewsLoading(true);
    try {
      const newsUrl = `/api/stock-news/${symbol}`;
      
      const response = await fetch(newsUrl);
      
      if (!response.ok) {
        console.error(`News API error ${response.status}:`, response.statusText);
        setNews([]);
        return;
      }
      
      const data = await response.json();
      
      if (data.error) {
        console.warn('News API warning:', data.error);
      }
      
      setNews(data.articles || []);
    } catch (error) {
      console.error('Failed to load news:', error);
      if (error instanceof Error) {
        console.error('Error details:', error.message, error.stack);
      }
      setNews([]);
    } finally {
      setNewsLoading(false);
    }
  };

  const loadTechnicals = async () => {
    try {
      const techUrl = `/api/market-dashboard/stock-technicals/${symbol}`;
      
      const response = await fetch(techUrl);
      
      if (!response.ok) {
        console.error(`Technicals API error ${response.status}:`, response.statusText);
        setTechnicals(null);
        return;
      }
      
      const data = await response.json();
      
      setTechnicals({
        rsi: data.indicators?.rsi || null,
        macd: data.indicators?.macd || null,
        adx: data.indicators?.adx || null,
        signal: data.signal || 'NEUTRAL',
        trend: data.trend || 'SIDEWAYS',
        recommendation: data.recommendation || 'HOLD'
      });
    } catch (error) {
      console.error('Failed to load technicals:', error);
      if (error instanceof Error) {
        console.error('Error details:', error.message, error.stack);
      }
      setTechnicals(null);
    }
  };

  const loadMLSignal = async () => {
    setMlLoading(true);
    try {
      const res = await mlAPI.predict(symbol);
      if (res.data && res.data.signal) {
        setMlSignal(res.data);
      }
    } catch (err) {
      console.warn('ML signal unavailable:', err);
      setMlSignal(null);
    } finally {
      setMlLoading(false);
    }
  };

  const loadTimeframeSuggestions = async () => {
    try {
      const response = await fetch(`/api/timeframe-suggestions/${symbol}`);
      const data = await response.json();
      setTimeframeSuggestions(data.suggestions || []);
    } catch (error) {
      console.error('Failed to load timeframe suggestions:', error);
      // Create default suggestions based on technicals
      setTimeframeSuggestions([
        {
          timeframe: '15m',
          score: 75,
          reason: 'Good for intraday momentum trades',
          suitability: 'good'
        },
        {
          timeframe: '1h',
          score: 85,
          reason: 'Optimal for swing trading entries',
          suitability: 'excellent'
        },
        {
          timeframe: '1d',
          score: 70,
          reason: 'Suitable for position trading',
          suitability: 'good'
        }
      ]);
    }
  };

  const getSentimentColor = (sentiment?: string) => {
    switch (sentiment) {
      case 'positive': return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
      case 'negative': return 'text-red-400 bg-red-500/10 border-red-500/20';
      default: return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
    }
  };

  const getSuitabilityColor = (suitability: string) => {
    switch (suitability) {
      case 'excellent': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'good': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'moderate': return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'poor': return 'bg-red-500/20 text-red-400 border-red-500/30';
      default: return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl shadow-2xl w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="border-b border-slate-700 p-6">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h2 className="text-2xl font-bold text-white">{symbol}</h2>
                <div className={`flex items-center gap-1 px-3 py-1 rounded-full text-sm ${
                  changePercent >= 0 
                    ? 'bg-emerald-500/20 text-emerald-400' 
                    : 'bg-red-500/20 text-red-400'
                }`}>
                  {changePercent >= 0 ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                  {changePercent >= 0 ? '+' : ''}{changePercent.toFixed(2)}%
                </div>
              </div>
              <div className="flex items-baseline gap-3 mt-2">
                <span className="text-3xl font-bold text-white">₹{currentPrice.toFixed(2)}</span>
                <span className={`text-lg ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {change >= 0 ? '+' : ''}{change.toFixed(2)}
                </span>
              </div>
            </div>
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-white transition p-2 hover:bg-slate-800 rounded-lg"
            >
              <X size={24} />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex items-center gap-2 mt-6">
            {[
              { id: 'overview', label: 'Overview', icon: Eye },            { id: 'strategies', label: 'Strategies', icon: Zap },              { id: 'news', label: 'News', icon: Newspaper },
              { id: 'technicals', label: 'Technicals', icon: BarChart3 },
              { id: 'timeframes', label: 'Timeframes', icon: Clock },
              { id: 'peers', label: 'Peers', icon: TrendIcon }
            ].map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id as typeof activeTab)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition ${
                  activeTab === id
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                }`}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-3">
                <Activity size={32} className="text-emerald-400 animate-pulse" />
                <p className="text-slate-400">Loading stock details...</p>
              </div>
            </div>
          ) : (
            <>
              {/* Overview Tab */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Chart */}
                  <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6">
                    <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                      <BarChart3 size={16} className="text-blue-400" />
                      Price Chart (15m)
                    </h3>
                    <div className="w-full" style={{ height: '450px' }}>
                      <TechnicalChart symbol={symbol} timeframe="15m" height={450} />
                    </div>
                  </div>

                  {/* ML Signal Card */}
                  {mlSignal && mlSignal.signal !== 'NO_TRADE' && (
                    <div className={`border rounded-xl p-5 ${
                      mlSignal.signal === 'BULLISH'
                        ? 'bg-emerald-500/10 border-emerald-500/30'
                        : mlSignal.signal === 'BEARISH'
                        ? 'bg-red-500/10 border-red-500/30'
                        : 'bg-slate-800/50 border-slate-700/50'
                    }`}>
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                          <Brain size={16} className="text-purple-400" />
                          ML Prediction
                          {mlSignal.model_type && (
                            <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                              mlSignal.model_type === 'ensemble'
                                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                                : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            }`}>
                              {mlSignal.model_type === 'ensemble' ? 'ENSEMBLE' : 'GBM'}
                            </span>
                          )}
                        </h3>
                        <span className={`text-lg font-bold ${
                          mlSignal.signal === 'BULLISH' ? 'text-emerald-400' :
                          mlSignal.signal === 'BEARISH' ? 'text-red-400' : 'text-slate-400'
                        }`}>
                          {mlSignal.signal === 'BULLISH' ? '▲' : mlSignal.signal === 'BEARISH' ? '▼' : '─'} {mlSignal.signal}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <p className="text-slate-400 text-xs">Confidence</p>
                          <div className="flex items-center gap-2 mt-1">
                            <div className="flex-1 h-2 rounded-full bg-slate-700 overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-all ${
                                  mlSignal.confidence >= 70 ? 'bg-emerald-400' :
                                  mlSignal.confidence >= 55 ? 'bg-yellow-400' : 'bg-slate-400'
                                }`}
                                style={{ width: `${mlSignal.confidence}%` }}
                              />
                            </div>
                            <span className="text-white text-sm font-bold">{mlSignal.confidence}%</span>
                          </div>
                        </div>
                        <div>
                          <p className="text-slate-400 text-xs">Bias</p>
                          <p className={`text-sm font-semibold mt-1 ${
                            mlSignal.bias === 'BULLISH' ? 'text-emerald-400' :
                            mlSignal.bias === 'BEARISH' ? 'text-red-400' : 'text-slate-400'
                          }`}>{mlSignal.bias}</p>
                        </div>
                      </div>
                      {mlSignal.reason && (
                        <p className="text-slate-500 text-xs mt-3 border-t border-slate-700/50 pt-2">{mlSignal.reason}</p>
                      )}
                      {mlSignal.indicators?.ensemble_prob_up !== undefined && (
                        <div className="mt-2 flex items-center gap-3 text-xs">
                          <span className="text-slate-400">Prob(Up):</span>
                          <span className="text-white font-mono">{(mlSignal.indicators.ensemble_prob_up * 100).toFixed(1)}%</span>
                          {mlSignal.indicators.per_model && (
                            <span className="text-slate-500">
                              GBM {(mlSignal.indicators.per_model.gbm * 100).toFixed(0)}%
                              {' · '}RF {(mlSignal.indicators.per_model.rf * 100).toFixed(0)}%
                              {' · '}XGB {(mlSignal.indicators.per_model.xgb * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      )}
                      {mlSignal.indicators?.ml_prob_up !== undefined && !mlSignal.indicators?.ensemble_prob_up && (
                        <div className="mt-2 flex items-center gap-3 text-xs">
                          <span className="text-slate-400">Prob(Up):</span>
                          <span className="text-white font-mono">{(mlSignal.indicators.ml_prob_up * 100).toFixed(1)}%</span>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Quick Stats */}
                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                        <Target size={16} className="text-emerald-400" />
                        Technical Signal
                      </h3>
                      {technicals && (
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 text-sm">Signal</span>
                            <span className={`text-sm font-semibold ${
                              technicals.signal.includes('BUY') ? 'text-emerald-400' :
                              technicals.signal.includes('SELL') ? 'text-red-400' : 'text-slate-400'
                            }`}>
                              {technicals.signal}
                            </span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 text-sm">Trend</span>
                            <span className="text-sm font-semibold text-white">{technicals.trend}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-400 text-sm">Recommendation</span>
                            <span className="text-sm font-semibold text-emerald-400">{technicals.recommendation}</span>
                          </div>
                          
                          {/* News Sentiment */}
                          {news.length > 0 && (() => {
                            const sentiment = calculateNewsSentiment();
                            return (
                              <div className="border-t border-slate-700 pt-3 mt-3">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-slate-400 text-sm">News Sentiment</span>
                                  <span className={`text-xs px-2 py-1 rounded-full font-semibold ${
                                    sentiment.dominant === 'positive' ? 'bg-emerald-500/20 text-emerald-400' :
                                    sentiment.dominant === 'negative' ? 'bg-red-500/20 text-red-400' :
                                    'bg-slate-500/20 text-slate-400'
                                  }`}>
                                    {sentiment.dominant.charAt(0).toUpperCase() + sentiment.dominant.slice(1)}
                                  </span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                  <span className="text-emerald-400">🟢 {sentiment.positive}</span>
                                  <span className="text-red-400">🔴 {sentiment.negative}</span>
                                  <span className="text-slate-400">⚪ {sentiment.neutral}</span>
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      )}
                    </div>

                    {/* Recent News Preview */}
                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
                        <Newspaper size={16} className="text-blue-400" />
                        Latest News
                      </h3>
                      <div className="space-y-3">
                        {news.slice(0, 3).map((article, idx) => (
                          <div key={idx} className="text-sm">
                            <p className="text-white line-clamp-2">{article.title}</p>
                            <p className="text-xs text-slate-400 mt-1">{article.source}</p>
                          </div>
                        ))}
                        {news.length === 0 && (
                          <p className="text-slate-400 text-sm">No recent news available</p>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Historical Returns */}
                  <HistoricalReturns 
                    symbol={symbol}
                    currentPrice={currentPrice}
                  />
                </div>
              )}

              {/* News Tab */}
              {activeTab === 'news' && (
                <div className="space-y-4">
                  {newsLoading ? (
                    <div className="flex items-center justify-center py-10">
                      <Activity size={24} className="text-emerald-400 animate-pulse" />
                    </div>
                  ) : news.length > 0 ? (
                    news.map((article, idx) => (
                      <div key={idx} className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5 hover:bg-slate-800/70 transition">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <h4 className="text-white font-semibold">{article.title}</h4>
                              {article.sentiment && (
                                <span className={`text-xs px-2 py-1 rounded-full border ${getSentimentColor(article.sentiment)}`}>
                                  {article.sentiment}
                                </span>
                              )}
                            </div>
                            <p className="text-slate-300 text-sm mb-3">{article.description}</p>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3 text-xs text-slate-400">
                                <span>{article.source}</span>
                                <span>•</span>
                                <span>{new Date(article.publishedAt).toLocaleString()}</span>
                              </div>
                              <a
                                href={article.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300"
                              >
                                Read more <ExternalLink size={12} />
                              </a>
                            </div>
                          </div>
                          {article.imageUrl && (
                            <img
                              src={article.imageUrl}
                              alt={article.title}
                              className="w-24 h-24 object-cover rounded-lg"
                            />
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-10">
                      <Newspaper size={48} className="mx-auto text-slate-600 mb-3" />
                      <p className="text-slate-400">No news articles found for {symbol}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Technicals Tab */}
              {activeTab === 'technicals' && technicals && (
                <div className="space-y-6">
                  {/* Indicators Grid */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* RSI */}
                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                      <h4 className="text-xs uppercase tracking-wider text-slate-400 mb-3">RSI (14)</h4>
                      <div className="flex items-baseline gap-2">
                        <span className="text-3xl font-bold text-white">
                          {technicals.rsi?.toFixed(1) || 'N/A'}
                        </span>
                        {technicals.rsi && (
                          <span className={`text-sm ${
                            technicals.rsi > 70 ? 'text-red-400' :
                            technicals.rsi < 30 ? 'text-emerald-400' : 'text-slate-400'
                          }`}>
                            {technicals.rsi > 70 ? 'Overbought' :
                             technicals.rsi < 30 ? 'Oversold' : 'Neutral'}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* ADX */}
                    {technicals.adx && (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                        <h4 className="text-xs uppercase tracking-wider text-slate-400 mb-3">ADX (14)</h4>
                        <div className="flex items-baseline gap-2">
                          <span className="text-3xl font-bold text-white">
                            {technicals.adx.adx.toFixed(1)}
                          </span>
                          <span className={`text-sm ${
                            technicals.adx.adx > 25 ? 'text-emerald-400' : 'text-slate-400'
                          }`}>
                            {technicals.adx.adx > 25 ? 'Strong Trend' : 'Weak Trend'}
                          </span>
                        </div>
                        <div className="mt-3 space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-400">+DI</span>
                            <span className="text-emerald-400">{technicals.adx.plus_di.toFixed(1)}</span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-400">-DI</span>
                            <span className="text-red-400">{technicals.adx.minus_di.toFixed(1)}</span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* MACD */}
                    {technicals.macd && (
                      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
                        <h4 className="text-xs uppercase tracking-wider text-slate-400 mb-3">MACD</h4>
                        <div className="flex items-baseline gap-2">
                          <span className="text-3xl font-bold text-white">
                            {technicals.macd.histogram.toFixed(2)}
                          </span>
                          <span className={`text-sm ${
                            technicals.macd.histogram > 0 ? 'text-emerald-400' : 'text-red-400'
                          }`}>
                            {technicals.macd.histogram > 0 ? 'Bullish' : 'Bearish'}
                          </span>
                        </div>
                        <div className="mt-3 space-y-1">
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-400">MACD</span>
                            <span className="text-white">{technicals.macd.macd.toFixed(2)}</span>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-400">Signal</span>
                            <span className="text-white">{technicals.macd.signal.toFixed(2)}</span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Trading Signal */}
                  <div className="bg-gradient-to-r from-emerald-500/10 to-blue-500/10 border border-emerald-500/20 rounded-xl p-6">
                    <div className="flex items-center gap-3 mb-3">
                      <Zap size={24} className="text-emerald-400" />
                      <h3 className="text-xl font-bold text-white">Trading Recommendation</h3>
                    </div>
                    <p className="text-lg text-emerald-400 font-semibold mb-2">{technicals.recommendation}</p>
                    <p className="text-slate-300">
                      Based on current technical indicators, the stock shows a <span className="text-white font-semibold">{technicals.trend}</span> trend 
                      with a <span className="text-white font-semibold">{technicals.signal}</span> signal.
                    </p>
                  </div>
                </div>
              )}

              {/* Timeframes Tab */}
              {activeTab === 'timeframes' && (
                <div className="space-y-4">
                  <div className="bg-slate-800/30 border border-slate-700/50 rounded-xl p-5">
                    <h3 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
                      <AlertCircle size={16} className="text-blue-400" />
                      Timeframe Analysis
                    </h3>
                    <p className="text-sm text-slate-400">
                      Based on volatility, trend strength, and market conditions, here are the recommended timeframes for trading {symbol}.
                    </p>
                  </div>

                  {timeframeSuggestions.map((suggestion, idx) => (
                    <div key={idx} className={`border rounded-xl p-5 ${getSuitabilityColor(suggestion.suitability)}`}>
                      <div className="flex items-center justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <Clock size={24} />
                          <div>
                            <h4 className="text-lg font-bold">{suggestion.timeframe}</h4>
                            <p className="text-xs opacity-70 uppercase tracking-wider">{suggestion.suitability}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold">{suggestion.score}</div>
                          <div className="text-xs opacity-70">Score</div>
                        </div>
                      </div>
                      <p className="text-sm">
                        {suggestion.reason}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              {/* Strategies Tab */}
              {activeTab === 'strategies' && (
                <StockStrategyPanel 
                  symbol={symbol} 
                  currentPrice={currentPrice}
                />
              )}

              {/* Peers Tab */}
              {activeTab === 'peers' && (
                <PeerComparison symbol={symbol} onClose={onClose} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default StockDetailModal;
