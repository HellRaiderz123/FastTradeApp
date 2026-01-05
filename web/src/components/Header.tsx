import React from 'react';
import { Menu, Bell, Settings, Power } from 'lucide-react';
import { useTradeStore } from '../lib/store';
import { systemAPI } from '../lib/api';

interface HeaderProps {
  onToggleSidebar: () => void;
  systemEnabled: boolean;
  onSystemToggle: (enabled: boolean) => void;
}

const Header: React.FC<HeaderProps> = ({ onToggleSidebar, systemEnabled, onSystemToggle }) => {
  const handleSystemToggle = async () => {
    try {
      if (systemEnabled) {
        await systemAPI.disable();
      } else {
        await systemAPI.enable();
      }
      onSystemToggle(!systemEnabled);
    } catch (error) {
      console.error('Failed to toggle system:', error);
    }
  };

  return (
    <header className="bg-slate-950 border-b border-slate-800 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <button onClick={onToggleSidebar} className="text-slate-400 hover:text-white">
          <Menu className="w-6 h-6" />
        </button>
        <h2 className="text-xl font-semibold text-white">FastTrade Pro</h2>
      </div>

      <div className="flex items-center gap-6">
        {/* System Status */}
        <button
          onClick={handleSystemToggle}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition ${
            systemEnabled
              ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30'
              : 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
          }`}
        >
          <Power className="w-4 h-4" />
          <span className="text-sm">{systemEnabled ? 'Trading ON' : 'Trading OFF'}</span>
        </button>

        {/* Notifications */}
        <button className="relative text-slate-400 hover:text-white transition">
          <Bell className="w-6 h-6" />
          <span className="absolute top-0 right-0 w-2 h-2 bg-red-500 rounded-full"></span>
        </button>

        {/* User Menu */}
        <div className="flex items-center gap-3 pl-6 border-l border-slate-800">
          <div className="text-right">
            <p className="text-sm font-medium text-white">Tarun</p>
            <p className="text-xs text-slate-400">Paper Trading</p>
          </div>
          <img
            src="https://api.dicebear.com/7.x/avataaars/svg?seed=tarun"
            alt="User"
            className="w-8 h-8 rounded-full"
          />
        </div>
      </div>
    </header>
  );
};

export default Header;
