import React, { useEffect, useState } from 'react';
import { Twitter, TrendingUp, TrendingDown, Minus, AlertTriangle, ExternalLink } from 'lucide-react';
import { twitterAPI } from '../lib/api';

interface Tweet {
  tweet_id: string;
  username: string;
  text: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  sentiment_score: number;
  engagement_score: number;
  impact_level: 'high' | 'medium' | 'low';
  retweets: number;
  likes: number;
  created_at: string;
}

interface TrendingSymbol {
  symbol: string;
  tweet_count: number;
  high_impact_count: number;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  sentiment_score: number;
  avg_engagement: number;
}

interface TwitterSentimentWidgetProps {
  symbol?: string;
  timeframe?: '15m' | '1h' | '4h' | '1d';
}

const TwitterSentimentWidget: React.FC<TwitterSentimentWidgetProps> = ({ 
  symbol, 
  timeframe = '1h' 
}) => {
  const [tweets, setTweets] = useState<Tweet[]>([]);
  const [trending, setTrending] = useState<TrendingSymbol[]>([]);
  const [overallSentiment, setOverallSentiment] = useState<{
    sentiment: string;
    score: number;
    confidence: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTwitterData();
    const interval = setInterval(fetchTwitterData, 60000); // Update every minute
    return () => clearInterval(interval);
  }, [symbol, timeframe]);

  const fetchTwitterData = async () => {
    try {
      setLoading(true);
      setError(null);

      if (symbol) {
        // Fetch sentiment for specific symbol
        const response = await twitterAPI.getSymbolSentiment(symbol, timeframe);
        setOverallSentiment({
          sentiment: response.data.sentiment,
          score: response.data.sentiment_score,
          confidence: response.data.confidence
        });
        setTweets(response.data.top_tweets || []);
      } else {
        // Fetch trending symbols and recent tweets
        const [trendingRes, tweetsRes] = await Promise.all([
          twitterAPI.getTrending(timeframe, 5),
          twitterAPI.getRecentTweets({ limit: 10, impact_level: 'high' })
        ]);
        setTrending(trendingRes.data.trending || []);
        setTweets(tweetsRes.data.tweets || []);
      }
    } catch (err: any) {
      if (err.response?.status === 503) {
        setError('Twitter API not configured');
      } else {
        console.error('Failed to fetch Twitter data:', err);
        setError('Failed to load');
      }
    } finally {
      setLoading(false);
    }
  };

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return 'text-green-400';
      case 'bearish': return 'text-red-400';
      default: return 'text-slate-400';
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return <TrendingUp className="w-4 h-4 text-green-400" />;
      case 'bearish': return <TrendingDown className="w-4 h-4 text-red-400" />;
      default: return <Minus className="w-4 h-4 text-slate-400" />;
    }
  };

  const getImpactBadge = (impact: string) => {
    const colors = {
      high: 'bg-red-900/30 text-red-400 border-red-700',
      medium: 'bg-yellow-900/30 text-yellow-400 border-yellow-700',
      low: 'bg-slate-700/30 text-slate-400 border-slate-600'
    };
    return `px-2 py-0.5 rounded-full text-xs border ${colors[impact as keyof typeof colors] || colors.low}`;
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  if (loading && tweets.length === 0) {
    return (
      <div className="bg-slate-900 rounded-lg border border-slate-800 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Twitter className="w-5 h-5 text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Twitter Sentiment</h3>
        </div>
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto"></div>
          <p className="text-slate-400 mt-2">Loading Twitter data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-slate-900 rounded-lg border border-slate-800 p-6">
        <div className="flex items-center gap-2 mb-4">
          <Twitter className="w-5 h-5 text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Twitter Sentiment</h3>
        </div>
        <div className="text-center py-8">
          <AlertTriangle className="w-8 h-8 text-yellow-500 mx-auto mb-2" />
          <p className="text-slate-400">{error}</p>
          <p className="text-xs text-slate-500 mt-1">Set TWITTER_BEARER_TOKEN in .env</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 rounded-lg border border-slate-800 p-6 h-full overflow-hidden flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Twitter className="w-5 h-5 text-blue-400" />
          <h3 className="text-lg font-semibold text-white">Twitter Sentiment</h3>
        </div>
        <span className="text-xs text-slate-500">{timeframe}</span>
      </div>

      {/* Overall Sentiment (if symbol specified) */}
      {overallSentiment && symbol && (
        <div className="mb-4 p-4 bg-slate-800 rounded-lg">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-400 mb-1">{symbol}</p>
              <div className="flex items-center gap-2">
                {getSentimentIcon(overallSentiment.sentiment)}
                <span className={`text-lg font-bold capitalize ${getSentimentColor(overallSentiment.sentiment)}`}>
                  {overallSentiment.sentiment}
                </span>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500">Confidence</p>
              <p className="text-lg font-bold text-white">{(overallSentiment.confidence * 100).toFixed(0)}%</p>
            </div>
          </div>
        </div>
      )}

      {/* Trending Symbols (if no symbol specified) */}
      {trending.length > 0 && !symbol && (
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-slate-300 mb-2">Trending</h4>
          <div className="space-y-2">
            {trending.slice(0, 3).map((item) => (
              <div key={item.symbol} className="flex items-center justify-between p-2 bg-slate-800 rounded">
                <div className="flex items-center gap-2">
                  {getSentimentIcon(item.sentiment)}
                  <span className="font-medium text-white">{item.symbol}</span>
                  {item.high_impact_count > 0 && (
                    <span className="text-xs text-red-400">🔥 {item.high_impact_count}</span>
                  )}
                </div>
                <div className="text-xs text-slate-400">{item.tweet_count} tweets</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Tweets */}
      <div className="flex-1 overflow-y-auto space-y-3">
        <h4 className="text-sm font-semibold text-slate-300 sticky top-0 bg-slate-900 pb-2">
          {tweets.length > 0 ? 'Recent Tweets' : 'No Recent Activity'}
        </h4>
        {tweets.map((tweet) => (
          <div key={tweet.tweet_id} className="p-3 bg-slate-800 rounded-lg space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2 flex-1">
                <Twitter className="w-4 h-4 text-blue-400 flex-shrink-0" />
                <span className="font-medium text-blue-400 text-sm">@{tweet.username}</span>
                <span className={getImpactBadge(tweet.impact_level)}>{tweet.impact_level}</span>
              </div>
              <span className="text-xs text-slate-500 whitespace-nowrap">
                {formatTime(tweet.created_at)}
              </span>
            </div>
            
            <p className="text-sm text-slate-300 line-clamp-3">{tweet.text}</p>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {getSentimentIcon(tweet.sentiment)}
                <span className={`text-xs capitalize ${getSentimentColor(tweet.sentiment)}`}>
                  {tweet.sentiment}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-500">
                <span>❤️ {tweet.likes}</span>
                <span>🔁 {tweet.retweets}</span>
                <a 
                  href={`https://twitter.com/${tweet.username}/status/${tweet.tweet_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300"
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TwitterSentimentWidget;
