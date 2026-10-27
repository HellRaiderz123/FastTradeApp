import React, { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import ProtectedRoute from './components/ProtectedRoute';
import { systemAPI } from './lib/api';
import { useTradeStore } from './lib/store';
import { SignalAlertMonitor } from './components/SignalAlertMonitor';
import CommandPalette from './components/CommandPalette';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { ToastProvider } from './components/Toast';

// Lazy-loaded pages — code splitting for faster initial load
const Terminal = lazy(() => import('./pages/TerminalBloomberg'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Screener = lazy(() => import('./pages/Screener'));
const Heatmap = lazy(() => import('./pages/Heatmap'));
const OptionsChain = lazy(() => import('./pages/OptionsChain'));
const Strategies = lazy(() => import('./pages/Strategies'));
const StrategyBuilder = lazy(() => import('./pages/StrategyBuilder'));
const Backtest = lazy(() => import('./pages/Backtest'));
const BacktestComparison = lazy(() => import('./pages/BacktestComparison'));
const Positions = lazy(() => import('./pages/Positions'));
const Journal = lazy(() => import('./pages/Journal'));
const Settings = lazy(() => import('./pages/Settings'));
const FinanceTracker = lazy(() => import('./pages/FinanceTracker'));
const Calendar = lazy(() => import('./pages/Calendar'));
const MLCenter = lazy(() => import('./pages/MLCenter'));
const AutoTrader = lazy(() => import('./pages/AutoTrader'));
const MultiTimeframe = lazy(() => import('./pages/MultiTimeframe'));
const TradeCostTracker = lazy(() => import('./pages/TradeCostTracker'));
const CustomWatchlists = lazy(() => import('./pages/CustomWatchlists'));
const CreateScanner = lazy(() => import('./pages/CreateScanner'));
const ScannerExecution = lazy(() => import('./pages/ScannerExecution'));
const BrokerReconciliation = lazy(() => import('./pages/BrokerReconciliation'));
const StrategyPnL = lazy(() => import('./pages/StrategyPnL'));
const StrategyMarketplace = lazy(() => import('./pages/StrategyMarketplace'));
const AIAssistant = lazy(() => import('./pages/AIAssistant'));
const AIAnalysis = lazy(() => import('./pages/AIAnalysis'));
const SignalReconciliation = lazy(() => import('./pages/SignalReconciliation'));
const CandleBackfill = lazy(() => import('./pages/CandleBackfill'));
const ScheduledJobs = lazy(() => import('./pages/ScheduledJobs'));
const ScalpTrading = lazy(() => import('./pages/ScalpTrading'));
const QuantBot = lazy(() => import('./pages/QuantBot'));
const FiiDii = lazy(() => import('./pages/FiiDii'));
const StockResearch = lazy(() => import('./pages/StockResearch'));
const Login = lazy(() => import('./pages/Login'));

// Page loader fallback
function PageLoader() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  );
}

// Error boundary
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error?: Error }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error) { return { hasError: true, error }; }
  componentDidCatch(error: Error, info: unknown) { console.error('UI Error:', error, info); }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-full flex-col items-center justify-center gap-4 p-6">
          <p className="text-lg font-semibold">Something went wrong</p>
          <p className="text-sm text-muted-foreground">{this.state.error?.message}</p>
          <button
            onClick={() => this.setState({ hasError: false, error: undefined })}
            className="btn-secondary"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children as React.ReactElement;
  }
}

// TanStack Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function AppInner() {
  const [sidebarOpen, setSidebarOpen] = React.useState(true);
  const [paletteOpen, setPaletteOpen] = React.useState(false);
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
      <Route
        path="/login"
        element={
          <Suspense fallback={<PageLoader />}>
            <Login />
          </Suspense>
        }
      />
      <Route
        path="*"
        element={
          <ProtectedRoute>
            <div className="flex h-screen terminal-shell">
              <Sidebar open={sidebarOpen} />
              <div className="flex flex-1 flex-col overflow-hidden">
                <Header
                  onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
                  systemEnabled={systemEnabled}
                  onSystemToggle={setSystemEnabled}
                />
                <SignalAlertMonitor />
                <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
                <main className="flex-1 overflow-auto p-6">
                  <Suspense fallback={<PageLoader />}>
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
                      <Route path="/scanner-execution" element={<ScannerExecution />} />
                      <Route path="/backfill-candles" element={<CandleBackfill />} />
                      <Route path="/backtest" element={<Backtest />} />
                      <Route path="/backtest-comparison" element={<BacktestComparison />} />
                      <Route path="/positions" element={<Positions />} />
                      <Route path="/reconciliation" element={<BrokerReconciliation />} />
                      <Route path="/strategy-pnl" element={<StrategyPnL />} />
                      <Route path="/journal" element={<Journal />} />
                      <Route path="/trade-costs" element={<TradeCostTracker />} />
                      <Route path="/auto-trader" element={<AutoTrader />} />
                      <Route path="/scalp-trading" element={<ScalpTrading />} />
                      <Route path="/watchlists" element={<CustomWatchlists />} />
                      <Route path="/multi-timeframe" element={<MultiTimeframe />} />
                      <Route path="/calendar" element={<Calendar />} />
                      <Route path="/finance" element={<FinanceTracker />} />
                      <Route path="/settings" element={<Settings />} />
                      <Route path="/ai-assistant" element={<AIAssistant />} />
                      <Route path="/ai-analysis" element={<AIAnalysis />} />
                      <Route path="/signal-reconciliation" element={<SignalReconciliation />} />
                      <Route path="/quant-bot" element={<QuantBot />} />
                      <Route path="/scheduled-jobs" element={<ScheduledJobs />} />
                      <Route path="/fii-dii" element={<FiiDii />} />
                      <Route path="/stock-research" element={<StockResearch />} />
                    </Routes>
                  </Suspense>
                </main>
              </div>
            </div>
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <ToastProvider>
          <Router>
            <AppInner />
          </Router>
          <Toaster
            position="top-right"
            toastOptions={{
              classNames: {
                toast: 'bg-card border border-border text-foreground',
                description: 'text-muted-foreground',
              },
            }}
          />
        </ToastProvider>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

export default App;
