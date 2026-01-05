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
  entry_time: string;
}

interface TradeStore {
  trades: Trade[];
  capital: number;
  dailyPnL: number;
  systemEnabled: boolean;
  
  setTrades: (trades: Trade[]) => void;
  addTrade: (trade: Trade) => void;
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
  setCapital: (capital) => set({ capital }),
  setDailyPnL: (dailyPnL) => set({ dailyPnL }),
  setSystemEnabled: (systemEnabled) => set({ systemEnabled }),
}));
