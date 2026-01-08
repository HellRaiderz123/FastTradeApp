# 🚀 FASTTRADEAPP - NEXT PHASES ANALYSIS
**Date:** January 7, 2026  
**Current Status:** Phase 5 Complete (Notifications, WebSocket, Health Monitoring)  
**Overall Progress:** 65% → Target: 100% (Algorooms Parity)  

---

## 📊 CURRENT IMPLEMENTATION STATUS

### ✅ COMPLETED (Phase 1-5)
| Phase | Status | Key Features |
|-------|--------|-------------|
| Phase 1 | ✅ COMPLETE | Core execution, paper trading, Zerodha integration |
| Phase 2 | ✅ COMPLETE | Daily capital tracking, risk limits, kill switch |
| Phase 3 | ✅ COMPLETE | Frontend integration, responsive UI, real-time charts |
| Phase 4A | ✅ COMPLETE | Backtest engine with realistic pricing, Greeks calculation |
| Phase 4B | ✅ COMPLETE | Advanced indicators (IV %, PCR, Greeks aggregation) |
| Phase 5 | ✅ COMPLETE | Notifications, WebSocket real-time updates, health monitoring |

### ⚠️ CRITICAL GAPS REMAINING (40% of work)
1. **Multi-Strategy Support** - Only 1 strategy runs at a time
2. **Strategy Builder UI** - No visual strategy creation tool
3. **Advanced Risk Management** - Missing portfolio-level hedging
4. **Performance Analytics** - Limited metrics dashboard
5. **Multi-Timeframe Support** - Only 15m candles

---

## 🎯 PHASE 6: MULTI-STRATEGY EXECUTION ENGINE
**Effort:** 4-5 days | **Impact:** HIGH | **Blocker Status:** Unblocks Phase 7-9

### 🔹 Core Concept
Enable parallel execution of **multiple independent strategies** with:
- Separate strategy registry and configuration system
- Portfolio-level position aggregation
- Individual strategy P&L tracking
- Shared risk limits but isolated execution flows

### 🏗️ Architecture Changes Required

#### A. Database Layer
**Add Tables:**
```sql
-- Strategy Registry & Config
CREATE TABLE strategy_configs (
    id INTEGER PRIMARY KEY,
    strategy_key VARCHAR UNIQUE,      -- "nifty_spread", "banknifty_strangle", etc.
    strategy_name VARCHAR,
    description TEXT,
    underlying VARCHAR,               -- NIFTY, BANKNIFTY, FINNIFTY, etc.
    enabled BOOLEAN DEFAULT TRUE,
    parameters JSON,                  -- {risk_mode, max_loss, max_trades, etc.}
    created_at DATETIME,
    deployed_at DATETIME NULL,
    performance_metrics JSON          -- {win_rate, sharpe, max_dd, etc.}
);

-- Strategy Execution History
CREATE TABLE strategy_executions (
    id INTEGER PRIMARY KEY,
    strategy_key VARCHAR,
    execution_timestamp DATETIME,
    signal_quality FLOAT,             -- 0-100 score
    entry_price FLOAT,
    exit_price FLOAT NULL,
    pnl FLOAT NULL,
    status VARCHAR,                   -- PENDING, ACTIVE, CLOSED, FAILED
    reason VARCHAR NULL
);

-- Portfolio Aggregation (strategy-agnostic)
CREATE TABLE portfolio_positions (
    id INTEGER PRIMARY KEY,
    strategy_key VARCHAR,
    underlying VARCHAR,
    position_type VARCHAR,            -- CE_BUY, PE_SELL, SPREAD, etc.
    entry_price FLOAT,
    current_price FLOAT,
    quantity INTEGER,
    pnl FLOAT,
    updated_at DATETIME
);
```

#### B. Backend Service Layer
**New Services:**
```python
# backend/app/core/strategies/strategy_registry.py
class StrategyRegistry:
    """Manages all available strategies"""
    _strategies: Dict[str, Type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, key: str, strategy_class: Type[BaseStrategy]):
        cls._strategies[key] = strategy_class
    
    @classmethod
    def get(cls, key: str) -> Type[BaseStrategy]:
        return cls._strategies.get(key)
    
    @classmethod
    def list_active(cls) -> List[StrategyMetadata]:
        # Returns all enabled strategies from DB

# backend/app/core/strategies/executor.py
class MultiStrategyExecutor:
    """Executes multiple strategies in parallel"""
    def __init__(self, db: Session):
        self.db = db
        self.active_strategies: Dict[str, StrategyExecutor] = {}
    
    async def deploy_strategy(self, config: StrategyConfig):
        """Deploy new strategy"""
        strategy_class = StrategyRegistry.get(config.strategy_key)
        executor = StrategyExecutor(strategy_class, config, self.db)
        self.active_strategies[config.strategy_key] = executor
        # Start background task for this strategy
    
    async def undeploy_strategy(self, strategy_key: str):
        """Stop strategy and close positions"""
        executor = self.active_strategies.pop(strategy_key)
        await executor.close_all_positions()
    
    async def execute_all(self):
        """Run all active strategies (called from scheduler)"""
        tasks = [
            executor.tick() 
            for executor in self.active_strategies.values()
        ]
        await asyncio.gather(*tasks)

# backend/app/core/risk/portfolio_risk.py
class PortfolioRiskManager:
    """Aggregate risk across all strategies"""
    def __init__(self, db: Session):
        self.db = db
    
    def get_portfolio_greeks(self) -> Greeks:
        """Sum greeks across all open positions"""
        # DELTA, GAMMA, THETA, VEGA across strategies
    
    def get_portfolio_pnl(self) -> Dict[str, float]:
        """Strategy-wise and total portfolio P&L"""
    
    def validate_new_position(self, new_pos: Position) -> bool:
        """Check if position violates portfolio limits"""
        # Portfolio-level checks before execution
```

#### C. API Endpoints
```python
# backend/app/api/routes/strategies.py (NEW/ENHANCED)

@router.post("/deploy")
async def deploy_strategy(config: StrategyConfig):
    """Deploy a strategy"""
    # 1. Validate config
    # 2. Create strategy_configs DB record
    # 3. Start execution task
    # 4. Return deployment ID

@router.get("/{strategy_key}/status")
async def get_strategy_status(strategy_key: str):
    """Get status of running strategy"""
    # Returns: active positions, P&L, signal quality, next execution time

@router.delete("/{strategy_key}")
async def undeploy_strategy(strategy_key: str):
    """Stop strategy and close all positions"""

@router.get("/portfolio/summary")
async def get_portfolio_summary():
    """Get aggregated metrics across all strategies"""
    return {
        "total_pnl": float,
        "strategies": [{strategy_key, pnl, win_rate, positions_count}],
        "portfolio_greeks": {...},
        "active_count": int,
        "pending_count": int
    }

@router.get("/portfolio/risk")
async def get_portfolio_risk():
    """Portfolio-level Greeks and margin usage"""
```

#### D. Frontend Components
**New/Modified Pages:**
```tsx
// web/src/pages/StrategyManager.tsx (ENHANCED)
- Deployed Strategies list with status cards
- Strategy deployment form (link to Phase 7 Builder)
- Deploy/Undeploy buttons
- Individual strategy metrics
- Portfolio summary section

// web/src/components/StrategyCard.tsx (NEW)
- Strategy name, underlying, status
- Current positions count
- Daily P&L badge
- Quick actions menu

// web/src/pages/Portfolio.tsx (NEW)
- Aggregated dashboard
- Total P&L chart
- Strategy comparison table
- Combined Greeks visualization
- Margin utilization by strategy
```

### 📋 Implementation Checklist (Phase 6)

**Backend (2-3 days)**
- [ ] Create strategy_configs table & migration
- [ ] Create portfolio_positions table & migration
- [ ] Implement StrategyRegistry class
- [ ] Implement MultiStrategyExecutor class
- [ ] Implement PortfolioRiskManager class
- [ ] Add 5 new API endpoints
- [ ] Update main.py scheduler to call MultiStrategyExecutor.execute_all()
- [ ] Add unit tests for strategy execution isolation
- [ ] Add integration tests for multi-strategy scenarios

**Frontend (1-2 days)**
- [ ] Create StrategyCard component
- [ ] Create Portfolio summary page
- [ ] Update Strategies page to show deployed strategies
- [ ] Add deploy/undeploy form
- [ ] Connect to new API endpoints
- [ ] Add status badges and indicators
- [ ] Test with 2-3 strategies simultaneously

**Testing (1 day)**
- [ ] Test 2 strategies running in parallel
- [ ] Test strategy isolation (one fails, other continues)
- [ ] Test portfolio P&L aggregation
- [ ] Test portfolio risk checks
- [ ] Test position closure on undeploy

---

## 🎨 PHASE 7: STRATEGY BUILDER UI
**Effort:** 5-7 days | **Impact:** CRITICAL | **Blocks:** Strategy creation without coding

### 🔹 Core Concept
Visual, drag-and-drop **strategy builder** allowing non-developers to:
- Select indicators and combinations
- Define entry/exit rules
- Set parameters visually
- Preview payoff diagrams
- Save as templates
- Deploy directly from builder

### 📐 Builder Architecture

#### A. Strategy Configuration Schema
```typescript
// Define strategy as JSON config (replaces Python code)
interface StrategyConfig {
    name: string;
    underlying: string;
    entry_rules: {
        type: "AND" | "OR";
        conditions: [
            {
                indicator: "RSI" | "ADX" | "MACD" | "IV_RANK" | "PCR";
                operator: "GT" | "LT" | "EQ" | "CROSS_ABOVE" | "CROSS_BELOW";
                threshold: number;
            }
        ];
    };
    exit_rules: {
        type: "AND" | "OR";
        conditions: [...];
    };
    position_sizing: {
        mode: "FIXED" | "KELLY" | "AGGRESSIVE";
        max_loss_pct: number;
        target_profit_pct: number;
    };
    parameters: {
        [key: string]: number | string | boolean;
    };
}
```

#### B. Backend Strategy Executor
```python
# backend/app/core/strategies/config_based_executor.py
class ConfigBasedStrategyExecutor:
    """Executes strategies from JSON config (no Python coding needed)"""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.ta_engine = TechAnalysisEngine()
    
    async def check_entry_signal(self, market_data: MarketData) -> bool:
        """Evaluate entry conditions"""
        indicators = self.ta_engine.compute_all(market_data, self.config.parameters)
        return self._evaluate_rules(
            self.config.entry_rules,
            indicators
        )
    
    async def check_exit_signal(self, position: Position) -> bool:
        """Check if exit conditions met"""
        indicators = self.ta_engine.compute_all(market_data, self.config.parameters)
        return self._evaluate_rules(
            self.config.exit_rules,
            indicators
        ) or self._check_tp_sl(position)
    
    def _evaluate_rules(self, rules: RuleSet, indicators: Dict) -> bool:
        """Recursively evaluate AND/OR logic"""
        # Supports nested AND/OR conditions
```

#### C. Frontend Builder Components
```tsx
// web/src/pages/StrategyBuilder.tsx (MAJOR ENHANCEMENT)
// Currently exists but needs significant expansion

// Key sections:
// 1. Strategy Basics
//    - Name, underlying selection
//    - Description, tags
//
// 2. Entry Rules Builder
//    - Indicator selection (dropdown)
//    - Operator selection (GT, LT, CROSS, etc.)
//    - Threshold input
//    - AND/OR logic selector
//    - Add/remove conditions
//
// 3. Exit Rules Builder
//    - Same as entry rules
//    - OR preset: "TP Hit" / "SL Hit"
//
// 4. Position Sizing
//    - Max loss % slider
//    - Target profit % slider
//    - Mode selector (FIXED, KELLY, AGGRESSIVE)
//
// 5. Payoff Preview
//    - Charts showing P&L at different price points
//    - Greeks breakdown
//    - Risk/reward ratio
//
// 6. Backtest Preview
//    - Last 30 days performance
//    - Win rate, sharpe ratio
//    - Drawdown chart
//
// 7. Deploy
//    - Save as template
//    - Deploy immediately
//    - Schedule for later

// web/src/components/IndicatorSelector.tsx (NEW)
// web/src/components/RuleBuilder.tsx (NEW)
// web/src/components/PayoffDiagram.tsx (NEW)
// web/src/components/StrategyBacktestPreview.tsx (NEW)
```

#### D. API Endpoints
```python
# backend/app/api/routes/strategy_builder.py (NEW)

@router.post("/builder/validate")
async def validate_strategy_config(config: StrategyConfig):
    """Validate config before saving"""
    # Checks: valid indicators, valid operators, logic consistency

@router.post("/builder/preview")
async def preview_strategy(config: StrategyConfig, days: int = 30):
    """Show last N days backtest performance"""
    # Quick backtest to show user what strategy would do

@router.post("/builder/payoff")
async def compute_payoff_diagram(config: StrategyConfig, underlying: str):
    """Compute payoff at different price points"""
    # For options: show P&L vs underlying price at expiry

@router.post("/templates")
async def save_as_template(name: str, config: StrategyConfig):
    """Save strategy as reusable template"""

@router.get("/templates")
async def get_templates():
    """List all saved templates"""

@router.post("/deploy-from-builder")
async def deploy_from_builder(config: StrategyConfig):
    """Deploy strategy directly from builder (calls Phase 6 deploy endpoint)"""
```

### 🎯 Builder Workflow
1. **User selects indicators** from dropdown
2. **Sets thresholds** with interactive sliders
3. **Combines conditions** with AND/OR buttons
4. **Previews payoff** diagram
5. **Runs quick backtest** on last 30 days
6. **Reviews metrics** (Sharpe, win rate, max DD)
7. **Saves as template** or deploys immediately

### 📋 Implementation Checklist (Phase 7)

**Backend (2-3 days)**
- [ ] Design StrategyConfig schema
- [ ] Create ConfigBasedStrategyExecutor
- [ ] Create template storage (DB table)
- [ ] Add 6 new API endpoints
- [ ] Implement payoff calculation
- [ ] Implement quick preview backtest
- [ ] Add validation for all operator/indicator combinations
- [ ] Unit tests for config-based execution

**Frontend (2-3 days)**
- [ ] Enhance StrategyBuilder.tsx significantly
- [ ] Create IndicatorSelector component (dropdown with descriptions)
- [ ] Create RuleBuilder component (condition + AND/OR logic)
- [ ] Create PayoffDiagram component (chart visualization)
- [ ] Create StrategyBacktestPreview component
- [ ] Add template management UI
- [ ] Connect all components to backend
- [ ] Add comprehensive error messages
- [ ] Mobile-responsive builder layout

**Testing (1-2 days)**
- [ ] Test all indicator/operator combinations
- [ ] Test AND/OR logic evaluation
- [ ] Test payoff calculations for spreads
- [ ] Test backtest preview accuracy
- [ ] Test template save/load
- [ ] Test deploy from builder
- [ ] User acceptance testing (drag-and-drop feel)

---

## 📊 PHASE 8: PERFORMANCE ANALYTICS DASHBOARD
**Effort:** 3-4 days | **Impact:** HIGH | **Value:** Decision-making insights

### 🔹 Core Concept
Comprehensive **analytics dashboard** showing:
- Detailed performance metrics (Sharpe, Sortino, Max DD, Calmar)
- Strategy comparison and ranking
- Trade-by-trade analysis
- Risk heat maps
- Equity curve analysis
- Monthly/yearly breakdowns

### 📈 New Metrics to Calculate

#### A. Performance Metrics
```python
class PerformanceMetrics:
    # Return metrics
    total_return: float              # Total % return
    annualized_return: float         # Extrapolated annual %
    monthly_returns: List[float]     # Return per month
    
    # Risk-adjusted returns
    sharpe_ratio: float              # Return per unit risk (15% annual RF)
    sortino_ratio: float             # Return per downside risk
    calmar_ratio: float              # Return / Max Drawdown
    
    # Drawdown metrics
    max_drawdown: float              # Largest peak-to-trough
    avg_drawdown: float              # Average drawdown
    drawdown_duration: int           # Days to recover from max DD
    
    # Trade metrics
    win_rate: float                  # % of winning trades
    profit_factor: float             # Gross wins / Gross losses
    avg_win: float                   # Average winning trade %
    avg_loss: float                  # Average losing trade %
    win_loss_ratio: float            # Avg win / Avg loss
    
    # Risk metrics
    best_trade: float                # Best single trade %
    worst_trade: float               # Worst single trade %
    consecutive_wins: int            # Max consecutive wins
    consecutive_losses: int          # Max consecutive losses
```

#### B. Database Schema
```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY,
    strategy_key VARCHAR,
    metric_date DATETIME,
    sharpe_ratio FLOAT,
    sortino_ratio FLOAT,
    max_drawdown FLOAT,
    win_rate FLOAT,
    total_return FLOAT,
    month_trades INT,
    month_wins INT,
    month_losses INT,
    updated_at DATETIME
);

CREATE TABLE equity_curve (
    id INTEGER PRIMARY KEY,
    strategy_key VARCHAR,
    date DATETIME,
    equity FLOAT,
    daily_pnl FLOAT,
    daily_return FLOAT
);
```

#### C. Backend Analytics Service
```python
# backend/app/core/analytics/performance.py
class PerformanceAnalyzer:
    def __init__(self, db: Session):
        self.db = db
    
    def compute_all_metrics(self, strategy_key: str, start_date, end_date) -> PerformanceMetrics:
        """Compute all performance metrics"""
        trades = self.get_trades(strategy_key, start_date, end_date)
        returns = self.compute_returns(trades)
        
        metrics = PerformanceMetrics(
            total_return=self._compute_total_return(returns),
            sharpe_ratio=self._compute_sharpe(returns),
            sortino_ratio=self._compute_sortino(returns),
            max_drawdown=self._compute_max_dd(returns),
            win_rate=self._compute_win_rate(trades),
            # ... other metrics
        )
        return metrics
    
    def get_equity_curve(self, strategy_key: str, start_date, end_date) -> List[Dict]:
        """Equity value over time"""
        # Returns: [{"date": "2026-01-07", "equity": 100000, "daily_pnl": 1500}, ...]
    
    def get_drawdown_curve(self, strategy_key: str) -> List[Dict]:
        """Drawdown over time"""
        # Shows running drawdown percentage
    
    def get_monthly_returns(self, strategy_key: str, year: int) -> List[Dict]:
        """Monthly returns breakdown"""
        # Returns: [{"month": "Jan", "return": 5.2, "trades": 20, "wins": 12}, ...]
    
    def compare_strategies(self) -> List[Dict]:
        """Rank all strategies by Sharpe ratio"""
        # Returns sorted list of all strategies with key metrics
```

#### D. Frontend Analytics Pages
```tsx
// web/src/pages/Analytics.tsx (NEW)
// Main analytics dashboard with tabs

// 1. Performance Tab
//    - Key metrics cards (Sharpe, Sortino, Max DD, Win Rate)
//    - Equity curve chart
//    - Drawdown chart
//    - Monthly returns heatmap
//
// 2. Strategy Comparison Tab
//    - Table of all strategies ranked by Sharpe
//    - Scatter plot: Sharpe vs Win Rate
//    - Correlation matrix
//
// 3. Trade Analysis Tab
//    - All trades table with filters
//    - Win/Loss breakdown
//    - Entry/exit quality analysis
//    - Trade duration distribution
//
// 4. Risk Tab
//    - Risk metrics (Sharpe, Sortino, Calmar)
//    - Drawdown analysis
//    - Consecutive loss analysis
//    - VaR/CVaR estimates
//
// 5. Monthly Performance Tab
//    - Year selector
//    - Monthly returns table and chart
//    - Best/worst month identification
//    - Month-to-date tracker

// web/src/components/PerformanceCards.tsx (NEW)
// web/src/components/EquityCurveChart.tsx (NEW)
// web/src/components/StrategyComparison.tsx (NEW)
// web/src/components/TradeAnalysisTable.tsx (NEW)
```

### 📋 Implementation Checklist (Phase 8)

**Backend (1-2 days)**
- [ ] Create performance_metrics table
- [ ] Create equity_curve table
- [ ] Implement PerformanceAnalyzer class
- [ ] Implement all metric calculations
- [ ] Add 6 new API endpoints for analytics
- [ ] Add scheduled task to update metrics daily
- [ ] Unit tests for all calculations

**Frontend (1-2 days)**
- [ ] Create Analytics.tsx main page
- [ ] Create PerformanceCards component
- [ ] Create charts (Equity, Drawdown, Monthly returns)
- [ ] Create Strategy Comparison table
- [ ] Create Trade Analysis table
- [ ] Connect to analytics endpoints
- [ ] Add time range selectors
- [ ] Add export to CSV functionality

**Testing (1 day)**
- [ ] Verify all metric calculations
- [ ] Compare with manual calculations
- [ ] Test with multiple strategies
- [ ] Test month/year boundary cases
- [ ] Performance test with large trade datasets
- [ ] UI responsiveness on different screen sizes

---

## 🔄 PHASE 9: MULTI-TIMEFRAME SUPPORT
**Effort:** 3-4 days | **Impact:** MEDIUM | **Value:** Better signal quality

### 🔹 Core Concept
Extend system to support **multiple timeframes** (currently 15m only):
- 1-minute candles (scalping)
- 5-minute candles (short-term)
- 15-minute candles (current)
- 1-hour candles (medium-term)
- Daily candles (swing trading)

### 📐 Implementation

#### A. Database Changes
```sql
-- Separate tables per timeframe
CREATE TABLE candles_1m (
    id INTEGER PRIMARY KEY,
    underlying VARCHAR,
    timestamp DATETIME,
    open FLOAT, high FLOAT, low FLOAT, close FLOAT, volume INT
);

CREATE TABLE candles_5m (...);
CREATE TABLE candles_15m (...);  -- Rename existing
CREATE TABLE candles_1h (...);
CREATE TABLE candles_daily (...);
```

#### B. Backend
```python
# backend/app/core/market/multi_timeframe.py
class MultiTimeframeDataFetcher:
    TIMEFRAMES = ["1m", "5m", "15m", "1h", "daily"]
    
    async def fetch_candles(self, underlying: str, timeframe: str, count: int = 100):
        """Fetch candles for any timeframe"""
        if timeframe not in self.TIMEFRAMES:
            raise ValueError(f"Invalid timeframe: {timeframe}")
        
        # Fetch from appropriate table
        return self.db.query(f"candles_{timeframe}").filter(...).all()
    
    async def compute_indicators(self, underlying: str, timeframe: str):
        """Compute TA indicators for any timeframe"""
        candles = await self.fetch_candles(underlying, timeframe)
        return self.ta_engine.compute_all(candles)

# Update TA engine to accept timeframe parameter
class TechAnalysisEngine:
    def compute_all(self, candles: List[Candle], timeframe: str = "15m", params: Dict = None):
        # Adjust period settings based on timeframe
        # Example: RSI(14) on daily = RSI(14) on 1m but different signal quality
        ...
```

#### C. Strategy Configuration
```typescript
// Strategy can reference multiple timeframes
interface StrategyConfig {
    name: string;
    timeframe_rules: {
        primary_timeframe: "1m" | "5m" | "15m" | "1h" | "daily";
        confirmation_timeframe?: "1h" | "daily";  // Optional: confirm on higher TF
        entry_rules: {
            timeframe: "5m",
            conditions: [...]
        };
        exit_rules: {
            timeframe: "15m",
            conditions: [...]
        };
    };
}

// Example: Entry on 5m, confirm on 1h, exit on 15m
```

#### D. Frontend
```tsx
// web/src/components/TimeframeSelector.tsx (NEW)
// Dropdown to select 1m, 5m, 15m, 1h, daily

// web/src/pages/StrategyBuilder.tsx (ENHANCED)
// Add timeframe selector to entry/exit rules

// web/src/components/MultiTimeframeChart.tsx (NEW)
// Show multiple timeframes side-by-side
```

---

## 🛡️ PHASE 10: ADVANCED RISK MANAGEMENT
**Effort:** 3-4 days | **Impact:** HIGH | **Value:** Prevent catastrophic losses

### 🔹 Core Concept
Portfolio-level **risk controls** replacing/enhancing single-strategy limits:
- Greeks aggregation and limits (Delta, Gamma, Theta, Vega)
- Scenario analysis (market shock testing)
- Correlation matrix and diversification checks
- Hedging recommendations
- Margin simulation

### 🏗️ Implementation

#### A. Portfolio Greeks Aggregation
```python
# backend/app/core/risk/portfolio_greeks.py
class PortfolioGreeksCalculator:
    def get_portfolio_greeks(self) -> Dict[str, float]:
        """Sum greeks across all active positions"""
        total_delta = 0
        total_gamma = 0
        total_theta = 0
        total_vega = 0
        
        for position in self.get_all_positions():
            # Fetch live Greeks from Greeks service
            greeks = self.greeks_service.get_greeks(position)
            total_delta += greeks.delta
            total_gamma += greeks.gamma
            total_theta += greeks.theta
            total_vega += greeks.vega
        
        return {
            "delta": total_delta,
            "gamma": total_gamma,
            "theta": total_theta,
            "vega": total_vega,
            "theta_1day": total_theta / 365  # Daily theta
        }
    
    def validate_position_within_limits(self, new_position: Position, limits: Dict) -> Tuple[bool, str]:
        """Check if new position violates Greeks limits"""
        portfolio_greeks = self.get_portfolio_greeks()
        new_greeks = self.greeks_service.get_greeks(new_position)
        
        # Check each greek against limits
        new_delta = portfolio_greeks["delta"] + new_greeks.delta
        if abs(new_delta) > limits.get("max_delta", 100):
            return False, f"Would exceed max delta: {new_delta}"
        
        # Similar checks for gamma, theta, vega
        ...
```

#### B. Scenario Analysis
```python
# backend/app/core/risk/scenario_analysis.py
class ScenarioAnalyzer:
    def stress_test(self, scenarios: List[Scenario]) -> Dict:
        """Test portfolio against various market scenarios"""
        # Scenarios: +5% market move, +10% volatility, -15% market move, etc.
        results = {}
        
        for scenario in scenarios:
            portfolio_pnl = 0
            for position in self.get_all_positions():
                # Compute P&L if scenario occurred
                pnl = self._compute_position_pnl_in_scenario(position, scenario)
                portfolio_pnl += pnl
            
            results[scenario.name] = {
                "portfolio_pnl": portfolio_pnl,
                "portfolio_return": portfolio_pnl / self.get_portfolio_value(),
                "affected_strategies": [...]
            }
        
        return results
    
    def get_var(self, confidence: float = 0.95, horizon_days: int = 1) -> float:
        """Value at Risk: max loss at confidence level"""
        # Use historical P&L distribution
```

#### C. Correlation Analysis
```python
# backend/app/core/risk/correlation.py
class CorrelationAnalyzer:
    def get_strategy_correlation_matrix(self) -> np.array:
        """Calculate correlation between strategy returns"""
        # If strategies highly correlated, portfolio doesn't diversify
        # If uncorrelated, good diversification
    
    def get_diversification_score(self) -> float:
        """Score 0-100: how well diversified is portfolio"""
        # Lower correlation = higher diversification = lower portfolio risk
    
    def recommend_hedge(self) -> List[HedgeRecommendation]:
        """Suggest hedges if portfolio is too concentrated"""
        # Example: "Add short call spread if portfolio too bullish"
```

#### D. Frontend Risk Dashboard
```tsx
// web/src/pages/RiskDashboard.tsx (NEW)

// 1. Portfolio Greeks Card
//    - Delta, Gamma, Theta, Vega
//    - Visual gauges showing distance to limits
//    - Traffic light (green/yellow/red)
//
// 2. Scenario Analysis
//    - Table: +5%, +10%, -15% scenarios
//    - Worst case P&L highlighted
//    - Affected strategies identified
//
// 3. Heat Map
//    - Correlation matrix of all strategies
//    - Clustering visualization
//    - Diversification score badge
//
// 4. VaR/CVaR
//    - "95% chance loss < $X"
//    - Historical drawdown percentiles
//
// 5. Hedging Recommendations
//    - Auto-generated suggestions
//    - "Add protective puts if..."
//    - Risk reduction estimates
```

---

## 📱 PHASE 11: MOBILE APP ENHANCEMENTS (Optional, Parallel)
**Effort:** 2-3 days | **Impact:** LOW-MEDIUM | **Value:** Mobile trading

### Focus Areas
- [ ] Complete Journal screen (currently missing)
- [ ] Complete Settings screen (API keys, risk limits)
- [ ] Push notifications for executions
- [ ] Biometric authentication
- [ ] Offline mode (cache recent data)
- [ ] Mobile-optimized analytics dashboard

---

## 🔧 PHASE 12: DEPLOYMENT & PRODUCTION HARDENING
**Effort:** 2-3 days | **Impact:** CRITICAL | **Value:** Live trading safety

### Focus Areas
- [ ] Database backup automation
- [ ] API rate limiting and throttling
- [ ] Request validation and sanitization
- [ ] Error recovery and circuit breakers
- [ ] Candle feed failover mechanisms
- [ ] Order execution retry logic
- [ ] Load testing (handle concurrent strategies)
- [ ] Monitoring dashboards (Prometheus/Grafana)
- [ ] Alert thresholds (CPU, memory, API latency)
- [ ] Automated testing pipeline (CI/CD)

---

## 🎯 RECOMMENDED EXECUTION ORDER

### **CRITICAL PATH (Do First)**
```
Phase 6: Multi-Strategy Execution Engine (4-5 days)
    ↓ (Unblocks Phase 7)
Phase 7: Strategy Builder UI (5-7 days)
    ↓ (Enables non-developers to create strategies)
Phase 8: Performance Analytics Dashboard (3-4 days)
    ↓ (Provides feedback on strategy quality)
```

### **HIGH-VALUE (Do Next)**
```
Phase 10: Advanced Risk Management (3-4 days)
    → Portfolio-level Greeks limits
    → Scenario analysis
    → Stress testing before live deployment

Phase 9: Multi-Timeframe Support (3-4 days)
    → Improves signal quality
    → Enables scalping strategies
```

### **NICE-TO-HAVE (Later)**
```
Phase 11: Mobile Enhancements (2-3 days)
Phase 12: Deployment Hardening (2-3 days)
```

---

## 📊 EFFORT SUMMARY

| Phase | Duration | Priority | Effort |
|-------|----------|----------|--------|
| **Phase 6** | 4-5 days | 🔴 CRITICAL | Medium |
| **Phase 7** | 5-7 days | 🔴 CRITICAL | High |
| **Phase 8** | 3-4 days | 🟡 HIGH | Medium |
| **Phase 9** | 3-4 days | 🟡 HIGH | Medium |
| **Phase 10** | 3-4 days | 🟡 HIGH | Medium |
| **Phase 11** | 2-3 days | 🟢 OPTIONAL | Low |
| **Phase 12** | 2-3 days | 🟠 IMPORTANT | Medium |
| **TOTAL** | **23-30 days** | | |

**Optimal Team:** 1 Senior Backend Dev + 1 Frontend Dev + 1 QA  
**Timeline:** 4-6 weeks with focused execution  
**Target Completion:** Mid-February 2026

---

## ✅ SUCCESS CRITERIA

### Phase 6 ✅
- [ ] 2+ strategies running simultaneously
- [ ] Portfolio P&L aggregates correctly
- [ ] No cross-strategy position conflicts

### Phase 7 ✅
- [ ] Non-developer can create strategy via UI
- [ ] Strategy config converts to executable engine
- [ ] Payoff diagrams render correctly
- [ ] User can deploy directly from builder

### Phase 8 ✅
- [ ] All performance metrics calculate correctly
- [ ] Analytics dashboard loads < 2 seconds
- [ ] Sharpe ratio matches manual calculation
- [ ] Export to CSV works

### Phase 9 ✅
- [ ] 1m, 5m, 1h, daily candles fetched
- [ ] Indicators calculated correctly per timeframe
- [ ] Strategy can mix timeframes (e.g., 5m entry, 1h exit)

### Phase 10 ✅
- [ ] Portfolio Greeks aggregated correctly
- [ ] Scenario analysis produces expected P&L
- [ ] New position rejected if exceeds limits
- [ ] Stress test identifies portfolio weaknesses

---

## 🚀 IMMEDIATE NEXT STEPS (This Week)

1. **Review this document** - Confirm priority order
2. **Setup Phase 6 database** - Create tables
3. **Start StrategyRegistry** - Design and code
4. **Create API stubs** - Define endpoints
5. **Plan Phase 7 schema** - StrategyConfig design
6. **Setup test data** - Multiple strategies for testing

---

**Document Created:** January 7, 2026  
**Analysis Confidence:** 95%  
**Ready to Execute:** YES  
