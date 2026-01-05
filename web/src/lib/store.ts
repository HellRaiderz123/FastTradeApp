import { create } from 'zustand';

export interface Trade {
  id: number;
  strategy: string;
  underlying: string;
  status: 'EXECUTED' | 'CLOSED' | 'CONFIRMED';
  entry_price: number;
  current_price: number;
  pnl: number;
  pnl_percent: number;
  tp: number;
  sl: number;
  entry_time: string;
  exit_time?: string;
}

export interface Signal {
  signal: string;
  confidence: number;
  bias: string;
  iv_regime: string;
}

interface TradeStore {
  trades: Trade[];
  capital: number;
  dailyPnL: number;
  systemEnabled: boolean;
  
  setTrades: (trades: Trade[]) => void;
  addTrade: (trade: Trade) => void;
  updateTrade: (id: number, trade: Partial<Trade>) => void;
  setCapital: (capital: number) => void;
  setDailyPnL: (pnl: number) => void;
  setSystemEnabled: (enabled: boolean) => void;
}

export const useTradeStore = create<TradeStore>((set) => ({
  trades: [],
  capital: 100000,
  dailyPnL: 0,
  systemEnabled: true,
  
  setTrades: (trades) => set({ trades }),
  addTrade: (trade) => set((state) => ({ trades: [...state.trades, trade] })),
  updateTrade: (id, updates) =>
    set((state) => ({
      trades: state.trades.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),
  setCapital: (capital) => set({ capital }),
  setDailyPnL: (dailyPnL) => set({ dailyPnL }),
  setSystemEnabled: (systemEnabled) => set({ systemEnabled }),
}));

interface SignalStore {
  signals: Signal[];
  lastSignal: Signal | null;
  
  setSignals: (signals: Signal[]) => void;
  setLastSignal: (signal: Signal) => void;
}

export const useSignalStore = create<SignalStore>((set) => ({
  signals: [],
  lastSignal: null,
  
  setSignals: (signals) => set({ signals }),
  setLastSignal: (signal) => set({ lastSignal: signal }),
}));
