import {
  Activity,
  BarChart3,
  BookOpen,
  Bot,
  Brain,
  Briefcase,
  Calendar,
  Clock,
  Command,
  Database,
  DollarSign,
  Filter,
  Gauge,
  GitCompare,
  Grid,
  LineChart,
  type LucideIcon,
  Package,
  PieChart,
  RefreshCw,
  Search,
  Settings,
  ShoppingBag,
  Star,
  Target,
  TrendingUp,
  Wallet,
  Zap,
  Newspaper,
  ArrowUpDown,
} from 'lucide-react'

export interface NavItem {
  path: string
  label: string
  icon: LucideIcon
}

export interface NavSection {
  id: string
  label: string
  items: NavItem[]
}

export const NAV_SECTIONS: NavSection[] = [
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
      { path: '/quant-bot', icon: Activity, label: 'Quant Bot' },
      { path: '/signal-reconciliation', icon: RefreshCw, label: 'Signal Reconciliation' },
      { path: '/fii-dii', icon: ArrowUpDown, label: 'FII / DII' },
      { path: '/stock-research', icon: Newspaper, label: 'Stock Research' },
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
]

export function isActiveRoute(pathname: string, path: string): boolean {
  if (path === '/') return pathname === '/'
  return pathname === path || pathname.startsWith(path + '/')
}
