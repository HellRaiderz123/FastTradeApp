# 🎯 FastTradeApp - Immediate Action Plan

**Status:** Ready to Execute  
**Timeline:** 4-6 weeks to feature parity  
**Owner:** Development Team

---

## 📌 QUICK ASSESSMENT

### What You Have ✅
- **Production-Ready Execution:** Paper + Zerodha live trading working
- **Risk Management:** Kill switch, daily limits, strike validation
- **Data Pipeline:** Candle scheduler, VIX tracking, daily capital snapshots
- **Modern Frontend:** React dashboard with real-time charts and statistics
- **Database Design:** SQLAlchemy ORM, proper migrations, extensible schema

### What You're Missing ❌
| Gap | Severity | Impact |
|-----|----------|--------|
| Multi-Strategy Support | 🔴 Critical | Cannot run parallel strategies |
| Strategy Builder | 🔴 Critical | No UI for non-developers |
| Backtesting | 🔴 Critical | No validation before live |
| Advanced Indicators | 🟡 High | Poor entry/exit signals |
| Performance Metrics | 🟡 High | Cannot compare strategies |
| Multi-Timeframe | 🟡 High | Limited strategy types |

---

## 🚀 PHASE 1: CLEANUP & FOUNDATION (Week 1)

**Goal:** Remove dead code, prepare architecture for multi-strategy

### Tasks
- [ ] **Remove deprecated files**
  ```
  - backend/app/api/option_spread.py (OLD API, routes/ is new)
  - Archive test files → /tests/ folder
  - Cleanup old documentation
  ```

- [ ] **Create Strategy Registry System**
  ```python
  # File: backend/app/core/strategies/registry.py
  
  from typing import Dict, Type, List
  from abc import ABC, abstractmethod
  
  class BaseStrategy(ABC):
      """All strategies inherit from this"""
      @abstractmethod
      def run(self, context: Dict) -> Dict:
          pass
  
  class StrategyRegistry:
      _strategies: Dict[str, Type[BaseStrategy]] = {}
      
      @classmethod
      def register(cls, name: str, strategy_class: Type[BaseStrategy]):
          cls._strategies[name] = strategy_class
      
      @classmethod
      def get(cls, name: str) -> Type[BaseStrategy]:
          return cls._strategies.get(name)
      
      @classmethod
      def list_all(cls) -> List[str]:
          return list(cls._strategies.keys())
  
  # Usage in strategies:
  StrategyRegistry.register('option_spread_15m', OptionSpread15m)
  ```

- [ ] **Add StrategyConfig Database Table**
  ```python
  # File: backend/app/db/models.py (append)
  
  class StrategyConfig(Base):
      """User-configured strategy parameters"""
      __tablename__ = "strategy_configs"
      
      id = Column(Integer, primary_key=True, index=True)
      name = Column(String, unique=True, index=True)
      description = Column(String, nullable=True)
      underlying = Column(String)  # NIFTY, BANKNIFTY, FINNIFTY
      strategy_type = Column(String)  # option_spread_15m, etc.
      enabled = Column(Boolean, default=False)
      parameters = Column(JSON)  # {risk_mode: BALANCED, lots: 1, ...}
      
      created_at = Column(DateTime, default=now_ist)
      updated_at = Column(DateTime, default=now_ist, onupdate=now_ist)
      deployed_at = Column(DateTime, nullable=True)
      created_by = Column(String, default="system")
  ```

- [ ] **Create Strategy Configuration API Endpoints**
  ```python
  # File: backend/app/api/routes/strategies.py (NEW)
  
  @router.post("/strategies")
  def create_strategy(config: StrategyConfigSchema, db: Session):
      # Save to DB, validate parameters
      
  @router.get("/strategies")
  def list_strategies(db: Session):
      # Return all strategy configs
      
  @router.put("/strategies/{id}/enable")
  def enable_strategy(id: int, db: Session):
      # Set enabled=True, deployed_at=now
      
  @router.delete("/strategies/{id}")
  def delete_strategy(id: int, db: Session):
      # Disable strategy, cannot delete deployed ones
  ```

### Deliverables
- ✅ Clean codebase (removed deprecated files)
- ✅ StrategyRegistry system in place
- ✅ StrategyConfig table created (needs migration)
- ✅ Strategy CRUD endpoints working

### Time Estimate
**3-4 days** (mostly database migrations, API testing)

---

## 🏗️ PHASE 2: MULTI-STRATEGY EXECUTION (Week 2)

**Goal:** Support multiple simultaneously deployed strategies

### Tasks
- [ ] **Update Strategy Engine to Use Registry**
  ```python
  # File: backend/app/core/strategies/orchestrator.py (NEW)
  
  class StrategyOrchestrator:
      def run_all_enabled_strategies(self, db: Session):
          """Run all enabled strategies from DB"""
          configs = db.query(StrategyConfig).filter(StrategyConfig.enabled==True).all()
          
          results = []
          for config in configs:
              strategy_class = StrategyRegistry.get(config.strategy_type)
              strategy = strategy_class()
              result = strategy.run(context={
                  'underlying': config.underlying,
                  'parameters': config.parameters,
                  'config_id': config.id
              })
              results.append(result)
          
          return results
  ```

- [ ] **Update Execution Flow**
  - Modify `/execute/{intent_id}` to get strategy type from StrategyRun
  - Link StrategyRun to StrategyConfig (add FK)
  - Validate strikes/risk limits based on strategy config

- [ ] **Update API Routes**
  - `POST /strategies/run` → Run single strategy now (by name)
  - `POST /strategies/run-all` → Run all enabled strategies
  - `GET /strategies/status` → Show status of all deployed strategies

- [ ] **Update Frontend**
  - Strategies page: Show list of deployed strategies (cards)
  - Each card: Name, Underlying, Status, Parameters, Actions (Run, Edit, Disable)
  - Add strategy deployment modal

### Deliverables
- ✅ Multiple strategies can run in parallel
- ✅ Strategy configs persistent in DB
- ✅ Strategies deployable without code changes
- ✅ UI shows all deployed strategies

### Time Estimate
**4-5 days** (careful execution flow changes, testing)

---

## 📊 PHASE 3: BACKTEST ENGINE (Week 3-4)

**Goal:** Allow users to validate strategies on historical data

### Implementation Steps

1. **Create Backtest Engine**
   ```python
   # File: backend/app/core/backtest/engine.py
   
   class BacktestEngine:
       def __init__(self, strategy_config: StrategyConfig):
           self.config = strategy_config
           self.trades = []
           self.equity_curve = []
       
       def run(self, start_date, end_date, initial_capital=100000):
           """Replay candles and simulate strategy execution"""
           candles = self._fetch_historical_candles(start_date, end_date)
           
           for idx, candle in enumerate(candles):
               signal = self._generate_signal(candle)
               if signal['action'] == 'BUY':
                   self.trades.append(self._simulate_entry(candle, signal))
               elif signal['action'] == 'SELL':
                   self._simulate_exit(candle)
               
               self.equity_curve.append(self._compute_equity(candle.timestamp))
           
           return self.compute_metrics()
       
       def compute_metrics(self):
           """Calculate Sharpe, Sortino, Max DD, etc."""
           returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
           
           return {
               'total_return': self.equity_curve[-1] / self.equity_curve[0],
               'annual_return': self._annualize(returns),
               'sharpe_ratio': self._calculate_sharpe(returns),
               'sortino_ratio': self._calculate_sortino(returns),
               'max_drawdown': self._calculate_max_drawdown(self.equity_curve),
               'win_rate': len([t for t in self.trades if t.pnl > 0]) / len(self.trades),
               'profit_factor': self._calculate_profit_factor(self.trades),
               'total_trades': len(self.trades),
               'avg_win': np.mean([t.pnl for t in self.trades if t.pnl > 0]),
               'avg_loss': np.mean([t.pnl for t in self.trades if t.pnl < 0]),
           }
   ```

2. **Create Backtest Results Database Table**
   ```python
   class BacktestResult(Base):
       __tablename__ = "backtest_results"
       
       id = Column(Integer, primary_key=True)
       strategy_config_id = Column(Integer, FK("strategy_configs.id"))
       start_date = Column(Date)
       end_date = Column(Date)
       
       # Metrics
       total_return = Column(Float)
       annual_return = Column(Float)
       sharpe_ratio = Column(Float)
       sortino_ratio = Column(Float)
       max_drawdown = Column(Float)
       win_rate = Column(Float)
       profit_factor = Column(Float)
       total_trades = Column(Integer)
       avg_win = Column(Float)
       avg_loss = Column(Float)
       
       # Details
       trades = Column(JSON)  # Full trade list
       equity_curve = Column(JSON)  # Daily equity values
       
       created_at = Column(DateTime, default=now_ist)
   ```

3. **Create Backtest API Endpoints**
   ```python
   # File: backend/app/api/routes/backtest.py (NEW)
   
   @router.post("/backtest/run")
   def run_backtest(
       strategy_id: int,
       start_date: date,
       end_date: date,
       initial_capital: float = 100000,
       db: Session = Depends(get_db)
   ):
       config = db.query(StrategyConfig).get(strategy_id)
       engine = BacktestEngine(config)
       results = engine.run(start_date, end_date, initial_capital)
       
       # Save results
       bt_result = BacktestResult(
           strategy_config_id=strategy_id,
           start_date=start_date,
           end_date=end_date,
           **results
       )
       db.add(bt_result)
       db.commit()
       
       return bt_result
   
   @router.get("/backtest/results/{id}")
   def get_backtest_result(id: int, db: Session):
       return db.query(BacktestResult).get(id)
   
   @router.post("/backtest/{id}/analyze")
   def analyze_backtest(id: int):
       """Return equity curve, drawdown curve, trade distribution"""
       result = db.query(BacktestResult).get(id)
       
       return {
           'metrics': {...result.metrics...},
           'equity_curve': result.equity_curve,
           'trades': result.trades,
           'drawdown_periods': compute_drawdown_periods(result.equity_curve)
       }
   ```

4. **Create Backtest UI**
   ```tsx
   // File: web/src/pages/Backtest.tsx (NEW)
   
   - Strategy selector (dropdown from DB)
   - Date range picker
   - Initial capital input
   - Run backtest button
   - Results visualization:
     * Equity curve chart
     * Max drawdown chart
     * Trade distribution histogram
     * Performance metrics table
     * Trade list with P&L
   ```

### Deliverables
- ✅ Full backtest engine with historical candle replay
- ✅ Performance metrics: Sharpe, Sortino, Max DD, Win Rate
- ✅ Trade simulation with realistic slippage
- ✅ Results persisted in database
- ✅ Backtest results UI

### Time Estimate
**5-7 days** (complex calculation, lots of testing)

---

## 🛠️ PHASE 4: HIGH-IMPACT INDICATORS (1 week)

**Priority Order:**

### 1️⃣ IV Percentile (Quick Win - 1 day)
```python
# File: backend/app/core/signals/indicators/iv_percentile.py

def calculate_iv_percentile(current_iv, iv_52w_high, iv_52w_low):
    """Already have IV Rank, just compute percentile"""
    if iv_52w_high == iv_52w_low:
        return 0
    return ((current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100

def interpret_iv_percentile(percentile):
    if percentile > 75:
        return "HIGH_IV" # Premium high, good for selling
    elif percentile > 25:
        return "MEDIUM_IV"
    else:
        return "LOW_IV" # Premium low, good for buying
```
**Impact:** Better entry timing, especially for spreads

### 2️⃣ Put/Call Ratio (2 days)
```python
# Extract from options chain that's already fetched
def calculate_put_call_ratio(option_chain):
    """PE ratio of total OI"""
    total_put_oi = sum(opt['oi'] for opt in option_chain if opt['type'] == 'PE')
    total_call_oi = sum(opt['oi'] for opt in option_chain if opt['type'] == 'CE')
    
    return total_put_oi / total_call_oi if total_call_oi > 0 else 0

# Interpretation:
# > 1.5 = Bearish (more puts than calls)
# 0.8-1.2 = Neutral
# < 0.8 = Bullish (more calls than puts)
```
**Impact:** Market sentiment, reduce against-the-trend trades

### 3️⃣ Greeks Aggregation (2 days)
```python
# File: backend/app/core/utils/greeks_calculator.py

def aggregate_position_greeks(positions):
    """Sum deltas, thetas, vegas across all legs"""
    total_delta = 0
    total_gamma = 0
    total_vega = 0
    total_theta = 0
    
    for pos in positions:
        leg = pos.leg
        total_delta += leg.delta * leg.quantity
        total_gamma += leg.gamma * leg.quantity
        total_vega += leg.vega * leg.quantity
        total_theta += leg.theta * leg.quantity
    
    return {
        'delta': total_delta,  # Directional exposure
        'gamma': total_gamma,  # Acceleration of delta
        'vega': total_vega,    # IV sensitivity
        'theta': total_theta   # Time decay
    }
```
**Impact:** Understand portfolio risk at a glance

### 4️⃣ Volume Profile (2-3 days)
```python
# Compute from existing candle data
def calculate_volume_profile(candles, num_bins=20):
    """Which price levels have most volume?"""
    high = max(c.high for c in candles)
    low = min(c.low for c in candles)
    
    bins = {}
    for c in candles:
        bin_level = round(((c.close - low) / (high - low)) * num_bins)
        bins[bin_level] = bins.get(bin_level, 0) + c.volume
    
    return bins

# Use for: Support/Resistance, liquidity zones
```
**Impact:** Better confluences for entries

### Deliverables
- ✅ IV Percentile calculation
- ✅ Put/Call Ratio from option chain
- ✅ Position Greeks aggregation
- ✅ Volume Profile calculation
- ✅ All added to signal enrichment

### Time Estimate
**5-6 days** (mostly integration, validation)

---

## 💎 PHASE 5: STRATEGY BUILDER UI (Week 4-5)

**Goal:** Non-developers can create/modify strategies

### Components Needed

1. **Strategy Configuration Schema**
   ```json
   {
     "name": "My First Spread",
     "description": "Short Call Spread on NIFTY when RSI > 70",
     "underlying": "NIFTY",
     "entry": {
       "type": "AND",
       "conditions": [
         {
           "indicator": "RSI",
           "period": 14,
           "operator": ">",
           "value": 70
         },
         {
           "indicator": "ADX",
           "period": 14,
           "operator": ">",
           "value": 25
         }
       ]
     },
     "position": {
       "type": "CALL_SPREAD",
       "short_strike_offset": 0.8,
       "long_strike_offset": 1.5,
       "expiry": "weekly"
     },
     "exit": {
       "type": "OR",
       "conditions": [
         {"type": "PROFIT_TARGET", "percent": 25},
         {"type": "STOP_LOSS", "percent": 50},
         {"type": "TIME_BASED", "minutes": 60}
       ]
     },
     "risk": {
       "max_loss_per_trade": 1000,
       "daily_max_loss": 5000,
       "lots": 1
     }
   }
   ```

2. **Builder UI (React)**
   ```tsx
   // File: web/src/pages/StrategyBuilder.tsx (NEW)
   
   Sections:
   1. Basic Info (Name, Description, Underlying)
   2. Entry Conditions
      - Indicator selector (RSI, ADX, MACD, IV%, etc.)
      - Operator (>, <, ==, between)
      - Value input
      - AND/OR logic
   3. Position Type
      - Dropdown (Call Spread, Put Spread, Iron Condor, etc.)
      - Strike offsets (% or rupees)
      - Expiry (weekly, monthly)
   4. Exit Conditions
      - Profit target (% or rupees)
      - Stop loss (% or rupees)
      - Time-based exit
   5. Risk Parameters
      - Max loss per trade
      - Daily loss limit
      - Number of lots
   6. Test & Deploy
      - Backtest button (runs Phase 3 backtest)
      - Deploy button (saves to StrategyConfig, enables)
   ```

### Deliverables
- ✅ JSON schema for strategies
- ✅ Strategy Builder UI (React component)
- ✅ Backend validation endpoints
- ✅ Save/load strategy templates
- ✅ Deploy strategies to trading

### Time Estimate
**6-8 days** (complex UI, lots of validation)

---

## 🎯 IMPLEMENTATION SEQUENCE

```
Week 1: Cleanup + Foundation
├─ Remove deprecated code
├─ Create StrategyRegistry
├─ Add StrategyConfig table
└─ Create strategy CRUD API

Week 2: Multi-Strategy
├─ Update strategy engine
├─ Link StrategyConfig to execution
├─ Update UI to show strategies
└─ Test parallel execution

Week 3-4: Backtest Engine
├─ Build backtest engine
├─ Create results table
├─ Build API endpoints
└─ Create backtest UI

Week 5: Advanced Indicators
├─ Add IV Percentile
├─ Add Put/Call Ratio
├─ Add Greeks aggregation
└─ Add Volume Profile

Week 6: Strategy Builder UI
├─ Design JSON schema
├─ Build React components
├─ Connect to backend
└─ Test end-to-end
```

---

## ✅ DEFINITION OF DONE

### Phase 1 Complete When:
- [ ] Deprecated files removed
- [ ] StrategyRegistry working
- [ ] StrategyConfig CRUD API tested
- [ ] No compilation errors

### Phase 2 Complete When:
- [ ] Multiple strategies run in parallel
- [ ] Configs saved to DB
- [ ] Strategies deployable from UI
- [ ] E2E test passes

### Phase 3 Complete When:
- [ ] Backtest engine produces correct results
- [ ] Metrics match benchmark (Sharpe calculation verified)
- [ ] UI displays results correctly
- [ ] 10 sample backtests saved

### Phase 4 Complete When:
- [ ] IV % displayed on dashboard
- [ ] Put/Call ratio in signal enrichment
- [ ] Greeks aggregation in positions
- [ ] All integrated and tested

### Phase 5 Complete When:
- [ ] Builder UI deployable
- [ ] Can create strategy without code
- [ ] Created strategy backtests correctly
- [ ] Live trading works with custom strategy

---

## ⚠️ RISKS & MITIGATIONS

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Backtest inaccuracy | Wrong strategy validation | Use paper trading to compare |
| Multi-strategy conflicts | Duplicate entries | Add position deduplication check |
| Builder schema too complex | Non-devs confused | Start with presets, gradual complexity |
| Performance degradation | Slow backtests | Cache candles, parallelize |
| Data quality issues | Bad signals | Validate indicators against ta-lib |

---

## 📞 DECISION POINTS

Before starting Phase 2, confirm:

1. **Strategy Lifecycle:** Once deployed, can users disable without deleting?
   → Yes: Add `enabled` flag
   → No: Support delete after deployment

2. **Parallel Limits:** Max concurrent strategies?
   → No limit: Infrastructure should handle
   → Limited: Add concurrency check

3. **Backtest Scope:** How far back to keep historical data?
   → 1 year: Manageable, good balance
   → 5 years: Better for long-term backtests

4. **Builder Flexibility:** Allow custom Python or visual only?
   → Visual only: Safer, limited
   → Custom code: Powerful, requires sandboxing

---

**Status:** Ready to implement  
**Next Step:** Confirm Phase 2 architecture with stakeholders before starting Week 2
