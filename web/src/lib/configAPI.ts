// Config API Client - Centralized configuration management
import axios from 'axios';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface MarketUniverse {
  universes: string[];
  default: string;
}

export interface UniverseSymbols { universe: string;
  symbols: string[];
  count: number;
}

export interface TradingStyle {
  id: string;
  name: string;
  timeframe: string;
}

export interface ScannerStrategy {
  id: string;
  name: string;
  description: string;
  criteria: string;
  ideal_for: string;
  timeframe: string;
  risk_level: string;
}

export interface SectorData {
  sectors: Record<string, string[]>;
  sector_names: string[];
}

export interface IndicatorDefaults {
  rsi: { period: number; overbought: number; oversold: number };
  macd: { fast: number; slow: number; signal: number };
  bollinger: { period: number; std_dev: number };
  adx: { period: number; trend_threshold: number };
  [key: string]: any;
}

export const configAPI = {
  // Market universes
  async getMarketUniverses() {
    const response = await api.get<MarketUniverse>('/config/market-universes');
    return response.data;
  },

  // Get symbols for a universe
  async getSymbols(universe: string = 'NIFTY50') {
    const response = await api.get<UniverseSymbols>(`/config/symbols/${universe}`);
    return response.data;
  },

  // Trading styles
  async getTradingStyles() {
    const response = await api.get<{ styles: TradingStyle[] }>('/config/trading-styles');
    return response.data;
  },

  // Scanner strategies
  async getScannerStrategies(tradingStyle?: string) {
    const url = tradingStyle 
      ? `/config/scanner-strategies?trading_style=${tradingStyle}`
      : '/config/scanner-strategies';
    const response = await api.get<{ strategies: ScannerStrategy[]; count: number }>(url);
    return response.data;
  },

  // Sectors
  async getSectors() {
    const response = await api.get<SectorData>('/config/sectors');
    return response.data;
  },

  // Indicator defaults
  async getIndicatorDefaults() {
    const response = await api.get<IndicatorDefaults>('/config/indicators');
    return response.data;
  },
};
