import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Eye, Star, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';
import { watchlistAPI } from '../lib/api';
import { useToast } from '../components/Toast';

interface Watchlist {
  id: number;
  name: string;
  description: string;
  symbols: string[];
  color: string;
  icon: string;
  is_default: boolean;
  is_active: boolean;
}

interface Quote {
  symbol: string;
  ltp: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  high: number | null;
  low: number | null;
  open: number | null;
  close: number | null;
  error?: string;
}

const CustomWatchlists: React.FC = () => {
  const { showToast } = useToast();
  const [watchlists, setWatchlists] = useState<Watchlist[]>([]);
  const [selectedWatchlist, setSelectedWatchlist] = useState<Watchlist | null>(null);
  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showAddSymbolModal, setShowAddSymbolModal] = useState(false);
  
  // Create modal state
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newColor, setNewColor] = useState('#3b82f6');
  
  // Add symbol modal state
  const [newSymbol, setNewSymbol] = useState('');

  useEffect(() => {
    loadWatchlists();
  }, []);

  useEffect(() => {
    if (selectedWatchlist) {
      loadQuotes(selectedWatchlist.id);
    }
  }, [selectedWatchlist]);

  const loadWatchlists = async () => {
    setLoading(true);
    try {
      const response = await watchlistAPI.getAll();
      const wls = response.data.watchlists || [];
      setWatchlists(wls);
      
      // Auto-select default or first watchlist
      if (wls.length > 0) {
        const defaultWl = wls.find((w: Watchlist) => w.is_default) || wls[0];
        setSelectedWatchlist(defaultWl);
      }
    } catch (err) {
      console.error('Failed to load watchlists:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadQuotes = async (watchlistId: number) => {
    setLoadingQuotes(true);
    try {
      const response = await watchlistAPI.getQuotes(watchlistId);
      setQuotes(response.data.quotes || []);
    } catch (err) {
      console.error('Failed to load quotes:', err);
    } finally {
      setLoadingQuotes(false);
    }
  };

  const createWatchlist = async () => {
    if (!newName.trim()) {
      showToast('warning', 'Missing Name', 'Please enter a watchlist name');
      return;
    }

    try {
      await watchlistAPI.create({
        name: newName,
        description: newDescription,
        color: newColor,
        symbols: [],
      });
      
      setShowCreateModal(false);
      setNewName('');
      setNewDescription('');
      setNewColor('#3b82f6');
      loadWatchlists();
    } catch (err: any) {
      showToast('error', 'Create Failed', err.response?.data?.detail || 'Failed to create watchlist');
    }
  };

  const deleteWatchlist = async (id: number) => {
    if (!confirm('Delete this watchlist?')) return;

    try {
      await watchlistAPI.delete(id, true);
      loadWatchlists();
      if (selectedWatchlist?.id === id) {
        setSelectedWatchlist(null);
      }
    } catch (err: any) {
      showToast('error', 'Delete Failed', err.response?.data?.detail || 'Failed to delete watchlist');
    }
  };

  const addSymbol = async () => {
    if (!selectedWatchlist || !newSymbol.trim()) return;

    try {
      await watchlistAPI.addSymbol(selectedWatchlist.id, newSymbol.toUpperCase());
      setShowAddSymbolModal(false);
      setNewSymbol('');
      loadWatchlists();
      loadQuotes(selectedWatchlist.id);
    } catch (err: any) {
      showToast('error', 'Add Failed', err.response?.data?.detail || 'Failed to add symbol');
    }
  };

  const removeSymbol = async (symbol: string) => {
    if (!selectedWatchlist) return;
    
    if (!confirm(`Remove ${symbol} from watchlist?`)) return;

    try {
      await watchlistAPI.removeSymbol(selectedWatchlist.id, symbol);
      loadWatchlists();
      loadQuotes(selectedWatchlist.id);
    } catch (err: any) {
      showToast('error', 'Remove Failed', err.response?.data?.detail || 'Failed to remove symbol');
    }
  };

  const formatChange = (value: number | null) => {
    if (value === null) return '-';
    return value >= 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
  };

  return (
    <div className="min-h-screen bg-gray-950 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Eye className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-3xl font-bold text-white">Custom Watchlists</h1>
              <p className="text-gray-400 mt-1">
                Create and manage your symbol watchlists
              </p>
            </div>
          </div>
          
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Watchlist
          </button>
        </div>

        <div className="grid grid-cols-12 gap-6">
          {/* Watchlist Sidebar */}
          <div className="col-span-3 bg-gray-900 rounded-lg border border-gray-800 p-4">
            <h2 className="text-sm font-semibold text-gray-400 mb-3">WATCHLISTS</h2>
            
            {loading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
              </div>
            ) : watchlists.length === 0 ? (
              <p className="text-gray-500 text-sm text-center py-8">No watchlists</p>
            ) : (
              <div className="space-y-2">
                {watchlists.map((wl) => (
                  <button
                    key={wl.id}
                    onClick={() => setSelectedWatchlist(wl)}
                    className={`
                      w-full text-left p-3 rounded-lg transition-colors
                      ${
                        selectedWatchlist?.id === wl.id
                          ? 'bg-gray-800 border border-gray-700'
                          : 'hover:bg-gray-800/50'
                      }
                    `}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: wl.color }}
                        />
                        <span className="text-white font-medium">{wl.name}</span>
                        {wl.is_default && (
                          <Star className="w-3 h-3 text-yellow-500 fill-yellow-500" />
                        )}
                      </div>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteWatchlist(wl.id);
                        }}
                        className="text-gray-500 hover:text-red-400"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-gray-500 text-xs mt-1">{wl.symbols?.length || 0} symbols</p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Quotes Panel */}
          <div className="col-span-9 bg-gray-900 rounded-lg border border-gray-800">
            {!selectedWatchlist ? (
              <div className="flex items-center justify-center h-96 text-gray-500">
                Select a watchlist to view quotes
              </div>
            ) : (
              <>
                {/* Header */}
                <div className="p-4 border-b border-gray-800 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: selectedWatchlist.color }}
                    />
                    <div>
                      <h2 className="text-lg font-semibold text-white">{selectedWatchlist.name}</h2>
                      {selectedWatchlist.description && (
                        <p className="text-sm text-gray-400">{selectedWatchlist.description}</p>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => loadQuotes(selectedWatchlist.id)}
                      disabled={loadingQuotes}
                      className="p-2 hover:bg-gray-800 rounded-lg transition-colors text-gray-400 hover:text-white"
                    >
                      <RefreshCw className={`w-4 h-4 ${loadingQuotes ? 'animate-spin' : ''}`} />
                    </button>
                    <button
                      onClick={() => setShowAddSymbolModal(true)}
                      className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg text-sm transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                      Add Symbol
                    </button>
                  </div>
                </div>

                {/* Quotes Table */}
                <div className="overflow-x-auto">
                  {loadingQuotes ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                    </div>
                  ) : quotes.length === 0 ? (
                    <div className="text-center py-12 text-gray-500">
                      <p>No symbols in this watchlist</p>
                      <button
                        onClick={() => setShowAddSymbolModal(true)}
                        className="mt-3 text-blue-400 hover:text-blue-300 text-sm"
                      >
                        Add your first symbol
                      </button>
                    </div>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="bg-gray-800">
                        <tr>
                          <th className="text-left p-3 text-gray-400">Symbol</th>
                          <th className="text-right p-3 text-gray-400">LTP</th>
                          <th className="text-right p-3 text-gray-400">Change</th>
                          <th className="text-right p-3 text-gray-400">Change %</th>
                          <th className="text-right p-3 text-gray-400">Volume</th>
                          <th className="text-right p-3 text-gray-400">High</th>
                          <th className="text-right p-3 text-gray-400">Low</th>
                          <th className="text-center p-3 text-gray-400">Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {quotes.map((quote, idx) => {
                          const isPositive = (quote.change || 0) >= 0;
                          return (
                            <tr
                              key={quote.symbol}
                              className={`border-b border-gray-800 hover:bg-gray-800/50 ${
                                idx % 2 === 0 ? 'bg-gray-900' : 'bg-gray-900/50'
                              }`}
                            >
                              <td className="p-3 text-white font-semibold">{quote.symbol}</td>
                              <td className="p-3 text-right text-white">
                                {quote.ltp !== null ? `₹${quote.ltp.toFixed(2)}` : '-'}
                              </td>
                              <td className={`p-3 text-right ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                                {formatChange(quote.change)}
                              </td>
                              <td className={`p-3 text-right font-semibold ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
                                <div className="flex items-center justify-end gap-1">
                                  {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                  {quote.change_pct !== null ? `${quote.change_pct.toFixed(2)}%` : '-'}
                                </div>
                              </td>
                              <td className="p-3 text-right text-gray-400">
                                {quote.volume !== null ? (quote.volume / 1000).toFixed(1) + 'K' : '-'}
                              </td>
                              <td className="p-3 text-right text-green-400">
                                {quote.high !== null ? `₹${quote.high.toFixed(2)}` : '-'}
                              </td>
                              <td className="p-3 text-right text-red-400">
                                {quote.low !== null ? `₹${quote.low.toFixed(2)}` : '-'}
                              </td>
                              <td className="p-3 text-center">
                                <button
                                  onClick={() => removeSymbol(quote.symbol)}
                                  className="text-gray-500 hover:text-red-400 transition-colors"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Create Watchlist Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 rounded-lg p-6 w-full max-w-md border border-gray-800">
            <h2 className="text-xl font-semibold text-white mb-4">Create Watchlist</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="e.g., Tech Stocks"
                />
              </div>
              
              <div>
                <label className="block text-sm text-gray-400 mb-2">Description (optional)</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                  rows={3}
                  placeholder="Brief description..."
                />
              </div>
              
              <div>
                <label className="block text-sm text-gray-400 mb-2">Color</label>
                <input
                  type="color"
                  value={newColor}
                  onChange={(e) => setNewColor(e.target.value)}
                  className="w-full h-10 rounded cursor-pointer"
                />
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 bg-gray-800 hover:bg-gray-700 text-white py-2 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createWatchlist}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg transition-colors"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Symbol Modal */}
      {showAddSymbolModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-900 rounded-lg p-6 w-full max-w-md border border-gray-800">
            <h2 className="text-xl font-semibold text-white mb-4">Add Symbol</h2>
            
            <div>
              <label className="block text-sm text-gray-400 mb-2">Symbol</label>
              <input
                type="text"
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="e.g., RELIANCE, INFY"
                onKeyPress={(e) => {
                  if (e.key === 'Enter') addSymbol();
                }}
              />
            </div>
            
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setShowAddSymbolModal(false);
                  setNewSymbol('');
                }}
                className="flex-1 bg-gray-800 hover:bg-gray-700 text-white py-2 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={addSymbol}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg transition-colors"
              >
                Add
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CustomWatchlists;
