import axios from 'axios';
import { authTokenStore } from '../lib/api';

const QUANT_API = axios.create({
  baseURL: (import.meta as any).env?.VITE_API_BASE ? `${(import.meta as any).env?.VITE_API_BASE}/api/quant` : '/api/quant',
  timeout: 30000,
});

QUANT_API.interceptors.request.use((config) => {
  const token = authTokenStore.get();
  if (token) config.headers['Authorization'] = `Bearer ${token}`;
  return config;
});

// ── Types ────────────────────────────────────────────────────────────────────

export interface CashQuantReport {
  symbol: string;
  timestamp: string;
  // ORB
  orb_high: number;
  orb_low: number;
  orb_breakout: 'BULLISH' | 'BEARISH' | 'NONE';
  // RVOL
  rvol: number;
  rvol_signal: 'HIGH' | 'LOW' | 'NORMAL';
  // VWAP
  vwap: number;
  vwap_upper_1sd: number;
  vwap_lower_1sd: number;
  vwap_upper_2sd: number;
  vwap_lower_2sd: number;
  price_vs_vwap: 'ABOVE' | 'BELOW' | 'AT_VWAP';
  // Relative Strength
  rs_vs_nifty_5d: number;
  rs_vs_sector_5d: number;
  // Regime
  hurst_exponent: number;
  regime: 'TRENDING' | 'MEAN_REVERTING' | 'RANDOM';
  zscore_20: number;
  bb_width_percentile: number;
  // ATR
  atr_14: number;
  suggested_stop_loss: number;
  position_size_lots: number;
  // Delivery
  delivery_pct: number;
  institutional_accumulation: boolean;
}

export interface OptionsQuantReport {
  underlying: string;
  spot: number;
  timestamp: string;
  // ATM
  atm_strike: number;
  // Greeks
  atm_ce_delta: number;
  atm_ce_gamma: number;
  atm_ce_theta: number;
  atm_ce_vega: number;
  atm_pe_delta: number;
  atm_pe_gamma: number;
  atm_pe_theta: number;
  atm_pe_vega: number;
  // IV
  atm_iv: number;
  iv_percentile: number;
  iv_rank: number;
  // OI
  pcr_oi: number;
  pcr_change_oi: number;
  max_pain: number;
  call_wall: number;
  put_wall: number;
  // GEX
  net_gex: number;
  gex_regime: 'POSITIVE_GEX' | 'NEGATIVE_GEX' | 'NEUTRAL';
  // Recommendation
  recommended_structure: string;
  structure_rationale: string;
}

export interface RiskCheckResult {
  symbol: string;
  allowed: boolean;
  size_multiplier: number;
  warnings: string[];
  blocks: string[];
  current_vix: number | null;
}

// ── API Client ───────────────────────────────────────────────────────────────

export const quantAPI = {
  // Get cash equity quant report
  getCashReport: (symbol: string) =>
    QUANT_API.get<CashQuantReport>(`/cash/${symbol}`),

  // Get options quant report
  getOptionsReport: (symbol: string, expiry?: string) =>
    QUANT_API.get<OptionsQuantReport>(`/options/${symbol}`, {
      params: expiry ? { expiry } : undefined,
    }),

  // Check trade risk
  checkRisk: (symbol: string, delta: number = 0, isIntraday: boolean = true) =>
    QUANT_API.get<RiskCheckResult>('/risk-check', {
      params: { symbol, delta, is_intraday: isIntraday },
    }),
};
