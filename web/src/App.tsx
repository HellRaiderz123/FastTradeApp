import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ProtectedRoute from './components/ProtectedRoute';
import Dashboard from './pages/Dashboard';
import Terminal from './pages/TerminalBloomberg';
import Screener from './pages/Screener';
import OptionsChain from './pages/OptionsChain';
import Strategies from './pages/Strategies';
import StrategyBuilder from './pages/StrategyBuilder';
import Backtest from './pages/Backtest';
import Positions from './pages/Positions';
import Journal from './pages/Journal';
import Settings from './pages/Settings';
import Heatmap from './pages/Heatmap';
import Login from './pages/Login';
import { systemAPI, journalAPI } from './lib/api';
import { useTradeStore } from './lib/store';
import FinanceTracker from './pages/FinanceTracker';
import Calendar from './pages/Calendar';
import MLCenter from './pages/MLCenter';
import AutoTrader from './pages/AutoTrader';
import MultiTimeframe from './pages/MultiTimeframe';
import BacktestComparison from './pages/BacktestComparison';
import TradeCostTracker from './pages/TradeCostTracker';
import CustomWatchlists from './pages/CustomWatchlists';
import CreateScanner from './pages/CreateScanner';
import BrokerReconciliation from './pages/BrokerReconciliation';
import StrategyPnL from './pages/StrategyPnL';
import StrategyMarketplace from './pages/StrategyMarketplace';
import AIAssistant from './pages/AIAssistant';
import AIAnalysis from './pages/AIAnalysis';
import SignalReconciliation from './pages/SignalReconciliation';
import CandleBackfill from './pages/CandleBackfill';
import { ToastProvider } from './components/Toast';
import { SignalAlertMonitor } from './components/SignalAlertMonitor';
import CommandPalette from './components/CommandPalette';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error?: Error }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error) { return { hasError: true, error }; }
  componentDidCatch(error: Error, info: any) { console.error('UI Error:', error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <div className="p-6 text-white">
          <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
          <p className="text-slate-300 mb-4">{this.state.error?.message}</p>
          <button onClick={() => this.setState({ hasError: false, error: undefined })} className="btn-secondary">Try again</button>
        </div>
      );
    }
    return this.props.children as React.ReactElement;
  }
}

// Inner component — must be inside Router so useNavigate works
function AppInner() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { systemEnabled, setSystemEnabled, darkMode } = useTradeStore();

  useKeyboardShortcuts({ onOpenPalette: () => setPaletteOpen(true) });

  useEffect(() => {
    if (!darkMode) {
      document.documentElement.classList.add('light-mode');
    } else {
      document.documentElement.classList.remove('light-mode');
    }
  }, [darkMode]);

  useEffect(() => {
    systemAPI.status()
      .then((r) => setSystemEnabled(r.data.trading_enabled))
      .catch(() => {});
  }, []);

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="*" element={
        <ProtectedRoute>
          <div className="flex h-screen terminal-shell">
            <Sidebar open={sidebarOpen} />
            <div className="flex-1 flex flex-col overflow-hidden">
              <Header
                onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
                systemEnabled={systemEnabled}
                onSystemToggle={setSystemEnabled}
              />
              <SignalAlertMonitor />
              <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
              <main className="flex-1 overflow-auto p-6">
                <Routes>
                  <Route path="/" element={<Terminal />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/screener" element={<Screener />} />
                  <Route path="/heatmap" element={<Heatmap />} />
                  <Route path="/options" element={<OptionsChain />} />
                  <Route path="/ml" element={<MLCenter />} />
                  <Route path="/ml-intelligence" element={<MLCenter />} />
                  <Route path="/strategies" element={<Strategies />} />
                  <Route path="/strategies/builder" element={<StrategyBuilder />} />
                  <Route path="/marketplace" element={<StrategyMarketplace />} />
                  <Route path="/create-scanner" element={<CreateScanner />} />
                  <Route path="/backfill-candles" element={<CandleBackfill />} />
                  <Route path="/backtest" element={<Backtest />} />
                  <Route path="/backtest-comparison" element={<BacktestComparison />} />
                  <Route path="/positions" element={<Positions />} />
                  <Route path="/reconciliation" element={<BrokerReconciliation />} />
                  <Route path="/strategy-pnl" element={<StrategyPnL />} />
                  <Route path="/journal" element={<Journal />} />
                  <Route path="/trade-costs" element={<TradeCostTracker />} />
                  <Route path="/auto-trader" element={<AutoTrader />} />
                  <Route path="/watchlists" element={<CustomWatchlists />} />
                  <Route path="/multi-timeframe" element={<MultiTimeframe />} />
                  <Route path="/calendar" element={<Calendar />} />
                  <Route path="/finance" element={<FinanceTracker />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/ai-assistant" element={<AIAssistant />} />
                  <Route path="/ai-analysis" element={<AIAnalysis />} />
                  <Route path="/signal-reconciliation" element={<SignalReconciliation />} />
                </Routes>
              </main>
            </div>
          </div>
        </ProtectedRoute>
      } />
    </Routes>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <Router>
          <AppInner />
        </Router>
      </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
