import React, { useEffect, useState } from 'react';
import { Menu, Power, Bell, LogOut, ChevronDown } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTradeStore } from '../lib/store';
import { systemAPI, settingsAPI, authAPI, authTokenStore } from '../lib/api';
import { NotificationBell } from './NotificationBell';

interface HeaderProps {
  onToggleSidebar: () => void;
  systemEnabled: boolean;
  onSystemToggle: (enabled: boolean) => void;
}

const Header: React.FC<HeaderProps> = ({ onToggleSidebar, systemEnabled, onSystemToggle }) => {
  const navigate = useNavigate();
  const [executionMode, setExecutionMode] = useState('PAPER_TRADING');
  const [activeBroker, setActiveBroker] = useState('ZERODHA');
  const [supportedBrokers, setSupportedBrokers] = useState<string[]>(['ZERODHA', 'INDMONEY']);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    loadHeaderSettings();
    const interval = setInterval(loadHeaderSettings, 5000);
    return () => clearInterval(interval);
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (userMenuOpen && !target.closest('.user-menu-container')) {
        setUserMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [userMenuOpen]);

  const loadHeaderSettings = async () => {
    try {
      const [modeResponse, brokerResponse] = await Promise.all([
        settingsAPI.getZerodhaSettings(),
        settingsAPI.getBrokerSettings(),
      ]);

      const modeData = modeResponse.data || modeResponse;
      setExecutionMode(modeData.execution_mode || 'PAPER_TRADING');

      const brokerData = brokerResponse.data || brokerResponse;
      setActiveBroker(brokerData.active_broker || 'ZERODHA');
      setSupportedBrokers(brokerData.supported_brokers || ['ZERODHA', 'INDMONEY']);
    } catch (error) {
      console.error('Error loading header settings:', error);
    }
  };

  const handleBrokerChange = async (broker: string) => {
    try {
      await settingsAPI.setActiveBroker(broker);
      setActiveBroker(broker);
    } catch (error) {
      console.error('Failed to set active broker:', error);
    }
  };

  const getModeDisplay = () => {
    if (executionMode === 'ZERODHA_LIVE') return 'Live Trading';
    if (executionMode === 'ZERODHA_DRY_RUN') return 'Dry Run';
    return 'Paper Trading';
  };
  class BellBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }>{
    constructor(props: { children: React.ReactNode }) {
      super(props);
      this.state = { hasError: false };
    }
    static getDerivedStateFromError() { return { hasError: true }; }
    componentDidCatch(error: any, info: any) { console.error('NotificationBell error:', error, info); }
    render() {
      if (this.state.hasError) {
        return (
          <button className="relative text-slate-400" title="Notifications unavailable">
            <Bell className="w-6 h-6" />
          </button>
        );
      }
      return this.props.children as React.ReactElement;
    }
  }
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

  const handleLogout = async () => {
    try {
      await authAPI.logout();
    } catch (error) {
      console.error('Logout API call failed:', error);
    }
    
    // Clear token and redirect to login
    authTokenStore.clear();
    navigate('/login');
  };

  return (
    <header className="bg-slate-950 border-b border-slate-800 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <button 
          onClick={onToggleSidebar} 
          className="text-slate-400 hover:text-white"
          title="Toggle Sidebar"
        >
          <Menu className="w-6 h-6" />
        </button>
        <h2 className="text-xl font-semibold text-white">FastTrade Pro</h2>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="text-xs uppercase tracking-wide text-slate-400">Broker</span>
          <select
            value={activeBroker}
            onChange={(e) => handleBrokerChange(e.target.value)}
            className="bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
            title="Active Broker"
          >
            {supportedBrokers.map((broker) => (
              <option key={broker} value={broker}>{broker}</option>
            ))}
          </select>
        </div>

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
        <BellBoundary>
          <NotificationBell />
        </BellBoundary>

        {/* User Menu */}
        <div className="relative user-menu-container">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-3 pl-6 border-l border-slate-800 hover:opacity-80 transition"
          >
            <div className="text-right">
              <p className="text-sm font-medium text-white">Tarun</p>
              <p className="text-xs text-slate-400">{getModeDisplay()}</p>
            </div>
            <img
              src="https://api.dicebear.com/7.x/avataaars/svg?seed=tarun"
              alt="User"
              className="w-8 h-8 rounded-full"
            />
            <ChevronDown className="w-4 h-4 text-slate-400" />
          </button>

          {/* Dropdown Menu */}
          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 bg-slate-900 border border-slate-800 rounded-lg shadow-xl z-50">
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2 px-4 py-3 text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition"
              >
                <LogOut className="w-4 h-4" />
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
