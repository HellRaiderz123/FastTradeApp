import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Minus, Newspaper, Sparkles, ExternalLink, RefreshCw } from 'lucide-react';
import { getNewsFeed, getTrendingTopics, type NewsItem, type TrendingTopic, type SentimentSummary } from '../api/newsAPI';
import { cn } from '@/lib/utils';

interface MarketPulseProps {
  /** unused — kept for drop-in compatibility with TwitterSentimentWidget */
  timeframe?: string;
  symbol?: string;
}

function timeAgo(ts: string) {
  const diff = Date.now() - new Date(ts).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  if (m < 1440) return `${Math.floor(m / 60)}h ago`;
  return `${Math.floor(m / 1440)}d ago`;
}

const sentimentColor = (s: string) =>
  s === 'bullish' ? 'text-emerald-500' : s === 'bearish' ? 'text-red-500' : 'text-muted-foreground';

const sentimentBg = (s: string) =>
  s === 'bullish' ? 'bg-emerald-500/10 text-emerald-500' : s === 'bearish' ? 'bg-red-500/10 text-red-500' : 'bg-muted/60 text-muted-foreground';

const impactBg = (m?: string) =>
  m === 'high' ? 'bg-red-500/10 text-red-400' : m === 'medium' ? 'bg-amber-500/10 text-amber-400' : 'bg-muted/40 text-muted-foreground';

const SentimentIcon: React.FC<{ s: string; className?: string }> = ({ s, className }) => {
  if (s === 'bullish') return <TrendingUp className={cn('h-3 w-3', className ?? 'text-emerald-500')} />;
  if (s === 'bearish') return <TrendingDown className={cn('h-3 w-3', className ?? 'text-red-500')} />;
  return <Minus className={cn('h-3 w-3', className ?? 'text-muted-foreground')} />;
};

const MarketPulse: React.FC<MarketPulseProps> = () => {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [topics, setTopics] = useState<TrendingTopic[]>([]);
  const [summary, setSummary] = useState<SentimentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(false);

  const load = async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    try {
      const [feedRes, topicsRes] = await Promise.allSettled([
        getNewsFeed(8, 0),
        getTrendingTopics(),
      ]);
      if (feedRes.status === 'fulfilled') {
        setNews(feedRes.value.news ?? []);
        setSummary(feedRes.value.sentiment_summary ?? null);
        setError(false);
      }
      if (topicsRes.status === 'fulfilled') {
        setTopics(topicsRes.value.topics?.slice(0, 5) ?? []);
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
    const t = setInterval(() => load(), 120_000);
    return () => clearInterval(t);
  }, []);

  const total = summary ? summary.bullish + summary.bearish + summary.neutral : 0;
  const bullPct = total > 0 ? Math.round((summary!.bullish / total) * 100) : 0;
  const bearPct = total > 0 ? Math.round((summary!.bearish / total) * 100) : 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-3.5 pb-2 shrink-0">
        <div className="flex items-center gap-2">
          <Newspaper className="h-3.5 w-3.5 text-muted-foreground" />
          <p className="text-sm font-semibold text-foreground">Market Pulse</p>
        </div>
        <button
          onClick={() => load(true)}
          className="text-muted-foreground hover:text-foreground transition-colors"
          disabled={refreshing}
        >
          <RefreshCw className={cn('h-3 w-3', refreshing && 'animate-spin')} />
        </button>
      </div>

      {loading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : error ? (
        <div className="flex flex-1 items-center justify-center px-4 text-center">
          <p className="text-xs text-muted-foreground">News feed unavailable</p>
        </div>
      ) : (
        <div className="flex flex-col flex-1 overflow-hidden px-3 pb-3 gap-3">

          {/* Sentiment bar */}
          {summary && total > 0 && (
            <div className="shrink-0">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-muted-foreground">Sentiment</span>
                <div className="flex items-center gap-2 text-[10px]">
                  <span className="text-emerald-500">{bullPct}% Bull</span>
                  <span className="text-red-500">{bearPct}% Bear</span>
                </div>
              </div>
              <div className="flex h-1.5 rounded-full overflow-hidden gap-px">
                <div className="bg-emerald-500 rounded-l-full transition-all" style={{ width: `${bullPct}%` }} />
                <div className="bg-muted flex-1" />
                <div className="bg-red-500 rounded-r-full transition-all" style={{ width: `${bearPct}%` }} />
              </div>
            </div>
          )}

          {/* Trending topics */}
          {topics.length > 0 && (
            <div className="shrink-0 flex flex-wrap gap-1">
              {topics.map((t) => (
                <span
                  key={t.keyword}
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium',
                    t.sentiment > 0.1 ? 'bg-emerald-500/10 text-emerald-500' :
                    t.sentiment < -0.1 ? 'bg-red-500/10 text-red-500' :
                    'bg-muted/60 text-muted-foreground'
                  )}
                >
                  {t.keyword}
                  <span className="opacity-60">{t.mentions}</span>
                </span>
              ))}
            </div>
          )}

          {/* News items */}
          <div className="flex-1 overflow-y-auto space-y-2 no-scrollbar">
            {news.length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-6">No news available</p>
            )}
            {news.map((item, i) => (
              <a
                key={i}
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-lg border border-border/60 bg-muted/20 px-3 py-2 hover:bg-accent/50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex items-center gap-1.5 shrink-0">
                    <SentimentIcon s={item.llm_impact ?? item.sentiment} />
                    {item.llm_impact && (
                      <span className={cn('text-[9px] font-semibold rounded px-1 py-px', impactBg(item.llm_magnitude))}>
                        {item.llm_magnitude ?? 'AI'}
                      </span>
                    )}
                    {item.llm_impact && (
                      <Sparkles className="h-2.5 w-2.5 text-violet-400" />
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <span className="text-[9px] text-muted-foreground">{timeAgo(item.published)}</span>
                    <ExternalLink className="h-2.5 w-2.5 text-muted-foreground/40 group-hover:text-muted-foreground transition-colors" />
                  </div>
                </div>
                <p className="text-[11px] font-medium text-foreground leading-snug line-clamp-2">{item.title}</p>
                {item.llm_symbols && item.llm_symbols.length > 0 && (
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {item.llm_symbols.slice(0, 3).map((sym) => (
                      <span key={sym} className="text-[9px] font-mono bg-primary/10 text-primary rounded px-1">{sym}</span>
                    ))}
                  </div>
                )}
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default MarketPulse;
