import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Menu, Power, LogOut, Sun, Moon, ExternalLink, ChevronDown, User } from 'lucide-react';
import { useTradeStore } from '../lib/store';
import { systemAPI, settingsAPI, authAPI, authTokenStore } from '../lib/api';
import { NotificationBell } from './NotificationBell';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

interface HeaderProps {
  onToggleSidebar: () => void;
  systemEnabled: boolean;
  onSystemToggle: (enabled: boolean) => void;
}

function getModeLabel(mode: string) {
  if (mode === 'LIVE') return 'Live';
  if (mode === 'DRY_RUN') return 'Dry Run';
  if (mode === 'PAPER_TRADING') return 'Paper';
  // legacy aliases
  if (mode === 'ZERODHA_LIVE') return 'Live';
  if (mode === 'ZERODHA_DRY_RUN') return 'Dry Run';
  return 'Paper';
}

function getModeVariant(mode: string): 'loss' | 'sell' | 'profit' {
  if (mode === 'LIVE' || mode === 'ZERODHA_LIVE') return 'loss';
  if (mode === 'DRY_RUN' || mode === 'ZERODHA_DRY_RUN') return 'sell';
  return 'profit';
}

class BellBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() { return { hasError: true }; }
  render() {
    if (this.state.hasError) return null;
    return this.props.children as React.ReactElement;
  }
}

const Header: React.FC<HeaderProps> = ({ onToggleSidebar, systemEnabled, onSystemToggle }) => {
  const navigate = useNavigate();
  const { darkMode, toggleDarkMode } = useTradeStore();
  const [executionMode, setExecutionMode] = useState('PAPER_TRADING');
  const [activeBroker, setActiveBroker] = useState('ZERODHA');
  const [supportedBrokers, setSupportedBrokers] = useState<string[]>(['ZERODHA', 'INDMONEY']);

  useEffect(() => {
    loadHeaderSettings();
    const handler = () => loadHeaderSettings();
    window.addEventListener('broker-settings-changed', handler);
    return () => window.removeEventListener('broker-settings-changed', handler);
  }, []);

  const loadHeaderSettings = async () => {
    try {
      const [modeRes, brokerRes] = await Promise.all([
        settingsAPI.getZerodhaSettings(),
        settingsAPI.getBrokerSettings(),
      ]);
      const modeData = modeRes.data || modeRes;
      setExecutionMode(modeData.execution_mode || 'PAPER_TRADING');
      const brokerData = brokerRes.data || brokerRes;
      setActiveBroker(brokerData.active_broker || 'ZERODHA');
      setSupportedBrokers(brokerData.supported_brokers || ['ZERODHA', 'INDMONEY']);
    } catch {
      // silent
    }
  };

  const handleBrokerChange = async (broker: string) => {
    try {
      await settingsAPI.setActiveBroker(broker);
      setActiveBroker(broker);
      window.dispatchEvent(new Event('broker-settings-changed'));
    } catch {
      // silent
    }
  };

  const handleSystemToggle = async () => {
    try {
      if (systemEnabled) await systemAPI.disable();
      else await systemAPI.enable();
      onSystemToggle(!systemEnabled);
    } catch {
      // silent
    }
  };

  const handleLogout = async () => {
    try { await authAPI.logout(); } catch { /* silent */ }
    authTokenStore.clear();
    navigate('/login');
  };

  return (
    <header className="sticky top-0 z-40 flex h-14 items-center border-b border-border bg-card backdrop-blur-sm px-4 gap-4">
      {/* Left: toggle + title */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={onToggleSidebar} title="Toggle Sidebar">
          <Menu className="h-4 w-4" />
        </Button>
        <span className="hidden font-semibold text-sm sm:inline-block text-foreground">FastTrade Pro</span>
      </div>

      {/* Right: controls */}
      <div className="ml-auto flex items-center gap-2">
        {/* Broker selector */}
        <div className="flex items-center gap-1.5">
          <span className="hidden text-xs text-muted-foreground sm:inline">Broker</span>
          <select
            value={activeBroker}
            onChange={(e) => handleBrokerChange(e.target.value)}
            className="h-7 rounded-md border border-border bg-background px-2 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
            title="Active Broker"
          >
            {supportedBrokers.map((b) => (
              <option key={b} value={b}>{b}</option>
            ))}
          </select>
        </div>

        {/* Trading mode badge */}
        <Badge variant={getModeVariant(executionMode)} className="hidden sm:flex">
          {getModeLabel(executionMode)}
        </Badge>

        {/* Theme toggle */}
        <Button variant="ghost" size="icon" onClick={toggleDarkMode} title={darkMode ? 'Light mode' : 'Dark mode'}>
          {darkMode ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        {/* API Docs */}
        <Button variant="ghost" size="icon" asChild title="API Documentation">
          <a href="/api/docs" target="_blank" rel="noopener noreferrer">
            <ExternalLink className="h-4 w-4" />
          </a>
        </Button>

        {/* System toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={handleSystemToggle}
          className={cn(
            'gap-1.5',
            systemEnabled
              ? 'text-green-400 hover:text-green-300 hover:bg-green-500/10'
              : 'text-red-400 hover:text-red-300 hover:bg-red-500/10'
          )}
        >
          <Power className="h-4 w-4" />
          <span className="hidden text-xs sm:inline">{systemEnabled ? 'ON' : 'OFF'}</span>
        </Button>

        {/* Notifications */}
        <BellBoundary>
          <NotificationBell />
        </BellBoundary>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="gap-2 pl-2">
              <img
                src="https://api.dicebear.com/7.x/avataaars/svg?seed=tarun"
                alt="User"
                className="h-7 w-7 rounded-full"
              />
              <span className="hidden text-sm font-medium sm:inline">Tarun</span>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuLabel className="flex items-center gap-2">
              <User className="h-3.5 w-3.5" />
              My Account
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
};

export default Header;
