import axios from 'axios';
import { authTokenStore } from '../lib/api';

const FUND_API = axios.create({
  baseURL: (import.meta as any).env?.VITE_API_BASE ? `${(import.meta as any).env?.VITE_API_BASE}/fundamentals` : '/api/fundamentals',
});
FUND_API.interceptors.request.use((config) => {
  const token = authTokenStore.get();
  if (token) config.headers['Authorization'] = `Bearer ${token}`;
  return config;
});

export interface PeerRow {
  'S.No.': number;
  Company: string;
  'CMP  Rs.': number;
  'P/E': number | null;
  'Mar Cap  Rs.Cr.': number | null;
  'Div Yld  %': number | null;
  'NP Qtr  Rs.Cr.': number | null;
  'Qtr Profit Var  %': number | null;
  'Sales Qtr  Rs.Cr.': number | null;
  'Qtr Sales Var  %': number | null;
  'ROCE  %': number | null;
}

export interface FundamentalsData {
  symbol: string;
  company_name: string | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  roe: number | null;
  roce: number | null;
  market_cap: number | null;
  current_price: number | null;
  book_value: number | null;
  dividend_yield: number | null;
  face_value: number | null;
  high_low_52w: string | null;
  week52_high: number | null;
  week52_low: number | null;
  about: string | null;
  industry: string | null;
  sector: string | null;
  peer_comparison: PeerRow[] | null;
  opm_pct: number | null;
  npm_pct: number | null;
  eps: number | null;
  debt_to_equity: number | null;
  key_points: string | null;
  shareholding_quarterly: Array<Record<string, string>> | null;
  annual_reports: Array<{ title: string; url: string; year: string }> | null;
  credit_ratings: Array<{ title: string; url: string; detail: string }> | null;
  quarterly_results: Array<Record<string, string | number | null>> | null;
  pnl_annual: Array<Record<string, string | number | null>> | null;
  cached_at: string | null;
  from_cache: boolean;
  cache_ttl_days: number;
}

export const fundamentalsAPI = {
  get: (symbol: string) => FUND_API.get<FundamentalsData>(`/${symbol}`),
  refresh: (symbol: string) => FUND_API.post<FundamentalsData>(`/${symbol}/refresh`),
};
