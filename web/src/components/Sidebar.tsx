import React, { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  TrendingUp, BarChart3, Briefcase, BookOpen, Settings, Zap, LineChart,
  Command, Search, Target, Grid, Calendar, Brain, Bot, Wallet, Clock,
  GitCompare, DollarSign, Star, Filter, RefreshCw, PieChart, ShoppingBag, Database,
  ChevronDown, Activity, Package, Gauge,
} from 'lucide-react';
import { settingsAPI } from '../lib/api';

interface SidebarProps {
  open: boolean;
}

interface MenuItem {
  path: string;
  icon: React.ElementType;
  label: string;
}

interface Section {
  id: string;
  label: string;
  items: MenuItem[];
}

const SECTIONS: Section[] = [
  {
    id: 'market',
    label: 'Market',
    items: [
      { path: '/', icon: Command, label: 'Terminal' },
      { path: '/dashboard', icon: TrendingUp, label: 'Dashboard' },
      { path: '/screener', icon: Search, label: 'Screener' },
      { path: '/heatmap', icon: Grid, label: 'Heatmap' },
      { path: '/watchlists', icon: Star, label: 'Watchlists' },
      { path: '/multi-timeframe', icon: Clock, label: 'Multi-Timeframe' },
      { path: '/options', icon: Target, label: 'Options Chain' },
      { path: '/calendar', icon: Calendar, label: 'Calendar' },
    ],
  },
  {
    id: 'trading',
    label: 'Trading',
    items: [
      { path: '/strategies', icon: Zap, label: 'Strategies' },
      { path: '/marketplace', icon: ShoppingBag, label: 'Marketplace' },
      { path: '/create-scanner', icon: Filter, label: 'Create Scanner' },
      { path: '/backfill-candles', icon: Database, label: 'Backfill Candles' },
      { path: '/auto-trader', icon: Bot, label: 'Auto Trader' },
      { path: '/scalp-trading', icon: Gauge, label: 'Scalp Trading' },
      { path: '/positions', icon: Briefcase, label: 'Positions' },
      { path: '/positions?tab=holdings', icon: Package, label: 'Stock Holdings' },
      { path: '/reconciliation', icon: RefreshCw, label: 'Reconciliation' },
    ],
  },
  {
    id: 'analytics',
    label: 'Analytics',
    items: [
      { path: '/strategy-pnl', icon: PieChart, label: 'Strategy P&L' },
      { path: '/journal', icon: BookOpen, label: 'Journal' },
      { path: '/backtest', icon: LineChart, label: 'Backtest' },
      { path: '/backtest-comparison', icon: GitCompare, label: 'Compare Backtests' },
      { path: '/trade-costs', icon: DollarSign, label: 'Trade Costs' },
    ],
  },
  {
    id: 'intelligence',
    label: 'Intelligence',
    items: [
      { path: '/ml', icon: Brain, label: 'ML Center' },
      { path: '/ai-assistant', icon: Bot, label: 'AI Assistant' },
      { path: '/ai-analysis', icon: BarChart3, label: 'AI Analysis' },
      { path: '/signal-reconciliation', icon: RefreshCw, label: 'Signal Reconciliation' },
    ],
  },
  {
    id: 'system',
    label: 'System',
    items: [
      { path: '/finance', icon: Wallet, label: 'Finance' },
      { path: '/scheduled-jobs', icon: Activity, label: 'Scheduled Jobs' },
      { path: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
];

const COLLAPSED_KEY = 'sidebar_collapsed_sections';

function loadCollapsed(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(COLLAPSED_KEY) || '{}');
  } catch {
    return {};
  }
}

const Sidebar: React.FC<SidebarProps> = ({ open }) => {
  const location = useLocation();
  const [executionMode, setExecutionMode] = useState('PAPER_TRADING');
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>(loadCollapsed);

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

  const toggleSection = (id: string) => {
    setCollapsed((prev) => {
      const next = { ...prev, [id]: !prev[id] };
      localStorage.setItem(COLLAPSED_KEY, JSON.stringify(next));
      return next;
    });
  };

  const getModeDisplay = () => {
    if (executionMode === 'ZERODHA_LIVE') return { text: 'Live Trading', color: 'text-red-400', bg: 'bg-red-500' };
    if (executionMode === 'ZERODHA_DRY_RUN') return { text: 'Dry Run', color: 'text-yellow-400', bg: 'bg-yellow-500' };
    return { text: 'Paper Trading', color: 'text-green-400', bg: 'bg-green-500' };
  };

  const modeDisplay = getModeDisplay();

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

      {/* Sections */}
      <nav className="flex-1 py-3 overflow-y-auto custom-scrollbar">
        {SECTIONS.map((section) => {
          const isCollapsed = !!collapsed[section.id];
          const hasActive = section.items.some((i) => i.path === location.pathname);

          return (
            <div key={section.id} className="mb-1">
              {/* Section header — only shown when sidebar is open */}
              {open && (
                <button
                  onClick={() => toggleSection(section.id)}
                  className={`w-full flex items-center justify-between px-4 py-2 text-xs font-semibold uppercase tracking-wider transition ${
                    hasActive ? 'text-blue-400' : 'text-slate-500 hover:text-slate-300'
                  }`}
                >
                  <span>{section.label}</span>
                  <ChevronDown
                    size={14}
                    className={`transition-transform ${isCollapsed ? '-rotate-90' : ''}`}
                  />
                </button>
              )}

              {/* Items */}
              {(!isCollapsed || !open) && (
                <div className={open ? 'px-2' : 'px-2'}>
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.path;
                    return (
                      <Link
                        key={item.path}
                        to={item.path}
                        title={!open ? item.label : undefined}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition mb-0.5 ${
                          isActive
                            ? 'bg-gradient-to-r from-green-500 to-blue-500 text-white'
                            : 'text-slate-400 hover:text-white hover:bg-slate-900'
                        }`}
                      >
                        <Icon className="w-5 h-5 flex-shrink-0" />
                        {open && <span className="font-medium text-sm">{item.label}</span>}
                      </Link>
                    );
                  })}
                </div>
              )}

              {/* Divider between sections */}
              {open && <div className="mx-4 mt-1 border-t border-slate-800/60" />}
            </div>
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
            <div className={`w-8 h-8 ${modeDisplay.bg} rounded-full mx-auto`} title={modeDisplay.text} />
          )}
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
