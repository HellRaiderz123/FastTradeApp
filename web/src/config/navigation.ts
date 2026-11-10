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
  FileSearch,
  Filter,
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
  Sigma,
  Star,
  Target,
  TrendingUp,
  Wallet,
  Zap,
  Newspaper,
  ArrowUpDown,
  MonitorDot,
  Layers,
  FlaskConical,
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

export interface Workspace {
  id: string
  label: string
  icon: LucideIcon
  color: string          // tailwind text color for active state
  sectionIds: string[]   // which NAV_SECTIONS to show
}

export const NAV_SECTIONS: NavSection[] = [
  {
    id: 'options',
    label: 'Options',
    items: [
      { path: '/options', icon: Target, label: 'Options Chain' },
      { path: '/strategies', icon: Zap, label: 'Spread Strategies' },
      { path: '/strategy-pnl', icon: PieChart, label: 'Strategy P&L' },
      { path: '/positions', icon: Briefcase, label: 'Positions' },
      { path: '/auto-trader', icon: Bot, label: 'Auto Trader' },
      { path: '/watchlists', icon: Star, label: 'Watchlists' },
    ],
  },
  {
    id: 'options_ai',
    label: 'AI',
    items: [
      { path: '/ai-analysis', icon: BarChart3, label: 'AI Analysis' },
      { path: '/ai-assistant', icon: Bot, label: 'AI Assistant' },
      { path: '/quant-bot', icon: Activity, label: 'Quant Bot' },
    ],
  },
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
      { path: '/filing-analysis', icon: FileSearch, label: 'Filing Analysis' },
    ],
  },
  {
    id: 'research_ai',
    label: 'AI',
    items: [
      { path: '/ai-assistant', icon: Bot, label: 'AI Assistant' },
      { path: '/ai-analysis', icon: BarChart3, label: 'AI Analysis' },
      { path: '/ml', icon: Brain, label: 'ML Center' },
      { path: '/quant-bot', icon: Activity, label: 'Quant Bot' },
    ],
  },
  {
    id: 'system',
    label: 'System',
    items: [
      { path: '/finance', icon: Wallet, label: 'Finance' },
      { path: '/scheduled-jobs', icon: Activity, label: 'Scheduled Jobs' },
      { path: '/system-metrics', icon: MonitorDot, label: 'System Metrics' },
      { path: '/settings', icon: Settings, label: 'Settings' },
    ],
  },
  {
    id: 'system_ai',
    label: 'AI',
    items: [
      { path: '/ai-assistant', icon: Bot, label: 'AI Assistant' },
      { path: '/ai-analysis', icon: BarChart3, label: 'AI Analysis' },
    ],
  },
]

export const WORKSPACES: Workspace[] = [
  {
    id: 'options',
    label: 'Options',
    icon: Sigma,
    color: 'text-violet-400',
    sectionIds: ['options', 'options_ai'],
  },
  {
    id: 'research',
    label: 'Research',
    icon: FlaskConical,
    color: 'text-sky-400',
    sectionIds: ['market', 'intelligence', 'research_ai', 'analytics'],
  },
  {
    id: 'trading',
    label: 'Trading',
    icon: Layers,
    color: 'text-emerald-400',
    sectionIds: ['market', 'trading', 'analytics', 'system_ai'],
  },
  {
    id: 'system',
    label: 'System',
    icon: Settings,
    color: 'text-slate-400',
    sectionIds: ['system', 'system_ai'],
  },
]

export function isActiveRoute(pathname: string, path: string): boolean {
  if (path === '/') return pathname === '/'
  return pathname === path || pathname.startsWith(path + '/')
}
