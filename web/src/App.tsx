import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
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
import { systemAPI } from './lib/api';
import { useTradeStore } from './lib/store';
import FinanceTracker from './pages/FinanceTracker';
import Calendar from './pages/Calendar';
import MLCenter from './pages/MLCenter';

// Simple Error Boundary to avoid white screen and show errors
class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; error?: Error }>{
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }
  componentDidCatch(error: Error, info: any) {
    console.error('UI Error:', error, info);
  }
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

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { systemEnabled, setSystemEnabled } = useTradeStore();

  useEffect(() => {
    checkSystemStatus();
  }, []);

  const checkSystemStatus = async () => {
    try {
      const response = await systemAPI.status();
      setSystemEnabled(response.data.trading_enabled);
    } catch (error) {
      console.error('Failed to fetch system status:', error);
    }
  };

  return (
    <ErrorBoundary>
      <Router>
        <div className="flex h-screen terminal-shell">
          <Sidebar open={sidebarOpen} />
          
          <div className="flex-1 flex flex-col overflow-hidden">
            <Header 
              onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
              systemEnabled={systemEnabled}
              onSystemToggle={setSystemEnabled}
            />
            
            <main className="flex-1 overflow-auto p-6">
              <Routes>
                <Route path="/" element={<Terminal />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/screener" element={<Screener />} />
                <Route path="/heatmap" element={<Heatmap />} />
                <Route path="/options" element={<OptionsChain />} />
                <Route path="/ml" element={<MLCenter />} />
                <Route path="/strategies" element={<Strategies />} />
                <Route path="/strategies/builder" element={<StrategyBuilder />} />
                <Route path="/backtest" element={<Backtest />} />
                <Route path="/positions" element={<Positions />} />
                <Route path="/journal" element={<Journal />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/finance" element={<FinanceTracker />} />
                <Route path="/calendar" element={<Calendar />} />
              </Routes>
            </main>
          </div>
        </div>
      </Router>
    </ErrorBoundary>
  );
}

export default App;
