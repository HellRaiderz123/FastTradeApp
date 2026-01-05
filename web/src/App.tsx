import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import Strategies from './pages/Strategies';
import Positions from './pages/Positions';
import Journal from './pages/Journal';
import Settings from './pages/Settings';
import { systemAPI } from './lib/api';
import { useTradeStore } from './lib/store';

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
    <Router>
      <div className="flex h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <Sidebar open={sidebarOpen} />
        
        <div className="flex-1 flex flex-col overflow-hidden">
          <Header 
            onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
            systemEnabled={systemEnabled}
            onSystemToggle={setSystemEnabled}
          />
          
          <main className="flex-1 overflow-auto p-6">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/strategies" element={<Strategies />} />
              <Route path="/positions" element={<Positions />} />
              <Route path="/journal" element={<Journal />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>
          </main>
        </div>
      </div>
    </Router>
  );
}

export default App;
