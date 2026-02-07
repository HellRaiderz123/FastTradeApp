import axios from 'axios';

const NEWS_API = axios.create({
  baseURL: 'http://localhost:8000/news',
  timeout: 15000,
});

export interface NewsItem {
  id: string;
  headline: string;
  category: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  sentiment_score: number;
  impact: 'high' | 'medium' | 'low';
  timestamp: string;
  source: string;
  read: boolean;
}

export interface SentimentSummary {
  bullish: number;
  bearish: number;
  neutral: number;
}

export interface NewsFeedResponse {
  news: NewsItem[];
  total_count: number;
  categories: string[];
  sentiment_summary: SentimentSummary;
}

export interface TrendingTopic {
  keyword: string;
  mentions: number;
  sentiment: number;
}

export interface TrendingTopicsResponse {
  topics: TrendingTopic[];
}

export interface MarketAlert {
  type: 'breaking' | 'volatility' | 'technical' | 'earnings';
  message: string;
  timestamp: string;
  priority: 'high' | 'medium' | 'low';
}

export interface MarketAlertsResponse {
  alerts: MarketAlert[];
}

export const getNewsFeed = async (
  limit: number = 20,
  offset: number = 0,
  category?: string,
  sentiment?: 'bullish' | 'bearish' | 'neutral'
): Promise<NewsFeedResponse> => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  params.append('offset', offset.toString());
  if (category) params.append('category', category);
  if (sentiment) params.append('sentiment', sentiment);

  const response = await NEWS_API.get<NewsFeedResponse>(`/feed?${params.toString()}`);
  return response.data;
};

export const getTrendingTopics = async (): Promise<TrendingTopicsResponse> => {
  const response = await NEWS_API.get<TrendingTopicsResponse>('/trending');
  return response.data;
};

export const getMarketAlerts = async (): Promise<MarketAlertsResponse> => {
  const response = await NEWS_API.get<MarketAlertsResponse>('/alerts');
  return response.data;
};

export const markNewsAsRead = async (newsId: string): Promise<void> => {
  // Mock implementation - could be real API call
  console.log(`Marked news ${newsId} as read`);
};
