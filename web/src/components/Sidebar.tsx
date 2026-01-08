import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Menu, X, TrendingUp, BarChart3, Briefcase, BookOpen, Settings, Zap, LineChart } from 'lucide-react';
import { settingsAPI } from '../lib/api';

interface SidebarProps {
  open: boolean;
}

const Sidebar: React.FC<SidebarProps> = ({ open }) => {
  const location = useLocation();
  const [executionMode, setExecutionMode] = useState('PAPER_TRADING');

  useEffect(() => {
    loadExecutionMode();
    const interval = setInterval(loadExecutionMode, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadExecutionMode = async () => {
    try {
      const response = await settingsAPI.getZerodhaSettings();
      const data = response.data || response;
      setExecutionMode(data.execution_mode || 'PAPER_TRADING');
    } catch (error) {
      console.error('Error loading execution mode:', error);
    }
  };

  const getModeDisplay = () => {
    if (executionMode === 'ZERODHA_LIVE') return { text: 'Live Trading', color: 'text-red-400', bg: 'bg-red-500' };
    if (executionMode === 'ZERODHA_DRY_RUN') return { text: 'Dry Run', color: 'text-yellow-400', bg: 'bg-yellow-500' };
    return { text: 'Paper Trading', color: 'text-green-400', bg: 'bg-green-500' };
  };

  const modeDisplay = getModeDisplay();

  const menuItems = [
    { path: '/', icon: TrendingUp, label: 'Dashboard' },
    { path: '/strategies', icon: Zap, label: 'Strategies' },
    { path: '/backtest', icon: LineChart, label: 'Backtest' },
    { path: '/positions', icon: Briefcase, label: 'Positions' },
    { path: '/journal', icon: BookOpen, label: 'Journal' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <aside
      className={`${
        open ? 'w-64' : 'w-20'
      } bg-slate-950 border-r border-slate-800 transition-all duration-300 flex flex-col`}
    >
      {/* Logo */}
      <div className="p-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-gradient-to-br from-green-400 to-blue-500 rounded-lg flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          {open && (
            <div>
              <h1 className="font-bold text-lg gradient-text">FastTrade</h1>
              <p className="text-xs text-slate-400">Algo Trading</p>
            </div>
          )}
        </div>
      </div>

      {/* Menu Items */}
      <nav className="flex-1 p-4 space-y-2">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-4 px-4 py-3 rounded-lg transition ${
                isActive
                  ? 'bg-gradient-to-r from-green-500 to-blue-500 text-white'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {open && <span className="font-medium">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-800">
        <div className="card-glass p-4 text-center">
          {open ? (
            <div>
              <p className="text-xs text-slate-400 mb-2">{modeDisplay.text}</p>
              <p className={`text-sm font-bold ${modeDisplay.color}`}>Live & Ready</p>
            </div>
          ) : (
            <div className={`w-8 h-8 ${modeDisplay.bg} rounded-full mx-auto`}></div>
          )}
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
