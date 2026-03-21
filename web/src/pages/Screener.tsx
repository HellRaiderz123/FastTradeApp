import React, { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Download,
  RefreshCcw,
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  Zap,
} from 'lucide-react';
import { screenerAPI } from '../lib/api';

interface ScreenerFilters {
  min_price?: number;
  max_price?: number;
  min_change_percent?: number;
  max_change_percent?: number;
  min_volume?: number;
  rsi_min?: number;
  rsi_max?: number;
  price_above_ma?: number;
  price_below_ma?: number;
  sectors?: string[];
  min_market_cap?: number;
  max_market_cap?: number;
  // Fundamentals
  min_pe_ratio?: number;
  max_pe_ratio?: number;
  min_pb_ratio?: number;
  max_pb_ratio?: number;
  min_dividend_yield?: number;
  max_debt_to_equity?: number;
  min_roe?: number;
  // 52w proximity
  near_52w_high?: boolean;
  near_52w_low?: boolean;
  sort_by?: string;
  sort_order?: string;
}

interface StockResult {
  symbol: string;
  name: string;
  ltp: number;
  change: number;
  change_percent: number;
  volume: number;
  volume_lakhs: number;
  rsi: number;
  sector: string;
  market_cap: number;
  market_cap_cr: number;
  ma_20: number;
  ma_50: number;
  open: number;
  high: number;
  low: number;
}

interface Preset {
  id: string;
  name: string;
  description: string;
  filters: ScreenerFilters;
  isCustom?: boolean;
}

const CUSTOM_PRESETS_KEY = 'screener_custom_presets';

function loadCustomPresets(): Preset[] {
  try {
    return JSON.parse(localStorage.getItem(CUSTOM_PRESETS_KEY) || '[]');
  } catch {
    return [];
  }
}

function saveCustomPresets(presets: Preset[]) {
  localStorage.setItem(CUSTOM_PRESETS_KEY, JSON.stringify(presets));
}

const Screener: React.FC = () => {
  const [filters, setFilters] = useState<ScreenerFilters>({
    sort_by: 'change_percent',
    sort_order: 'desc',
  });
  const [results, setResults] = useState<StockResult[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [customPresets, setCustomPresets] = useState<Preset[]>(loadCustomPresets);
  const [showFilters, setShowFilters] = useState<boolean>(true);
  const [showFundamentals, setShowFundamentals] = useState<boolean>(false);
  const [totalScanned, setTotalScanned] = useState<number>(0);
  const [savePresetName, setSavePresetName] = useState<string>('');
  const [showSavePreset, setShowSavePreset] = useState<boolean>(false);

  // Fetch presets on mount
  useEffect(() => {
    fetchPresets();
  }, []);

  const fetchPresets = async () => {
    try {
      const response = await screenerAPI.getPresets();
      setPresets(response.data.presets);
    } catch (err) {
      console.error('Error fetching presets:', err);
    }
  };

  const runScreener = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await screenerAPI.filterStocks(filters);
      setResults(response.data.results);
      setTotalScanned(response.data.total_scanned);
      setLoading(false);
    } catch (err: any) {
      console.error('Screener error:', err);
      setError(err.response?.data?.detail || 'Failed to run screener');
      setLoading(false);
    }
  };

  const applyPreset = async (preset: Preset) => {
    setFilters(preset.filters);
    // Auto-run after applying preset
    setTimeout(() => runScreener(), 100);
  };

  const resetFilters = () => {
    setFilters({
      sort_by: 'change_percent',
      sort_order: 'desc',
    });
    setResults([]);
  };

  const saveCurrentPreset = () => {
    if (!savePresetName.trim()) return;
    const newPreset: Preset = {
      id: `custom_${Date.now()}`,
      name: savePresetName.trim(),
      description: 'Custom saved preset',
      filters: { ...filters },
      isCustom: true,
    };
    const updated = [...customPresets, newPreset];
    setCustomPresets(updated);
    saveCustomPresets(updated);
    setSavePresetName('');
    setShowSavePreset(false);
  };

  const deleteCustomPreset = (id: string) => {
    const updated = customPresets.filter((p) => p.id !== id);
    setCustomPresets(updated);
    saveCustomPresets(updated);
  };

  const exportResults = () => {
    if (results.length === 0) return;

    const csv = [
      ['Symbol', 'Price', 'Change%', 'Volume (L)', 'RSI', 'Sector', 'Market Cap (Cr)'],
      ...results.map((r) => [
        r.symbol,
        r.ltp,
        r.change_percent,
        r.volume_lakhs,
        r.rsi,
        r.sector,
        r.market_cap_cr,
      ]),
    ]
      .map((row) => row.join(','))
      .join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `screener_results_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Stock Screener</h1>
            <p className="text-slate-400">
              Filter NIFTY 50 stocks with technical & fundamental criteria
            </p>
          </div>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors"
          >
            <Filter size={18} />
            {showFilters ? 'Hide Filters' : 'Show Filters'}
          </button>
        </div>

        {/* Quick Presets */}
        <div className="flex flex-wrap gap-2">
          {presets.map((preset) => (
            <button
              key={preset.id}
              onClick={() => applyPreset(preset)}
              className="px-4 py-2 bg-slate-800 hover:bg-blue-600 rounded-lg text-sm text-white transition-colors group"
              title={preset.description}
            >
              <div className="flex items-center gap-2">
                {preset.id === 'breakout' && <TrendingUp size={16} />}
                {preset.id === 'oversold' && <TrendingDown size={16} />}
                {preset.id === 'high_volume' && <BarChart3 size={16} />}
                {preset.id === 'trending_up' && <Zap size={16} />}
                {!['breakout', 'oversold', 'high_volume', 'trending_up'].includes(preset.id) && (
                  <Activity size={16} />
                )}
                {preset.name}
              </div>
            </button>
          ))}
          {customPresets.map((preset) => (
            <div key={preset.id} className="flex items-center gap-1">
              <button
                onClick={() => applyPreset(preset)}
                className="px-4 py-2 bg-purple-900/50 hover:bg-purple-700 border border-purple-700 rounded-lg text-sm text-white transition-colors"
                title={preset.description}
              >
                <div className="flex items-center gap-2">
                  <Activity size={16} />
                  {preset.name}
                </div>
              </button>
              <button
                onClick={() => deleteCustomPreset(preset.id)}
                className="px-2 py-2 bg-slate-800 hover:bg-red-900/50 rounded-lg text-slate-400 hover:text-red-400 transition-colors text-xs"
                title="Delete preset"
              >✕</button>
            </div>
          ))}
        </div>
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Price Range */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Price Range (₹)
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="Min"
                  value={filters.min_price || ''}
                  onChange={(e) =>
                    setFilters({ ...filters, min_price: Number(e.target.value) || undefined })
                  }
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <input
                  type="number"
                  placeholder="Max"
                  value={filters.max_price || ''}
                  onChange={(e) =>
                    setFilters({ ...filters, max_price: Number(e.target.value) || undefined })
                  }
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Change % Range */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Change % Range
              </label>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="Min"
                  step="0.1"
                  value={filters.min_change_percent ?? ''}
                  onChange={(e) =>
                    setFilters({
                      ...filters,
                      min_change_percent: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <input
                  type="number"
                  placeholder="Max"
                  step="0.1"
                  value={filters.max_change_percent ?? ''}
                  onChange={(e) =>
                    setFilters({
                      ...filters,
                      max_change_percent: e.target.value ? Number(e.target.value) : undefined,
                    })
                  }
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>

            {/* RSI Range */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">RSI Range</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="Min (0-100)"
                  min="0"
                  max="100"
                  value={filters.rsi_min || ''}
                  onChange={(e) =>
                    setFilters({ ...filters, rsi_min: Number(e.target.value) || undefined })
                  }
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
                <input
                  type="number"
                  placeholder="Max (0-100)"
                  min="0"
                  max="100"
                  value={filters.rsi_max || ''}
                  onChange={(e) =>
                    setFilters({ ...filters, rsi_max: Number(e.target.value) || undefined })
                  }
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                />
              </div>
            </div>

            {/* Min Volume */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Min Volume
              </label>
              <input
                type="number"
                placeholder="e.g., 1000000"
                value={filters.min_volume || ''}
                onChange={(e) =>
                  setFilters({ ...filters, min_volume: Number(e.target.value) || undefined })
                }
                className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
              />
            </div>

            {/* Sort By */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Sort By</label>
              <select
                value={filters.sort_by || 'change_percent'}
                onChange={(e) => setFilters({ ...filters, sort_by: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="change_percent">Change %</option>
                <option value="volume">Volume</option>
                <option value="price">Price</option>
                <option value="rsi">RSI</option>
                <option value="market_cap">Market Cap</option>
              </select>
            </div>

            {/* Sort Order */}
            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Sort Order</label>
              <select
                value={filters.sort_order || 'desc'}
                onChange={(e) => setFilters({ ...filters, sort_order: e.target.value })}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                <option value="desc">Descending</option>
                <option value="asc">Ascending</option>
              </select>
            </div>
          </div>

          {/* Fundamentals Toggle */}
          <div className="mt-4">
            <button
              onClick={() => setShowFundamentals(!showFundamentals)}
              className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              {showFundamentals ? '▲ Hide' : '▼ Show'} Fundamental Filters
            </button>
          </div>

          {showFundamentals && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-4 pt-4 border-t border-slate-700">
              {/* P/E Ratio */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">P/E Ratio</label>
                <div className="flex gap-2">
                  <input type="number" placeholder="Min" value={filters.min_pe_ratio || ''}
                    onChange={(e) => setFilters({ ...filters, min_pe_ratio: Number(e.target.value) || undefined })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                  <input type="number" placeholder="Max" value={filters.max_pe_ratio || ''}
                    onChange={(e) => setFilters({ ...filters, max_pe_ratio: Number(e.target.value) || undefined })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
              </div>
              {/* P/B Ratio */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">P/B Ratio</label>
                <div className="flex gap-2">
                  <input type="number" placeholder="Min" value={filters.min_pb_ratio || ''}
                    onChange={(e) => setFilters({ ...filters, min_pb_ratio: Number(e.target.value) || undefined })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                  <input type="number" placeholder="Max" value={filters.max_pb_ratio || ''}
                    onChange={(e) => setFilters({ ...filters, max_pb_ratio: Number(e.target.value) || undefined })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none" />
                </div>
              </div>
              {/* Min Dividend Yield */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Min Dividend Yield (%)</label>
                <input type="number" placeholder="e.g. 2.0" step="0.1" value={filters.min_dividend_yield || ''}
                  onChange={(e) => setFilters({ ...filters, min_dividend_yield: Number(e.target.value) || undefined })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none" />
              </div>
              {/* Max Debt/Equity */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Max Debt/Equity</label>
                <input type="number" placeholder="e.g. 1.0" step="0.1" value={filters.max_debt_to_equity || ''}
                  onChange={(e) => setFilters({ ...filters, max_debt_to_equity: Number(e.target.value) || undefined })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none" />
              </div>
              {/* Min ROE */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">Min ROE (%)</label>
                <input type="number" placeholder="e.g. 15" value={filters.min_roe || ''}
                  onChange={(e) => setFilters({ ...filters, min_roe: Number(e.target.value) || undefined })}
                  className="w-full px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:outline-none" />
              </div>
              {/* 52W Proximity */}
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-2">52-Week Proximity</label>
                <div className="flex gap-3">
                  <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                    <input type="checkbox" checked={!!filters.near_52w_high}
                      onChange={(e) => setFilters({ ...filters, near_52w_high: e.target.checked || undefined })}
                      className="w-4 h-4" />
                    Near High
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-300 cursor-pointer">
                    <input type="checkbox" checked={!!filters.near_52w_low}
                      onChange={(e) => setFilters({ ...filters, near_52w_low: e.target.checked || undefined })}
                      className="w-4 h-4" />
                    Near Low
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-3 mt-6">
            <button
              onClick={runScreener}
              disabled={loading}
              className="flex items-center gap-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 rounded-lg text-white font-medium transition-colors"
            >
              {loading ? (
                <>
                  <RefreshCcw size={18} className="animate-spin" />
                  Scanning...
                </>
              ) : (
                <>
                  <Search size={18} />
                  Run Screener
                </>
              )}
            </button>
            <button
              onClick={resetFilters}
              className="flex items-center gap-2 px-6 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white transition-colors"
            >
              <RefreshCcw size={18} />
              Reset
            </button>
            <button
              onClick={() => setShowSavePreset(!showSavePreset)}
              className="flex items-center gap-2 px-6 py-2 bg-purple-700 hover:bg-purple-600 rounded-lg text-white transition-colors"
            >
              Save Preset
            </button>
            {results.length > 0 && (
              <button
                onClick={exportResults}
                className="flex items-center gap-2 px-6 py-2 bg-green-600 hover:bg-green-700 rounded-lg text-white transition-colors ml-auto"
              >
                <Download size={18} />
                Export CSV
              </button>
            )}
          </div>
          {showSavePreset && (
            <div className="flex gap-2 mt-3">
              <input
                type="text"
                placeholder="Preset name..."
                value={savePresetName}
                onChange={(e) => setSavePresetName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && saveCurrentPreset()}
                className="flex-1 px-3 py-2 bg-slate-900 border border-slate-600 rounded-lg text-white focus:ring-2 focus:ring-purple-500 focus:outline-none"
              />
              <button onClick={saveCurrentPreset} className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-white transition-colors">
                Save
              </button>
            </div>
          )}
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/20 border border-red-500 rounded-lg p-4 mb-6 text-red-400">
          <p>{error}</p>
        </div>
      )}

      {/* Results Stats */}
      {results.length > 0 && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between">
            <div className="text-white">
              <span className="text-2xl font-bold">{results.length}</span>
              <span className="text-slate-400 ml-2">
                stocks matched out of {totalScanned} scanned
              </span>
            </div>
            <div className="text-slate-400 text-sm">
              Last updated: {new Date().toLocaleTimeString()}
            </div>
          </div>
        </div>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-slate-900/50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-slate-300">
                    Symbol
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-300">
                    LTP
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-300">
                    Change %
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-300">
                    Volume (L)
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-300">
                    RSI
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-slate-300">
                    Sector
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-300">
                    Mkt Cap (Cr)
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-300">
                    P/E
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-semibold text-slate-300">
                    ROE%
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {results.map((stock, index) => (
                  <tr
                    key={stock.symbol}
                    className="hover:bg-slate-700/30 transition-colors"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{stock.symbol}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right text-white font-medium">
                      ₹{stock.ltp.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`font-medium ${
                          stock.change_percent >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}
                      >
                        {stock.change_percent >= 0 ? '+' : ''}
                        {stock.change_percent.toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {stock.volume_lakhs.toFixed(2)}L
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span
                        className={`font-medium ${
                          stock.rsi > 70
                            ? 'text-red-400'
                            : stock.rsi < 30
                            ? 'text-green-400'
                            : 'text-slate-300'
                        }`}
                      >
                        {stock.rsi.toFixed(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{stock.sector}</td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      ₹{stock.market_cap_cr.toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {(stock as any).pe_ratio?.toFixed(1) ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-300">
                      {(stock as any).roe?.toFixed(1) ?? '—'}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty State */}
      {results.length === 0 && !loading && !error && (
        <div className="bg-slate-800/50 backdrop-blur-sm border border-slate-700 rounded-xl p-12 text-center">
          <Search size={48} className="mx-auto mb-4 text-slate-600" />
          <h3 className="text-xl font-semibold text-white mb-2">No Results Yet</h3>
          <p className="text-slate-400 mb-6">
            Set your filters and click "Run Screener" to find matching stocks
          </p>
          <button
            onClick={runScreener}
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded-lg text-white font-medium transition-colors"
          >
            <Search size={20} />
            Run Screener
          </button>
        </div>
      )}
    </div>
  );
};

export default Screener;
