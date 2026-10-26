import { authTokenStore } from '@/lib/api';
import axios from 'axios';

const NEWS_API = axios.create({
  baseURL:(import.meta as any).env?.VITE_API_BASE ? `${(import.meta as any).env?.VITE_API_BASE}/news` : '/api/news',
  timeout: 15000,
});

// Attach Axios Request Interceptor
NEWS_API.interceptors.request.use(
  async (config) => {
    try {
      // 1. Fetch token asynchronously from your auth store
      const token = await authTokenStore.get();
      // const token = localStorage.getItem('access_token') || localStorage.getItem('token');

      // 2. Safely attach Bearer token if present
      if (token) {
        // Axios v1.x supports config.headers.set or direct header access
        if (config.headers && typeof config.headers.set === 'function') {
          config.headers.set('Authorization', `Bearer ${token}`);
        } else {
          config.headers = config.headers || {};
          config.headers.Authorization = `Bearer ${token}`;
        }
      }
    } catch (err) {
      // Avoid blocking the request completely if fetching token fails,
      // or log/handle based on auth failure requirements
      console.error('Failed to resolve auth token:', err);
    }

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export interface NewsItem {
  title: string;
  description: string;
  link: string;
  published: string;
  category: string;
  sentiment: 'bullish' | 'bearish' | 'neutral';
  source: string;
  // LLM (NVIDIA) impact scoring — present when LLM is configured
  llm_impact?: 'bullish' | 'bearish' | 'neutral';
  llm_magnitude?: 'high' | 'medium' | 'low';
  llm_symbols?: string[];
  llm_reason?: string;
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
  data_source: string;
  timestamp: string;
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
  type: 'breaking' | 'volatility' | 'technical' | 'earnings' | 'regulatory';
  message: string;
  timestamp: string;
  priority: 'high' | 'medium' | 'low';
  source?: string;
  link?: string;
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
