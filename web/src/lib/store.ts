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

export interface AccountProfile {
  user_id: string;
  email: string;
  phone: string;
  capital: number;
  margins_available: number;
  margins_utilised: number;
  equity: number;
  net_worth: number;
}

interface TradeStore {
  trades: Trade[];
  capital: number;
  dailyPnL: number;
  systemEnabled: boolean;
  accountProfile: AccountProfile | null;
  loading: boolean;
  
  setTrades: (trades: Trade[]) => void;
  addTrade: (trade: Trade) => void;
  updateTrade: (id: number, trade: Partial<Trade>) => void;
  setCapital: (capital: number) => void;
  setDailyPnL: (pnl: number) => void;
  setSystemEnabled: (enabled: boolean) => void;
  setAccountProfile: (profile: AccountProfile | null) => void;
  setLoading: (loading: boolean) => void;
}

export const useTradeStore = create<TradeStore>((set) => ({
  trades: [],
  capital: 100000,
  dailyPnL: 0,
  systemEnabled: true,
  accountProfile: null,
  loading: false,
  
  setTrades: (trades) => set({ trades }),
  addTrade: (trade) => set((state) => ({ trades: [...state.trades, trade] })),
  updateTrade: (id, updates) =>
    set((state) => ({
      trades: state.trades.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),
  setCapital: (capital) => set({ capital }),
  setDailyPnL: (dailyPnL) => set({ dailyPnL }),
  setSystemEnabled: (systemEnabled) => set({ systemEnabled }),
  setAccountProfile: (accountProfile) => set({ accountProfile }),
  setLoading: (loading) => set({ loading }),
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
