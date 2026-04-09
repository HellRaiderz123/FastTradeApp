import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Plus, Trash2, Play, Save, ChevronRight, ChevronDown,
  Zap, Filter, Star, Search, MoreVertical, Activity,
  TrendingUp, TrendingDown, Settings2, Eye, Download,
  AlertTriangle, CheckCircle, XCircle, Loader2, ArrowRight,
  BarChart3, Calendar, Sparkles
} from 'lucide-react';
import { useToast } from '../components/Toast';
import api, { tradeCostAPI } from '../lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

interface ConditionParam {
  name: string;
  type: string;
  default: any;
  options?: string[];
}

interface IndicatorMeta {
  id: string;
  name: string;
  description: string;
  params: ConditionParam[];
  icon: string;
}

interface Condition {
  indicator: string;
  params: Record<string, any>;
  comparator: string;
  value: string;
}

interface ExitConfig {
  sl_pct: number;
  tp_pct: number;
  tsl_pct: number;
  exit_mode: string;
  require_htf_confirm?: boolean;
  htf_timeframe?: string | null;
  use_atr_sizing?: boolean;
  atr_period?: number;
  atr_multiplier?: number;
  risk_per_trade_pct?: number;
}

interface Strategy {
  id: number;
  name: string;
  description: string;
  strategy_type: string;
  direction: string;
  timeframe: string;
  instruments: string[];
  universe: string;
  entry_conditions: Condition[];
  exit_config: ExitConfig;
  is_active: boolean;
  created_at: string;
  last_scan?: string;
  last_signal_count?: number;
  auto_scan_enabled?: boolean;
  auto_amount?: number;
  last_backtest_result?: BacktestResult;
  last_backtest_at?: string;
}

interface PrebuiltStrategy {
  key: string;
  name: string;
  description: string;
  strategy_type: string;
  direction: string;
  timeframe: string;
  conditions_count: number;
  entry_conditions: Condition[];
  exit_config: ExitConfig;
}

interface ScanSignal {
  symbol: string;
  ltp: number;
  change_percent: number;
  indicators: Record<string, number>;
  conditions_met: number;
  htf_confirmed?: boolean;
  htf_timeframe?: string | null;
  atr?: number | null;
  suggested_quantity?: number;
  capital_used?: number;
  position_sizing?: string;
}

interface ScanResult {
  strategy_id: number;
  strategy_name: string;
  direction: string;
  signals: ScanSignal[];
  total_scanned: number;
  matches_found: number;
  execution_mode: string;
  exit_config: ExitConfig;
}

interface BacktestTrade {
  symbol: string;
  entry_date: string;
  exit_date: string;
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
  exit_reason: string;
  holding_bars: number;
}

interface BacktestSymbolResult {
  symbol: string;
  total_trades: number;
  win_rate: number;
  total_pnl_pct: number;
  avg_pnl_pct: number;
  max_win_pct: number;
  max_loss_pct: number;
  avg_holding_bars: number;
}

interface BacktestSummary {
  total_trades: number;
  winners: number;
  losers: number;
  win_rate: number;
  total_return_pct: number;
  annual_return_pct: number;
  max_drawdown_pct: number;
  profit_factor: number;
  sharpe_ratio: number;
  avg_pnl_pct: number;
  avg_win_pct: number;
  avg_loss_pct: number;
  max_win_pct: number;
  max_loss_pct: number;
  symbols_traded: number;
  symbols_scanned: number;
}

interface BacktestResult {
  strategy_id: number;
  strategy_name: string;
  direction: string;
  universe: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_capital: number;
  summary: BacktestSummary;
  equity_curve: { date: string; equity: number; symbol?: string; pnl_pct?: number }[];
  per_symbol: BacktestSymbolResult[];
  all_trades: BacktestTrade[];
}

interface BrokerageConfig {
  equity_delivery_brokerage_pct: number;
  equity_delivery_brokerage_flat: number;
  equity_intraday_brokerage_pct: number;
  equity_intraday_brokerage_cap: number;
  fno_brokerage_flat: number;
  stt_equity_delivery: number;
  stt_equity_intraday: number;
  stt_fno_options: number;
  stt_fno_futures: number;
  nse_equity_charge: number;
  nse_fno_charge: number;
  gst_pct: number;
  sebi_charges_per_crore: number;
  stamp_duty_pct: number;
  stamp_duty_cap: number;
}

// ── Constants ──────────────────────────────────────────────────────────────

const COMPARATORS = [
  { id: 'crosses_above', label: 'crosses above' },
  { id: 'crosses_below', label: 'crosses below' },
  { id: 'higher_than', label: 'higher than' },
  { id: 'lower_than', label: 'lower than' },
];

const STRATEGY_TYPES = ['Equity Swing', 'Equity Intraday', 'Options Buying', 'Options Selling'];
const TIMEFRAMES = ['1 Min', '5 Min', '15 Min', '1 Hour', 'Day'];
const HTF_TIMEFRAME_OPTIONS = ['Auto', '5 Min', '15 Min', '1 Hour', 'Day'];
const DEFAULT_EXIT_CONFIG: ExitConfig = {
  sl_pct: 5,
  tp_pct: 10,
  tsl_pct: 0,
  exit_mode: 'percentage',
  require_htf_confirm: false,
  htf_timeframe: 'Auto',
  use_atr_sizing: false,
  atr_period: 14,
  atr_multiplier: 1.5,
  risk_per_trade_pct: 1,
};

const TYPE_COLORS: Record<string, string> = {
  'Equity Swing': 'bg-blue-500/20 text-blue-300 border-blue-500/40',
  'Equity Intraday': 'bg-purple-500/20 text-purple-300 border-purple-500/40',
  'Options Buying': 'bg-green-500/20 text-green-300 border-green-500/40',
  'Options Selling': 'bg-orange-500/20 text-orange-300 border-orange-500/40',
};

const LAST_SELECTED_SCANNER_STRATEGY_KEY = 'scanner:lastSelectedStrategyId';
const BACKTEST_POSITION_SIZE_PCT = 10;

const formatNumber = (value: unknown, fallback = '0') => {
  const n = Number(value);
  return Number.isFinite(n) ? n.toLocaleString() : fallback;
};

const formatCurrency = (value: unknown, fallback = '₹0') => {
  const n = Number(value);
  return Number.isFinite(n) ? `₹${n.toLocaleString()}` : fallback;
};

const DEFAULT_ZERODHA_CONFIG: BrokerageConfig = {
  equity_delivery_brokerage_pct: 0,
  equity_delivery_brokerage_flat: 0,
  equity_intraday_brokerage_pct: 0.03,
  equity_intraday_brokerage_cap: 20,
  fno_brokerage_flat: 20,
  stt_equity_delivery: 0.1,
  stt_equity_intraday: 0.025,
  stt_fno_options: 0.0625,
  stt_fno_futures: 0.0125,
  nse_equity_charge: 0.00297,
  nse_fno_charge: 0.00173,
  gst_pct: 18,
  sebi_charges_per_crore: 10,
  stamp_duty_pct: 0.003,
  stamp_duty_cap: 300,
};

// ── Component ──────────────────────────────────────────────────────────────

const CreateScanner: React.FC = () => {
  const { showToast } = useToast();

  // Strategy list
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [prebuiltStrategies, setPrebuiltStrategies] = useState<PrebuiltStrategy[]>([]);
  const [indicators, setIndicators] = useState<IndicatorMeta[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filterType, setFilterType] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);

  // Editor state
  const [editing, setEditing] = useState(false);
  const [editorName, setEditorName] = useState('');
  const [editorDescription, setEditorDescription] = useState('');
  const [editorType, setEditorType] = useState('Equity Swing');
  const [editorDirection, setEditorDirection] = useState<'BUY' | 'SELL'>('BUY');
  const [editorTimeframe, setEditorTimeframe] = useState('1 Hour');
  const [editorUniverse, setEditorUniverse] = useState('NIFTY50');
  const [editorConditions, setEditorConditions] = useState<Condition[]>([]);
  const [editorExit, setEditorExit] = useState<ExitConfig>(DEFAULT_EXIT_CONFIG);
  const [saving, setSaving] = useState(false);

  // Scan state
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [scanning, setScanning] = useState(false);

  // Execution state
  const [executing, setExecuting] = useState<string | null>(null);

  // Tab
  const [showPrebuilt, setShowPrebuilt] = useState(false);

  // Backtest state
  const [backtestResult, setBacktestResult] = useState<BacktestResult | null>(null);
  const [backtesting, setBacktesting] = useState(false);
  const [applyZerodhaCharges, setApplyZerodhaCharges] = useState(false);
  const [brokerageConfig, setBrokerageConfig] = useState<BrokerageConfig>(DEFAULT_ZERODHA_CONFIG);
  const [loadingBrokerageConfig, setLoadingBrokerageConfig] = useState(false);
  const [btStartDate, setBtStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [btEndDate, setBtEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [btTab, setBtTab] = useState<'summary' | 'symbols' | 'trades'>('summary');
  const [showBacktestPanel, setShowBacktestPanel] = useState(false);
  const [candleRange, setCandleRange] = useState<{
    min_date: string | null; max_date: string | null;
    total_rows: number; symbols_with_data: number;
    symbols_in_universe: number; zerodha_max_days: number;
  } | null>(null);

  // Auto-scan state
  const [editorAutoScan, setEditorAutoScan] = useState(false);
  const [editorAutoQty, setEditorAutoQty] = useState(10000);
  const [togglingAutoScan, setTogglingAutoScan] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  const [restoredSelection, setRestoredSelection] = useState(false);

  // LLM explainer state
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);

  const explainStrategy = useCallback(async () => {
    if (!selectedId) return;
    setExplaining(true);
    setExplanation(null);
    try {
      const res = await api.get(`/condition-scanner/strategies/${selectedId}/explain`);
      setExplanation(res.data.explanation || null);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'LLM not available — set LLM_API_KEY in .env';
      setExplanation(`⚠️ ${msg}`);
    } finally {
      setExplaining(false);
    }
  }, [selectedId]);

  // ── Data loading ───────────────────────────────────────────────────────

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [stratRes, prebuiltRes, indRes] = await Promise.all([
        api.get('/condition-scanner/strategies'),
        api.get('/condition-scanner/prebuilt'),
        api.get('/condition-scanner/indicators'),
      ]);
      setStrategies(stratRes.data.strategies || []);
      setPrebuiltStrategies(prebuiltRes.data.strategies || []);
      setIndicators(indRes.data.indicators || []);
    } catch (err) {
      console.error('Failed to load scanner data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Select a strategy ─────────────────────────────────────────────────

  const selectStrategy = useCallback((strategy: Strategy) => {
    if (!strategy) return;
    setSelectedId(strategy.id);
    localStorage.setItem(LAST_SELECTED_SCANNER_STRATEGY_KEY, String(strategy.id));
    setEditorName(strategy.name);
    setEditorDescription(strategy.description || '');
    setEditorType(strategy.strategy_type || 'Equity Swing');
    setEditorDirection((strategy.direction as 'BUY' | 'SELL') || 'BUY');
    setEditorTimeframe(strategy.timeframe || '1 Hour');
    setEditorUniverse(strategy.universe || 'NIFTY50');
    setEditorConditions([...(strategy.entry_conditions || [])]);
    setEditorExit({ ...DEFAULT_EXIT_CONFIG, ...(strategy.exit_config || {}) });
    setEditorAutoScan(strategy.auto_scan_enabled || false);
    setEditorAutoQty(strategy.auto_amount || 10000);
    setEditing(true);
    setScanResult(null);
    setExplanation(null);

    if (strategy.last_backtest_result?.summary) {
      setBacktestResult(strategy.last_backtest_result);
      setShowBacktestPanel(true);
      if (strategy.last_backtest_result.start_date) {
        setBtStartDate(strategy.last_backtest_result.start_date);
      }
      if (strategy.last_backtest_result.end_date) {
        setBtEndDate(strategy.last_backtest_result.end_date);
      }
    } else {
      setBacktestResult(null);
      setShowBacktestPanel(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  useEffect(() => {
    if (restoredSelection || selectedId !== null || strategies.length === 0) return;

    const raw = localStorage.getItem(LAST_SELECTED_SCANNER_STRATEGY_KEY);
    if (!raw) {
      setRestoredSelection(true);
      return;
    }

    const id = Number(raw);
    if (!Number.isFinite(id)) {
      localStorage.removeItem(LAST_SELECTED_SCANNER_STRATEGY_KEY);
      setRestoredSelection(true);
      return;
    }

    const strategy = strategies.find(s => s.id === id);
    if (strategy) {
      selectStrategy(strategy);
    }
    setRestoredSelection(true);
  }, [restoredSelection, selectedId, strategies, selectStrategy]);

  // ── Select a strategy ─────────────────────────────────────────────────

  // Fetch candle date range when timeframe or universe changes
  useEffect(() => {
    if (!editorTimeframe || !editorUniverse) return;
    api.get(`/condition-scanner/candle-range/${encodeURIComponent(editorTimeframe)}`, {
      params: { universe: editorUniverse },
    }).then(res => {
      const r = res.data;
      setCandleRange(r);
      // Auto-set dates to actual data range
      if (r.min_date && r.max_date) {
        setBtStartDate(r.min_date);
        setBtEndDate(r.max_date);
      } else {
        // No data — set to Zerodha max range as hint
        const maxDays = r.zerodha_max_days || 365;
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - maxDays);
        setBtStartDate(start.toISOString().slice(0, 10));
        setBtEndDate(end.toISOString().slice(0, 10));
      }
    }).catch(() => {});
  }, [editorTimeframe, editorUniverse]);

  useEffect(() => {
    if (!applyZerodhaCharges || loadingBrokerageConfig) return;
    if (brokerageConfig !== DEFAULT_ZERODHA_CONFIG) return;

    setLoadingBrokerageConfig(true);
    tradeCostAPI.getConfig()
      .then(res => {
        const cfg = res?.data;
        if (!cfg || cfg.error) return;
        setBrokerageConfig({
          equity_delivery_brokerage_pct: Number(cfg.equity_delivery_brokerage_pct ?? DEFAULT_ZERODHA_CONFIG.equity_delivery_brokerage_pct),
          equity_delivery_brokerage_flat: Number(cfg.equity_delivery_brokerage_flat ?? DEFAULT_ZERODHA_CONFIG.equity_delivery_brokerage_flat),
          equity_intraday_brokerage_pct: Number(cfg.equity_intraday_brokerage_pct ?? DEFAULT_ZERODHA_CONFIG.equity_intraday_brokerage_pct),
          equity_intraday_brokerage_cap: Number(cfg.equity_intraday_brokerage_cap ?? DEFAULT_ZERODHA_CONFIG.equity_intraday_brokerage_cap),
          fno_brokerage_flat: Number(cfg.fno_brokerage_flat ?? DEFAULT_ZERODHA_CONFIG.fno_brokerage_flat),
          stt_equity_delivery: Number(cfg.stt_equity_delivery ?? DEFAULT_ZERODHA_CONFIG.stt_equity_delivery),
          stt_equity_intraday: Number(cfg.stt_equity_intraday ?? DEFAULT_ZERODHA_CONFIG.stt_equity_intraday),
          stt_fno_options: Number(cfg.stt_fno_options ?? DEFAULT_ZERODHA_CONFIG.stt_fno_options),
          stt_fno_futures: Number(cfg.stt_fno_futures ?? DEFAULT_ZERODHA_CONFIG.stt_fno_futures),
          nse_equity_charge: Number(cfg.nse_equity_charge ?? DEFAULT_ZERODHA_CONFIG.nse_equity_charge),
          nse_fno_charge: Number(cfg.nse_fno_charge ?? DEFAULT_ZERODHA_CONFIG.nse_fno_charge),
          gst_pct: Number(cfg.gst_pct ?? DEFAULT_ZERODHA_CONFIG.gst_pct),
          sebi_charges_per_crore: Number(cfg.sebi_charges_per_crore ?? DEFAULT_ZERODHA_CONFIG.sebi_charges_per_crore),
          stamp_duty_pct: Number(cfg.stamp_duty_pct ?? DEFAULT_ZERODHA_CONFIG.stamp_duty_pct),
          stamp_duty_cap: Number(cfg.stamp_duty_cap ?? DEFAULT_ZERODHA_CONFIG.stamp_duty_cap),
        });
      })
      .catch(() => {})
      .finally(() => setLoadingBrokerageConfig(false));
  }, [applyZerodhaCharges, brokerageConfig, loadingBrokerageConfig]);

  const adjustedBacktestResult = useMemo(() => {
    if (!backtestResult || !applyZerodhaCharges) return null;
    if (!backtestResult.summary || !backtestResult.all_trades) return null;

    const currentStrategy = strategies.find(s => s.id === selectedId);
    const strategyType = currentStrategy?.strategy_type || editorType;
    const segment = strategyType.includes('Options') ? 'FNO' : 'EQUITY';
    const productType: 'DELIVERY' | 'INTRADAY' | 'OPTIONS' | 'FUTURES' = strategyType === 'Equity Intraday'
      ? 'INTRADAY'
      : strategyType === 'Options Selling' || strategyType === 'Options Buying'
      ? 'OPTIONS'
      : 'DELIVERY';

    const computeSideCharge = (tradeValue: number, side: 'BUY' | 'SELL') => {
      let brokerage = 0;
      if (segment === 'EQUITY') {
        if (productType === 'DELIVERY') {
          brokerage = Math.max(
            tradeValue * (brokerageConfig.equity_delivery_brokerage_pct / 100),
            brokerageConfig.equity_delivery_brokerage_flat,
          );
        } else {
          brokerage = Math.min(
            tradeValue * (brokerageConfig.equity_intraday_brokerage_pct / 100),
            brokerageConfig.equity_intraday_brokerage_cap,
          );
        }
      } else {
        brokerage = brokerageConfig.fno_brokerage_flat;
      }

      let stt = 0;
      if (side === 'SELL') {
        if (segment === 'EQUITY') {
          stt = tradeValue * ((productType === 'DELIVERY' ? brokerageConfig.stt_equity_delivery : brokerageConfig.stt_equity_intraday) / 100);
        } else {
          stt = tradeValue * (brokerageConfig.stt_fno_options / 100);
        }
      }

      const exchangeCharge = tradeValue * ((segment === 'EQUITY' ? brokerageConfig.nse_equity_charge : brokerageConfig.nse_fno_charge) / 100);
      const gst = (brokerage + exchangeCharge) * (brokerageConfig.gst_pct / 100);
      const sebi = (tradeValue / 10000000) * brokerageConfig.sebi_charges_per_crore;
      const stamp = side === 'BUY'
        ? Math.min(tradeValue * (brokerageConfig.stamp_duty_pct / 100), brokerageConfig.stamp_duty_cap)
        : 0;

      return brokerage + stt + exchangeCharge + gst + sebi + stamp;
    };

    const daysSpan = Math.max(1, Math.round((new Date(backtestResult.end_date).getTime() - new Date(backtestResult.start_date).getTime()) / (1000 * 60 * 60 * 24)));
    let capital = backtestResult.initial_capital;
    let totalCharges = 0;
    const adjustedTrades: (BacktestTrade & { charges: number })[] = [];
    const netCurve: { date: string; equity: number; symbol?: string; pnl_pct?: number }[] = [
      { date: backtestResult.start_date, equity: capital },
    ];

    for (const trade of backtestResult.all_trades) {
      const tradeCapital = capital * (BACKTEST_POSITION_SIZE_PCT / 100);
      const quantity = trade.entry_price > 0 ? tradeCapital / trade.entry_price : 0;
      const entryValue = quantity * trade.entry_price;
      const exitValue = quantity * trade.exit_price;

      const entrySide = backtestResult.direction === 'BUY' ? 'BUY' : 'SELL';
      const exitSide = backtestResult.direction === 'BUY' ? 'SELL' : 'BUY';
      const charges = computeSideCharge(entryValue, entrySide) + computeSideCharge(exitValue, exitSide);
      totalCharges += charges;

      const grossPnlAmount = tradeCapital * (trade.pnl_pct / 100);
      const netPnlAmount = grossPnlAmount - charges;
      const netPnlPct = tradeCapital > 0 ? (netPnlAmount / tradeCapital) * 100 : 0;
      capital += netPnlAmount;

      adjustedTrades.push({
        ...trade,
        pnl_pct: Number(netPnlPct.toFixed(2)),
        charges: Number(charges.toFixed(2)),
      });

      netCurve.push({
        date: trade.exit_date,
        equity: Number(capital.toFixed(2)),
        symbol: trade.symbol,
        pnl_pct: Number(netPnlPct.toFixed(2)),
      });
    }

    const winners = adjustedTrades.filter(t => t.pnl_pct > 0);
    const losers = adjustedTrades.filter(t => t.pnl_pct <= 0);
    const totalTrades = adjustedTrades.length;
    const totalReturn = ((capital - backtestResult.initial_capital) / backtestResult.initial_capital) * 100;
    const annualReturn = totalReturn * (365 / daysSpan);
    const grossProfit = winners.reduce((sum, t) => sum + t.pnl_pct, 0);
    const grossLoss = Math.abs(losers.reduce((sum, t) => sum + t.pnl_pct, 0));
    const profitFactor = grossLoss > 0 ? grossProfit / grossLoss : (grossProfit > 0 ? 999 : 0);
    const avgPnl = totalTrades > 0 ? adjustedTrades.reduce((sum, t) => sum + t.pnl_pct, 0) / totalTrades : 0;
    const avgWin = winners.length > 0 ? winners.reduce((sum, t) => sum + t.pnl_pct, 0) / winners.length : 0;
    const avgLoss = losers.length > 0 ? losers.reduce((sum, t) => sum + t.pnl_pct, 0) / losers.length : 0;
    const maxWin = totalTrades > 0 ? Math.max(...adjustedTrades.map(t => t.pnl_pct)) : 0;
    const maxLoss = totalTrades > 0 ? Math.min(...adjustedTrades.map(t => t.pnl_pct)) : 0;
    const winRate = totalTrades > 0 ? (winners.length / totalTrades) * 100 : 0;

    let peak = netCurve[0]?.equity || backtestResult.initial_capital;
    let maxDrawdown = 0;
    for (const p of netCurve) {
      if (p.equity > peak) peak = p.equity;
      const dd = peak > 0 ? ((peak - p.equity) / peak) * 100 : 0;
      if (dd > maxDrawdown) maxDrawdown = dd;
    }

    const grouped = new Map<string, BacktestTrade[]>();
    for (const trade of adjustedTrades) {
      if (!grouped.has(trade.symbol)) grouped.set(trade.symbol, []);
      grouped.get(trade.symbol)!.push(trade);
    }
    const perSymbolAdjusted: BacktestSymbolResult[] = Array.from(grouped.entries()).map(([symbol, trades]) => {
      const w = trades.filter(t => t.pnl_pct > 0);
      const l = trades.filter(t => t.pnl_pct <= 0);
      const total = trades.length;
      const totalPnl = trades.reduce((sum, t) => sum + t.pnl_pct, 0);
      const avg = total > 0 ? totalPnl / total : 0;
      const avgHolding = total > 0 ? trades.reduce((sum, t) => sum + (t.holding_bars || 0), 0) / total : 0;
      return {
        symbol,
        total_trades: total,
        win_rate: Number((total > 0 ? (w.length / total) * 100 : 0).toFixed(1)),
        total_pnl_pct: Number(totalPnl.toFixed(2)),
        avg_pnl_pct: Number(avg.toFixed(2)),
        max_win_pct: Number((total > 0 ? Math.max(...trades.map(t => t.pnl_pct)) : 0).toFixed(2)),
        max_loss_pct: Number((total > 0 ? Math.min(...trades.map(t => t.pnl_pct)) : 0).toFixed(2)),
        avg_holding_bars: Number(avgHolding.toFixed(1)),
      };
    });

    return {
      ...backtestResult,
      final_capital: Number(capital.toFixed(2)),
      equity_curve: netCurve,
      per_symbol: perSymbolAdjusted,
      all_trades: adjustedTrades,
      summary: {
        ...backtestResult.summary,
        total_trades: totalTrades,
        winners: winners.length,
        losers: losers.length,
        win_rate: Number(winRate.toFixed(1)),
        total_return_pct: Number(totalReturn.toFixed(2)),
        annual_return_pct: Number(annualReturn.toFixed(2)),
        max_drawdown_pct: Number(maxDrawdown.toFixed(2)),
        profit_factor: Number((profitFactor === 999 ? 999 : profitFactor).toFixed(2)),
        avg_pnl_pct: Number(avgPnl.toFixed(2)),
        avg_win_pct: Number(avgWin.toFixed(2)),
        avg_loss_pct: Number(avgLoss.toFixed(2)),
        max_win_pct: Number(maxWin.toFixed(2)),
        max_loss_pct: Number(maxLoss.toFixed(2)),
      },
      charges_summary: {
        total_charges: Number(totalCharges.toFixed(2)),
      },
    } as BacktestResult & { charges_summary: { total_charges: number } };
  }, [applyZerodhaCharges, backtestResult, brokerageConfig, editorType, strategies, selectedId]);

  const displayedBacktestResult = adjustedBacktestResult || backtestResult;

  // ── New strategy ──────────────────────────────────────────────────────

  const newStrategy = () => {
    setSelectedId(null);
    localStorage.removeItem(LAST_SELECTED_SCANNER_STRATEGY_KEY);
    setEditorName('');
    setEditorDescription('');
    setEditorType('Equity Swing');
    setEditorDirection('BUY');
    setEditorTimeframe('1 Hour');
    setEditorUniverse('NIFTY50');
    setEditorConditions([{
      indicator: 'RSI',
      params: { period: 14 },
      comparator: 'crosses_above',
      value: '30',
    }]);
    setEditorExit(DEFAULT_EXIT_CONFIG);
    setEditorAutoScan(false);
    setEditorAutoQty(10000);
    setEditing(true);
    setScanResult(null);
    setBacktestResult(null);
    setShowBacktestPanel(false);
  };

  // ── Add condition ─────────────────────────────────────────────────────

  const addCondition = () => {
    if (editorConditions.length >= 5) {
      showToast('warning', 'Max 5 conditions allowed');
      return;
    }
    setEditorConditions([...editorConditions, {
      indicator: 'RSI',
      params: { period: 14 },
      comparator: 'higher_than',
      value: '50',
    }]);
  };

  const removeCondition = (idx: number) => {
    setEditorConditions(editorConditions.filter((_, i) => i !== idx));
  };

  const updateCondition = (idx: number, field: string, value: any) => {
    const updated = [...editorConditions];
    if (field === 'indicator') {
      const meta = indicators.find(i => i.id === value);
      const defaultParams: Record<string, any> = {};
      meta?.params.forEach(p => { defaultParams[p.name] = p.default; });
      updated[idx] = { ...updated[idx], indicator: value, params: defaultParams };
    } else if (field.startsWith('param.')) {
      const paramName = field.replace('param.', '');
      updated[idx] = { ...updated[idx], params: { ...updated[idx].params, [paramName]: value } };
    } else {
      (updated[idx] as any)[field] = value;
    }
    setEditorConditions(updated);
  };

  // ── Install prebuilt ──────────────────────────────────────────────────

  const installPrebuilt = async (key: string) => {
    try {
      await api.post(`/condition-scanner/prebuilt/${key}/install`);
      showToast('success', 'Strategy installed');
      await loadData();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to install';
      showToast('error', msg);
    }
  };

  // ── Save strategy ─────────────────────────────────────────────────────

  const saveStrategy = async () => {
    if (!editorName.trim()) {
      showToast('error', 'Strategy name is required');
      return;
    }
    if (editorConditions.length === 0) {
      showToast('error', 'At least one entry condition is required');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: editorName,
        description: editorDescription,
        strategy_type: editorType,
        direction: editorDirection,
        timeframe: editorTimeframe,
        universe: editorUniverse,
        instruments: [],
        entry_conditions: editorConditions,
        exit_config: editorExit,
        is_active: true,
        auto_scan_enabled: editorAutoScan,
        auto_amount: editorAutoQty,
      };
      if (selectedId) {
        await api.put(`/condition-scanner/strategies/${selectedId}`, payload);
        showToast('success', 'Strategy updated');
      } else {
        const res = await api.post('/condition-scanner/strategies', payload);
        setSelectedId(res.data.strategy.id);
        showToast('success', 'Strategy created');
      }
      await loadData();
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to save';
      showToast('error', msg);
    } finally {
      setSaving(false);
    }
  };

  // ── Delete strategy ───────────────────────────────────────────────────

  const deleteStrategy = async (id: number) => {
    try {
      await api.delete(`/condition-scanner/strategies/${id}`);
      showToast('success', 'Strategy deleted');
      if (selectedId === id) {
        setSelectedId(null);
        localStorage.removeItem(LAST_SELECTED_SCANNER_STRATEGY_KEY);
        setEditing(false);
      }
      await loadData();
    } catch {
      showToast('error', 'Failed to delete strategy');
    }
  };

  // ── Run scan ──────────────────────────────────────────────────────────

  const runScan = async () => {
    if (!selectedId) return;
    setScanning(true);
    setScanResult(null);
    setShowBacktestPanel(false);
    try {
      const res = await api.post(`/condition-scanner/scan/${selectedId}`);
      setScanResult(res.data);
      if (res.data.matches_found === 0) {
        showToast('info', 'No signals found in current scan');
      } else {
        showToast('success', `${res.data.matches_found} signal(s) found!`);
      }
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Scan failed');
    } finally {
      setScanning(false);
    }
  };

  // ── Execute signal ────────────────────────────────────────────────────

  const executeSignal = async (signal: ScanSignal) => {
    if (!scanResult) return;
    setExecuting(signal.symbol);
    try {
      const res = await api.post('/condition-scanner/execute-signal', {
        symbol: signal.symbol,
        direction: scanResult.direction,
        strategy_name: scanResult.strategy_name,
        exit_config: scanResult.exit_config,
        quantity: signal.suggested_quantity || 1,
        suggested_quantity: signal.suggested_quantity || 1,
      });
      const o = res.data.order;
      showToast(
        o.status.includes('FAILED') ? 'error' : 'success',
        `${res.data.message}`
      );
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Execution failed');
    } finally {
      setExecuting(null);
    }
  };

  // ── Run backtest ──────────────────────────────────────────────────────

  const runBacktest = async () => {
    if (!selectedId) return;
    setBacktesting(true);
    setBacktestResult(null);
    setShowBacktestPanel(true);
    setScanResult(null);
    try {
      const res = await api.post(`/condition-scanner/backtest/${selectedId}`, {
        start_date: btStartDate,
        end_date: btEndDate,
        initial_capital: 100000,
        position_size_pct: 10,
        max_open_trades: 5,
      });
      const resultData = res.data;
      if (!resultData.summary || !resultData.all_trades) {
        showToast('warning', resultData.error || 'Backtest returned no data — load candles first');
        setBacktestResult(null);
        setShowBacktestPanel(false);
        return;
      }
      setBacktestResult(resultData);
      setStrategies(prev => prev.map(strategy => (
        strategy.id === selectedId
          ? {
              ...strategy,
              last_backtest_result: resultData,
              last_backtest_at: new Date().toISOString(),
            }
          : strategy
      )));
      const s = resultData.summary;
      if (s.total_trades === 0) {
        showToast('info', 'No trades generated in backtest period');
      } else {
        showToast('success', `Backtest complete: ${s.total_trades} trades, ${s.total_return_pct}% return`);
      }
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Backtest failed');
    } finally {
      setBacktesting(false);
    }
  };

  // ── Backfill candles for strategy ─────────────────────────────────────

  const backfillCandles = async () => {
    if (!selectedId) return;
    setBackfilling(true);
    try {
      const res = await api.post(`/condition-scanner/backfill-candles/${selectedId}`);
      const d = res.data;
      if (d.failed === d.symbols_attempted) {
        showToast('error', `Backfill failed: ${d.errors?.[0] || 'All symbols failed'}`);
      } else {
        showToast('success', `Loaded ${d.timeframe} candles: ${d.success}/${d.symbols_attempted} symbols, ${d.total_rows_in_table?.toLocaleString()} total rows`);
      }
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Backfill failed — check Zerodha API key');
    } finally {
      setBackfilling(false);
    }
  };

  // ── Toggle auto-scan ──────────────────────────────────────────────────

  const toggleAutoScan = async () => {
    if (!selectedId) return;
    setTogglingAutoScan(true);
    try {
      const newState = !editorAutoScan;
      if (newState) {
        // Save first so backend has latest conditions
        await saveStrategy();
        await api.post(`/condition-scanner/scheduler/start/${selectedId}`);
        showToast('success', `Auto-scan enabled — scanning every ${editorTimeframe}`);
      } else {
        await api.post(`/condition-scanner/scheduler/stop/${selectedId}`);
        showToast('info', 'Auto-scan disabled');
      }
      setEditorAutoScan(newState);
      await loadData();
    } catch (err: any) {
      showToast('error', err?.response?.data?.detail || 'Failed to toggle auto-scan');
    } finally {
      setTogglingAutoScan(false);
    }
  };

  // ── Filtered strategies ───────────────────────────────────────────────

  const filteredStrategies = strategies.filter(s => {
    if (filterType !== 'All' && s.strategy_type !== filterType) return false;
    if (searchQuery && !s.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const selectedStrategy = strategies.find(s => s.id === selectedId);

  // ── Render ────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex">
      {/* ─── Left Panel: Strategy List ─────────────────────────────── */}
      <div className="w-96 border-r border-slate-800 flex flex-col bg-slate-950">
        {/* Header */}
        <div className="p-4 border-b border-slate-800">
          <div className="flex items-center justify-between mb-3">
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              <Zap className="w-5 h-5 text-yellow-400" />
              Create Scanner
            </h1>
            <button
              onClick={newStrategy}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" /> New
            </button>
          </div>

          {/* Type filters */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {['All', ...STRATEGY_TYPES].map(type => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`px-2.5 py-1 rounded-md text-xs font-medium transition ${
                  filterType === type
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-800 text-slate-400 hover:text-white'
                }`}
              >
                {type}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search for Strategies"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Strategy list */}
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {/* My Strategies */}
          {filteredStrategies.length > 0 && (
            <div className="p-2">
              {filteredStrategies.map(s => (
                <div
                  key={s.id}
                  onClick={() => selectStrategy(s)}
                  className={`flex items-center justify-between px-3 py-3 rounded-lg cursor-pointer transition mb-1 group ${
                    selectedId === s.id
                      ? 'bg-blue-600/20 border border-blue-500/40'
                      : 'hover:bg-slate-900 border border-transparent'
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Activity className="w-4 h-4 text-blue-400 flex-shrink-0" />
                      <span className="text-sm font-semibold text-white truncate">{s.name}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${TYPE_COLORS[s.strategy_type] || 'bg-slate-700 text-slate-300'}`}>
                        {s.strategy_type}
                      </span>
                      <span className="text-[10px] text-slate-500">{s.timeframe}</span>
                      {s.last_signal_count !== undefined && s.last_signal_count > 0 && (
                        <span className="text-[10px] text-green-400">● {s.last_signal_count} signals</span>
                      )}
                      {s.auto_scan_enabled && (
                        <span className="text-[9px] bg-purple-500/20 text-purple-300 px-1 py-0.5 rounded font-semibold">AUTO</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); deleteStrategy(s.id); }}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded transition"
                    title="Delete strategy"
                  >
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </div>
              ))}
            </div>
          )}

          {filteredStrategies.length === 0 && !showPrebuilt && (
            <div className="p-6 text-center">
              <p className="text-sm text-slate-500 mb-3">No strategies yet</p>
              <button
                onClick={() => setShowPrebuilt(true)}
                className="text-sm text-blue-400 hover:text-blue-300"
              >
                Browse pre-built strategies →
              </button>
            </div>
          )}

          {/* Pre-built Templates */}
          <div className="p-2 border-t border-slate-800">
            <button
              onClick={() => setShowPrebuilt(!showPrebuilt)}
              className="flex items-center gap-2 w-full px-3 py-2 text-sm text-slate-400 hover:text-white"
            >
              {showPrebuilt ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
              <Star className="w-4 h-4 text-yellow-400" />
              Pre-built Strategies ({prebuiltStrategies.length})
            </button>

            {showPrebuilt && (
              <div className="space-y-1 mt-1">
                {prebuiltStrategies.map(p => {
                  const installed = strategies.some(s => s.name === p.name);
                  return (
                    <div key={p.key} className="px-3 py-2.5 rounded-lg bg-slate-900/50 border border-slate-800">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-white">{p.name}</span>
                        {installed ? (
                          <span className="text-[10px] text-green-400 flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> Installed
                          </span>
                        ) : (
                          <button
                            onClick={() => installPrebuilt(p.key)}
                            className="px-2 py-0.5 bg-blue-600 hover:bg-blue-700 text-white text-[10px] font-semibold rounded flex items-center gap-1"
                          >
                            <Download className="w-3 h-3" /> Install
                          </button>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-2">{p.description}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${TYPE_COLORS[p.strategy_type] || ''}`}>
                          {p.strategy_type}
                        </span>
                        <span className="text-[10px] text-slate-500">{p.timeframe}</span>
                        <span className="text-[10px] text-slate-500">{p.conditions_count} conditions</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ─── Right Panel: Editor / Scan Results ───────────────────── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {editing ? (
          <div className="flex-1 overflow-y-auto custom-scrollbar">
            {/* Strategy header */}
            <div className="p-6 border-b border-slate-800 bg-slate-950/80">
              <input
                type="text"
                placeholder="Strategy Name"
                value={editorName}
                onChange={e => setEditorName(e.target.value)}
                className="text-xl font-bold text-white bg-transparent border-none outline-none w-full placeholder-slate-600 mb-1"
              />
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Description (optional)"
                  value={editorDescription}
                  onChange={e => { setEditorDescription(e.target.value); setExplanation(null); }}
                  className="text-sm text-slate-400 bg-transparent border-none outline-none flex-1 placeholder-slate-600"
                />
                {selectedId && (
                  <button
                    onClick={explainStrategy}
                    disabled={explaining}
                    title="Generate AI explanation using NVIDIA LLM"
                    className="flex items-center gap-1 px-2 py-1 text-xs rounded-md bg-violet-600/20 hover:bg-violet-600/40 border border-violet-500/40 text-violet-300 transition-colors disabled:opacity-50 shrink-0"
                  >
                    {explaining
                      ? <Loader2 className="w-3 h-3 animate-spin" />
                      : <Sparkles className="w-3 h-3" />}
                    {explaining ? 'Thinking…' : 'Explain'}
                  </button>
                )}
              </div>
              {explanation && (
                <div className="mt-2 p-2.5 rounded-lg bg-violet-900/20 border border-violet-500/30 text-xs text-violet-200 leading-relaxed">
                  {explanation}
                </div>
              )}
            </div>

            <div className="flex gap-6 p-6">
              {/* Left: Conditions Editor */}
              <div className="flex-1 space-y-6">
                {/* Entry section */}
                <div className="bg-slate-900/70 rounded-xl border border-slate-800 p-5">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-base font-semibold text-white">Entry</h3>
                    <div className="flex items-center gap-2">
                      {/* Direction toggle */}
                      <div className="flex rounded-lg overflow-hidden border border-slate-700">
                        <button
                          onClick={() => setEditorDirection('BUY')}
                          className={`px-4 py-1.5 text-xs font-semibold ${
                            editorDirection === 'BUY'
                              ? 'bg-green-600 text-white'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          Buy
                        </button>
                        <button
                          onClick={() => setEditorDirection('SELL')}
                          className={`px-4 py-1.5 text-xs font-semibold ${
                            editorDirection === 'SELL'
                              ? 'bg-red-600 text-white'
                              : 'bg-slate-800 text-slate-400'
                          }`}
                        >
                          Sell
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Strategy type + timeframe */}
                  <div className="flex items-center gap-3 mb-4 flex-wrap">
                    <select
                      value={editorType}
                      onChange={e => setEditorType(e.target.value)}
                      className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                      title="Strategy type"
                    >
                      {STRATEGY_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <select
                      value={editorTimeframe}
                      onChange={e => setEditorTimeframe(e.target.value)}
                      className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                      title="Timeframe"
                    >
                      {TIMEFRAMES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                    <select
                      value={editorUniverse}
                      onChange={e => setEditorUniverse(e.target.value)}
                      className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:border-blue-500 focus:outline-none"
                      title="Universe"
                    >
                      <option value="NIFTY50">NIFTY 50</option>
                      <option value="NIFTY100">NIFTY 100</option>
                      <option value="NIFTYIT">NIFTY IT</option>
                      <option value="NIFTYBANK">NIFTY BANK</option>
                    </select>
                  </div>

                  {/* Conditions */}
                  <div className="mb-4">
                    <p className="text-xs text-slate-500 mb-3 uppercase tracking-wider">
                      Conditions ({editorConditions.length}/5)
                    </p>

                    <div className="space-y-3">
                      {editorConditions.map((cond, idx) => {
                        const meta = indicators.find(i => i.id === cond.indicator);
                        return (
                          <div key={idx} className="flex items-start gap-2 bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
                            <span className="text-xs text-slate-500 mt-2 w-8 flex-shrink-0">
                              {idx === 0 ? 'If' : 'And'}
                            </span>

                            {/* Indicator */}
                            <div className="flex-1 min-w-0">
                              <div className="flex flex-wrap gap-2 items-center">
                                <select
                                  value={cond.indicator}
                                  onChange={e => updateCondition(idx, 'indicator', e.target.value)}
                                  className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none min-w-[140px]"
                                  title="Indicator"
                                >
                                  {indicators.map(ind => (
                                    <option key={ind.id} value={ind.id}>
                                      {ind.icon} {ind.name}
                                    </option>
                                  ))}
                                </select>

                                {/* Param inputs */}
                                {meta?.params.map(p => (
                                  <div key={p.name} className="flex items-center gap-1">
                                    {p.type === 'select' ? (
                                      <select
                                        value={cond.params[p.name] ?? p.default}
                                        onChange={e => updateCondition(idx, `param.${p.name}`, e.target.value)}
                                        className="bg-slate-900 border border-slate-600 rounded px-2 py-2 text-xs text-white"
                                        title={p.name}
                                      >
                                        {p.options?.map(o => <option key={o} value={o}>{o}</option>)}
                                      </select>
                                    ) : (
                                      <input
                                        type="number"
                                        value={cond.params[p.name] ?? p.default}
                                        onChange={e => updateCondition(idx, `param.${p.name}`, parseFloat(e.target.value) || 0)}
                                        className="bg-slate-900 border border-slate-600 rounded px-2 py-2 text-xs text-white w-16 text-center"
                                        title={p.name}
                                      />
                                    )}
                                  </div>
                                ))}

                                {/* Comparator */}
                                <select
                                  value={cond.comparator}
                                  onChange={e => updateCondition(idx, 'comparator', e.target.value)}
                                  className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none"
                                  title="Comparator"
                                >
                                  {COMPARATORS.map(c => (
                                    <option key={c.id} value={c.id}>{c.label}</option>
                                  ))}
                                </select>

                                {/* Value */}
                                <input
                                  type="text"
                                  value={cond.value}
                                  onChange={e => updateCondition(idx, 'value', e.target.value)}
                                  placeholder="Value or Close(0)"
                                  className="bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white w-24 focus:border-blue-500 focus:outline-none"
                                />
                              </div>
                            </div>

                            <button
                              onClick={() => removeCondition(idx)}
                              className="p-1.5 hover:bg-red-500/20 rounded transition mt-1"
                              title="Remove condition"
                            >
                              <Trash2 className="w-4 h-4 text-red-400" />
                            </button>
                          </div>
                        );
                      })}
                    </div>

                    <button
                      onClick={addCondition}
                      className="mt-3 px-4 py-2 border border-dashed border-slate-600 text-slate-400 hover:text-white hover:border-blue-500 rounded-lg text-sm flex items-center gap-2 transition"
                    >
                      <Plus className="w-4 h-4" /> Add Another Condition
                    </button>
                  </div>

                  {/* Pre-built setup chips */}
                  <div>
                    <p className="text-xs text-slate-500 mb-2">Pre built Setups</p>
                    <div className="flex flex-wrap gap-2">
                      {indicators.slice(0, 8).map(ind => (
                        <button
                          key={ind.id}
                          onClick={() => {
                            const defaultParams: Record<string, any> = {};
                            ind.params.forEach(p => { defaultParams[p.name] = p.default; });
                            if (editorConditions.length < 5) {
                              setEditorConditions([...editorConditions, {
                                indicator: ind.id,
                                params: defaultParams,
                                comparator: 'crosses_above',
                                value: '0',
                              }]);
                            }
                          }}
                          className="px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg text-xs text-slate-300 hover:text-white transition flex flex-col items-center gap-1 min-w-[60px]"
                        >
                          <span className="text-lg">{ind.icon}</span>
                          <span>{ind.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Exit section */}
                <div className="bg-slate-900/70 rounded-xl border border-slate-800 p-5">
                  <h3 className="text-base font-semibold text-white mb-4">Exit (for individual instrument)</h3>
                  <div className="grid grid-cols-3 gap-4 mb-3">
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">SL</label>
                      <div className="flex items-center">
                        <input
                          type="number"
                          value={editorExit.sl_pct}
                          onChange={e => setEditorExit({ ...editorExit, sl_pct: parseFloat(e.target.value) || 0 })}
                          className="bg-slate-800 border border-slate-700 rounded-l-lg px-3 py-2 text-sm text-white w-full focus:border-blue-500 focus:outline-none"
                          title="Stop Loss %"
                        />
                        <span className="bg-slate-700 border border-slate-600 rounded-r-lg px-2 py-2 text-xs text-slate-400">%</span>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">TP</label>
                      <div className="flex items-center">
                        <input
                          type="number"
                          value={editorExit.tp_pct}
                          onChange={e => setEditorExit({ ...editorExit, tp_pct: parseFloat(e.target.value) || 0 })}
                          className="bg-slate-800 border border-slate-700 rounded-l-lg px-3 py-2 text-sm text-white w-full focus:border-blue-500 focus:outline-none"
                          title="Take Profit %"
                        />
                        <span className="bg-slate-700 border border-slate-600 rounded-r-lg px-2 py-2 text-xs text-slate-400">%</span>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs text-slate-400 block mb-1">TSL</label>
                      <div className="flex items-center">
                        <input
                          type="number"
                          value={editorExit.tsl_pct}
                          onChange={e => setEditorExit({ ...editorExit, tsl_pct: parseFloat(e.target.value) || 0 })}
                          className="bg-slate-800 border border-slate-700 rounded-l-lg px-3 py-2 text-sm text-white w-full focus:border-blue-500 focus:outline-none"
                          title="Trailing Stop Loss %"
                        />
                        <span className="bg-slate-700 border border-slate-600 rounded-r-lg px-2 py-2 text-xs text-slate-400">%</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-4 text-xs mb-4">
                    {['percentage', 'points', 'pnl'].map(m => (
                      <label key={m} className="flex items-center gap-1.5 text-slate-400 cursor-pointer">
                        <input
                          type="radio"
                          name="exit_mode"
                          checked={editorExit.exit_mode === m}
                          onChange={() => setEditorExit({ ...editorExit, exit_mode: m })}
                          className="accent-blue-500"
                        />
                        {m === 'percentage' ? '%Percentage' : m === 'points' ? 'Points' : 'PNL'}
                      </label>
                    ))}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 space-y-3">
                      <label className="flex items-center justify-between gap-3 text-sm text-slate-300 cursor-pointer">
                        <span className="font-medium">Multi-timeframe confirmation</span>
                        <input
                          type="checkbox"
                          checked={!!editorExit.require_htf_confirm}
                          onChange={e => setEditorExit({ ...editorExit, require_htf_confirm: e.target.checked })}
                          className="accent-blue-500"
                        />
                      </label>
                      <div>
                        <label className="text-xs text-slate-400 block mb-1">Higher timeframe</label>
                        <select
                          value={editorExit.htf_timeframe || 'Auto'}
                          onChange={e => setEditorExit({ ...editorExit, htf_timeframe: e.target.value })}
                          disabled={!editorExit.require_htf_confirm}
                          className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
                          title="Higher timeframe confirmation"
                        >
                          {HTF_TIMEFRAME_OPTIONS.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                        </select>
                      </div>
                      <p className="text-[11px] text-slate-500">
                        Requires the same setup on the next higher timeframe before a signal is accepted.
                      </p>
                    </div>

                    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 space-y-3">
                      <label className="flex items-center justify-between gap-3 text-sm text-slate-300 cursor-pointer">
                        <span className="font-medium">ATR-based sizing</span>
                        <input
                          type="checkbox"
                          checked={!!editorExit.use_atr_sizing}
                          onChange={e => setEditorExit({ ...editorExit, use_atr_sizing: e.target.checked })}
                          className="accent-blue-500"
                        />
                      </label>
                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="text-[11px] text-slate-400 block mb-1">Risk %</label>
                          <input
                            type="number"
                            min="0.1"
                            step="0.1"
                            value={editorExit.risk_per_trade_pct ?? 1}
                            onChange={e => setEditorExit({ ...editorExit, risk_per_trade_pct: parseFloat(e.target.value) || 1 })}
                            disabled={!editorExit.use_atr_sizing}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-slate-400 block mb-1">ATR period</label>
                          <input
                            type="number"
                            min="2"
                            step="1"
                            value={editorExit.atr_period ?? 14}
                            onChange={e => setEditorExit({ ...editorExit, atr_period: parseInt(e.target.value || '14', 10) || 14 })}
                            disabled={!editorExit.use_atr_sizing}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-slate-400 block mb-1">ATR x</label>
                          <input
                            type="number"
                            min="0.5"
                            step="0.1"
                            value={editorExit.atr_multiplier ?? 1.5}
                            onChange={e => setEditorExit({ ...editorExit, atr_multiplier: parseFloat(e.target.value) || 1.5 })}
                            disabled={!editorExit.use_atr_sizing}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-2 py-2 text-sm text-white focus:border-blue-500 focus:outline-none disabled:opacity-50"
                          />
                        </div>
                      </div>
                      <p className="text-[11px] text-slate-500">
                        Uses ATR to size quantity by risk instead of a flat allocation cap.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Auto-Scan Section */}
                <div className="bg-slate-900/70 rounded-xl border border-purple-500/20 p-5 mb-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h3 className="text-base font-semibold text-white flex items-center gap-2">
                        <Activity className="w-4 h-4 text-purple-400" />
                        Auto-Scan & Execute
                      </h3>
                      <p className="text-xs text-slate-500 mt-1">
                        Runs automatically every <span className="text-purple-300 font-medium">{editorTimeframe}</span> during market hours (9:15–15:30)
                      </p>
                    </div>
                    <button
                      onClick={toggleAutoScan}
                      disabled={!selectedId || togglingAutoScan}
                      className={`relative w-12 h-6 rounded-full transition-colors ${
                        editorAutoScan ? 'bg-purple-500' : 'bg-slate-700'
                      } disabled:opacity-50`}
                      title={editorAutoScan ? 'Disable auto-scan' : 'Enable auto-scan'}
                    >
                      <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                        editorAutoScan ? 'translate-x-7' : 'translate-x-1'
                      }`} />
                    </button>
                  </div>
                  {editorAutoScan && (
                    <div className="flex items-center gap-4 mt-2">
                      <div>
                        <label className="text-xs text-slate-400 block mb-1">₹ Amount per trade</label>
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-slate-500">₹</span>
                          <input
                            type="number"
                            min={100}
                            max={10000000}
                            step={1000}
                            value={editorAutoQty}
                            onChange={e => setEditorAutoQty(Math.max(100, parseInt(e.target.value) || 10000))}
                            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white w-28 focus:border-purple-500 focus:outline-none"
                            title="Amount per trade in ₹"
                          />
                        </div>
                      </div>
                      <div className="flex-1 text-xs text-slate-500">
                        <p>Qty = ⌊ amount ÷ stock price ⌋. E.g. ₹{formatNumber(editorAutoQty)} on a ₹2,500 stock = {Math.floor(editorAutoQty / 2500)} shares.</p>
                      </div>
                    </div>
                  )}
                  {editorAutoScan && selectedStrategy?.last_scan && (
                    <div className="mt-2 text-[10px] text-slate-600 flex items-center gap-2">
                      <span>Last scan: {new Date(selectedStrategy.last_scan).toLocaleString()}</span>
                      {selectedStrategy.last_signal_count !== undefined && (
                        <span>| {selectedStrategy.last_signal_count} signal(s)</span>
                      )}
                    </div>
                  )}
                </div>

                {/* Action buttons */}
                <div className="flex items-center gap-3 pb-2">
                  <button
                    onClick={saveStrategy}
                    disabled={saving}
                    className="px-6 py-3 bg-slate-700 hover:bg-slate-600 text-white font-semibold rounded-xl flex items-center gap-2 transition disabled:opacity-50"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    Save
                  </button>
                  <button
                    onClick={() => { saveStrategy().then(() => runScan()); }}
                    disabled={saving || scanning || !selectedId}
                    className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl flex items-center gap-2 transition disabled:opacity-50"
                  >
                    {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    Execute
                  </button>
                  <button
                    onClick={() => { saveStrategy().then(() => runBacktest()); }}
                    disabled={saving || backtesting || !selectedId}
                    className="px-6 py-3 bg-purple-600 hover:bg-purple-700 text-white font-semibold rounded-xl flex items-center gap-2 transition disabled:opacity-50"
                  >
                    {backtesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
                    Backtest
                  </button>
                </div>

                {/* Backtest date range */}
                <div className="pb-6">
                  <div className="flex items-center gap-3 text-xs">
                    <div className="flex items-center gap-1.5 text-slate-400">
                      <Calendar className="w-3.5 h-3.5" />
                      <span>Period:</span>
                    </div>
                    <input
                      type="date"
                      value={btStartDate}
                      onChange={e => setBtStartDate(e.target.value)}
                      min={candleRange?.min_date || undefined}
                      max={candleRange?.max_date || undefined}
                      className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white focus:border-purple-500 focus:outline-none"
                      title="Backtest start date"
                    />
                    <span className="text-slate-500">to</span>
                    <input
                      type="date"
                      value={btEndDate}
                      onChange={e => setBtEndDate(e.target.value)}
                      min={candleRange?.min_date || undefined}
                      max={candleRange?.max_date || undefined}
                      className="bg-slate-800 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white focus:border-purple-500 focus:outline-none"
                      title="Backtest end date"
                    />
                  </div>
                  {/* Data availability hint */}
                  <div className="mt-1.5 text-[10px] text-slate-500 flex items-center gap-2 flex-wrap">
                    {candleRange && candleRange.total_rows > 0 ? (
                      <>
                        <span className="text-green-500">●</span>
                        <span>
                          {formatNumber(candleRange.total_rows)} {editorTimeframe} candles available
                          ({candleRange.symbols_with_data}/{candleRange.symbols_in_universe} symbols)
                        </span>
                        <span className="text-slate-600">|</span>
                        <span>Data: {candleRange.min_date} → {candleRange.max_date}</span>
                      </>
                    ) : candleRange ? (
                      <>
                        <span className="text-orange-400">●</span>
                        <span className="text-orange-400">
                          No {editorTimeframe} candle data — load candles first (max {candleRange.zerodha_max_days} days from Zerodha)
                        </span>
                      </>
                    ) : null}
                  </div>
                </div>
              </div>

              {/* Right: Scan Results / Backtest Results */}
              <div className="w-80 flex-shrink-0 space-y-4">
                {/* Scan Results */}
                {scanResult ? (
                  <div className="bg-slate-900/70 rounded-xl border border-slate-800 p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-white">Scan Results</h3>
                      <span className="text-xs text-slate-400">
                        {scanResult.matches_found}/{scanResult.total_scanned}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mb-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        scanResult.execution_mode === 'ZERODHA_LIVE'
                          ? 'bg-red-500/20 text-red-300'
                          : scanResult.execution_mode === 'PAPER_TRADING'
                          ? 'bg-green-500/20 text-green-300'
                          : 'bg-yellow-500/20 text-yellow-300'
                      }`}>
                        {scanResult.execution_mode === 'ZERODHA_LIVE' ? '🔴 LIVE' :
                         scanResult.execution_mode === 'PAPER_TRADING' ? '🟢 PAPER' : '🟡 DRY RUN'}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {scanResult.direction}
                      </span>
                    </div>

                    {scanResult.signals.length > 0 ? (
                      <div className="space-y-2 max-h-[500px] overflow-y-auto custom-scrollbar">
                        {scanResult.signals.map(sig => (
                          <div key={sig.symbol} className="bg-slate-800/50 rounded-lg p-3 border border-slate-700/50">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-semibold text-white">{sig.symbol}</span>
                              <span className="text-sm font-semibold text-white">₹{sig.ltp}</span>
                            </div>
                            <div className="flex items-center justify-between mb-2">
                              <span className={`text-xs ${sig.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {sig.change_percent >= 0 ? '+' : ''}{sig.change_percent.toFixed(2)}%
                              </span>
                              <div className="flex gap-1.5 text-[10px] text-slate-400">
                                {Object.entries(sig.indicators).map(([k, v]) => (
                                  <span key={k}>{k}: {v}</span>
                                ))}
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-1.5 mb-2 text-[10px]">
                              {sig.htf_confirmed && sig.htf_timeframe && (
                                <span className="px-1.5 py-0.5 rounded bg-blue-500/15 text-blue-300 border border-blue-500/30">
                                  HTF: {sig.htf_timeframe}
                                </span>
                              )}
                              {sig.position_sizing && (
                                <span className="px-1.5 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/30">
                                  {sig.position_sizing}
                                </span>
                              )}
                              {sig.suggested_quantity ? (
                                <span className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                  Qty: {sig.suggested_quantity}
                                </span>
                              ) : null}
                              {typeof sig.atr === 'number' ? (
                                <span className="px-1.5 py-0.5 rounded bg-slate-700/70 text-slate-300 border border-slate-600">
                                  ATR: {sig.atr}
                                </span>
                              ) : null}
                            </div>
                            <button
                              onClick={() => executeSignal(sig)}
                              disabled={executing === sig.symbol}
                              className={`w-full py-1.5 rounded-lg text-xs font-semibold flex items-center justify-center gap-1 transition ${
                                scanResult.direction === 'BUY'
                                  ? 'bg-green-600 hover:bg-green-700 text-white'
                                  : 'bg-red-600 hover:bg-red-700 text-white'
                              } disabled:opacity-50`}
                            >
                              {executing === sig.symbol ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <ArrowRight className="w-3 h-3" />
                              )}
                              {scanResult.direction === 'BUY' ? 'Buy' : 'Sell'} {sig.symbol}
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-6">
                        <XCircle className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                        <p className="text-xs text-slate-500">No signals match conditions</p>
                      </div>
                    )}
                  </div>
                ) : null}

                {/* Backtest Loading */}
                {backtesting && (
                  <div className="bg-slate-900/70 rounded-xl border border-purple-500/30 p-6 text-center">
                    <Loader2 className="w-8 h-8 animate-spin text-purple-400 mx-auto mb-3" />
                    <p className="text-sm text-purple-300 font-medium">Running Backtest...</p>
                    <p className="text-xs text-slate-500 mt-1">Replaying candles bar-by-bar</p>
                  </div>
                )}

                {/* Backtest Results */}
                {backtestResult && showBacktestPanel && backtestResult.summary && displayedBacktestResult?.summary && (
                  <div className="bg-slate-900/70 rounded-xl border border-purple-500/30 p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold text-purple-300 flex items-center gap-1.5">
                        <BarChart3 className="w-4 h-4" /> Backtest Results
                      </h3>
                      <button
                        onClick={() => setShowBacktestPanel(false)}
                        className="text-slate-500 hover:text-white text-xs"
                        title="Close backtest panel"
                      >✕</button>
                    </div>

                    {/* No data error */}
                    {(backtestResult as any).error && (
                      <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 mb-3">
                        <p className="text-xs text-orange-300 mb-2">{(backtestResult as any).error}</p>
                        <button
                          onClick={backfillCandles}
                          disabled={backfilling}
                          className="px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white text-xs font-medium rounded-lg disabled:opacity-50 flex items-center gap-1.5"
                        >
                          {backfilling ? <Loader2 className="w-3 h-3 animate-spin" /> : <Download className="w-3 h-3" />}
                          {backfilling ? 'Loading Candles...' : 'Load Candles from Zerodha'}
                        </button>
                      </div>
                    )}

                    {/* Period info */}
                    <div className="flex items-center gap-2 mb-2 text-[10px] text-slate-400 flex-wrap">
                      <span>{backtestResult.start_date} → {backtestResult.end_date}</span>
                      <span>|</span>
                      <span>{backtestResult.universe}</span>
                      {(backtestResult.summary as any).timeframe && (
                        <>
                          <span>|</span>
                          <span className="bg-purple-500/10 text-purple-400 px-1.5 py-0.5 rounded font-medium">
                            {(backtestResult.summary as any).timeframe} candles
                          </span>
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mb-3 text-[9px]">
                      <span className="bg-green-500/10 text-green-400 px-1.5 py-0.5 rounded">
                        {(backtestResult.summary as any).data_source || 'Real DB data'}
                      </span>
                      {(backtestResult.summary as any).total_candles_used > 0 && (
                        <span className="text-slate-500">
                          {formatNumber((backtestResult.summary as any).total_candles_used)} candles
                        </span>
                      )}
                    </div>
                    <div className="flex items-center justify-between mb-3 bg-slate-800/40 border border-slate-700 rounded-lg px-2.5 py-2">
                      <div className="text-[10px] text-slate-400">
                        {applyZerodhaCharges ? 'Net after Zerodha charges' : 'Gross (without brokerage/charges)'}
                      </div>
                      <button
                        onClick={() => setApplyZerodhaCharges(v => !v)}
                        className={`relative w-10 h-5 rounded-full transition-colors ${
                          applyZerodhaCharges ? 'bg-green-500' : 'bg-slate-700'
                        }`}
                        title="Toggle Zerodha charges in backtest metrics"
                      >
                        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                          applyZerodhaCharges ? 'translate-x-5' : 'translate-x-0.5'
                        }`} />
                      </button>
                    </div>
                    {applyZerodhaCharges && (displayedBacktestResult as any)?.charges_summary && (
                      <div className="mb-3 text-[10px] text-orange-300 bg-orange-500/10 border border-orange-500/20 rounded-lg px-2.5 py-2">
                        Total estimated charges: {formatCurrency((displayedBacktestResult as any).charges_summary.total_charges || 0)}
                        {loadingBrokerageConfig ? ' (loading config...)' : ''}
                      </div>
                    )}

                    {/* Summary metrics */}
                    <div className="grid grid-cols-2 gap-2 mb-3">
                      <div className="bg-slate-800/70 rounded-lg p-2.5 text-center">
                        <p className="text-[10px] text-slate-500 uppercase">Total Return</p>
                        <p className={`text-base font-bold ${displayedBacktestResult!.summary.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {displayedBacktestResult!.summary.total_return_pct >= 0 ? '+' : ''}{displayedBacktestResult!.summary.total_return_pct}%
                        </p>
                      </div>
                      <div className="bg-slate-800/70 rounded-lg p-2.5 text-center">
                        <p className="text-[10px] text-slate-500 uppercase">Win Rate</p>
                        <p className="text-base font-bold text-white">{displayedBacktestResult!.summary.win_rate}%</p>
                      </div>
                      <div className="bg-slate-800/70 rounded-lg p-2.5 text-center">
                        <p className="text-[10px] text-slate-500 uppercase">Total Trades</p>
                        <p className="text-base font-bold text-white">{displayedBacktestResult!.summary.total_trades}</p>
                      </div>
                      <div className="bg-slate-800/70 rounded-lg p-2.5 text-center">
                        <p className="text-[10px] text-slate-500 uppercase">Max Drawdown</p>
                        <p className="text-base font-bold text-red-400">-{displayedBacktestResult!.summary.max_drawdown_pct}%</p>
                      </div>
                    </div>

                    {/* Capital */}
                    <div className="bg-slate-800/50 rounded-lg p-2.5 mb-3 flex items-center justify-between">
                      <span className="text-xs text-slate-400">Capital</span>
                      <span className="text-xs text-white">
                        {formatCurrency(displayedBacktestResult!.initial_capital)} → {formatCurrency(displayedBacktestResult!.final_capital)}
                      </span>
                    </div>

                    {/* More metrics */}
                    <div className="grid grid-cols-2 gap-x-4 gap-y-1 mb-3 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Sharpe</span>
                        <span className="text-white">{displayedBacktestResult!.summary.sharpe_ratio}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">P. Factor</span>
                        <span className="text-white">{displayedBacktestResult!.summary.profit_factor}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Avg Win</span>
                        <span className="text-green-400">+{displayedBacktestResult!.summary.avg_win_pct}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Avg Loss</span>
                        <span className="text-red-400">{displayedBacktestResult!.summary.avg_loss_pct}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Max Win</span>
                        <span className="text-green-400">+{displayedBacktestResult!.summary.max_win_pct}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Max Loss</span>
                        <span className="text-red-400">{displayedBacktestResult!.summary.max_loss_pct}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Annual Ret</span>
                        <span className={displayedBacktestResult!.summary.annual_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}>
                          {displayedBacktestResult!.summary.annual_return_pct}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Symbols</span>
                        <span className="text-white">{displayedBacktestResult!.summary.symbols_traded}/{displayedBacktestResult!.summary.symbols_scanned}</span>
                      </div>
                    </div>

                    {/* Tabs: symbols / trades */}
                    <div className="flex border-b border-slate-700 mb-3">
                      {(['summary', 'symbols', 'trades'] as const).map(tab => (
                        <button
                          key={tab}
                          onClick={() => setBtTab(tab)}
                          className={`px-3 py-1.5 text-[11px] font-medium capitalize transition ${
                            btTab === tab
                              ? 'text-purple-300 border-b-2 border-purple-400'
                              : 'text-slate-500 hover:text-slate-300'
                          }`}
                        >
                          {tab}
                        </button>
                      ))}
                    </div>

                    {/* Tab: Equity Curve Summary */}
                    {btTab === 'summary' && displayedBacktestResult!.equity_curve.length > 1 && (
                      <div className="space-y-2">
                        <p className="text-[10px] text-slate-500 uppercase">Equity Curve</p>
                        <div className="h-28 bg-slate-800/50 rounded-lg p-2 relative">
                          {(() => {
                            const curve = displayedBacktestResult!.equity_curve;
                            const minEq = Math.min(...curve.map(c => c.equity));
                            const maxEq = Math.max(...curve.map(c => c.equity));
                            const range = maxEq - minEq || 1;
                            const w = 100 / Math.max(curve.length - 1, 1);
                            const points = curve.map((c, i) => ({
                              x: i * w,
                              y: 100 - ((c.equity - minEq) / range) * 100,
                            }));
                            const pathD = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
                            const isProfit = curve[curve.length - 1].equity >= curve[0].equity;
                            return (
                              <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="w-full h-full">
                                <path d={pathD} fill="none" stroke={isProfit ? '#4ade80' : '#f87171'} strokeWidth="1.5" />
                              </svg>
                            );
                          })()}
                        </div>
                        {/* W/L bar */}
                        <div className="flex items-center gap-1">
                          <div
                            className="h-2 bg-green-500 rounded-l"
                            style={{ width: `${displayedBacktestResult!.summary.win_rate}%` }}
                          />
                          <div
                            className="h-2 bg-red-500 rounded-r"
                            style={{ width: `${100 - displayedBacktestResult!.summary.win_rate}%` }}
                          />
                        </div>
                        <div className="flex justify-between text-[10px]">
                          <span className="text-green-400">{displayedBacktestResult!.summary.winners}W</span>
                          <span className="text-red-400">{displayedBacktestResult!.summary.losers}L</span>
                        </div>
                      </div>
                    )}

                    {/* Tab: Per Symbol */}
                    {btTab === 'symbols' && (
                      <div className="max-h-[400px] overflow-y-auto custom-scrollbar space-y-1.5">
                        {displayedBacktestResult!.per_symbol.length > 0 ? displayedBacktestResult!.per_symbol.map(ps => (
                          <div key={ps.symbol} className="bg-slate-800/50 rounded-lg p-2.5 border border-slate-700/50">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-semibold text-white">{ps.symbol}</span>
                              <span className={`text-xs font-bold ${ps.total_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {ps.total_pnl_pct >= 0 ? '+' : ''}{ps.total_pnl_pct}%
                              </span>
                            </div>
                            <div className="grid grid-cols-3 gap-1 text-[10px]">
                              <span className="text-slate-500">Trades: <span className="text-white">{ps.total_trades}</span></span>
                              <span className="text-slate-500">WR: <span className="text-white">{ps.win_rate}%</span></span>
                              <span className="text-slate-500">Avg: <span className={ps.avg_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}>{ps.avg_pnl_pct}%</span></span>
                            </div>
                          </div>
                        )) : (
                          <p className="text-xs text-slate-500 text-center py-4">No symbols traded</p>
                        )}
                      </div>
                    )}

                    {/* Tab: Trade Log */}
                    {btTab === 'trades' && (
                      <div className="max-h-[400px] overflow-y-auto custom-scrollbar space-y-1">
                        {displayedBacktestResult!.all_trades.length > 0 ? displayedBacktestResult!.all_trades.map((t: any, i) => (
                          <div key={i} className="bg-slate-800/50 rounded p-2 border border-slate-700/30 text-[10px]">
                            <div className="flex items-center justify-between mb-0.5">
                              <span className="font-semibold text-white">{t.symbol}</span>
                              <span className={`font-bold ${t.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct}%
                              </span>
                            </div>
                            <div className="flex items-center justify-between text-slate-500">
                              <span>₹{t.entry_price} → ₹{t.exit_price}</span>
                              <span className={`px-1 py-0.5 rounded text-[9px] font-medium ${
                                t.exit_reason === 'TP' ? 'bg-green-500/20 text-green-300' :
                                t.exit_reason === 'SL' ? 'bg-red-500/20 text-red-300' :
                                t.exit_reason === 'TSL' ? 'bg-yellow-500/20 text-yellow-300' :
                                'bg-blue-500/20 text-blue-300'
                              }`}>{t.exit_reason}</span>
                            </div>
                            {applyZerodhaCharges && t.charges !== undefined && (
                              <div className="text-orange-300 mt-0.5">
                                Charges: ₹{Number(t.charges).toFixed(2)}
                              </div>
                            )}
                            <div className="text-slate-600 mt-0.5">
                              {t.entry_date} → {t.exit_date} ({t.holding_bars} bars)
                            </div>
                          </div>
                        )) : (
                          <p className="text-xs text-slate-500 text-center py-4">No trades generated</p>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Default empty state */}
                {!scanResult && !backtestResult && !backtesting && selectedId ? (
                  <div className="bg-slate-900/70 rounded-xl border border-slate-800 p-6 text-center">
                    <Play className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                    <p className="text-sm text-slate-400 mb-2">Click Execute or Backtest</p>
                    <p className="text-xs text-slate-500">
                      Execute scans live, Backtest replays historical candles
                    </p>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ) : (
          /* Empty state */
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center max-w-md">
              <Zap className="w-16 h-16 text-slate-700 mx-auto mb-4" />
              <h2 className="text-xl font-semibold text-white mb-2">Create Scanner</h2>
              <p className="text-sm text-slate-400 mb-6">
                Build condition-based strategies using technical indicators like TEMA, Stochastic, RSI, MACD, and more.
                Scan the market and execute trades automatically.
              </p>
              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={newStrategy}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-xl flex items-center gap-2"
                >
                  <Plus className="w-4 h-4" /> Create Strategy
                </button>
                <button
                  onClick={() => setShowPrebuilt(true)}
                  className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-white font-semibold rounded-xl flex items-center gap-2"
                >
                  <Star className="w-4 h-4 text-yellow-400" /> Browse Pre-built
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CreateScanner;
