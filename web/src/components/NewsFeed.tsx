import React, { useState, useEffect } from 'react';
import { 
  getNewsFeed, 
  getTrendingTopics, 
  getMarketAlerts,
  NewsItem, 
  TrendingTopic, 
  MarketAlert,
  SentimentSummary 
} from '../api/newsAPI';
import { 
  Newspaper, 
  TrendingUp, 
  AlertTriangle, 
  ArrowUp, 
  ArrowDown, 
  Minus,
  Clock,
  ExternalLink
} from 'lucide-react';

interface NewsFeedProps {
  height?: number;
}

const NewsFeed: React.FC<NewsFeedProps> = ({ height = 600 }) => {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [trendingTopics, setTrendingTopics] = useState<TrendingTopic[]>([]);
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [sentimentSummary, setSentimentSummary] = useState<SentimentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedSentiment, setSelectedSentiment] = useState<string>('all');
  const [categories, setCategories] = useState<string[]>([]);

  useEffect(() => {
    loadNewsFeed();
    loadTrendingTopics();
    loadMarketAlerts();

    // Auto-refresh every 2 minutes
    const interval = setInterval(() => {
      loadNewsFeed();
      loadTrendingTopics();
      loadMarketAlerts();
    }, 120000);

    return () => clearInterval(interval);
  }, [selectedCategory, selectedSentiment]);

  const loadNewsFeed = async () => {
    try {
      setLoading(true);
      const categoryParam = selectedCategory === 'all' ? undefined : selectedCategory;
      const sentimentParam = selectedSentiment === 'all' ? undefined : selectedSentiment as any;
      
      const response = await getNewsFeed(20, 0, categoryParam, sentimentParam);
      setNews(response.news);
      setCategories(response.categories);
      setSentimentSummary(response.sentiment_summary);
    } catch (error) {
      console.error('Failed to load news feed:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadTrendingTopics = async () => {
    try {
      const response = await getTrendingTopics();
      setTrendingTopics(response.topics);
    } catch (error) {
      console.error('Failed to load trending topics:', error);
    }
  };

  const loadMarketAlerts = async () => {
    try {
      const response = await getMarketAlerts();
      setAlerts(response.alerts);
    } catch (error) {
      console.error('Failed to load market alerts:', error);
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish':
        return <ArrowUp className="w-4 h-4 text-green-400" />;
      case 'bearish':
        return <ArrowDown className="w-4 h-4 text-red-400" />;
      default:
        return <Minus className="w-4 h-4 text-gray-400" />;
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish':
        return 'text-green-400 bg-green-500/10 border-green-500/30';
      case 'bearish':
        return 'text-red-400 bg-red-500/10 border-red-500/30';
      default:
        return 'text-gray-400 bg-gray-500/10 border-gray-500/30';
    }
  };

  const getImpactBadgeColor = (impact: string) => {
    switch (impact) {
      case 'high':
        return 'bg-red-500/20 text-red-300 border-red-500/40';
      case 'medium':
        return 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40';
      case 'low':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
      default:
        return 'bg-gray-500/20 text-gray-300 border-gray-500/40';
    }
  };

  const getAlertColor = (type: string) => {
    switch (type) {
      case 'breaking':
        return 'border-red-500/50 bg-red-500/10';
      case 'volatility':
        return 'border-orange-500/50 bg-orange-500/10';
      case 'technical':
        return 'border-blue-500/50 bg-blue-500/10';
      case 'earnings':
        return 'border-purple-500/50 bg-purple-500/10';
      default:
        return 'border-gray-500/50 bg-gray-500/10';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor((now.getTime() - date.getTime()) / 60000);

    if (diffInMinutes < 1) return 'Just now';
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
  };

  return (
    <div style={{ height: `${height}px` }} className="flex flex-col space-y-3 overflow-hidden">
      {/* Market Alerts */}
      {alerts.length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 space-y-2">
          <div className="flex items-center space-x-2 text-orange-400">
            <AlertTriangle className="w-4 h-4" />
            <span className="text-sm font-semibold">Market Alerts</span>
          </div>
          <div className="space-y-1.5">
            {alerts.slice(0, 3).map((alert, index) => (
              <div
                key={index}
                className={`p-2 rounded border ${getAlertColor(alert.type)}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <span className="text-xs font-mono uppercase text-gray-400">
                      {alert.type}
                    </span>
                    <p className="text-sm text-gray-200 mt-0.5">{alert.message}</p>
                  </div>
                  <Clock className="w-3 h-3 text-gray-500 flex-shrink-0 ml-2" />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sentiment Summary */}
      {sentimentSummary && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="text-sm font-semibold text-gray-300 mb-2">Market Sentiment</div>
          <div className="grid grid-cols-3 gap-2">
            <div className="flex flex-col items-center p-2 bg-green-500/10 rounded border border-green-500/30">
              <ArrowUp className="w-4 h-4 text-green-400 mb-1" />
              <span className="text-xl font-bold text-green-400">{sentimentSummary.bullish}</span>
              <span className="text-xs text-gray-400">Bullish</span>
            </div>
            <div className="flex flex-col items-center p-2 bg-red-500/10 rounded border border-red-500/30">
              <ArrowDown className="w-4 h-4 text-red-400 mb-1" />
              <span className="text-xl font-bold text-red-400">{sentimentSummary.bearish}</span>
              <span className="text-xs text-gray-400">Bearish</span>
            </div>
            <div className="flex flex-col items-center p-2 bg-gray-500/10 rounded border border-gray-500/30">
              <Minus className="w-4 h-4 text-gray-400 mb-1" />
              <span className="text-xl font-bold text-gray-400">{sentimentSummary.neutral}</span>
              <span className="text-xs text-gray-400">Neutral</span>
            </div>
          </div>
        </div>
      )}

      {/* Trending Topics */}
      {trendingTopics.length > 0 && (
        <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-3">
          <div className="flex items-center space-x-2 text-blue-400 mb-2">
            <TrendingUp className="w-4 h-4" />
            <span className="text-sm font-semibold">Trending</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {trendingTopics.slice(0, 5).map((topic, index) => (
              <div
                key={index}
                className="px-2 py-1 bg-slate-700/50 rounded-full border border-slate-600 flex items-center space-x-1.5"
              >
                <span className="text-xs text-gray-200">{topic.keyword}</span>
                <span className="text-xs text-gray-500">•</span>
                <span className="text-xs text-gray-400">{topic.mentions}</span>
                {topic.sentiment > 0.2 && <ArrowUp className="w-3 h-3 text-green-400" />}
                {topic.sentiment < -0.2 && <ArrowDown className="w-3 h-3 text-red-400" />}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center space-x-2 pb-2">
        <select
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-gray-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Categories</option>
          {categories.map((cat) => (
            <option key={cat} value={cat}>{cat}</option>
          ))}
        </select>

        <select
          value={selectedSentiment}
          onChange={(e) => setSelectedSentiment(e.target.value)}
          className="px-3 py-1.5 bg-slate-800 border border-slate-700 rounded text-sm text-gray-300 focus:outline-none focus:border-blue-500"
        >
          <option value="all">All Sentiment</option>
          <option value="bullish">Bullish</option>
          <option value="bearish">Bearish</option>
          <option value="neutral">Neutral</option>
        </select>
      </div>

      {/* News Feed */}
      <div className="flex-1 overflow-y-auto space-y-2 pr-2 custom-scrollbar">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-gray-400 text-sm">Loading news...</div>
          </div>
        ) : news.length === 0 ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-gray-500 text-sm">No news found</div>
          </div>
        ) : (
          news.map((item) => (
            <div
              key={item.id}
              className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 hover:border-slate-600 hover:bg-slate-800/70 transition-all cursor-pointer group"
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className={`p-1 rounded ${getSentimentColor(item.sentiment)}`}>
                    {getSentimentIcon(item.sentiment)}
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${getImpactBadgeColor(item.impact)}`}>
                    {item.impact}
                  </span>
                  <span className="text-xs text-gray-500">{item.category}</span>
                </div>
                <ExternalLink className="w-3 h-3 text-gray-600 group-hover:text-gray-400 transition-colors" />
              </div>

              <h4 className="text-sm text-gray-200 font-medium mb-2 leading-snug">
                {item.headline}
              </h4>

              <div className="flex items-center justify-between text-xs text-gray-500">
                <div className="flex items-center space-x-2">
                  <span className="font-mono">{item.source}</span>
                  <span>•</span>
                  <span>{formatTimestamp(item.timestamp)}</span>
                </div>
                <div className={`px-2 py-0.5 rounded-full ${getSentimentColor(item.sentiment)}`}>
                  {item.sentiment_score > 0 ? '+' : ''}{(item.sentiment_score * 100).toFixed(0)}%
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default NewsFeed;
