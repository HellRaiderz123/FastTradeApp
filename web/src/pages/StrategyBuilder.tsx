import React, { useState, useEffect } from 'react';
import { Plus, X, Trash2, TrendingUp, Calendar } from 'lucide-react';
import { strategyAPI, greeksAPI, marketAPI } from '../lib/api';

interface OptionLeg {
  id: string;
  type: 'BUY' | 'SELL';
  option_type: 'CE' | 'PE';
  strike: number;
  quantity: number;
  premium?: number;
}

interface StrategyPayoff {
  spot: number;
  pnl: number;
  maxProfit?: number;
  maxLoss?: number;
}

interface GreeksData {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
  premium: number;
  max_profit?: number;
  max_loss?: number;
}

type StrategyTemplate = 'CUSTOM' | 'BULL_PUT' | 'BEAR_CALL' | 'IRON_CONDOR';

const NIFTY_LOT_SIZE = 65;

const StrategyBuilder: React.FC = () => {
  const [legs, setLegs] = useState<OptionLeg[]>([]);
  const [spot, setSpot] = useState<number>(26150);
  const [atm, setAtm] = useState<number>(26150);
  const [greeks, setGreeks] = useState<GreeksData | null>(null);
  const [payoffData, setPayoffData] = useState<StrategyPayoff[]>([]);
  const [strategyId, setStrategyId] = useState<number | null>(null);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [showLoadDialog, setShowLoadDialog] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expiryDates, setExpiryDates] = useState<string[]>([]);
  const [selectedExpiry, setSelectedExpiry] = useState<string>('');
  const [fetchingSpot, setFetchingSpot] = useState(true);
  const [strategyName, setStrategyName] = useState('');
  const [savedStrategies, setSavedStrategies] = useState<any[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(false);

  const [template, setTemplate] = useState<StrategyTemplate>('CUSTOM');

  // Fetch spot price and expiry dates on component mount
  useEffect(() => {
    const fetchMarketData = async () => {
      try {
        setFetchingSpot(true);
        console.log('=== Starting market data fetch ===');
        
        // Fetch spot price
        console.log('1. Fetching LTP...');
        const spotResponse = await marketAPI.getLTP('NIFTY');
        console.log('   LTP Response:', spotResponse);
        console.log('   LTP Response data:', spotResponse?.data);
        
        // Handle axios response - data is inside .data property
        const spotData = spotResponse?.data || spotResponse;
        if (spotData?.ltp) {
          console.log('   Setting spot to:', spotData.ltp);
          setSpot(Number(spotData.ltp));
          setAtm(Number(spotData.ltp));
        } else {
          console.warn('   No LTP in response, keeping default 26150');
        }
        
        // Fetch available expiry dates
        console.log('2. Fetching expiries...');
        const expiriesResponse = await marketAPI.getAvailableExpiries('NIFTY');
        console.log('   Expiries Response:', expiriesResponse);
        console.log('   Expiries Response data:', expiriesResponse?.data);
        
        // Handle axios response
        const expiryData = expiriesResponse?.data || expiriesResponse;
        console.log('   Type of expiries:', typeof expiryData?.expiries);
        console.log('   Is array?:', Array.isArray(expiryData?.expiries));
        
        if (expiryData?.expiries && Array.isArray(expiryData.expiries) && expiryData.expiries.length > 0) {
          console.log('   Setting expiry dates to:', expiryData.expiries);
          setExpiryDates(expiryData.expiries);
          setSelectedExpiry(expiryData.expiries[0]);
          console.log('   Set selected expiry to:', expiryData.expiries[0]);
        } else {
          console.warn('   Empty or invalid expiries, using fallback');
          // Set defaults if API returns empty
          const today = new Date();
          const fallbackExpiries = [
            new Date(today.getTime() + 6 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            new Date(today.getTime() + 13 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            new Date(today.getTime() + 20 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            new Date(today.getTime() + 27 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          ];
          console.log('   Fallback expiries:', fallbackExpiries);
          setExpiryDates(fallbackExpiries);
          setSelectedExpiry(fallbackExpiries[0]);
        }
        
        console.log('=== Market data fetch complete ===');
      } catch (err) {
        console.error('❌ Failed to fetch market data:', err);
        // Keep defaults if API fails
      } finally {
        console.log('Setting fetchingSpot to false');
        setFetchingSpot(false);
      }
    };

    console.log('StrategyBuilder mounted, fetching market data');
    fetchMarketData();
  }, []);

  // Fetch premium when strike is selected
  const fetchPremium = async (strike: number, optionType: 'CE' | 'PE') => {
    try {
      if (!selectedExpiry) {
        console.warn('No expiry selected, cannot fetch premium');
        return 0;
      }
      
      console.log(`Fetching premium for ${strike} ${optionType} expiry ${selectedExpiry}`);
      const premiumResponse = await marketAPI.getOptionPremium('NIFTY', strike, optionType, selectedExpiry);
      
      // Handle axios response - data is inside .data property
      const premiumData = premiumResponse?.data || premiumResponse;
      console.log('Premium response:', premiumData);
      
      const premium = premiumData?.premium || 0;
      console.log(`Got premium: ${premium}`);
      return premium;
    } catch (err) {
      console.error('Failed to fetch premium:', err);
      return 0;
    }
  };

  const getStep = () => 50; // NIFTY default

  const roundToStep = (value: number, step: number) => Math.round(value / step) * step;

  const buildTemplateLegs = async (tpl: StrategyTemplate) => {
    if (!selectedExpiry) {
      setError('Please select an expiry date');
      return;
    }

    setTemplate(tpl);

    const step = getStep();
    const atmStrike = roundToStep(atm, step);

    // Simple defaults (can be made configurable later)
    const offset = step * 2; // 100 for NIFTY
    const width = step * 2;  // 100 for NIFTY

    let newLegs: OptionLeg[] = [];

    if (tpl === 'BULL_PUT') {
      const shortPut = atmStrike - offset;
      const longPut = shortPut - width;
      newLegs = [
        { id: `${Date.now()}-sp`, type: 'SELL', option_type: 'PE', strike: shortPut, quantity: 1 },
        { id: `${Date.now()}-lp`, type: 'BUY', option_type: 'PE', strike: longPut, quantity: 1 },
      ];
    }

    if (tpl === 'BEAR_CALL') {
      const shortCall = atmStrike + offset;
      const longCall = shortCall + width;
      newLegs = [
        { id: `${Date.now()}-sc`, type: 'SELL', option_type: 'CE', strike: shortCall, quantity: 1 },
        { id: `${Date.now()}-lc`, type: 'BUY', option_type: 'CE', strike: longCall, quantity: 1 },
      ];
    }

    if (tpl === 'IRON_CONDOR') {
      const shortPut = atmStrike - offset;
      const longPut = shortPut - width;
      const shortCall = atmStrike + offset;
      const longCall = shortCall + width;
      newLegs = [
        { id: `${Date.now()}-sp`, type: 'SELL', option_type: 'PE', strike: shortPut, quantity: 1 },
        { id: `${Date.now()}-lp`, type: 'BUY', option_type: 'PE', strike: longPut, quantity: 1 },
        { id: `${Date.now()}-sc`, type: 'SELL', option_type: 'CE', strike: shortCall, quantity: 1 },
        { id: `${Date.now()}-lc`, type: 'BUY', option_type: 'CE', strike: longCall, quantity: 1 },
      ];
    }

    if (tpl === 'CUSTOM') {
      setTemplate('CUSTOM');
      return;
    }

    // Fetch premiums in parallel
    const premiums = await Promise.all(
      newLegs.map((leg) => fetchPremium(leg.strike, leg.option_type))
    );
    newLegs = newLegs.map((leg, idx) => ({ ...leg, premium: premiums[idx] }));

    setLegs(newLegs);
    setError(null);
    setGreeks(null);
    setPayoffData([]);
  };

  const refreshAllPremiums = async (currentLegs: OptionLeg[]) => {
    if (!selectedExpiry || currentLegs.length === 0) return;
    try {
      const premiums = await Promise.all(
        currentLegs.map((leg) => fetchPremium(leg.strike, leg.option_type))
      );
      setLegs(currentLegs.map((leg, idx) => ({ ...leg, premium: premiums[idx] })));
    } catch {
      // keep previous premiums
    }
  };

  // Refresh premiums when expiry changes (or when we get a new spot/ATM on load)
  useEffect(() => {
    if (legs.length > 0) {
      refreshAllPremiums(legs);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedExpiry]);

  // Add new leg
  const addLeg = async () => {
    // Round ATM to nearest 100 for NIFTY strikes
    const atmStrike = Math.round(atm / 50) * 50;
    
    const newLeg: OptionLeg = {
      id: Date.now().toString(),
      type: 'BUY',
      option_type: 'CE',
      strike: atmStrike,
      quantity: 1,
    };
    
    // Fetch premium for this leg
    const premium = await fetchPremium(atmStrike, 'CE');
    newLeg.premium = premium;
    
    setLegs([...legs, newLeg]);
    setError(null);
    console.log('Added leg with strike:', atmStrike, 'premium:', premium);
  };

  // Remove leg
  const removeLeg = (id: string) => {
    setLegs(legs.filter(leg => leg.id !== id));
    setError(null);
  };

  // Update leg
  const updateLeg = (id: string, field: string, value: any) => {
    const normalizeLots = (lots: unknown) => {
      const num = Number(lots);
      if (!Number.isFinite(num)) return 1;
      return Math.max(1, Math.floor(num));
    };

    const updatedLegs = legs.map(leg => {
      if (leg.id === id) {
        const updated = {
          ...leg,
          [field]: field === 'quantity' ? normalizeLots(value) : value,
        };
        
        // If strike or option_type changed, fetch new premium
        if ((field === 'strike' || field === 'option_type') && selectedExpiry) {
          console.log(`Leg ${id} changed ${field} to ${value}, fetching premium...`);
          fetchPremium(updated.strike, updated.option_type).then(premium => {
            console.log(`Setting premium for leg ${id} to ${premium}`);
            setLegs(legs =>
              legs.map(l =>
                l.id === id ? { ...l, premium } : l
              )
            );
          });
        }
        
        return updated;
      }
      return leg;
    });
    
    setLegs(updatedLegs);
    setError(null);
  };

  // Calculate Greeks
  const calculateGreeks = async () => {
    if (legs.length === 0) {
      setError('Please add at least one option leg');
      return;
    }

    if (!selectedExpiry) {
      setError('Please select an expiry date');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Calculate days to expiry from selected expiry date
      const expiryDate = new Date(selectedExpiry);
      const today = new Date();
      const daysToExpiry = Math.ceil((expiryDate.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

      const legsData = legs.map(leg => ({
        type: leg.type,
        option_type: leg.option_type,
        strike: leg.strike,
        spot,
        expiry_days: Math.max(daysToExpiry, 1),
        volatility: 20,
        // UI quantity is in lots; API expects actual contract quantity
        quantity: Math.max(1, Math.floor(leg.quantity)) * NIFTY_LOT_SIZE,
      }));

      const response = await greeksAPI.calculate({
        legs: legsData,
        spot,
        rate: 5.0,
      });

      console.log('Greeks response:', response);
      console.log('Greeks response data:', response?.data);

      // Handle axios response - data is inside .data property
      const greeksData = response?.data || response;
      console.log('Greeks data:', greeksData);

      if (greeksData && ('delta' in greeksData || 'gamma' in greeksData)) {
        console.log('Valid Greeks response, setting state');
        setGreeks(greeksData);
        calculatePayoff();
      } else {
        console.error('Unexpected response structure:', greeksData);
        setError('Invalid response structure from Greeks API');
        setGreeks(null);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Failed to calculate Greeks';
      console.error('Greeks calculation error:', error);
      setError(errorMsg);
      setGreeks(null);
      setPayoffData([]);
    } finally {
      setLoading(false);
    }
  };

  // Calculate payoff at different spot prices
  const calculatePayoff = () => {
    try {
      const payoffs: StrategyPayoff[] = [];
      
      // Get all strike prices to ensure we capture the breakpoints
      const strikes = legs.map(l => l.strike).sort((a, b) => a - b);
      const minStrike = strikes[0] || atm;
      const maxStrike = strikes[strikes.length - 1] || atm;
      
      const baseSpot = Math.min(atm - 500, minStrike - 200);
      const maxSpot = Math.max(atm + 500, maxStrike + 200);
      
      // Generate points with extra granularity around strikes
      const points = new Set<number>();
      
      // Add strike points
      strikes.forEach(strike => {
        points.add(strike - 1);
        points.add(strike);
        points.add(strike + 1);
      });
      
      // Add regular interval points
      const step = Math.max(10, (maxSpot - baseSpot) / 100);
      for (let s = baseSpot; s <= maxSpot; s += step) {
        points.add(Math.round(s * 100) / 100);
      }
      
      // Sort and calculate payoff for each point
      const sortedPoints = Array.from(points).sort((a, b) => a - b);
      
      sortedPoints.forEach(s => {
        let totalPnL = 0;

        legs.forEach(leg => {
          const intrinsic = leg.option_type === 'CE'
            ? Math.max(s - leg.strike, 0)
            : Math.max(leg.strike - s, 0);

          // Fix: SELL should be premium - intrinsic, BUY should be intrinsic - premium
          const qty = Math.max(1, Math.floor(leg.quantity)) * NIFTY_LOT_SIZE;
          const legPnl = leg.type === 'BUY'
            ? (intrinsic - (leg.premium || 0)) * qty
            : ((leg.premium || 0) - intrinsic) * qty;

          totalPnL += legPnl;
        });

        payoffs.push({ spot: s, pnl: totalPnL });
      });

      setPayoffData(payoffs);
    } catch (error) {
      console.error('Payoff calculation error:', error);
      setPayoffData([]);
    }
  };

  // Calculate breakeven spot prices (where P&L = 0)
  const calculateBreakevens = () => {
    const breakevens: number[] = [];
    for (let i = 1; i < payoffData.length; i++) {
      const prev = payoffData[i - 1];
      const curr = payoffData[i];
      
      // Check if P&L crosses zero between these two points
      if ((prev.pnl < 0 && curr.pnl > 0) || (prev.pnl > 0 && curr.pnl < 0)) {
        // Linear interpolation to find exact breakeven
        const ratio = Math.abs(prev.pnl) / (Math.abs(prev.pnl) + Math.abs(curr.pnl));
        const breakeven = prev.spot + ratio * (curr.spot - prev.spot);
        breakevens.push(breakeven);
      }
    }
    return breakevens;
  };

  // Calculate risk/reward ratio
  const calculateRiskReward = () => {
    if (!payoffData.length) return null;
    
    const pnls = payoffData.map(p => p.pnl);
    const maxProfit = Math.max(...pnls);
    const maxLoss = Math.min(...pnls);
    
    if (maxLoss >= 0 || maxProfit <= 0) return null; // No defined risk/reward
    
    return {
      maxProfit,
      maxLoss: Math.abs(maxLoss),
      ratio: maxProfit / Math.abs(maxLoss),
    };
  };

  // Get P&L at different spot prices
  const getPnLAtSpots = () => {
    if (!payoffData.length) return [];
    
    const minSpot = Math.min(...payoffData.map(p => p.spot));
    const maxSpot = Math.max(...payoffData.map(p => p.spot));
    const range = maxSpot - minSpot;
    
    const testSpots = [
      minSpot,
      atm - 200,
      atm - 100,
      atm,
      atm + 100,
      atm + 200,
      maxSpot,
    ].filter(s => s >= minSpot && s <= maxSpot);
    
    return testSpots.map(testSpot => {
      // Find closest data points for interpolation
      let pnl = 0;
      const dataPoints = payoffData.sort((a, b) => a.spot - b.spot);
      
      const idx = dataPoints.findIndex(p => p.spot >= testSpot);
      if (idx === -1) {
        pnl = dataPoints[dataPoints.length - 1].pnl;
      } else if (idx === 0) {
        pnl = dataPoints[0].pnl;
      } else {
        const prev = dataPoints[idx - 1];
        const curr = dataPoints[idx];
        const ratio = (testSpot - prev.spot) / (curr.spot - prev.spot);
        pnl = prev.pnl + ratio * (curr.pnl - prev.pnl);
      }
      
      return { spot: testSpot, pnl };
    });
  };

  // Save strategy
  const handleSave = async () => {
    if (!strategyName.trim()) {
      alert('Please enter strategy name');
      return;
    }

    setSaveStatus('saving');
    try {
      // Calculate total premium (net debit/credit)
      const totalPremium = legs.reduce((sum, leg) => {
        const qty = Math.max(1, Math.floor(leg.quantity)) * NIFTY_LOT_SIZE;
        const legPremium = (leg.premium || 0) * qty;
        return sum + (leg.type === 'BUY' ? -legPremium : legPremium);
      }, 0);

      // Get max profit and max loss from Greeks
      const maxProfit = greeks?.max_profit || null;
      const maxLoss = greeks?.max_loss || null;

      const strategyData = {
        name: strategyName,
        description: `${legs.length}-leg strategy created on ${new Date().toLocaleDateString()}`,
        strategy_type: 'option_spread_custom',
        underlying: 'NIFTY',
        parameters: {
          expiry: selectedExpiry,
          spot_at_creation: spot,
          legs: legs.map(leg => ({
            type: leg.type,
            option_type: leg.option_type,
            strike: leg.strike,
            // Persist actual quantity to match execution/backtest expectations
            quantity: Math.max(1, Math.floor(leg.quantity)) * NIFTY_LOT_SIZE,
            premium: leg.premium,
          })),
          total_premium: totalPremium,
          max_profit: maxProfit,
          max_loss: maxLoss,
          greeks: greeks,
        },
      };

      if (strategyId) {
        // Update existing
        await strategyAPI.updateStrategy(strategyId, strategyData);
        setSaveStatus('success');
        alert('Strategy updated successfully!');
      } else {
        // Create new
        const response = await strategyAPI.createStrategy(strategyData);
        setSaveStatus('success');
        alert('Strategy saved successfully!');
      }

      setShowSaveDialog(false);
      setStrategyName('');
      setTimeout(() => setSaveStatus('idle'), 2000);
    } catch (error) {
      console.error('Failed to save strategy:', error);
      setSaveStatus('error');
      alert('Failed to save strategy: ' + (error instanceof Error ? error.message : 'Unknown error'));
      setTimeout(() => setSaveStatus('idle'), 2000);
    }
  };

  const loadSavedStrategies = async () => {
    try {
      setLoadingStrategies(true);
      const response = await strategyAPI.listStrategies();
      const strategies = response.data || response;
      setSavedStrategies(Array.isArray(strategies) ? strategies : []);
    } catch (error) {
      console.error('Failed to load strategies:', error);
      alert('Failed to load strategies');
    } finally {
      setLoadingStrategies(false);
    }
  };

  const handleLoadStrategy = (strategy: any) => {
    try {
      const params = strategy.parameters || {};
      const strategyLegs = params.legs || [];
      
      // Populate the builder with loaded strategy data
      setLegs(strategyLegs.map((leg: any, idx: number) => ({
        id: `leg-${Date.now()}-${idx}`,
        type: leg.type,
        option_type: leg.option_type,
        strike: leg.strike,
        // Backend stores actual quantity; UI uses lots.
        quantity: (() => {
          const q = Number(leg.quantity);
          if (!Number.isFinite(q) || q <= 0) return 1;
          if (q >= NIFTY_LOT_SIZE && q % NIFTY_LOT_SIZE === 0) return q / NIFTY_LOT_SIZE;
          return q; // backward compat if older saved strategies used lots
        })(),
        premium: leg.premium,
      })));
      
      setSelectedExpiry(params.expiry || '');
      setSpot(params.spot_at_creation || spot);
      setStrategyId(strategy.id);
      setStrategyName(strategy.name);
      
      // If we have saved Greeks, use them
      if (params.greeks) {
        setGreeks(params.greeks);
      }
      
      setShowLoadDialog(false);
      alert(`Loaded strategy: ${strategy.name}`);
    } catch (error) {
      console.error('Failed to load strategy:', error);
      alert('Failed to load strategy');
    }
  };

  const handleDeleteStrategy = async (strategyId: number) => {
    if (!window.confirm('Are you sure you want to delete this strategy?')) {
      return;
    }
    
    try {
      await strategyAPI.deleteStrategy(strategyId);
      alert('Strategy deleted successfully');
      loadSavedStrategies(); // Refresh list
    } catch (error) {
      console.error('Failed to delete strategy:', error);
      alert('Failed to delete strategy');
    }
  };

  const handleNewStrategy = () => {
    setLegs([]);
    setStrategyId(null);
    setStrategyName('');
    setGreeks(null);
    setPayoffData([]);
    setSaveStatus('idle');
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 p-6 gap-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-white">Strategy Builder</h1>
          <p className="text-sm text-slate-400 mt-1">Drag & drop option legs, visualize payoff</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              loadSavedStrategies();
              setShowLoadDialog(true);
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            title="Load saved strategies"
          >
            Load Strategy
          </button>
          <button
            onClick={() => setShowSaveDialog(true)}
            disabled={legs.length === 0 || !greeks}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition flex items-center gap-2"
            title="Save strategy after calculating Greeks"
          >
            {saveStatus === 'success' ? '✓ Saved' : 'Save Strategy'}
          </button>
          {strategyId && (
            <button
              onClick={handleNewStrategy}
              className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-500 transition"
              title="Start new strategy"
            >
              New
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6 flex-1 min-h-0">
        {/* Left: Legs Builder */}
        <div className="col-span-4 bg-slate-900 border border-slate-700 rounded-lg p-4 flex flex-col gap-4 overflow-auto">
          <div className="flex justify-between items-center">
            <h2 className="text-lg font-semibold text-white">Legs</h2>
            <button
              onClick={addLeg}
              className="p-1 bg-blue-600 hover:bg-blue-700 rounded text-white"
              title="Add option leg"
            >
              <Plus size={18} />
            </button>
          </div>

          {/* Templates */}
          <div className="space-y-2">
            <label className="text-xs text-slate-300">Template</label>
            <div className="flex gap-2">
              <select
                value={template}
                onChange={(e) => setTemplate(e.target.value as StrategyTemplate)}
                className="flex-1 px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                aria-label="Strategy template"
              >
                <option value="CUSTOM">Custom</option>
                <option value="BULL_PUT">Bull Put Spread</option>
                <option value="BEAR_CALL">Bear Call Spread</option>
                <option value="IRON_CONDOR">Iron Condor</option>
              </select>
              <button
                onClick={() => buildTemplateLegs(template)}
                disabled={template === 'CUSTOM'}
                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-200 rounded disabled:opacity-50 transition"
                title="Auto-create legs from template"
              >
                Apply
              </button>
              <button
                onClick={() => refreshAllPremiums(legs)}
                disabled={legs.length === 0}
                className="px-3 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-200 rounded disabled:opacity-50 transition"
                title="Refresh premiums from market"
              >
                Refresh
              </button>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="bg-red-900 border border-red-700 rounded p-3">
              <p className="text-red-200 text-sm">{error}</p>
            </div>
          )}

          {/* Spot Price Input */}
          <div className="space-y-2">
            <label className="text-xs text-slate-300">Spot Price (Live: {atm.toFixed(2)})</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={spot.toFixed(2)}
                onChange={(e) => setSpot(Number(e.target.value))}
                className="flex-1 px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm"
              />
              <button
                onClick={() => { setSpot(atm); console.log('Reset spot to ATM:', atm); }}
                className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-xs text-slate-300 rounded transition"
                title="Reset to live spot price"
              >
                ↺ ATM
              </button>
            </div>
          </div>

          {/* Expiry Date Dropdown */}
          <div className="space-y-2">
            <label className="text-xs text-slate-300 flex items-center gap-1">
              <Calendar size={14} />
              Expiry Date
            </label>
            <select
              value={selectedExpiry || ''}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              className="w-full px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm"
            >
              {expiryDates.length === 0 ? (
                <option value="">Loading expiries...</option>
              ) : (
                expiryDates.map((expiry) => (
                  <option key={expiry} value={expiry}>
                    {new Date(expiry).toLocaleDateString('en-US', {
                      month: 'short',
                      day: 'numeric',
                      year: 'numeric',
                    })}
                    {' '}
                    ({Math.ceil((new Date(expiry).getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24))} days)
                  </option>
                ))
              )}
            </select>
            {/* Debug info */}
            <div className="text-xs text-slate-500">
              Expiries: {expiryDates.length} loaded | Selected: {selectedExpiry}
            </div>
          </div>

          {/* Calculate Greeks Button */}
          <button
            onClick={calculateGreeks}
            disabled={legs.length === 0 || loading}
            className="w-full px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white rounded-lg font-semibold transition"
            title="Calculate Greeks for current legs"
          >
            {loading ? 'Calculating...' : 'Calculate Greeks'}
          </button>

          {/* Legs List */}
          <div className="space-y-3 flex-1 overflow-y-auto">
            {legs.length === 0 ? (
              <p className="text-slate-400 text-sm text-center py-8">No legs added yet</p>
            ) : (
              legs.map(leg => (
                <div key={leg.id} className="bg-slate-800 border border-slate-700 rounded p-3 space-y-2">
                  <div className="flex justify-between items-center">
                    <div className="flex gap-2">
                      <select
                        value={leg.type}
                        onChange={(e) => updateLeg(leg.id, 'type', e.target.value)}
                        className="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                      >
                        <option>BUY</option>
                        <option>SELL</option>
                      </select>
                      <select
                        value={leg.option_type}
                        onChange={(e) => updateLeg(leg.id, 'option_type', e.target.value)}
                        className="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                      >
                        <option>CE</option>
                        <option>PE</option>
                      </select>
                    </div>
                    <button
                      onClick={() => removeLeg(leg.id)}
                      className="p-1 hover:bg-red-600 rounded text-red-300"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-slate-400">Strike</label>
                      <input
                        type="number"
                        value={leg.strike}
                        onChange={(e) => updateLeg(leg.id, 'strike', Number(e.target.value))}
                        className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                      />
                    </div>
                    <div>
                      <label className="text-xs text-slate-400">Lots (1 lot = {NIFTY_LOT_SIZE})</label>
                      <input
                        type="number"
                        value={leg.quantity}
                        onChange={(e) => updateLeg(leg.id, 'quantity', Number(e.target.value))}
                        min={1}
                        step={1}
                        className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-xs text-slate-400">Premium</label>
                    <input
                      type="number"
                      value={leg.premium || 0}
                      onChange={(e) => updateLeg(leg.id, 'premium', Number(e.target.value))}
                      className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Middle: Payoff Diagram */}
        <div className="col-span-4 bg-slate-900 border border-slate-700 rounded-lg p-4 flex flex-col gap-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <TrendingUp size={20} />
            Payoff Diagram
          </h2>

          {payoffData.length > 0 ? (
            <div className="flex-1 flex flex-col justify-end gap-1">
              {/* SVG Payoff Chart */}
              <svg width="100%" height="200" viewBox="0 0 500 200" className="border border-slate-700 rounded bg-slate-800" preserveAspectRatio="xMidYMid meet">
                {/* Calculate min/max for scaling */}
                {(() => {
                  const pnls = payoffData.map(p => p.pnl);
                  const minPnl = Math.min(...pnls, 0);
                  const maxPnl = Math.max(...pnls, 0);
                  const range = Math.max(Math.abs(minPnl), Math.abs(maxPnl)) || 100;
                  const scale = 80 / range; // Use 80% of height for data
                  const centerY = 100; // Center line at 100
                  const padding = 30;
                  const chartWidth = 500 - padding * 2;
                  
                  return (
                    <>
                      {/* Y-axis */}
                      <line x1={padding} y1="20" x2={padding} y2="180" stroke="#475569" strokeWidth="1" />
                      {/* X-axis */}
                      <line x1={padding} y1={centerY} x2={500 - padding} y2={centerY} stroke="#475569" strokeWidth="1" />
                      
                      {/* Zero line (profit line) */}
                      <line x1={padding} y1={centerY} x2={500 - padding} y2={centerY} stroke="#ef4444" strokeWidth="1" strokeDasharray="5" />
                      
                      {/* Payoff line */}
                      {payoffData.map((p, i, arr) => {
                        if (i === 0) return null;
                        const prev = arr[i - 1];
                        const x1 = padding + (i - 1) * (chartWidth / (arr.length - 1));
                        const x2 = padding + i * (chartWidth / (arr.length - 1));
                        const y1 = centerY - prev.pnl * scale;
                        const y2 = centerY - p.pnl * scale;
                        return (
                          <line
                            key={i}
                            x1={x1}
                            y1={y1}
                            x2={x2}
                            y2={y2}
                            stroke="#3b82f6"
                            strokeWidth="2"
                          />
                        );
                      })}
                      
                      {/* Y-axis labels */}
                      <text x={padding - 25} y={centerY + 5} fontSize="10" fill="#94a3b8" textAnchor="end">0</text>
                      <text x={padding - 25} y="25" fontSize="10" fill="#94a3b8" textAnchor="end">+{(range).toFixed(0)}</text>
                      <text x={padding - 25} y="185" fontSize="10" fill="#94a3b8" textAnchor="end">-{(range).toFixed(0)}</text>
                    </>
                  );
                })()}
              </svg>

              <div className="text-xs text-slate-400 text-center">Spot: {spot.toFixed(0)}</div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-slate-400">
              Add legs to see payoff
            </div>
          )}
        </div>

        {/* Right: Greeks & Summary */}
        <div className="col-span-4 bg-slate-900 border border-slate-700 rounded-lg p-4 space-y-4 overflow-auto">
          <h2 className="text-lg font-semibold text-white">Analytics</h2>

          {loading ? (
            <div className="py-8 text-center">
              <p className="text-slate-400 mb-2">Calculating Greeks...</p>
              <div className="inline-block">
                <div className="animate-spin rounded-full h-8 w-8 border border-slate-700 border-t-blue-500"></div>
              </div>
            </div>
          ) : error ? (
            <div className="bg-red-900 border border-red-700 rounded p-3">
              <p className="text-red-200 text-sm">Error: {error}</p>
              <p className="text-red-300 text-xs mt-2">Check browser console (F12) for details</p>
            </div>
          ) : greeks ? (
            <div className="space-y-4">
              {/* Portfolio Greeks */}
              <div>
                <h3 className="text-xs font-semibold text-slate-300 mb-2">Portfolio Greeks</h3>
                <div className="space-y-1 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Delta</span>
                    <span className="font-mono text-blue-400">{greeks.delta.toFixed(4)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Gamma</span>
                    <span className="font-mono text-blue-400">{greeks.gamma.toFixed(6)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Theta/Day</span>
                    <span className="font-mono text-blue-400">{greeks.theta.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Vega/1%</span>
                    <span className="font-mono text-blue-400">{greeks.vega.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Rho/1%</span>
                    <span className="font-mono text-blue-400">{greeks.rho.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* Risk/Reward */}
              {(() => {
                const rr = calculateRiskReward();
                return rr ? (
                  <div className="border-t border-slate-700 pt-2">
                    <h3 className="text-xs font-semibold text-slate-300 mb-2">Risk/Reward</h3>
                    <div className="space-y-1 text-xs">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Max Profit</span>
                        <span className="font-mono text-green-400">₹{rr.maxProfit.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">Max Loss</span>
                        <span className="font-mono text-red-400">₹-{rr.maxLoss.toFixed(2)}</span>
                      </div>
                      <div className="flex justify-between bg-slate-800 p-1 rounded">
                        <span className="text-slate-300 font-semibold">Ratio</span>
                        <span className="font-mono text-yellow-400">1:{rr.ratio.toFixed(2)}</span>
                      </div>
                    </div>
                  </div>
                ) : null;
              })()}

              {/* Breakeven */}
              {(() => {
                const breakevens = calculateBreakevens();
                return breakevens.length > 0 ? (
                  <div className="border-t border-slate-700 pt-2">
                    <h3 className="text-xs font-semibold text-slate-300 mb-2">Breakeven(s)</h3>
                    <div className="space-y-1 text-xs">
                      {breakevens.map((be, i) => (
                        <div key={i} className="flex justify-between">
                          <span className="text-slate-400">BE {i + 1}</span>
                          <span className="font-mono text-purple-400">₹{be.toFixed(2)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null;
              })()}

              {/* P&L Table */}
              {(() => {
                const pnlAtSpots = getPnLAtSpots();
                return pnlAtSpots.length > 0 ? (
                  <div className="border-t border-slate-700 pt-2">
                    <h3 className="text-xs font-semibold text-slate-300 mb-2">P&L at Spots</h3>
                    <div className="space-y-1 text-xs max-h-48 overflow-y-auto">
                      {pnlAtSpots.map((p, i) => (
                        <div
                          key={i}
                          className={`flex justify-between px-1 py-0.5 rounded ${
                            Math.abs(p.pnl) < 1
                              ? 'bg-slate-700'
                              : p.pnl > 0
                              ? 'bg-green-900 bg-opacity-30'
                              : 'bg-red-900 bg-opacity-30'
                          }`}
                        >
                          <span className="text-slate-400">₹{p.spot.toFixed(0)}</span>
                          <span
                            className={`font-mono ${
                              p.pnl > 0 ? 'text-green-400' : p.pnl < 0 ? 'text-red-400' : 'text-slate-400'
                            }`}
                          >
                            {p.pnl > 0 ? '+' : ''}{p.pnl.toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null;
              })()}
            </div>
          ) : (
            <p className="text-slate-400 text-sm py-8">Add legs and click "Calculate Greeks" to see analytics</p>
          )}

          {/* Summary */}
          <div className="pt-4 border-t border-slate-700 space-y-2">
            <h3 className="text-sm font-semibold text-slate-300">Summary</h3>
            <div className="text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-slate-400">Total Legs:</span>
                <span className="text-white">{legs.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Spot Price:</span>
                <span className="text-white">₹{spot.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Max Profit:</span>
                <span className="text-green-400">
                  {payoffData.length > 0
                    ? `₹${Math.max(...payoffData.map(p => p.pnl)).toFixed(0)}`
                    : '-'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Max Loss:</span>
                <span className="text-red-400">
                  {payoffData.length > 0
                    ? `₹${Math.min(...payoffData.map(p => p.pnl)).toFixed(0)}`
                    : '-'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Save Modal */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-96 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-bold text-white">
                {strategyId ? 'Update Strategy' : 'Save New Strategy'}
              </h3>
              <button onClick={() => setShowSaveDialog(false)} title="Close dialog">
                <X size={20} className="text-slate-300" />
              </button>
            </div>

            <div className="space-y-2">
              <label className="block text-sm text-slate-300">Strategy Name</label>
              <input
                type="text"
                value={strategyName}
                onChange={(e) => setStrategyName(e.target.value)}
                placeholder="e.g., Bull Call Spread - NIFTY"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                onKeyDown={(e) => e.key === 'Enter' && handleSave()}
              />
            </div>

            {saveStatus === 'error' && (
              <div className="bg-red-900 border border-red-700 rounded p-2">
                <p className="text-red-200 text-xs">Failed to save strategy</p>
              </div>
            )}

            <div className="flex gap-2">
              <button
                onClick={handleSave}
                disabled={!strategyName.trim() || saveStatus === 'saving'}
                className="flex-1 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white rounded font-semibold transition"
              >
                {saveStatus === 'saving' ? 'Saving...' : 'Save'}
              </button>
              <button
                onClick={() => setShowSaveDialog(false)}
                className="flex-1 px-3 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Load Strategies Modal */}
      {showLoadDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-6 w-full max-w-2xl max-h-96 flex flex-col space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-bold text-white">Load Strategy</h3>
              <button onClick={() => setShowLoadDialog(false)} title="Close dialog">
                <X size={20} className="text-slate-300" />
              </button>
            </div>

            {loadingStrategies ? (
              <div className="text-center py-8">
                <p className="text-slate-300">Loading strategies...</p>
              </div>
            ) : savedStrategies.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-slate-400">No saved strategies yet</p>
              </div>
            ) : (
              <div className="overflow-y-auto space-y-2">
                {savedStrategies.map((strategy) => (
                  <div
                    key={strategy.id}
                    className="bg-slate-800 border border-slate-700 rounded p-3 flex justify-between items-center hover:bg-slate-750 transition"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold text-white truncate">{strategy.name}</p>
                      <p className="text-xs text-slate-400 mt-1">
                        Underlying: {strategy.underlying} | Expiry: {strategy.parameters?.expiry || 'N/A'} | Max Profit: {strategy.parameters?.max_profit?.toFixed(2) || 'N/A'} | Max Loss: {strategy.parameters?.max_loss?.toFixed(2) || 'N/A'}
                      </p>
                    </div>
                    <div className="flex gap-2 ml-2">
                      <button
                        onClick={() => handleLoadStrategy(strategy)}
                        className="px-3 py-1 bg-green-600 hover:bg-green-700 text-white rounded text-sm transition"
                      >
                        Load
                      </button>
                      <button
                        onClick={() => handleDeleteStrategy(strategy.id)}
                        className="px-3 py-1 bg-red-600 hover:bg-red-700 text-white rounded text-sm transition"
                        title="Delete strategy"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowLoadDialog(false)}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StrategyBuilder;
