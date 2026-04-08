import React, { useState, useEffect, useMemo } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  RefreshCcw,
  Info,
} from 'lucide-react';
import { optionsAPI } from '../lib/api';

interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

interface OptionData {
  ltp: number;
  change: number;
  change_percent: number;
  volume: number;
  oi: number;
  iv: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  bid: number;
  ask: number;
  intrinsic: number;
  time_value: number;
}

interface StrikeData {
  strike: number;
  call: OptionData | null;
  put: OptionData | null;
}

interface ChainData {
  symbol: string;
  spot: number;
  expiry: string;
  days_to_expiry: number;
  strikes: StrikeData[];
  atm_strike: number;
}

type BuildupLabel = 'Long Buildup' | 'Short Buildup' | 'Short Covering' | 'Long Unwinding';

interface OptionSignal {
  strike: number;
  side: 'CE' | 'PE';
  label: BuildupLabel;
  tone: 'bullish' | 'bearish' | 'neutral';
  score: number;
  changePercent: number;
  oi: number;
}

interface OptionAnalytics {
  totalCallOi: number;
  totalPutOi: number;
  totalCallVolume: number;
  totalPutVolume: number;
  pcr: number;
  supportStrike: number | null;
  resistanceStrike: number | null;
  maxPain: number | null;
  biasLabel: string;
  biasTone: string;
  biasNote: string;
  signals: OptionSignal[];
}

const OptionsChain: React.FC = () => {
  const [symbol, setSymbol] = useState<string>('NIFTY');
  const [expiry, setExpiry] = useState<string>('');
  const [expiries, setExpiries] = useState<string[]>([]);
  const [chainData, setChainData] = useState<ChainData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showGreeks, setShowGreeks] = useState<boolean>(true);

  useEffect(() => {
    fetchExpiries();
  }, [symbol]);

  useEffect(() => {
    if (expiry) {
      fetchChain();
    }
  }, [symbol, expiry]);

  const fetchExpiries = async () => {
    try {
      const response = await optionsAPI.getExpiries(symbol);
      const expiryList = response.data.expiries;
      setExpiries(expiryList);
      if (expiryList.length > 0 && !expiry) {
        setExpiry(expiryList[0]);
      }
    } catch (err) {
      console.error('Error fetching expiries:', err);
    }
  };

  const fetchChain = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await optionsAPI.getChain(symbol, expiry);
      setChainData(response.data);
      setLoading(false);
    } catch (err: any) {
      console.error('Chain error:', err);
      setError(err.response?.data?.detail || 'Failed to load options chain');
      setLoading(false);
    }
  };

  const formatNumber = (num: number | undefined | null): string => {
    if (num === undefined || num === null || Number.isNaN(num)) return '-';
    if (Math.abs(num) >= 100000) {
      return (num / 100000).toFixed(2) + 'L';
    }
    return num.toLocaleString('en-IN');
  };

  const formatDecimal = (num: number | undefined | null, digits = 2): string => {
    if (num === undefined || num === null || Number.isNaN(num)) return '—';
    return num.toFixed(digits);
  };

  const formatPercent = (num: number | undefined | null, digits = 1, signed = false): string => {
    if (num === undefined || num === null || Number.isNaN(num)) return '—';
    return `${signed && num >= 0 ? '+' : ''}${num.toFixed(digits)}%`;
  };

  const getDeltaColor = (delta: number): string => {
    if (delta > 0.7) return 'text-green-400';
    if (delta > 0.3) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getSignalClasses = (tone: OptionSignal['tone']) => {
    if (tone === 'bullish') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
    if (tone === 'bearish') return 'border-red-500/30 bg-red-500/10 text-red-300';
    return 'border-slate-600 bg-slate-800/70 text-slate-300';
  };

  const analytics = useMemo<OptionAnalytics | null>(() => {
    if (!chainData) return null;

    const totalCallOi = chainData.strikes.reduce((sum, item) => sum + (item.call?.oi || 0), 0);
    const totalPutOi = chainData.strikes.reduce((sum, item) => sum + (item.put?.oi || 0), 0);
    const totalCallVolume = chainData.strikes.reduce((sum, item) => sum + (item.call?.volume || 0), 0);
    const totalPutVolume = chainData.strikes.reduce((sum, item) => sum + (item.put?.volume || 0), 0);
    const callOis = chainData.strikes.map((item) => item.call?.oi || 0).filter((oi) => oi > 0);
    const putOis = chainData.strikes.map((item) => item.put?.oi || 0).filter((oi) => oi > 0);
    const avgCallOi = callOis.length ? callOis.reduce((sum, oi) => sum + oi, 0) / callOis.length : 0;
    const avgPutOi = putOis.length ? putOis.reduce((sum, oi) => sum + oi, 0) / putOis.length : 0;
    const atmIndex = chainData.strikes.findIndex((item) => item.strike === chainData.atm_strike);

    const buildSignal = (option: OptionData | null, side: 'CE' | 'PE', strike: number): OptionSignal | null => {
      if (!option) return null;

      const oi = option.oi || 0;
      const changePercent = option.change_percent ?? 0;
      const avgOi = side === 'CE' ? avgCallOi : avgPutOi;

      if (oi <= 0 || Math.abs(changePercent) < 0.5 || avgOi <= 0) {
        return null;
      }

      const oiRatio = oi / avgOi;
      let label: BuildupLabel | null = null;

      if (changePercent >= 0.5 && oiRatio >= 1.15) label = 'Long Buildup';
      else if (changePercent <= -0.5 && oiRatio >= 1.15) label = 'Short Buildup';
      else if (changePercent >= 0.5 && oiRatio <= 0.9) label = 'Short Covering';
      else if (changePercent <= -0.5 && oiRatio <= 0.9) label = 'Long Unwinding';

      if (!label) return null;

      const tone: OptionSignal['tone'] =
        side === 'CE'
          ? label === 'Long Buildup' || label === 'Short Covering'
            ? 'bullish'
            : 'bearish'
          : label === 'Long Buildup' || label === 'Short Covering'
            ? 'bearish'
            : 'bullish';

      const strikeIndex = chainData.strikes.findIndex((item) => item.strike === strike);
      const proximityBoost = atmIndex >= 0 && strikeIndex >= 0 ? Math.max(0, 4 - Math.abs(strikeIndex - atmIndex)) : 0;
      const score = Math.abs(changePercent) * 2 + Math.max(0, oiRatio - 1) * 8 + proximityBoost;

      return { strike, side, label, tone, score, changePercent, oi };
    };

    const focusStrikes = chainData.strikes.filter((_, index) => atmIndex === -1 || Math.abs(index - atmIndex) <= 4);
    const signals = focusStrikes
      .flatMap((item) => [buildSignal(item.call, 'CE', item.strike), buildSignal(item.put, 'PE', item.strike)])
      .filter((item): item is OptionSignal => Boolean(item))
      .sort((a, b) => b.score - a.score)
      .slice(0, 6);

    const supportStrike =
      chainData.strikes.reduce<StrikeData | null>((best, item) => {
        if (!best || (item.put?.oi || 0) > (best.put?.oi || 0)) return item;
        return best;
      }, null)?.strike ?? null;

    const resistanceStrike =
      chainData.strikes.reduce<StrikeData | null>((best, item) => {
        if (!best || (item.call?.oi || 0) > (best.call?.oi || 0)) return item;
        return best;
      }, null)?.strike ?? null;

    const maxPain = chainData.strikes.reduce(
      (best, candidate) => {
        const payout = chainData.strikes.reduce((total, item) => {
          const callLoss = (item.call?.oi || 0) * Math.max(candidate.strike - item.strike, 0);
          const putLoss = (item.put?.oi || 0) * Math.max(item.strike - candidate.strike, 0);
          return total + callLoss + putLoss;
        }, 0);

        return payout < best.payout ? { strike: candidate.strike, payout } : best;
      },
      { strike: chainData.atm_strike, payout: Number.POSITIVE_INFINITY }
    ).strike;

    const pcr = totalCallOi > 0 ? totalPutOi / totalCallOi : 0;
    const bullishScore =
      signals.filter((item) => item.tone === 'bullish').reduce((sum, item) => sum + item.score, 0) +
      (pcr > 1 ? Math.min((pcr - 1) * 12, 8) : 0);
    const bearishScore =
      signals.filter((item) => item.tone === 'bearish').reduce((sum, item) => sum + item.score, 0) +
      (pcr < 1 ? Math.min((1 - pcr) * 12, 8) : 0);

    let biasLabel = 'Balanced Setup';
    let biasTone = 'text-slate-200';
    let biasNote = `PCR ${pcr.toFixed(2)} with support near ${supportStrike ?? '—'} and resistance near ${resistanceStrike ?? '—'}.`;

    if (bullishScore - bearishScore > 4) {
      biasLabel = 'Bullish Bias';
      biasTone = 'text-emerald-300';
      biasNote = `Call short covering / put writing is stronger. Support is building near ${supportStrike ?? '—'}.`;
    } else if (bearishScore - bullishScore > 4) {
      biasLabel = 'Bearish Bias';
      biasTone = 'text-red-300';
      biasNote = `Call writing / put long buildup dominates. Resistance is clustered near ${resistanceStrike ?? '—'}.`;
    } else if (pcr >= 1.15) {
      biasLabel = 'Supportive PCR';
      biasTone = 'text-blue-300';
      biasNote = `Put OI is heavier than call OI. Dips may find support near ${supportStrike ?? '—'}.`;
    } else if (pcr <= 0.85) {
      biasLabel = 'Resistance Heavy';
      biasTone = 'text-orange-300';
      biasNote = `Call OI is dominating overhead. Watch ${resistanceStrike ?? '—'} for supply pressure.`;
    }

    return {
      totalCallOi,
      totalPutOi,
      totalCallVolume,
      totalPutVolume,
      pcr,
      supportStrike,
      resistanceStrike,
      maxPain,
      biasLabel,
      biasTone,
      biasNote,
      signals,
    };
  }, [chainData]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Options Chain</h1>
            <p className="text-slate-400">
              Real-time options data with Greeks and implied volatility
            </p>
          </div>
          <button
            onClick={fetchChain}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 rounded-lg text-white transition-colors"
          >
            <RefreshCcw size={18} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap gap-4 items-center">
          {/* Symbol Selector */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Symbol</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              <option value="NIFTY">NIFTY</option>
              <option value="BANKNIFTY">BANKNIFTY</option>
              <option value="FINNIFTY">FINNIFTY</option>
            </select>
          </div>

          {/* Expiry Selector */}
          <div>
            <label className="block text-sm text-slate-400 mb-1">Expiry</label>
            <select
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
              className="px-4 py-2 bg-slate-800 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              {expiries.map((exp) => (
                <option key={exp} value={exp}>
                  {new Date(exp).toLocaleDateString('en-IN', {
                    day: '2-digit',
                    month: 'short',
                    year: 'numeric',
                  })}
                </option>
              ))}
            </select>
          </div>

          {/* Greeks Toggle */}
          <div className="ml-auto">
            <label className="flex items-center gap-2 text-white cursor-pointer">
              <input
                type="checkbox"
                checked={showGreeks}
                onChange={(e) => setShowGreeks(e.target.checked)}
                className="w-4 h-4"
              />
              <span className="text-sm">Show Greeks</span>
            </label>
          </div>
        </div>
      </div>

      {/* Spot Info */}
      {chainData && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4 mb-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-slate-400 text-sm mb-1">Spot Price</div>
              <div className="text-white text-2xl font-bold">₹{chainData.spot.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-slate-400 text-sm mb-1">ATM Strike</div>
              <div className="text-white text-2xl font-bold">{chainData.atm_strike}</div>
            </div>
            <div>
              <div className="text-slate-400 text-sm mb-1">Days to Expiry</div>
              <div className="text-white text-2xl font-bold">{chainData.days_to_expiry}</div>
            </div>
            <div>
              <div className="text-slate-400 text-sm mb-1">Total Strikes</div>
              <div className="text-white text-2xl font-bold">{chainData.strikes.length}</div>
            </div>
          </div>
        </div>
      )}

      {/* Snapshot Analytics */}
      {analytics && (
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-6">
          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Activity size={18} className="text-blue-400" />
              <h3 className="text-white font-semibold">Chain Snapshot</h3>
            </div>
            <div className={`text-xl font-bold ${analytics.biasTone}`}>{analytics.biasLabel}</div>
            <p className="text-sm text-slate-400 mt-1">{analytics.biasNote}</p>
            <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
              <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <div className="text-slate-400 text-xs">PCR</div>
                <div className="text-white font-semibold mt-1">{analytics.pcr.toFixed(2)}</div>
              </div>
              <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <div className="text-slate-400 text-xs">Max Pain</div>
                <div className="text-white font-semibold mt-1">{analytics.maxPain ?? '—'}</div>
              </div>
              <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <div className="text-slate-400 text-xs">Support</div>
                <div className="text-emerald-300 font-semibold mt-1">{analytics.supportStrike ?? '—'}</div>
              </div>
              <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <div className="text-slate-400 text-xs">Resistance</div>
                <div className="text-red-300 font-semibold mt-1">{analytics.resistanceStrike ?? '—'}</div>
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp size={18} className="text-emerald-400" />
              <h3 className="text-white font-semibold">OI & Volume Breadth</h3>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <span className="text-slate-400">Total Call OI</span>
                <span className="text-white font-semibold">{formatNumber(analytics.totalCallOi)}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <span className="text-slate-400">Total Put OI</span>
                <span className="text-white font-semibold">{formatNumber(analytics.totalPutOi)}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <span className="text-slate-400">Call Volume</span>
                <span className="text-white font-semibold">{formatNumber(analytics.totalCallVolume)}</span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-slate-900/60 p-3 border border-slate-700">
                <span className="text-slate-400">Put Volume</span>
                <span className="text-white font-semibold">{formatNumber(analytics.totalPutVolume)}</span>
              </div>
            </div>
          </div>

          <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Info size={18} className="text-violet-400" />
              <h3 className="text-white font-semibold">Buildup Signals</h3>
            </div>
            <div className="space-y-2">
              {analytics.signals.length > 0 ? (
                analytics.signals.map((signal) => (
                  <div
                    key={`${signal.strike}-${signal.side}-${signal.label}`}
                    className={`rounded-lg border px-3 py-2 ${getSignalClasses(signal.tone)}`}
                  >
                    <div className="flex items-center justify-between gap-2 text-sm">
                      <span className="font-semibold">{signal.strike} {signal.side}</span>
                      <span className="text-[11px] uppercase tracking-wide">{signal.label}</span>
                    </div>
                    <div className="text-[11px] opacity-80 mt-1">
                      Premium {formatPercent(signal.changePercent, 1, true)} • OI {formatNumber(signal.oi)}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-slate-400">No strong buildup signal around ATM right now.</p>
              )}
            </div>
            <p className="text-[11px] text-slate-500 mt-3">
              Snapshot heuristics use premium move + relative OI concentration near ATM.
            </p>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 mb-6 text-red-400">
          <p>{error}</p>
        </div>
      )}

      {/* Options Chain Table */}
      {chainData && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/50">
                <tr>
                  {/* CALL Headers */}
                  <th className="px-2 py-3 text-center text-xs font-semibold text-green-400">OI</th>
                  <th className="px-2 py-3 text-center text-xs font-semibold text-green-400">Volume</th>
                  <th className="px-2 py-3 text-center text-xs font-semibold text-green-400">IV</th>
                  {showGreeks && (
                    <>
                      <th className="px-2 py-3 text-center text-xs font-semibold text-green-400">
                        Delta
                      </th>
                      <th className="px-2 py-3 text-center text-xs font-semibold text-green-400">
                        Theta
                      </th>
                    </>
                  )}
                  <th className="px-2 py-3 text-center text-xs font-semibold text-green-400">LTP</th>
                  <th className="px-2 py-3 text-center text-xs font-semibold text-green-400">Chg%</th>

                  {/* Strike */}
                  <th className="px-4 py-3 text-center text-xs font-semibold text-white bg-slate-800">
                    STRIKE
                  </th>

                  {/* PUT Headers */}
                  <th className="px-2 py-3 text-center text-xs font-semibold text-red-400">Chg%</th>
                  <th className="px-2 py-3 text-center text-xs font-semibold text-red-400">LTP</th>
                  {showGreeks && (
                    <>
                      <th className="px-2 py-3 text-center text-xs font-semibold text-red-400">
                        Delta
                      </th>
                      <th className="px-2 py-3 text-center text-xs font-semibold text-red-400">
                        Theta
                      </th>
                    </>
                  )}
                  <th className="px-2 py-3 text-center text-xs font-semibold text-red-400">IV</th>
                  <th className="px-2 py-3 text-center text-xs font-semibold text-red-400">Volume</th>
                  <th className="px-2 py-3 text-center text-xs font-semibold text-red-400">OI</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {chainData.strikes.map((strike) => {
                  const isATM = strike.strike === chainData.atm_strike;
                  const isITMCall = strike.strike < chainData.spot;
                  const isITMPut = strike.strike > chainData.spot;

                  return (
                    <tr
                      key={strike.strike}
                      className={`hover:bg-slate-700/30 transition-colors ${
                        isATM ? 'bg-blue-900/20' : ''
                      }`}
                    >
                      {/* CALL Data */}
                      <td className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}>
                        <span className="text-slate-300 text-xs">
                          {formatNumber(strike.call?.oi)}
                        </span>
                      </td>
                      <td className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}>
                        <span className="text-slate-300 text-xs">
                          {formatNumber(strike.call?.volume)}
                        </span>
                      </td>
                      <td className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}>
                        <span className="text-slate-300 text-xs">{formatPercent(strike.call?.iv, 1)}</span>
                      </td>
                      {showGreeks && (
                        <>
                          <td
                            className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}
                          >
                            <span className={`text-xs font-medium ${getDeltaColor(strike.call?.delta || 0)}`}>
                              {formatDecimal(strike.call?.delta, 2)}
                            </span>
                          </td>
                          <td
                            className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}
                          >
                            <span className="text-slate-300 text-xs">
                              {formatDecimal(strike.call?.theta, 2)}
                            </span>
                          </td>
                        </>
                      )}
                      <td className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}>
                        <span className="text-white font-medium">
                          {formatDecimal(strike.call?.ltp, 2)}
                        </span>
                      </td>
                      <td className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}>
                        <span
                          className={`text-xs font-medium ${
                            (strike.call?.change_percent || 0) >= 0
                              ? 'text-green-400'
                              : 'text-red-400'
                          }`}
                        >
                          {formatPercent(strike.call?.change_percent, 1, true)}
                        </span>
                      </td>

                      {/* STRIKE */}
                      <td className="px-4 py-2 text-center text-white font-bold bg-slate-800">
                        {strike.strike}
                        {isATM && (
                          <span className="ml-2 text-xs text-blue-400 font-normal">ATM</span>
                        )}
                      </td>

                      {/* PUT Data */}
                      <td className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}>
                        <span
                          className={`text-xs font-medium ${
                            (strike.put?.change_percent || 0) >= 0
                              ? 'text-green-400'
                              : 'text-red-400'
                          }`}
                        >
                          {formatPercent(strike.put?.change_percent, 1, true)}
                        </span>
                      </td>
                      <td className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}>
                        <span className="text-white font-medium">
                          {formatDecimal(strike.put?.ltp, 2)}
                        </span>
                      </td>
                      {showGreeks && (
                        <>
                          <td
                            className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}
                          >
                            <span className={`text-xs font-medium ${getDeltaColor(Math.abs(strike.put?.delta || 0))}`}>
                              {formatDecimal(strike.put?.delta, 2)}
                            </span>
                          </td>
                          <td
                            className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}
                          >
                            <span className="text-slate-300 text-xs">
                              {formatDecimal(strike.put?.theta, 2)}
                            </span>
                          </td>
                        </>
                      )}
                      <td className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}>
                        <span className="text-slate-300 text-xs">{formatPercent(strike.put?.iv, 1)}</span>
                      </td>
                      <td className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}>
                        <span className="text-slate-300 text-xs">
                          {formatNumber(strike.put?.volume)}
                        </span>
                      </td>
                      <td className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}>
                        <span className="text-slate-300 text-xs">
                          {formatNumber(strike.put?.oi)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && !chainData && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <RefreshCcw size={48} className="mx-auto mb-4 text-slate-600 animate-spin" />
          <h3 className="text-xl font-semibold text-white mb-2">Loading Options Chain...</h3>
          <p className="text-slate-400">Fetching data from market</p>
        </div>
      )}

      {/* Legend */}
      <div className="mt-6 bg-slate-800/30 border border-slate-700 rounded-lg p-4">
        <div className="flex flex-wrap gap-6 text-sm text-slate-400">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-green-900/20 border border-green-900/50 rounded"></div>
            <span>ITM (In The Money)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-blue-900/20 border border-blue-900/50 rounded"></div>
            <span>ATM (At The Money)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 bg-red-900/20 border border-red-900/50 rounded"></div>
            <span>ITM Put</span>
          </div>
          <div className="ml-auto text-xs">
            <span>Delta: Position sensitivity | Theta: Time decay | IV: Implied Volatility</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OptionsChain;
