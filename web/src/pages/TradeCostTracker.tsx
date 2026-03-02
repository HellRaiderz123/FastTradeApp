import React, { useState, useEffect } from 'react';
import { DollarSign, TrendingUp, Calculator, History, Settings } from 'lucide-react';
import { tradeCostAPI } from '../lib/api';
import { useToast } from '../components/Toast';

interface CostBreakdown {
  trade_value: number;
  brokerage: number;
  stt_ctt: number;
  exchange_txn_charge: number;
  gst: number;
  sebi_charges: number;
  stamp_duty: number;
  total_cost: number;
  net_value: number;
  cost_pct: number;
}

interface CostSummary {
  total_costs: number;
  total_brokerage: number;
  total_stt: number;
  total_gst: number;
  total_trades: number;
  avg_cost_per_trade: number;
}

const TradeCostTracker: React.FC = () => {
  const { showToast } = useToast();
  const [activeTab, setActiveTab] = useState<'calculator' | 'history' | 'summary'>('calculator');
  
  // Calculator state
  const [symbol, setSymbol] = useState('NIFTY24FEB48000CE');
  const [tradeType, setTradeType] = useState<'BUY' | 'SELL'>('BUY');
  const [segment, setSegment] = useState<'EQUITY' | 'FNO'>('FNO');
  const [productType, setProductType] = useState<'DELIVERY' | 'INTRADAY' | 'OPTIONS' | 'FUTURES'>('OPTIONS');
  const [quantity, setQuantity] = useState(50);
  const [price, setPrice] = useState(100);
  const [costBreakdown, setCostBreakdown] = useState<CostBreakdown | null>(null);
  const [calculating, setCalculating] = useState(false);
  
  // Summary state
  const [summary, setSummary] = useState<CostSummary | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  
  // History state
  const [history, setHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (activeTab === 'summary') {
      loadSummary();
    } else if (activeTab === 'history') {
      loadHistory();
    }
  }, [activeTab]);

  const loadSummary = async () => {
    setLoadingSummary(true);
    try {
      const response = await tradeCostAPI.getSummary();
      setSummary(response.data);
    } catch (err) {
      console.error('Failed to load summary:', err);
    } finally {
      setLoadingSummary(false);
    }
  };

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await tradeCostAPI.getHistory(50);
      setHistory(response.data.costs || []);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setLoadingHistory(false);
    }
  };

  const calculateCosts = async () => {
    setCalculating(true);
    try {
      const response = await tradeCostAPI.calculate({
        symbol,
        trade_type: tradeType,
        segment,
        product_type: productType,
        quantity,
        price,
      });
      setCostBreakdown(response.data);
    } catch (err: any) {
      console.error('Failed to calculate costs:', err);
      showToast('error', 'Calculation Failed', err.response?.data?.detail || 'Failed to calculate costs');
    } finally {
      setCalculating(false);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
    }).format(value);
  };

  const toSafeNumber = (value: unknown, fallback = 0): number => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  };

  const formatFixed = (value: unknown, digits = 2): string => {
    return toSafeNumber(value).toFixed(digits);
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <DollarSign className="w-8 h-8 text-green-500" />
          <div>
            <h1 className="text-3xl font-bold text-white">Trade Cost Tracker</h1>
            <p className="text-gray-400 mt-1">
              Calculate and track brokerage, STT, GST, and other trading charges
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-gray-800">
          <button
            onClick={() => setActiveTab('calculator')}
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'calculator'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <Calculator className="w-4 h-4" />
              Calculator
            </div>
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'history'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <History className="w-4 h-4" />
              History
            </div>
          </button>
          <button
            onClick={() => setActiveTab('summary')}
            className={`px-6 py-3 font-semibold transition-colors ${
              activeTab === 'summary'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Summary
            </div>
          </button>
        </div>

        {/* Calculator Tab */}
        {activeTab === 'calculator' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Input Form */}
            <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
              <h2 className="text-lg font-semibold text-white mb-4">Trade Details</h2>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-2">Symbol</label>
                  <input
                    type="text"
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="e.g., NIFTY24FEB48000CE"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Trade Type</label>
                    <select
                      value={tradeType}
                      onChange={(e) => setTradeType(e.target.value as 'BUY' | 'SELL')}
                      title="Trade Type"
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Segment</label>
                    <select
                      value={segment}
                      onChange={(e) => setSegment(e.target.value as 'EQUITY' | 'FNO')}
                      title="Segment"
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="FNO">F&O</option>
                      <option value="EQUITY">Equity</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-2">Product Type</label>
                  <select
                    value={productType}
                    onChange={(e) => setProductType(e.target.value as any)}
                    title="Product Type"
                    className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="OPTIONS">Options</option>
                    <option value="FUTURES">Futures</option>
                    <option value="INTRADAY">Intraday</option>
                    <option value="DELIVERY">Delivery</option>
                  </select>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Quantity</label>
                    <input
                      type="number"
                      value={quantity}
                      onChange={(e) => setQuantity(parseInt(e.target.value) || 0)}
                      title="Quantity"
                      placeholder="Enter quantity"
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm text-gray-400 mb-2">Price (₹)</label>
                    <input
                      type="number"
                      step="0.01"
                      value={price}
                      onChange={(e) => setPrice(parseFloat(e.target.value) || 0)}
                      title="Price"
                      placeholder="Enter price"
                      className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>

                <button
                  onClick={calculateCosts}
                  disabled={calculating}
                  className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-lg transition-colors"
                >
                  {calculating ? 'Calculating...' : 'Calculate Costs'}
                </button>
              </div>
            </div>

            {/* Cost Breakdown */}
            <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
              <h2 className="text-lg font-semibold text-white mb-4">Cost Breakdown</h2>
              
              {!costBreakdown ? (
                <div className="text-center py-12 text-gray-500">
                  <Calculator className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>Enter trade details and click "Calculate Costs"</p>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex justify-between items-center py-2 border-b border-gray-800">
                    <span className="text-gray-400">Trade Value</span>
                    <span className="text-white font-semibold">{formatCurrency(costBreakdown.trade_value)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-400">Brokerage</span>
                    <span className="text-red-400">{formatCurrency(costBreakdown.brokerage)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-400">STT/CTT</span>
                    <span className="text-red-400">{formatCurrency(costBreakdown.stt_ctt)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-400">Exchange Charges</span>
                    <span className="text-red-400">{formatCurrency(costBreakdown.exchange_txn_charge)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-400">GST (18%)</span>
                    <span className="text-red-400">{formatCurrency(costBreakdown.gst)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-400">SEBI Charges</span>
                    <span className="text-red-400">{formatCurrency(costBreakdown.sebi_charges)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-2">
                    <span className="text-gray-400">Stamp Duty</span>
                    <span className="text-red-400">{formatCurrency(costBreakdown.stamp_duty)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-3 border-t border-gray-700 mt-3">
                    <span className="text-white font-semibold">Total Costs</span>
                    <span className="text-red-400 font-bold text-lg">{formatCurrency(costBreakdown.total_cost)}</span>
                  </div>
                  
                  <div className="flex justify-between items-center py-3 bg-gray-800 rounded-lg px-4">
                    <span className="text-white font-semibold">Net Value ({tradeType})</span>
                    <span className="text-green-400 font-bold text-lg">{formatCurrency(costBreakdown.net_value)}</span>
                  </div>
                  
                  <div className="text-center text-sm text-gray-500 mt-4">
                    Cost as % of trade value: <span className="text-yellow-400 font-semibold">{formatFixed(costBreakdown.cost_pct, 4)}%</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Summary Tab */}
        {activeTab === 'summary' && (
          <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
            <h2 className="text-lg font-semibold text-white mb-6">Trading Costs Summary</h2>
            
            {loadingSummary ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              </div>
            ) : summary ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Total Costs</p>
                  <p className="text-2xl font-bold text-red-400">{formatCurrency(summary.total_costs)}</p>
                </div>
                
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Total Brokerage</p>
                  <p className="text-2xl font-bold text-white">{formatCurrency(summary.total_brokerage)}</p>
                </div>
                
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Total STT</p>
                  <p className="text-2xl font-bold text-white">{formatCurrency(summary.total_stt)}</p>
                </div>
                
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Total GST</p>
                  <p className="text-2xl font-bold text-white">{formatCurrency(summary.total_gst)}</p>
                </div>
                
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Total Trades</p>
                  <p className="text-2xl font-bold text-blue-400">{summary.total_trades}</p>
                </div>
                
                <div className="bg-gray-800 rounded-lg p-4">
                  <p className="text-gray-400 text-sm mb-1">Avg Cost/Trade</p>
                  <p className="text-2xl font-bold text-yellow-400">{formatCurrency(summary.avg_cost_per_trade)}</p>
                </div>
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">No data available</p>
            )}
          </div>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <div className="bg-gray-900 rounded-lg border border-gray-800 overflow-hidden">
            <div className="p-4 border-b border-gray-800">
              <h2 className="text-lg font-semibold text-white">Trade Cost History</h2>
            </div>
            
            {loadingHistory ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              </div>
            ) : history.length === 0 ? (
              <p className="text-gray-500 text-center py-12">No trade history available</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-800">
                    <tr>
                      <th className="text-left p-3 text-gray-400">Symbol</th>
                      <th className="text-left p-3 text-gray-400">Type</th>
                      <th className="text-right p-3 text-gray-400">Qty</th>
                      <th className="text-right p-3 text-gray-400">Price</th>
                      <th className="text-right p-3 text-gray-400">Trade Value</th>
                      <th className="text-right p-3 text-gray-400">Brokerage</th>
                      <th className="text-right p-3 text-gray-400">STT</th>
                      <th className="text-right p-3 text-gray-400">Total Cost</th>
                      <th className="text-right p-3 text-gray-400">Net Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((item, idx) => (
                      <tr key={item.id} className={`border-b border-gray-800 ${idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-900/50'}`}>
                        <td className="p-3 text-white">{item.symbol}</td>
                        <td className="p-3">
                          <span className={`px-2 py-1 rounded text-xs ${item.trade_type === 'BUY' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}`}>
                            {item.trade_type}
                          </span>
                        </td>
                        <td className="p-3 text-right text-white">{item.quantity}</td>
                        <td className="p-3 text-right text-white">₹{formatFixed(item.price, 2)}</td>
                        <td className="p-3 text-right text-white">₹{formatFixed(item.trade_value, 2)}</td>
                        <td className="p-3 text-right text-red-400">₹{formatFixed(item.brokerage, 2)}</td>
                        <td className="p-3 text-right text-red-400">₹{formatFixed(item.stt_ctt, 2)}</td>
                        <td className="p-3 text-right text-red-400 font-semibold">₹{formatFixed(item.total_cost, 2)}</td>
                        <td className="p-3 text-right text-green-400 font-semibold">₹{formatFixed(item.net_value, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Info Box */}
        <div className="bg-blue-900/20 border border-blue-800 rounded-lg p-4">
          <h3 className="text-blue-400 font-semibold mb-2">ℹ️ About Trade Costs</h3>
          <ul className="text-gray-300 text-sm space-y-1 list-disc list-inside">
            <li><strong>Brokerage:</strong> ₹20 flat for F&O | 0.03% or ₹20 for equity intraday | ₹0 for delivery</li>
            <li><strong>STT:</strong> Securities Transaction Tax (on sell side mostly)</li>
            <li><strong>Exchange Charges:</strong> NSE charges (0.00173% for F&O, 0.00297% for equity)</li>
            <li><strong>GST:</strong> 18% on (brokerage + exchange charges)</li>
            <li><strong>SEBI Charges:</strong> ₹10 per crore of turnover</li>
            <li><strong>Stamp Duty:</strong> 0.003% on buy side (capped at ₹300)</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default TradeCostTracker;
