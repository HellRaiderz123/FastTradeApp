import React, { useState, useEffect } from 'react';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  RefreshCcw,
  Download,
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

  const formatNumber = (num: number | undefined): string => {
    if (num === undefined || num === null) return '-';
    if (Math.abs(num) >= 100000) {
      return (num / 100000).toFixed(2) + 'L';
    }
    return num.toLocaleString();
  };

  const getDeltaColor = (delta: number): string => {
    if (delta > 0.7) return 'text-green-400';
    if (delta > 0.3) return 'text-yellow-400';
    return 'text-red-400';
  };

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
                        <span className="text-slate-300 text-xs">{strike.call?.iv.toFixed(1)}%</span>
                      </td>
                      {showGreeks && (
                        <>
                          <td
                            className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}
                          >
                            <span className={`text-xs font-medium ${getDeltaColor(strike.call?.delta || 0)}`}>
                              {strike.call?.delta.toFixed(2)}
                            </span>
                          </td>
                          <td
                            className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}
                          >
                            <span className="text-slate-300 text-xs">
                              {strike.call?.theta.toFixed(2)}
                            </span>
                          </td>
                        </>
                      )}
                      <td className={`px-2 py-2 text-center ${isITMCall ? 'bg-green-900/10' : ''}`}>
                        <span className="text-white font-medium">
                          {strike.call?.ltp.toFixed(2)}
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
                          {(strike.call?.change_percent || 0) >= 0 ? '+' : ''}
                          {strike.call?.change_percent.toFixed(1)}%
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
                          {(strike.put?.change_percent || 0) >= 0 ? '+' : ''}
                          {strike.put?.change_percent.toFixed(1)}%
                        </span>
                      </td>
                      <td className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}>
                        <span className="text-white font-medium">
                          {strike.put?.ltp.toFixed(2)}
                        </span>
                      </td>
                      {showGreeks && (
                        <>
                          <td
                            className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}
                          >
                            <span className={`text-xs font-medium ${getDeltaColor(Math.abs(strike.put?.delta || 0))}`}>
                              {strike.put?.delta.toFixed(2)}
                            </span>
                          </td>
                          <td
                            className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}
                          >
                            <span className="text-slate-300 text-xs">
                              {strike.put?.theta.toFixed(2)}
                            </span>
                          </td>
                        </>
                      )}
                      <td className={`px-2 py-2 text-center ${isITMPut ? 'bg-red-900/10' : ''}`}>
                        <span className="text-slate-300 text-xs">{strike.put?.iv.toFixed(1)}%</span>
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
