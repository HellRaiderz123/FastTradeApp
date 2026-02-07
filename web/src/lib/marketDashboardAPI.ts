// Market Dashboard API Client
import axios from 'axios';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

async function apiRequest<T>(url: string, options?: any): Promise<T> {
  const response = await api.get(url, options);
  return response.data;
}

export interface TopMover {
  symbol: string;
  ltp: number;
  change: number;
  change_percent: number;
  volume: number;
  prev_close: number;
}

export interface MarketBreadth {
  advancing: number;
  declining: number;
  unchanged: number;
  advance_decline_ratio: number;
  new_highs_52w: number;
  new_lows_52w: number;
  breadth_strength: string;
  total_stocks: number;
}

export interface HeatmapStock {
  symbol: string;
  ltp: number;
  change_percent: number;
  volume: number;
  volume_ratio: number;
  market_cap_rank: number;
  avg_price: number;
}

export interface SectorPerformance {
  name: string;
  change_percent: number;
  stocks_count: number;
  top_performers: string[];
  strength: string;
}

export interface StockTechnicals {
  symbol: string;
  ltp: number;
  indicators: {
    rsi: number | null;
    macd: {
      macd: number;
      signal: number;
      histogram: number;
    } | null;
    bollinger: {
      upper: number;
      middle: number;
      lower: number;
      percent_b: number;
      bandwidth: number;
    } | null;
    adx: {
      adx: number;
      plus_di: number;
      minus_di: number;
    } | null;
    volume: any;
  };
  swing_pattern: any;
  signal: string;
}

export interface SwingOpportunity {
  symbol: string;
  ltp: number;
  change_percent: number;
  signal: string;
  strength: number;
  patterns: string[];
  indicators: {
    rsi: number | null;
    adx: number | null;
    volume_spike: boolean;
  };
  volume: number;
  strategy_match: string;
}

export interface SentimentData {
  sentiment_score: number;
  sentiment: string;
  fear_greed_index: number;
  fear_greed_interpretation: string;
  components: {
    vix?: {
      level: number;
      interpretation: string;
      score: number;
    };
    pcr?: {
      value: number;
      interpretation: string;
      score: number;
    };
    advance_decline?: {
      ratio: number;
      advancing: number;
      declining: number;
      strength: string;
      score: number;
    };
    momentum?: {
      nifty_change_percent: number;
      state: string;
      score: number;
    };
  };
}

export const marketDashboardAPI = {
  // Top movers
  async getTopMovers(limit: number = 10, universe: string = 'NIFTY50') {
    return apiRequest<{
      gainers: TopMover[];
      losers: TopMover[];
      most_active: TopMover[];
    }>(`/market-dashboard/top-movers?limit=${limit}&universe=${universe}`);
  },

  // Market breadth
  async getMarketBreadth(universe: string = 'NIFTY50') {
    return apiRequest<MarketBreadth>(`/market-dashboard/market-breadth?universe=${universe}`);
  },

  // Heatmap data
  async getHeatmap(universe: string = 'NIFTY50') {
    return apiRequest<{ stocks: HeatmapStock[] }>(`/market-dashboard/heatmap?universe=${universe}`);
  },

  // Sector performance
  async getSectorPerformance() {
    return apiRequest<{ sectors: SectorPerformance[] }>('/market-dashboard/sector-performance');
  },

  // Stock technicals
  async getStockTechnicals(symbol: string) {
    return apiRequest<StockTechnicals>(`/market-dashboard/stock-technicals/${symbol}`);
  },
};

// Swing Scanner API
export const swingScannerAPI = {
  async scan(strategy: string = 'all', minScore: number = 50, universe: string = 'NIFTY50') {
    return apiRequest<{
      opportunities: SwingOpportunity[];
      total_scanned: number;
      matches_found: number;
      data_source?: string;
      timestamp: string;
    }>(`/swing-scanner/scan?strategy=${strategy}&min_score=${minScore}&universe=${universe}`);
  },

  async getStrategies() {
    return apiRequest<{
      strategies: Array<{
        id: string;
        name: string;
        description: string;
        criteria: string;
        ideal_for: string;
        risk_level: string;
      }>;
    }>('/swing-scanner/strategies');
  },
};

// Sentiment API
export const sentimentAPI = {
  async getOverallSentiment() {
    return apiRequest<SentimentData>('/sentiment/overall');
  },

  async getVIX() {
    return apiRequest<{
      current: number;
      change: number;
      change_percent: number;
      interpretation: string;
      regime: string;
      implications: string;
    }>('/sentiment/vix');
  },

  async getPCR() {
    return apiRequest<{
      pcr: number;
      interpretation: string;
      put_oi: number;
      call_oi: number;
      implications: string;
    }>('/sentiment/pcr');
  },
};
