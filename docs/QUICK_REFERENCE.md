# 🚀 FastTradeApp - Implementation Quick Reference

**TL;DR:** Your app is 60% complete. Add Multi-Strategy + Backtest + Builder to reach Algorooms parity.

---

## 📊 COMPLETION STATUS

| Component | Status | Effort to Complete |
|-----------|--------|-------------------|
| **Core Trading** | ✅ 95% | Done |
| → Paper trading | ✅ Done | - |
| → Zerodha integration | ✅ Done | - |
| → Order execution | ✅ Done | - |
| → Position tracking | ✅ Done | - |
| **Risk Management** | ✅ 85% | Small additions |
| → Kill switch | ✅ Done | - |
| → Daily limits | ✅ Done | - |
| → Strike validation | ✅ Done | - |
| → Greeks tracking | ⚠️ 20% | 2-3 days |
| **Data Pipeline** | ✅ 90% | Small additions |
| → Candle fetching | ✅ Done | - |
| → Signal generation | ✅ Done | - |
| → VIX tracking | ✅ Done | - |
| → Multi-timeframe | ⚠️ 0% | 2-3 days |
| **Strategy Management** | ⚠️ 20% | CRITICAL |
| → Single strategy | ✅ 100% | - |
| → Multi-strategy | ❌ 0% | 4-5 days |
| → Strategy builder | ❌ 0% | 6-8 days |
| → Backtest engine | ❌ 0% | 5-7 days |
| **Analytics** | ⚠️ 30% | Medium additions |
| → Daily P&L | ✅ Done | - |
| → Trade stats | ✅ Done | - |
| → Performance metrics | ⚠️ 20% | 2-3 days |
| **Frontend** | ✅ 70% | Medium additions |
| → Dashboard | ✅ Done | - |
| → Positions page | ✅ Done | - |
| → Journal | ✅ Done | - |
| → Strategy builder UI | ❌ 0% | 4-5 days |
| → Backtest UI | ❌ 0% | 2-3 days |
| → Analytics page | ⚠️ 20% | 2-3 days |

**Total Completion:** 60%  
**To Reach Algorooms Parity:** Add 30% (Multi-Strategy + Backtest + Builder)  
**Time Estimate:** 4-6 weeks (if focused)

---

## 🎯 CRITICAL PATH (Do These First)

### Must Have (Blocking)
1. **Multi-Strategy Support** (4-5 days)
   - Without this: Can only run ONE strategy at a time
   - Parity impact: HIGH
   - Recommended: Phase 2 in roadmap

2. **Backtest Engine** (5-7 days)
   - Without this: Cannot validate strategies before live
   - Parity impact: HIGH
   - Recommended: Phase 3 in roadmap

3. **Strategy Builder** (6-8 days)
   - Without this: Only developers can create strategies
   - Parity impact: HIGH
   - Recommended: Phase 5 in roadmap

### Should Have (High Value)
4. **Performance Metrics** (2-3 days)
   - Sharpe, Sortino, Max DD
   - Parity impact: MEDIUM

5. **Advanced Indicators** (1 week)
   - IV %, Put/Call Ratio, Greeks
   - Parity impact: MEDIUM

### Nice to Have (Optional)
6. **Multi-Timeframe Support** (2-3 days)
   - Support 1m, 5m, 15m, 1H, daily
   - Parity impact: LOW-MEDIUM

---

## 🛠️ SPECIFIC CODE ADDITIONS

### Addition #1: StrategyConfig Database Table

**File:** `backend/app/db/models.py`

```python
# Add this to the file:

class StrategyConfig(Base):
    """User-configured strategy instances"""
    __tablename__ = "strategy_configs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Identification
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    
    # Strategy details
    strategy_type = Column(String)  # option_spread_15m, etc.
    underlying = Column(String)  # NIFTY, BANKNIFTY, FINNIFTY
    
    # Configuration
    parameters = Column(JSON)  # {risk_mode, lots, capital_percent, etc.}
    
    # State
    enabled = Column(Boolean, default=False)
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), default=now_ist)
    updated_at = Column(DateTime(timezone=True), default=now_ist, onupdate=now_ist)
    created_by = Column(String, default="system")
    
    __table_args__ = (Index('idx_enabled_deployed', 'enabled', 'deployed_at'),)
```

**Migration Command:**
```bash
cd backend
alembic revision --autogenerate -m "Add StrategyConfig table"
alembic upgrade head
```

---

### Addition #2: Strategy Registry

**File:** `backend/app/core/strategies/registry.py` (NEW)

```python
from typing import Dict, Type, List, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """Interface for all trading strategies"""
    
    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute strategy logic.
        
        Args:
            context: {
                underlying: str,
                parameters: Dict,
                config_id: int (optional)
            }
        
        Returns:
            {
                approved: bool,
                strategy: str,
                reason: str,
                signal: Dict,
                context: Dict,
                ticket: Dict (if approved),
                risk_metrics: Dict
            }
        """
        pass


class StrategyRegistry:
    """Central registry for all strategies"""
    
    _strategies: Dict[str, Type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, name: str, strategy_class: Type[BaseStrategy]) -> None:
        """Register a strategy"""
        logger.info(f"Registering strategy: {name}")
        cls._strategies[name] = strategy_class
    
    @classmethod
    def get(cls, name: str) -> Type[BaseStrategy]:
        """Get strategy class by name"""
        if name not in cls._strategies:
            raise ValueError(f"Strategy not found: {name}")
        return cls._strategies[name]
    
    @classmethod
    def list_all(cls) -> List[str]:
        """List all registered strategies"""
        return list(cls._strategies.keys())
    
    @classmethod
    def list_with_metadata(cls) -> List[Dict]:
        """List strategies with metadata"""
        return [
            {
                'name': name,
                'class': cls.__name__,
                'description': cls.__doc__ or 'No description'
            }
            for name, cls in cls._strategies.items()
        ]


# Register built-in strategies at module load
def register_default_strategies():
    """Called at app startup"""
    from app.core.strategies.option_spread_15m.engine import OptionSpread15m
    
    StrategyRegistry.register('option_spread_15m', OptionSpread15m)


# Auto-register on import
register_default_strategies()
```

---

### Addition #3: Performance Metrics Calculator

**File:** `backend/app/core/utils/performance_metrics.py` (NEW)

```python
import numpy as np
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Calculate trading performance metrics"""
    
    @staticmethod
    def calculate_metrics(
        trades: List[Dict],
        equity_curve: List[float],
        risk_free_rate: float = 0.05
    ) -> Dict:
        """
        Calculate comprehensive metrics.
        
        Args:
            trades: List of {entry_price, exit_price, quantity, pnl}
            equity_curve: Daily equity values
            risk_free_rate: Annual risk-free rate (default 5%)
        
        Returns:
            Dictionary with all metrics
        """
        if not trades or len(equity_curve) < 2:
            return {
                'total_trades': 0,
                'total_return': 0,
                'sharpe_ratio': 0,
                'sortino_ratio': 0,
                'max_drawdown': 0,
            }
        
        # Basic stats
        returns = np.diff(equity_curve) / equity_curve[:-1]
        pnls = [t.get('pnl', 0) for t in trades]
        
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        
        # Sharpe Ratio
        excess_returns = returns - (risk_free_rate / 252)  # Daily risk-free
        sharpe = np.mean(excess_returns) / np.std(excess_returns) if np.std(excess_returns) > 0 else 0
        sharpe_annual = sharpe * np.sqrt(252)  # Annualized
        
        # Sortino Ratio (only downside volatility)
        downside_returns = np.minimum(excess_returns, 0)
        downside_std = np.std(downside_returns)
        sortino = np.mean(excess_returns) / downside_std if downside_std > 0 else 0
        sortino_annual = sortino * np.sqrt(252)
        
        # Max Drawdown
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak
        max_drawdown = np.min(drawdown)
        
        # Calmar Ratio
        calmar = total_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Win rate & Profit factor
        win_rate = len(winning_trades) / len(trades) if trades else 0
        
        gross_profit = sum(winning_trades) if winning_trades else 0
        gross_loss = abs(sum(losing_trades)) if losing_trades else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Recovery factor
        total_pnl = sum(pnls)
        recovery_factor = total_pnl / abs(max_drawdown * equity_curve[0]) if max_drawdown != 0 else 0
        
        return {
            'total_trades': len(trades),
            'total_return': total_return,
            'annual_return': total_return,  # Approximate
            'sharpe_ratio': float(sharpe_annual),
            'sortino_ratio': float(sortino_annual),
            'max_drawdown': float(max_drawdown),
            'calmar_ratio': float(calmar),
            'win_rate': win_rate,
            'profit_factor': float(profit_factor),
            'recovery_factor': float(recovery_factor),
            'avg_win': np.mean(winning_trades) if winning_trades else 0,
            'avg_loss': np.mean(losing_trades) if losing_trades else 0,
            'gross_profit': gross_profit,
            'gross_loss': gross_loss,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
        }
```

---

### Addition #4: Greeks Calculation

**File:** `backend/app/core/utils/greeks.py` (NEW)

```python
from typing import List, Dict


class GreeksCalculator:
    """Aggregate and track Greeks across positions"""
    
    @staticmethod
    def aggregate_position_greeks(positions: List[Dict]) -> Dict:
        """
        Sum deltas, gammas, thetas, vegas across all legs.
        
        Args:
            positions: List of {leg_type, strike, quantity, delta, gamma, theta, vega}
        
        Returns:
            {delta, gamma, theta, vega} - aggregated
        """
        total_delta = 0.0
        total_gamma = 0.0
        total_theta = 0.0
        total_vega = 0.0
        
        for pos in positions:
            quantity = pos.get('quantity', 1)
            total_delta += pos.get('delta', 0) * quantity
            total_gamma += pos.get('gamma', 0) * quantity
            total_theta += pos.get('theta', 0) * quantity
            total_vega += pos.get('vega', 0) * quantity
        
        return {
            'delta': round(total_delta, 3),  # Directional risk
            'gamma': round(total_gamma, 3),  # Gamma acceleration
            'theta': round(total_theta, 3),  # Time decay per day
            'vega': round(total_vega, 3),    # IV sensitivity per 1%
        }
    
    @staticmethod
    def interpret_greeks(greeks: Dict) -> Dict:
        """Provide human-readable interpretation"""
        delta = greeks.get('delta', 0)
        theta = greeks.get('theta', 0)
        vega = greeks.get('vega', 0)
        
        return {
            'direction': {
                'interpretation': 'Long' if delta > 0 else 'Short' if delta < 0 else 'Neutral',
                'exposure': f"{abs(delta):.0%} of 1 ATM contract"
            },
            'decay': {
                'interpretation': 'Positive' if theta > 0 else 'Negative' if theta < 0 else 'Neutral',
                'daily_pnl': f"₹{theta:.0f} per day (if IV constant)"
            },
            'volatility': {
                'interpretation': 'Long IV' if vega > 0 else 'Short IV' if vega < 0 else 'Neutral',
                'per_percent': f"₹{vega:.0f} per 1% IV change"
            }
        }
```

---

### Addition #5: IV Percentile Calculation

**File:** `backend/app/core/signals/indicators/iv_percentile.py` (NEW)

```python
from typing import Optional


def calculate_iv_percentile(
    current_iv: float,
    iv_52w_high: float,
    iv_52w_low: float
) -> Optional[float]:
    """
    Calculate IV percentile (normalized 0-100).
    
    Args:
        current_iv: Current India VIX or implied volatility
        iv_52w_high: 52-week high
        iv_52w_low: 52-week low
    
    Returns:
        Percentile 0-100 or None if range is zero
    """
    if iv_52w_high == iv_52w_low:
        return None
    
    percentile = ((current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100
    return max(0, min(100, percentile))  # Clamp to 0-100


def interpret_iv_percentile(percentile: Optional[float]) -> str:
    """Interpret IV percentile for trading"""
    if percentile is None:
        return "INSUFFICIENT_DATA"
    elif percentile >= 75:
        return "VERY_HIGH_IV"  # Good for premium selling
    elif percentile >= 50:
        return "HIGH_IV"       # Favorable for sellers
    elif percentile >= 25:
        return "MEDIUM_IV"     # Neutral
    else:
        return "LOW_IV"        # Good for premium buying
```

---

### Addition #6: Put/Call Ratio Calculation

**File:** `backend/app/core/signals/indicators/put_call_ratio.py` (NEW)

```python
from typing import Dict, List, Optional


def calculate_put_call_ratio(option_chain: List[Dict]) -> Optional[float]:
    """
    Calculate put/call ratio from option chain data.
    
    Args:
        option_chain: List of options with {instrument_type, oi, ...}
    
    Returns:
        PE OI / CE OI or None if invalid
    """
    put_oi = sum(opt.get('oi', 0) for opt in option_chain if opt.get('instrument_type') == 'PE')
    call_oi = sum(opt.get('oi', 0) for opt in option_chain if opt.get('instrument_type') == 'CE')
    
    if call_oi == 0:
        return None
    
    return put_oi / call_oi


def interpret_put_call_ratio(ratio: Optional[float]) -> str:
    """Interpret put/call ratio for sentiment"""
    if ratio is None:
        return "INSUFFICIENT_DATA"
    elif ratio > 1.5:
        return "VERY_BEARISH"    # Strong put buying
    elif ratio > 1.2:
        return "BEARISH"          # Moderate put buying
    elif ratio > 0.8:
        return "NEUTRAL"          # Balanced
    elif ratio > 0.5:
        return "BULLISH"          # Moderate call buying
    else:
        return "VERY_BULLISH"    # Strong call buying
```

---

## 🚀 NEXT IMMEDIATE STEPS

### Week 1 (Right Now)
```bash
# 1. Add StrategyConfig table
cd backend
alembic revision --autogenerate -m "Add StrategyConfig table"
alembic upgrade head

# 2. Create registry system (copy code above)
cp code_samples/registry.py backend/app/core/strategies/registry.py

# 3. Create utility modules
cp code_samples/performance_metrics.py backend/app/core/utils/
cp code_samples/greeks.py backend/app/core/utils/
cp code_samples/iv_percentile.py backend/app/core/signals/indicators/
cp code_samples/put_call_ratio.py backend/app/core/signals/indicators/

# 4. Test imports
cd backend
python -c "from app.core.strategies.registry import StrategyRegistry; print(StrategyRegistry.list_all())"
```

### Week 2-3
- Implement strategy CRUD API (`/api/routes/strategies.py`)
- Create backtest engine (`/api/routes/backtest.py`)
- Update execution to support multi-strategy

### Week 4-5
- Build Strategy Builder UI (React component)
- Connect to backend endpoints
- E2E testing

---

## 📋 WHAT NOT TO DO (Avoid)

### ❌ Don't Build These
| Feature | Why | Alternative |
|---------|-----|-------------|
| Real-time order book | Too complex, low value | Use Zerodha quotes |
| Advanced charting | Use Recharts, good enough | Extend existing Dashboard |
| Mobile app (initially) | Takes time, less users | Focus on web |
| Account sync | Zerodha already does | Use API endpoints |
| Custom indicators | Use TA-lib, sufficient | Extend ta.py coverage |

### ❌ Don't Change
| Component | Why | Status |
|-----------|-----|--------|
| Zerodha integration | Working perfectly | ✅ Keep |
| Paper trader | Good for testing | ✅ Keep |
| Execution pipeline | Solid foundation | ✅ Keep |
| Daily capital tracking | Recently added, working | ✅ Keep |
| Intent system | Prevents race conditions | ✅ Keep |

---

## 🎓 LEARNING RESOURCES

**For Multi-Strategy:**
- Pattern: Strategy Registry + Factory pattern
- Reference: Django signals, Flask blueprints

**For Backtest:**
- Zipline (complex but comprehensive)
- Backtrader (simpler, good for options)
- VectorBT (fast, modern)

**For Greeks:**
- Black-Scholes model for calculation
- Zerodha provides pre-calculated values (better to use)

**For Indicators:**
- TA-lib documentation
- Algorooms implementation (reference)
- TradingView Pine Script (reference)

---

## 💡 PRO TIPS

1. **Start with StrategyConfig table** - Everything else builds on this
2. **Keep strategy engine pluggable** - Use registry pattern, don't hardcode
3. **Backtest must match live** - Validate paper trading = backtest
4. **Builder feedback loop** - Users create → backtest → deploy → evaluate
5. **Greeks from Zerodha** - Don't calculate, use API values (more accurate)

---

## ✅ SUCCESS CRITERIA

When you're done, you should have:

- ✅ Multiple strategies deployable from UI
- ✅ Strategies backtestable on historical data
- ✅ Non-developers can create strategies
- ✅ Sharpe ratio, Sortino, Max DD calculated
- ✅ IV percentile and Put/Call ratio displayed
- ✅ Greeks aggregation in positions
- ✅ Feature parity with Algorooms core
- ✅ Production-ready performance

---

**Last Updated:** 2026-01-06  
**Status:** Ready to Implement  
**Estimated Completion:** 4-6 weeks  
**Required Resources:** 1 senior dev + 1 junior dev
