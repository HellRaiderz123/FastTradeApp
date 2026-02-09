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
  strike_type?: 'ABSOLUTE' | 'RELATIVE';  // Strike mode
  strike_offset?: number;  // Offset from ATM (used when strike_type is RELATIVE)
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

type StrategyTemplate =
  | 'CUSTOM'
  | 'BULL_PUT'
  | 'BEAR_CALL'
  | 'IRON_CONDOR'
  | 'BULL_CALL'
  | 'BEAR_PUT'
  | 'SHORT_STRANGLE'
  | 'LONG_STRADDLE'
  | 'SHORT_STRADDLE'
  | 'BUTTERFLY_SPREAD'
  | 'LONG_STRANGLE'
  | 'CALENDAR_SPREAD';

const LOT_SIZES: Record<string, number> = {
  NIFTY: 65,
  BANKNIFTY: 15,
  FINNIFTY: 40,
};

const STRIKE_STEPS: Record<string, number> = {
  NIFTY: 50,
  BANKNIFTY: 100,
  FINNIFTY: 50,
};

const StrategyBuilder: React.FC = () => {
  const [legs, setLegs] = useState<OptionLeg[]>([]);
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [underlying, setUnderlying] = useState<'NIFTY' | 'BANKNIFTY' | 'FINNIFTY'>('NIFTY');
  const [spot, setSpot] = useState<number>(26150);
  const [atm, setAtm] = useState<number>(26150);
  const wsRef = React.useRef<WebSocket | null>(null);
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
  const [daysToExpiry, setDaysToExpiry] = useState<number>(0);
  const [fetchingSpot, setFetchingSpot] = useState(true);
  const [strategyName, setStrategyName] = useState('');
  const [tpPct, setTpPct] = useState<number>(0);
  const [slPct, setSlPct] = useState<number>(0);
  const [trailingSlPct, setTrailingSlPct] = useState<number>(0);
  const [entryTime, setEntryTime] = useState<string>('09:20');
  const [exitTime, setExitTime] = useState<string>('15:20');
  const [savedStrategies, setSavedStrategies] = useState<any[]>([]);
  const [loadingStrategies, setLoadingStrategies] = useState(false);

  const [template, setTemplate] = useState<StrategyTemplate>('CUSTOM');
  const [assumedVolPct, setAssumedVolPct] = useState<number>(18); // for POP estimation
  const [popPct, setPopPct] = useState<number | null>(null);
  const [popVerdict, setPopVerdict] = useState<'GOOD' | 'NEUTRAL' | 'RISKY' | null>(null);

  const lotSize = LOT_SIZES[underlying] || 1;
  const strikeStep = STRIKE_STEPS[underlying] || 50;

  // Drag & drop handlers for reordering legs
  const handleDragStart = (index: number) => {
    setDragIndex(index);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    // Allow dropping by preventing default
    e.preventDefault();
  };

  const handleDrop = (dropIndex: number) => {
    if (dragIndex === null || dragIndex === dropIndex) return;
    const updated = [...legs];
    const [moved] = updated.splice(dragIndex, 1);
    updated.splice(dropIndex, 0, moved);
    setLegs(updated);
    setDragIndex(null);
  };

  // Fetch spot price and expiry dates on component mount, and subscribe to live spot price via WebSocket
  useEffect(() => {
    let ws: WebSocket | null = null;
    const fetchMarketData = async () => {
      try {
        setFetchingSpot(true);
        // Fetch spot price (initial)
        const spotResponse = await marketAPI.getLTP(underlying);
        const spotData = spotResponse?.data || spotResponse;
        if (spotData?.ltp) {
          setSpot(Number(spotData.ltp));
          setAtm(Number(spotData.ltp));
        }
        // Fetch available expiry dates
        const expiriesResponse = await marketAPI.getAvailableExpiries(underlying);
        const expiryData = expiriesResponse?.data || expiriesResponse;
        if (expiryData?.expiries && Array.isArray(expiryData.expiries) && expiryData.expiries.length > 0) {
          setExpiryDates(expiryData.expiries);
          setSelectedExpiry(expiryData.expiries[0]);
          const today = new Date();
          const dte = Math.max(1, Math.ceil((new Date(expiryData.expiries[0]).getTime() - today.getTime()) / (1000 * 60 * 60 * 24)));
          setDaysToExpiry(dte);
        } else {
          // Set defaults if API returns empty
          const today = new Date();
          const fallbackExpiries = [
            new Date(today.getTime() + 6 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            new Date(today.getTime() + 13 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            new Date(today.getTime() + 20 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            new Date(today.getTime() + 27 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          ];
          setExpiryDates(fallbackExpiries);
          setSelectedExpiry(fallbackExpiries[0]);
          const dte = Math.max(1, Math.ceil((new Date(fallbackExpiries[0]).getTime() - today.getTime()) / (1000 * 60 * 60 * 24)));
          setDaysToExpiry(dte);
        }
      } catch (err) {
        // Keep defaults if API fails
      } finally {
        setFetchingSpot(false);
      }
    };

    fetchMarketData();

    // WebSocket for live spot price
    try {
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const wsUrl = `${proto}://${window.location.host}/api/ws/spot`;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          // Expecting { type: 'spot_update', ltp: number }
          if (msg?.type === 'spot_update' && typeof msg.ltp === 'number') {
            setSpot(msg.ltp);
            setAtm(msg.ltp);
          }
        } catch (e) {
          // ignore malformed messages
        }
      };
    } catch (e) {
      // ignore ws errors
    }

    return () => {
      if (wsRef.current) wsRef.current.close();
      wsRef.current = null;
    };
  }, [underlying]);

  // Update DTE when expiry changes
  useEffect(() => {
    if (selectedExpiry) {
      const today = new Date();
      const dte = Math.max(1, Math.ceil((new Date(selectedExpiry).getTime() - today.getTime()) / (1000 * 60 * 60 * 24)));
      setDaysToExpiry(dte);
    }
  }, [selectedExpiry]);

  // Update relative strikes when ATM changes
  useEffect(() => {
    const updatedLegs = legs.map(leg => {
      if (leg.strike_type === 'RELATIVE') {
        const newStrike = calculateAbsoluteStrike(leg.strike_offset || 0);
        if (newStrike !== leg.strike) {
          // Fetch new premium for updated strike
          fetchPremium(newStrike, leg.option_type).then(premium => {
            setLegs(prevLegs =>
              prevLegs.map(l =>
                l.id === leg.id ? { ...l, strike: newStrike, premium } : l
              )
            );
          });
          return { ...leg, strike: newStrike };
        }
      }
      return leg;
    });
    
    if (JSON.stringify(updatedLegs) !== JSON.stringify(legs)) {
      setLegs(updatedLegs);
    }
  }, [atm]);

  // Fetch premium when strike is selected
  const fetchPremium = async (strike: number, optionType: 'CE' | 'PE') => {
    try {
      if (!selectedExpiry) {
        console.warn('No expiry selected, cannot fetch premium');
        return 0;
      }
      
      console.log(`Fetching premium for ${strike} ${optionType} expiry ${selectedExpiry}`);
      const premiumResponse = await marketAPI.getOptionPremium(underlying, strike, optionType, selectedExpiry);
      
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

  const getStep = () => strikeStep;

  const roundToStep = (value: number, step: number) => Math.round(value / step) * step;

  // Calculate absolute strike from relative offset
  const calculateAbsoluteStrike = (offset: number) => {
    const atmStrike = Math.round(atm / strikeStep) * strikeStep;
    return atmStrike + offset;
  };

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

    if (tpl === 'BULL_CALL') {
      // Debit call spread: BUY lower strike call, SELL higher strike call
      const longCall = atmStrike - width;
      const shortCall = longCall + width;
      newLegs = [
        { id: `${Date.now()}-lc`, type: 'BUY', option_type: 'CE', strike: longCall, quantity: 1 },
        { id: `${Date.now()}-sc`, type: 'SELL', option_type: 'CE', strike: shortCall, quantity: 1 },
      ];
    }

    if (tpl === 'BEAR_PUT') {
      // Debit put spread: BUY higher strike put, SELL lower strike put
      const longPut = atmStrike + width;
      const shortPut = longPut - width;
      newLegs = [
        { id: `${Date.now()}-lp`, type: 'BUY', option_type: 'PE', strike: longPut, quantity: 1 },
        { id: `${Date.now()}-sp`, type: 'SELL', option_type: 'PE', strike: shortPut, quantity: 1 },
      ];
    }

    if (tpl === 'SHORT_STRANGLE') {
      const shortPut = atmStrike - offset;
      const shortCall = atmStrike + offset;
      newLegs = [
        { id: `${Date.now()}-sp`, type: 'SELL', option_type: 'PE', strike: shortPut, quantity: 1 },
        { id: `${Date.now()}-sc`, type: 'SELL', option_type: 'CE', strike: shortCall, quantity: 1 },
      ];
    }

    if (tpl === 'LONG_STRADDLE') {
      const k = atmStrike;
      newLegs = [
        { id: `${Date.now()}-bc`, type: 'BUY', option_type: 'CE', strike: k, quantity: 1 },
        { id: `${Date.now()}-bp`, type: 'BUY', option_type: 'PE', strike: k, quantity: 1 },
      ];
    }

    if (tpl === 'SHORT_STRADDLE') {
      const k = atmStrike;
      newLegs = [
        { id: `${Date.now()}-sc`, type: 'SELL', option_type: 'CE', strike: k, quantity: 1 },
        { id: `${Date.now()}-sp`, type: 'SELL', option_type: 'PE', strike: k, quantity: 1 },
      ];
    }

    if (tpl === 'BUTTERFLY_SPREAD') {
      // Butterfly: Buy 1 lower, Sell 2 middle, Buy 1 upper (equal width)
      const lowerStrike = atmStrike - width;
      const middleStrike = atmStrike;
      const upperStrike = atmStrike + width;
      newLegs = [
        { id: `${Date.now()}-bl`, type: 'BUY', option_type: 'CE', strike: lowerStrike, quantity: 1 },
        { id: `${Date.now()}-sm1`, type: 'SELL', option_type: 'CE', strike: middleStrike, quantity: 2 },
        { id: `${Date.now()}-bu`, type: 'BUY', option_type: 'CE', strike: upperStrike, quantity: 1 },
      ];
    }

    if (tpl === 'LONG_STRANGLE') {
      const longPut = atmStrike - offset;
      const longCall = atmStrike + offset;
      newLegs = [
        { id: `${Date.now()}-bp`, type: 'BUY', option_type: 'PE', strike: longPut, quantity: 1 },
        { id: `${Date.now()}-bc`, type: 'BUY', option_type: 'CE', strike: longCall, quantity: 1 },
      ];
    }

    if (tpl === 'CALENDAR_SPREAD') {
      // Calendar spread: Sell near-month, Buy far-month (same strike)
      // Note: This is a simplified version. In reality, you'd need 2 different expiries.
      // For now, we'll use same expiry but user can manually adjust
      const k = atmStrike;
      newLegs = [
        { id: `${Date.now()}-sc`, type: 'SELL', option_type: 'CE', strike: k, quantity: 1 },
        { id: `${Date.now()}-bc`, type: 'BUY', option_type: 'CE', strike: k, quantity: 1 },
      ];
      setError('Calendar spread requires different expiries. Please adjust legs manually after creation.');
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
      strike_type: 'ABSOLUTE',  // Default to absolute
      strike_offset: 0,
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
        let updated = {
          ...leg,
          [field]: field === 'quantity' ? normalizeLots(value) : value,
        };
        
        // When switching to RELATIVE mode, calculate offset from current strike
        if (field === 'strike_type' && value === 'RELATIVE') {
          const atmStrike = Math.round(atm / 50) * 50;
          const offset = leg.strike - atmStrike;
          updated = { ...updated, strike_offset: offset };
        }
        
        // When switching to ABSOLUTE mode, use current strike
        if (field === 'strike_type' && value === 'ABSOLUTE') {
          updated = { ...updated, strike_offset: 0 };
        }
        
        // When offset changes in RELATIVE mode, update strike
        if (field === 'strike_offset' && leg.strike_type === 'RELATIVE') {
          const newStrike = calculateAbsoluteStrike(Number(value));
          updated = { ...updated, strike: newStrike };
        }
        
        // If strike or option_type changed, fetch new premium
        if ((field === 'strike' || field === 'option_type' || field === 'strike_offset') && selectedExpiry) {
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
        quantity: Math.max(1, Math.floor(leg.quantity)) * lotSize,
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
          const qty = Math.max(1, Math.floor(leg.quantity)) * lotSize;
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

  // --- POP calculation helpers ---
  const erf = (x: number) => {
    // Abramowitz and Stegun formula 7.1.26
    const sign = x >= 0 ? 1 : -1;
    const a1 = 0.254829592;
    const a2 = 0.284496736;
    const a3 = 1.421413741;
    const a4 = 1.453152027;
    const a5 = 1.061405429;
    const p = 0.3275911;
    const t = 1 / (1 + p * Math.abs(x));
    const y = 1 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
    return sign * y;
  };

  const normalCdf = (x: number, mean: number, std: number) => {
    if (std <= 0) return x >= mean ? 1 : 0;
    return 0.5 * (1 + erf((x - mean) / (std * Math.SQRT2)));
  };

  const computePopFromPayoff = (data: StrategyPayoff[], meanSpot: number, volPct: number, dteDays: number): number | null => {
    if (!data || data.length < 2) return null;
    const t = Math.max(1, dteDays) / 365;
    const std = Math.max(1e-6, meanSpot * (volPct / 100) * Math.sqrt(t));

    // Sort by spot ascending
    const points = [...data].sort((a, b) => a.spot - b.spot);
    let prob = 0;

    for (let i = 0; i < points.length - 1; i++) {
      const a = points[i];
      const b = points[i + 1];
      const cdfA = normalCdf(a.spot, meanSpot, std);
      const cdfB = normalCdf(b.spot, meanSpot, std);
      const intervalMass = Math.max(0, cdfB - cdfA);

      // If both endpoints are profitable, count entire interval
      if (a.pnl >= 0 && b.pnl >= 0) {
        prob += intervalMass;
        continue;
      }

      // If both endpoints are loss, skip
      if (a.pnl <= 0 && b.pnl <= 0) {
        continue;
      }

      // Endpoint signs differ -> find zero crossing by linear interpolation
      const denom = (b.pnl - a.pnl);
      if (Math.abs(denom) < 1e-9) continue;
      const ratio = Math.abs(a.pnl) / (Math.abs(a.pnl) + Math.abs(b.pnl));
      const beSpot = a.spot + ratio * (b.spot - a.spot);
      const cdfBE = normalCdf(beSpot, meanSpot, std);

      // Determine which side is profitable
      if (a.pnl >= 0 && b.pnl <= 0) {
        prob += Math.max(0, cdfBE - cdfA);
      } else if (a.pnl <= 0 && b.pnl >= 0) {
        prob += Math.max(0, cdfB - cdfBE);
      }
    }

    return Math.min(1, Math.max(0, prob));
  };

  const recomputePop = () => {
    const pop = computePopFromPayoff(payoffData, spot, assumedVolPct, daysToExpiry);
    if (pop == null) {
      setPopPct(null);
      setPopVerdict(null);
      return;
    }
    const pct = pop * 100;
    setPopPct(pct);
    if (pct >= 65) setPopVerdict('GOOD');
    else if (pct >= 45) setPopVerdict('NEUTRAL');
    else setPopVerdict('RISKY');
  };

  useEffect(() => {
    recomputePop();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [payoffData, assumedVolPct, daysToExpiry, spot]);

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
        const qty = Math.max(1, Math.floor(leg.quantity)) * lotSize;
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
        underlying,
        parameters: {
          tp_pct: tpPct,
          sl_pct: slPct,
          trailing_sl_pct: trailingSlPct,
          entry_time: entryTime,
          exit_time: exitTime,
          expiry: selectedExpiry,
          spot_at_creation: spot,
          legs: legs.map(leg => ({
            type: leg.type,
            option_type: leg.option_type,
            strike: leg.strike,
            strike_type: leg.strike_type || 'ABSOLUTE',
            strike_offset: leg.strike_offset || 0,
            // Persist actual quantity to match execution/backtest expectations
            quantity: Math.max(1, Math.floor(leg.quantity)) * lotSize,
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
        const created = response?.data || response;
        if (created?.id) {
          // Newly created strategies default to disabled in backend; enable so it can run.
          await strategyAPI.enableStrategy(created.id);
          setStrategyId(created.id);
        }
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
      const strategyUnderlying = String(strategy.underlying || 'NIFTY').toUpperCase();
      const lotSizeForStrategy = LOT_SIZES[strategyUnderlying] || 1;
      const params = strategy.parameters || {};
      const strategyLegs = params.legs || [];
      
      // Populate the builder with loaded strategy data
      setLegs(strategyLegs.map((leg: any, idx: number) => ({
        id: `leg-${Date.now()}-${idx}`,
        type: leg.type,
        option_type: leg.option_type,
        strike: leg.strike,
        strike_type: leg.strike_type || 'ABSOLUTE',
        strike_offset: leg.strike_offset || 0,
        // Backend stores actual quantity; UI uses lots.
        quantity: (() => {
          const q = Number(leg.quantity);
          if (!Number.isFinite(q) || q <= 0) return 1;
          if (q >= lotSizeForStrategy && q % lotSizeForStrategy === 0) return q / lotSizeForStrategy;
          return q; // backward compat if older saved strategies used lots
        })(),
        premium: leg.premium,
      })));
      
      setUnderlying(strategyUnderlying as typeof underlying);
      setSelectedExpiry(params.expiry || '');
      setSpot(params.spot_at_creation || spot);
      setStrategyId(strategy.id);
      setStrategyName(strategy.name);

      setTpPct(Number(params.tp_pct) || 0);
      setSlPct(Number(params.sl_pct) || 0);
      setTrailingSlPct(Number(params.trailing_sl_pct) || 0);
      setEntryTime(params.entry_time || '09:20');
      setExitTime(params.exit_time || '15:20');
      
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
    setTpPct(0);
    setSlPct(0);
    setTrailingSlPct(0);
    setEntryTime('09:20');
    setExitTime('15:20');
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
                <optgroup label="Credit Spreads">
                  <option value="BULL_PUT">Bull Put Spread</option>
                  <option value="BEAR_CALL">Bear Call Spread</option>
                  <option value="IRON_CONDOR">Iron Condor</option>
                </optgroup>
                <optgroup label="Debit Spreads">
                  <option value="BULL_CALL">Bull Call Spread</option>
                  <option value="BEAR_PUT">Bear Put Spread</option>
                </optgroup>
                <optgroup label="Straddles & Strangles">
                  <option value="LONG_STRADDLE">Long Straddle (Buy ATM Call + Put)</option>
                  <option value="SHORT_STRADDLE">Short Straddle (Sell ATM Call + Put)</option>
                  <option value="LONG_STRANGLE">Long Strangle (Buy OTM Call + Put)</option>
                  <option value="SHORT_STRANGLE">Short Strangle (Sell OTM Call + Put)</option>
                </optgroup>
                <optgroup label="Advanced">
                  <option value="BUTTERFLY_SPREAD">Butterfly Spread (3 strikes)</option>
                  <option value="CALENDAR_SPREAD">Calendar Spread (Same strike, different expiry)</option>
                </optgroup>
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

          {/* Underlying */}
          <div className="space-y-2">
            <label className="text-xs text-slate-300">Underlying</label>
            <select
              value={underlying}
              onChange={(e) => setUnderlying(e.target.value as typeof underlying)}
              className="w-full px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm"
              aria-label="Underlying"
            >
              <option value="NIFTY">NIFTY50</option>
              <option value="BANKNIFTY">BANKNIFTY</option>
              <option value="FINNIFTY">FINNIFTY</option>
            </select>
          </div>

          {/* Spot Price Input */}
          <div className="space-y-2">
            <label className="text-xs text-slate-300">Spot Price (Live: {atm.toFixed(2)})</label>
            <div className="flex gap-2">
              <input
                type="number"
                value={spot.toFixed(2)}
                onChange={(e) => setSpot(Number(e.target.value))}
                className="flex-1 px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                aria-label="Spot price"
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
            <label className="text-xs text-slate-300 flex items-center gap-2">
              <Calendar size={14} />
              Expiry Date
              <span className="ml-auto px-2 py-0.5 bg-green-900 text-green-200 text-[10px] font-semibold rounded">
                WEEKLY ONLY
              </span>
            </label>
            <select
              value={selectedExpiry || ''}
              onChange={(e) => setSelectedExpiry(e.target.value)}
              className="w-full px-2 py-1 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                aria-label="Expiry date"
            >
              {expiryDates.length === 0 ? (
                <option value="">Loading expiries...</option>
              ) : (
                expiryDates.map((expiry) => {
                  const expiryDate = new Date(expiry);
                  const daysToExpiry = Math.ceil((expiryDate.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
                  const weekday = expiryDate.toLocaleDateString('en-US', { weekday: 'short' });
                  
                  return (
                    <option key={expiry} value={expiry}>
                      {expiryDate.toLocaleDateString('en-US', {
                        month: 'short',
                        day: 'numeric',
                        year: 'numeric',
                      })}
                      {' '}
                      ({weekday}) - {daysToExpiry} day{daysToExpiry !== 1 ? 's' : ''}
                    </option>
                  );
                })
              )}
            </select>
            {/* Info Display */}
            <div className="text-xs text-slate-400 flex items-center justify-between">
              <span>{expiryDates.length} weekly expiries available</span>
              {selectedExpiry && (
                <span className="text-green-400">
                  {daysToExpiry} DTE
                </span>
              )}
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

          {/* Legs List (Drag & Drop to reorder) */}
          <div className="space-y-3 flex-1 overflow-y-auto">
            {legs.length === 0 ? (
              <p className="text-slate-400 text-sm text-center py-8">No legs added yet</p>
            ) : (
              legs.map((leg, idx) => (
                <div
                  key={leg.id}
                  className="bg-slate-800 border border-slate-700 rounded p-3 space-y-2"
                  draggable
                  onDragStart={() => handleDragStart(idx)}
                  onDragOver={handleDragOver}
                  onDrop={() => handleDrop(idx)}
                  title="Drag to reorder"
                >
                  <div className="flex justify-between items-center">
                    <div className="flex gap-2">
                      <select
                        value={leg.type}
                        onChange={(e) => updateLeg(leg.id, 'type', e.target.value)}
                        className="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                        aria-label="Leg action"
                      >
                        <option>BUY</option>
                        <option>SELL</option>
                      </select>
                      <select
                        value={leg.option_type}
                        onChange={(e) => updateLeg(leg.id, 'option_type', e.target.value)}
                        className="px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                        aria-label="Option type"
                      >
                        <option>CE</option>
                        <option>PE</option>
                      </select>
                    </div>
                    <button
                      onClick={() => removeLeg(leg.id)}
                      className="p-1 hover:bg-red-600 rounded text-red-300"
                      title="Remove leg"
                      aria-label="Remove leg"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>

                  {/* Strike Mode Toggle */}
                  <div className="space-y-2">
                    <label className="text-xs text-slate-400">Strike Mode</label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => updateLeg(leg.id, 'strike_type', 'ABSOLUTE')}
                        className={`flex-1 px-2 py-1 text-xs rounded transition ${
                          (leg.strike_type || 'ABSOLUTE') === 'ABSOLUTE'
                            ? 'bg-blue-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                        title="Use fixed strike price"
                      >
                        Absolute
                      </button>
                      <button
                        onClick={() => updateLeg(leg.id, 'strike_type', 'RELATIVE')}
                        className={`flex-1 px-2 py-1 text-xs rounded transition ${
                          leg.strike_type === 'RELATIVE'
                            ? 'bg-purple-600 text-white'
                            : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                        }`}
                        title="Use offset from ATM (dynamic)"
                      >
                        Relative
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    {leg.strike_type === 'RELATIVE' ? (
                      <>
                        <div>
                          <label className="text-xs text-slate-400">
                            Offset from ATM
                            <span className="ml-1 text-slate-500">(ATM: {Math.round(atm / strikeStep) * strikeStep})</span>
                          </label>
                          <input
                            type="number"
                            value={leg.strike_offset || 0}
                            onChange={(e) => updateLeg(leg.id, 'strike_offset', Number(e.target.value))}
                            step={strikeStep}
                            className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                            aria-label="Strike offset"
                            placeholder="e.g., 0, +100, -200"
                          />
                        </div>
                        <div>
                          <label className="text-xs text-slate-400">
                            Calculated Strike
                          </label>
                          <input
                            type="number"
                            value={leg.strike}
                            disabled
                            className="w-full px-2 py-1 bg-slate-900 border border-slate-600 rounded text-slate-400 text-xs cursor-not-allowed"
                            aria-label="Calculated strike"
                            title="Auto-calculated from ATM + Offset"
                          />
                        </div>
                      </>
                    ) : (
                      <div>
                        <label className="text-xs text-slate-400">Strike</label>
                        <input
                          type="number"
                          value={leg.strike}
                          onChange={(e) => updateLeg(leg.id, 'strike', Number(e.target.value))}
                          step={strikeStep}
                          className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                          aria-label="Strike"
                        />
                      </div>
                    )}
                    <div>
                      <label className="text-xs text-slate-400">Lots (1 lot = {lotSize})</label>
                      <input
                        type="number"
                        value={leg.quantity}
                        onChange={(e) => updateLeg(leg.id, 'quantity', Number(e.target.value))}
                        min={1}
                        step={1}
                        className="w-full px-2 py-1 bg-slate-700 border border-slate-600 rounded text-white text-xs"
                        aria-label="Lots"
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
                      aria-label="Premium"
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

              {/* POP disabled: hidden to avoid misleading results */}

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
                aria-label="Strategy name"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="block text-sm text-slate-300">Profit Target (%)</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={tpPct}
                  onChange={(e) => setTpPct(Number(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                  aria-label="Profit target percent"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-sm text-slate-300">Stop Loss (%)</label>
                <input
                  type="number"
                  min={0}
                  max={300}
                  step={1}
                  value={slPct}
                  onChange={(e) => setSlPct(Number(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                  aria-label="Stop loss percent"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-sm text-slate-300">Trailing SL (%)</label>
                <input
                  type="number"
                  min={0}
                  max={300}
                  step={1}
                  value={trailingSlPct}
                  onChange={(e) => setTrailingSlPct(Number(e.target.value) || 0)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                  aria-label="Trailing stop loss percent"
                />
              </div>

              <div className="space-y-1">
                <label className="block text-sm text-slate-300">Entry Time</label>
                <input
                  type="time"
                  value={entryTime}
                  onChange={(e) => setEntryTime(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                  aria-label="Entry time"
                />
              </div>

              <div className="space-y-1 col-span-2">
                <label className="block text-sm text-slate-300">Exit Time</label>
                <input
                  type="time"
                  value={exitTime}
                  onChange={(e) => setExitTime(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-800 border border-slate-600 rounded text-white text-sm"
                  aria-label="Exit time"
                />
              </div>
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
                        Underlying: {strategy.underlying === 'NIFTY' ? 'NIFTY50' : strategy.underlying} | Expiry: {strategy.parameters?.expiry || 'N/A'} | Max Profit: {strategy.parameters?.max_profit?.toFixed(2) || 'N/A'} | Max Loss: {strategy.parameters?.max_loss?.toFixed(2) || 'N/A'}
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
