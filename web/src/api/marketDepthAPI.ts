import axios from 'axios';

const DEPTH_API = axios.create({
  baseURL:(import.meta as any).env?.VITE_API_BASE ? `${(import.meta as any).env?.VITE_API_BASE}/market-depth` : '/api/market-depth',
  timeout: 15000,
});

export interface DepthLevel {
  price: number;
  quantity: number;
  orders: number;
  cumulative_qty: number;
}

export interface MarketDepth {
  symbol: string;
  timestamp: string;
  spot_price: number;
  best_bid: number;
  best_ask: number;
  spread: number;
  spread_percentage: number;
  bids: DepthLevel[];
  asks: DepthLevel[];
  total_bid_qty: number;
  total_ask_qty: number;
  total_bid_orders: number;
  total_ask_orders: number;
  imbalance: number;
  imbalance_direction: 'bullish' | 'bearish' | 'neutral';
  data_source?: 'live' | 'simulated';
}

export interface DepthSnapshot {
  symbol: string;
  snapshots: MarketDepth[];
  count: number;
}

export interface SpreadAnalysis {
  absolute: number;
  percentage: number;
  rating: 'tight' | 'normal' | 'wide';
}

export interface LiquidityAnalysis {
  total_bid_qty: number;
  total_ask_qty: number;
  avg_bid_size: number;
  avg_ask_size: number;
  max_bid_level: DepthLevel | null;
  max_ask_level: DepthLevel | null;
}

export interface OrderFlowAnalysis {
  imbalance: number;
  direction: 'bullish' | 'bearish' | 'neutral';
  signal: string;
  avg_bid_orders: number;
  avg_ask_orders: number;
}

export interface SupportResistance {
  support: number | null;
  resistance: number | null;
  strong_support: number | null;
  strong_resistance: number | null;
}

export interface DepthAnalysis {
  symbol: string;
  timestamp: string;
  spot_price: number;
  spread_analysis: SpreadAnalysis;
  liquidity: LiquidityAnalysis;
  order_flow: OrderFlowAnalysis;
  support_resistance: SupportResistance;
}

export const getMarketDepth = async (symbol: string): Promise<MarketDepth> => {
  const response = await DEPTH_API.get<MarketDepth>(`/depth/${symbol}`);
  return response.data;
};

export const getDepthSnapshot = async (
  symbol: string,
  interval: number = 5
): Promise<DepthSnapshot> => {
  const response = await DEPTH_API.get<DepthSnapshot>(`/depth/${symbol}/snapshot?interval=${interval}`);
  return response.data;
};

export const getDepthAnalysis = async (symbol: string): Promise<DepthAnalysis> => {
  const response = await DEPTH_API.get<DepthAnalysis>(`/depth/${symbol}/analysis`);
  return response.data;
};
