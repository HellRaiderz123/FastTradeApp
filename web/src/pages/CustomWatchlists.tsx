import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Eye, Star, TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';
import { watchlistAPI } from '../lib/api';
import { useToast } from '../components/Toast';
import { cn } from '@/lib/utils';

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
  change_percent?: number | null;
  volume: number | null;
  high: number | null;
  low: number | null;
  open: number | null;
  close: number | null;
  error?: string;
}

interface Suggestion {
  symbol: string;
  score: number;
  recent_signal_count: number;
  bullish_count: number;
  bearish_count: number;
  latest_signal_at: string | null;
  latest_direction: string | null;
  latest_strategy: string | null;
  avg_change_pct: number | null;
  rationale: string[];
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
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [applyingSuggestion, setApplyingSuggestion] = useState<string | null>(null);

  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newColor, setNewColor] = useState('#3b82f6');
  const [newSymbol, setNewSymbol] = useState('');

  useEffect(() => { loadWatchlists(); }, []);

  useEffect(() => {
    if (selectedWatchlist) {
      loadQuotes(selectedWatchlist.id);
      loadSuggestions(selectedWatchlist.id);
    }
  }, [selectedWatchlist]);

  const loadWatchlists = async () => {
    setLoading(true);
    try {
      const response = await watchlistAPI.getAll();
      const wls = response.data.watchlists || [];
      setWatchlists(wls);
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

  const loadSuggestions = async (watchlistId: number) => {
    setLoadingSuggestions(true);
    try {
      const response = await watchlistAPI.getSuggestions(watchlistId, 10, 14);
      setSuggestions(response.data?.suggestions || []);
    } catch {
      setSuggestions([]);
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const createWatchlist = async () => {
    if (!newName.trim()) { showToast('warning', 'Missing Name', 'Please enter a watchlist name'); return; }
    try {
      await watchlistAPI.create({ name: newName, description: newDescription, color: newColor, symbols: [] });
      setShowCreateModal(false);
      setNewName(''); setNewDescription(''); setNewColor('#3b82f6');
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
      if (selectedWatchlist?.id === id) setSelectedWatchlist(null);
    } catch (err: any) {
      showToast('error', 'Delete Failed', err.response?.data?.detail || 'Failed to delete watchlist');
    }
  };

  const addSymbol = async () => {
    if (!selectedWatchlist || !newSymbol.trim()) return;
    try {
      await watchlistAPI.addSymbol(selectedWatchlist.id, newSymbol.toUpperCase());
      setShowAddSymbolModal(false); setNewSymbol('');
      loadWatchlists(); loadQuotes(selectedWatchlist.id); loadSuggestions(selectedWatchlist.id);
    } catch (err: any) {
      showToast('error', 'Add Failed', err.response?.data?.detail || 'Failed to add symbol');
    }
  };

  const removeSymbol = async (symbol: string) => {
    if (!selectedWatchlist || !confirm(`Remove ${symbol} from watchlist?`)) return;
    try {
      await watchlistAPI.removeSymbol(selectedWatchlist.id, symbol);
      loadWatchlists(); loadQuotes(selectedWatchlist.id); loadSuggestions(selectedWatchlist.id);
    } catch (err: any) {
      showToast('error', 'Remove Failed', err.response?.data?.detail || 'Failed to remove symbol');
    }
  };

  const applySuggestion = async (symbol: string) => {
    if (!selectedWatchlist) return;
    setApplyingSuggestion(symbol);
    try {
      await watchlistAPI.applySuggestions(selectedWatchlist.id, [symbol]);
      showToast('success', 'Applied', `${symbol} added to ${selectedWatchlist.name}`);
      await loadWatchlists(); await loadQuotes(selectedWatchlist.id); await loadSuggestions(selectedWatchlist.id);
    } catch (err: any) {
      showToast('error', 'Apply Failed', err.response?.data?.detail || 'Failed to apply suggestion');
    } finally { setApplyingSuggestion(null); }
  };

  const applyTopSuggestions = async () => {
    if (!selectedWatchlist || suggestions.length === 0) return;
    const symbols = suggestions.slice(0, 5).map((s) => s.symbol);
    setApplyingSuggestion('__BULK__');
    try {
      await watchlistAPI.applySuggestions(selectedWatchlist.id, symbols);
      showToast('success', 'Applied', `Added up to ${symbols.length} suggestions to ${selectedWatchlist.name}`);
      await loadWatchlists(); await loadQuotes(selectedWatchlist.id); await loadSuggestions(selectedWatchlist.id);
    } catch (err: any) {
      showToast('error', 'Apply Failed', err.response?.data?.detail || 'Failed to apply suggestions');
    } finally { setApplyingSuggestion(null); }
  };

  const formatChange = (value: number | null | undefined) => {
    if (value === null || value === undefined || Number.isNaN(value)) return '-';
    return value >= 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
  };

  const getChangePercent = (quote: Quote) => {
    const value = quote.change_pct ?? quote.change_percent ?? null;
    return value === undefined || Number.isNaN(value) ? null : value;
  };

  const inputCls = 'w-full px-4 py-2 bg-background border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-blue-500';

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Eye className="w-8 h-8 text-blue-500" />
            <div>
              <h1 className="text-3xl font-bold text-foreground">Custom Watchlists</h1>
              <p className="text-muted-foreground mt-1">Create and manage your symbol watchlists</p>
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
          {/* Sidebar */}
          <div className="col-span-3 bg-card rounded-lg border border-border p-4">
            <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-3">Watchlists</h2>

            {loading ? (
              <div className="flex justify-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500" />
              </div>
            ) : watchlists.length === 0 ? (
              <p className="text-muted-foreground text-sm text-center py-8">No watchlists</p>
            ) : (
              <div className="space-y-1.5">
                {watchlists.map((wl) => (
                  <button
                    key={wl.id}
                    onClick={() => setSelectedWatchlist(wl)}
                    className={cn(
                      'w-full text-left p-3 rounded-lg transition-colors',
                      selectedWatchlist?.id === wl.id
                        ? 'bg-accent border border-border'
                        : 'hover:bg-accent/50'
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: wl.color }} />
                        <span className="text-foreground font-medium truncate">{wl.name}</span>
                        {wl.is_default && <Star className="w-3 h-3 text-yellow-500 fill-yellow-500 shrink-0" />}
                      </div>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteWatchlist(wl.id); }}
                        className="text-muted-foreground hover:text-red-500 shrink-0 ml-1"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                    <p className="text-muted-foreground text-xs mt-1">{wl.symbols?.length || 0} symbols</p>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Main Panel */}
          <div className="col-span-9 bg-card rounded-lg border border-border">
            {!selectedWatchlist ? (
              <div className="flex items-center justify-center h-96 text-muted-foreground">
                Select a watchlist to view quotes
              </div>
            ) : (
              <>
                {/* Panel Header */}
                <div className="p-4 border-b border-border flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-4 h-4 rounded-full" style={{ backgroundColor: selectedWatchlist.color }} />
                    <div>
                      <h2 className="text-lg font-semibold text-foreground">{selectedWatchlist.name}</h2>
                      {selectedWatchlist.description && (
                        <p className="text-sm text-muted-foreground">{selectedWatchlist.description}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => loadSuggestions(selectedWatchlist.id)}
                      disabled={loadingSuggestions}
                      className="flex items-center gap-2 px-3 py-2 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
                    >
                      <RefreshCw className={cn('w-4 h-4', loadingSuggestions && 'animate-spin')} />
                      ML Suggestions
                    </button>
                    <button
                      onClick={() => loadQuotes(selectedWatchlist.id)}
                      disabled={loadingQuotes}
                      className="p-2 hover:bg-accent rounded-lg transition-colors text-muted-foreground hover:text-foreground"
                    >
                      <RefreshCw className={cn('w-4 h-4', loadingQuotes && 'animate-spin')} />
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

                {/* Suggestions Panel */}
                <div className="p-4 border-b border-border bg-muted/30">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-violet-500">ML Suggestions (from recent scanner signals)</h3>
                    <button
                      onClick={applyTopSuggestions}
                      disabled={suggestions.length === 0 || applyingSuggestion === '__BULK__'}
                      className="text-xs px-3 py-1.5 rounded-md bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white transition-colors"
                    >
                      {applyingSuggestion === '__BULK__' ? 'Applying...' : 'Apply Top 5'}
                    </button>
                  </div>

                  {loadingSuggestions ? (
                    <div className="text-xs text-muted-foreground">Generating suggestions...</div>
                  ) : suggestions.length === 0 ? (
                    <div className="text-xs text-muted-foreground">No fresh suggestions yet. Click ML Suggestions to refresh.</div>
                  ) : (
                    <div className="space-y-2">
                      {suggestions.slice(0, 8).map((s) => (
                        <div key={s.symbol} className="flex items-center justify-between p-2 rounded-md bg-card border border-border">
                          <div>
                            <div className="text-sm font-semibold text-foreground">{s.symbol}</div>
                            <div className="text-[11px] text-muted-foreground">
                              score {s.score.toFixed(1)} • {s.recent_signal_count} signals • {s.latest_strategy || 'strategy n/a'}
                            </div>
                          </div>
                          <button
                            onClick={() => applySuggestion(s.symbol)}
                            disabled={applyingSuggestion === s.symbol}
                            className="text-xs px-2.5 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white transition-colors"
                          >
                            {applyingSuggestion === s.symbol ? 'Adding...' : 'Add'}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Quotes Table */}
                <div className="overflow-x-auto">
                  {loadingQuotes ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
                    </div>
                  ) : quotes.length === 0 ? (
                    <div className="text-center py-12 text-muted-foreground">
                      <p>No symbols in this watchlist</p>
                      <button
                        onClick={() => setShowAddSymbolModal(true)}
                        className="mt-3 text-blue-500 hover:text-blue-400 text-sm"
                      >
                        Add your first symbol
                      </button>
                    </div>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="bg-muted/60">
                        <tr>
                          <th className="text-left p-3 text-muted-foreground font-semibold">Symbol</th>
                          <th className="text-right p-3 text-muted-foreground font-semibold">LTP</th>
                          <th className="text-right p-3 text-muted-foreground font-semibold">Change</th>
                          <th className="text-right p-3 text-muted-foreground font-semibold">Change %</th>
                          <th className="text-right p-3 text-muted-foreground font-semibold">Volume</th>
                          <th className="text-right p-3 text-muted-foreground font-semibold">High</th>
                          <th className="text-right p-3 text-muted-foreground font-semibold">Low</th>
                          <th className="text-center p-3 text-muted-foreground font-semibold">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {quotes.map((quote) => {
                          const changePercent = getChangePercent(quote);
                          const isPositive = (quote.change ?? changePercent ?? 0) >= 0;
                          return (
                            <tr key={quote.symbol} className="hover:bg-accent/40 transition-colors">
                              <td className="p-3 text-foreground font-semibold">{quote.symbol}</td>
                              <td className="p-3 text-right text-foreground">
                                {quote.ltp !== null ? `₹${quote.ltp.toFixed(2)}` : '-'}
                              </td>
                              <td className={cn('p-3 text-right', isPositive ? 'text-emerald-500' : 'text-red-500')}>
                                {formatChange(quote.change)}
                              </td>
                              <td className={cn('p-3 text-right font-semibold', isPositive ? 'text-emerald-500' : 'text-red-500')}>
                                <div className="flex items-center justify-end gap-1">
                                  {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                  {changePercent !== null ? `${changePercent >= 0 ? '+' : ''}${changePercent.toFixed(2)}%` : '-'}
                                </div>
                              </td>
                              <td className="p-3 text-right text-muted-foreground">
                                {quote.volume !== null ? (quote.volume / 1000).toFixed(1) + 'K' : '-'}
                              </td>
                              <td className="p-3 text-right text-emerald-500">
                                {quote.high !== null ? `₹${quote.high.toFixed(2)}` : '-'}
                              </td>
                              <td className="p-3 text-right text-red-500">
                                {quote.low !== null ? `₹${quote.low.toFixed(2)}` : '-'}
                              </td>
                              <td className="p-3 text-center">
                                <button
                                  onClick={() => removeSymbol(quote.symbol)}
                                  className="text-muted-foreground hover:text-red-500 transition-colors"
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
          <div className="bg-card rounded-xl p-6 w-full max-w-md border border-border shadow-xl">
            <h2 className="text-xl font-semibold text-foreground mb-4">Create Watchlist</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className={inputCls}
                  placeholder="e.g., Tech Stocks"
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Description (optional)</label>
                <textarea
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  className={inputCls}
                  rows={3}
                  placeholder="Brief description..."
                />
              </div>
              <div>
                <label className="block text-sm text-muted-foreground mb-2">Color</label>
                <input
                  type="color"
                  value={newColor}
                  onChange={(e) => setNewColor(e.target.value)}
                  className="w-full h-10 rounded cursor-pointer border border-border bg-background"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowCreateModal(false)}
                className="flex-1 bg-muted hover:bg-accent border border-border text-foreground py-2 rounded-lg transition-colors"
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
          <div className="bg-card rounded-xl p-6 w-full max-w-md border border-border shadow-xl">
            <h2 className="text-xl font-semibold text-foreground mb-4">Add Symbol</h2>
            <div>
              <label className="block text-sm text-muted-foreground mb-2">Symbol</label>
              <input
                type="text"
                value={newSymbol}
                onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
                className={inputCls}
                placeholder="e.g., RELIANCE, INFY"
                onKeyDown={(e) => { if (e.key === 'Enter') addSymbol(); }}
              />
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => { setShowAddSymbolModal(false); setNewSymbol(''); }}
                className="flex-1 bg-muted hover:bg-accent border border-border text-foreground py-2 rounded-lg transition-colors"
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
