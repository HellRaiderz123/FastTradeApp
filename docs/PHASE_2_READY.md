# Phase 2: Multi-Strategy Execution - Ready to Start

## What You Have After Phase 1

✅ **Multi-Strategy Foundation:**
- Central StrategyRegistry with auto-registration
- Database-backed strategy configuration
- Full REST API for strategy management
- Unit tests confirming everything works

✅ **Database Ready:**
- `strategy_configs` table created and tested
- All CRUD operations working
- JSON support for flexible parameters

✅ **Code Structure:**
- Clean separation: Registry → Config → Execution
- No breaking changes to existing code
- Wrapper pattern allows incremental integration

## Phase 2 Roadmap

### Task 1: Update Strategy Execution Engine
**Goal:** Make the execution engine aware of StrategyRegistry

**Files to modify:**
- `backend/app/core/strategies/strategy_engine.py` (or similar)
- Update run_option_spread() to:
  - Accept strategy_id from request
  - Fetch config from database
  - Use parameters from StrategyConfig

**Pseudo-code:**
```python
def execute_strategy(strategy_id: int, db: Session):
    # 1. Get strategy config from DB
    config = db.query(StrategyConfig).filter_by(id=strategy_id).first()
    
    # 2. Get strategy class from registry
    strategy_class = StrategyRegistry.get(config.strategy_type)
    
    # 3. Run strategy with config parameters
    context = {
        "underlying": config.underlying,
        "parameters": config.parameters,
        "config_id": strategy_id
    }
    result = strategy_class().run(context)
    
    # 4. Log execution
    # store_execution_record(strategy_id, result)
    
    return result
```

### Task 2: Multi-Strategy Orchestration
**Goal:** Support running multiple enabled strategies in parallel

**Approach:**
1. Create `MultiStrategyExecutor` class
2. Query all enabled=True strategies
3. Run each in parallel (async/threading)
4. Aggregate results
5. Handle failures gracefully

**File to create:**
- `backend/app/core/strategies/multi_executor.py`

### Task 3: Frontend Integration
**Goal:** UI for strategy management

**Components to build (React/TypeScript):**
- Strategy list view
- Create/edit strategy form
- Enable/disable toggle
- Parameter configuration panel
- Deployment status display

**Backend endpoints already exist:**
- POST /strategies (create)
- GET /strategies (list)
- PUT /strategies/{id} (update)
- DELETE /strategies/{id} (delete)
- POST /strategies/{id}/enable (deploy)
- POST /strategies/{id}/disable (undeploy)

### Task 4: Testing & Validation
**Goal:** Verify multi-strategy execution works

**Tests to write:**
- Execute single strategy from config
- Execute multiple strategies in parallel
- Verify isolation (one failure doesn't break others)
- Load test (run many strategies concurrently)

## Starting Point for Phase 2

The execution entry point is likely in:
```
backend/app/core/strategies/option_spread_15m/engine.py  (run_option_spread function)
```

This is where you'll connect the new StrategyRegistry system to actual execution.

## Code Locations

**Registry & Config:**
- Registry: `backend/app/core/strategies/registry.py`
- Model: `backend/app/db/models.py` (StrategyConfig class)
- API: `backend/app/api/routes/strategies.py`

**Execution:**
- Option Spread 15m: `backend/app/core/strategies/option_spread_15m/engine.py`
- (Likely) Main execution: `backend/app/core/signals/` or `backend/app/core/strategies/`

**Database:**
- Session: `backend/app/db/session.py`
- Tables: `backend/fastrade.db` (SQLite)

## Quick Test Commands

```bash
# Direct test (no server needed)
cd backend && python test_phase1_direct.py

# API test (requires running server)
cd backend && python test_phase1_api.py

# Start server
cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Estimated Phase 2 Timeline

- **Task 1 (Execution Engine)**: 1-2 hours
- **Task 2 (Multi-Strategy Orchestration)**: 2-3 hours  
- **Task 3 (Frontend Integration)**: 3-4 hours
- **Task 4 (Testing & Validation)**: 1-2 hours

**Total Phase 2**: 7-11 hours

## Key Files You'll Work With

1. ✅ `backend/app/db/models.py` - DONE (StrategyConfig added)
2. ✅ `backend/app/core/strategies/registry.py` - DONE (Registry system)
3. ✅ `backend/app/api/routes/strategies.py` - DONE (REST API)
4. 📝 `backend/app/core/strategies/option_spread_15m/engine.py` - NEXT (Update with registry)
5. 📝 `backend/app/core/strategies/multi_executor.py` - NEW (Multi-strategy runner)
6. 📝 `web/src/components/StrategyManager.tsx` - NEW (Frontend)

## Commands to Execute Phase 2

```bash
# 1. Check what strategy execution currently looks like
grep -r "def run_option_spread" backend/app/

# 2. Find where strategy execution happens
find backend/app -name "*.py" | xargs grep -l "run_option_spread"

# 3. Start Phase 2 implementation
cd backend && python -c "
from app.core.strategies.registry import StrategyRegistry
print('✅ Registry working:', StrategyRegistry.list_all())
"
```

## What's NOT Needed for Phase 2

- ❌ More database migrations (table already exists)
- ❌ New REST endpoints (all 8 exist already)
- ❌ Registry improvements (it's ready)
- ❌ Unit test framework (tests already work)

## You're Ready When

- [ ] You understand where `run_option_spread()` is called
- [ ] You know how to pass strategy_id from API to execution
- [ ] You can fetch StrategyConfig from DB and use its parameters
- [ ] You understand the flow: Request → Config → Registry → Execution

Good luck with Phase 2! 🚀
