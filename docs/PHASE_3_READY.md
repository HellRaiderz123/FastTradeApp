# Phase 3: Frontend Integration - Ready to Start

## What You Have After Phase 2

✅ **Complete Execution Engine:**
- Single strategy execution via API
- Multi-strategy parallel execution
- Database-backed configuration
- Full error handling and logging

✅ **REST API Ready:**
- POST /strategies/run/single
- POST /strategies/run/multiple
- POST /strategies/run/all
- GET /strategies/run/{id}/status

✅ **Database:**
- strategy_configs table created
- Parameters stored as JSON
- Enable/disable flags working

## Phase 3 Tasks

### Task 1: Strategy Dashboard UI
**Goal:** Display all strategies and their status

**File to create**: `web/src/components/StrategyDashboard.tsx`

**Features:**
- List all strategies from `/strategies` endpoint
- Show name, underlying, type, enabled status
- Color-coded based on deployment status
- Search/filter by name or underlying

**Code sketch:**
```typescript
export function StrategyDashboard() {
  const [strategies, setStrategies] = useState([]);
  
  useEffect(() => {
    // Fetch from /strategies
    api.get('/strategies').then(setStrategies);
  }, []);
  
  return (
    <div>
      {strategies.map(s => (
        <StrategyCard key={s.id} strategy={s} />
      ))}
    </div>
  );
}
```

### Task 2: Execution Controls UI
**Goal:** Trigger single and multi-strategy execution

**Features:**
- "Execute" button for each strategy
- "Execute All" for enabled strategies
- "Execute Multiple" with checkbox selection
- Loading state during execution
- Results modal

**Endpoints to call:**
- POST /strategies/run/single (single)
- POST /strategies/run/multiple (specific)
- POST /strategies/run/all (all)

### Task 3: Execution Results Display
**Goal:** Show execution results in real-time

**Features:**
- Strategy name and execution status
- Buy/sell decision (if any)
- Signal strength/confidence
- Error messages (if failed)
- Execution timestamp

**Response structure** (already available):
```json
{
  "success": true,
  "strategy_id": 1,
  "strategy_name": "NIFTY_15m",
  "executed_at": "2026-01-06T22:00:54",
  "result": {
    "strategy": "BullPut",
    "approved": true,
    "reason": "High confidence signal"
  }
}
```

### Task 4: Parameter Configuration UI
**Goal:** Update strategy parameters before execution

**Features:**
- Edit strategy parameters (currently JSON)
- Form validation
- Save to database (PUT /strategies/{id})
- Real-time preview

**Fields to edit:**
- risk_mode (Conservative/Balanced/Aggressive)
- lots (1-10)
- capital (100000-1000000)
- min_confidence (50-95)

## UI Components to Build

```
StrategyDashboard
├── StrategyList
│   ├── StrategyCard (for each)
│   │   ├── StrategyName
│   │   ├── UnderlyingBadge
│   │   ├── StatusBadge (Enabled/Disabled)
│   │   ├── ExecuteButton
│   │   └── EditButton
│   └── BulkActions
│       ├── SelectAll
│       ├── ExecuteSelected
│       └── ExecuteAll
└── ExecutionResults
    ├── ResultsList
    │   └── ResultCard (for each)
    │       ├── StrategyName
    │       ├── Status (Success/Failed)
    │       ├── Signal (if available)
    │       └── Timestamp
    └── ErrorPanel
```

## API Integration Checklist

- [ ] GET /strategies - List all strategies
- [ ] POST /strategies - Create new strategy
- [ ] PUT /strategies/{id} - Update strategy config
- [ ] DELETE /strategies/{id} - Delete strategy
- [ ] POST /strategies/{id}/enable - Enable strategy
- [ ] POST /strategies/{id}/disable - Disable strategy
- [ ] POST /strategies/run/single - Execute single
- [ ] POST /strategies/run/multiple - Execute multiple
- [ ] POST /strategies/run/all - Execute all
- [ ] GET /strategies/run/{id}/status - Check status

## Backend Already Provides

✅ All Phase 1 endpoints (strategy management)
✅ All Phase 2 endpoints (execution)
✅ Database persistence
✅ Error handling
✅ Result aggregation

## Frontend Needs to Build

📝 Dashboard layout
📝 Execution buttons
📝 Results display
📝 Parameter editor
📝 Status indicators
📝 Loading states
📝 Error messages

## Example: Execute Single Strategy

```typescript
async function executeStrategy(strategyId: number) {
  setLoading(true);
  try {
    const response = await fetch(`/strategies/run/single`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ strategy_id: strategyId })
    });
    
    const result = await response.json();
    
    if (result.success) {
      showNotification(`Executed: ${result.strategy_name}`);
      displayResult(result);
    } else {
      showError(result.error);
    }
  } finally {
    setLoading(false);
  }
}
```

## Example: Execute All Strategies

```typescript
async function executeAllStrategies() {
  setLoading(true);
  try {
    const response = await fetch(`/strategies/run/all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    
    const result = await response.json();
    
    showNotification(
      `Executed ${result.completed}/${result.total} strategies`
    );
    
    if (result.failed > 0) {
      showWarning(`${result.failed} strategies failed`);
      result.errors.forEach(e => console.error(e));
    }
    
    displayResults(result.results);
  } finally {
    setLoading(false);
  }
}
```

## State Management

**Suggested Zustand store:**
```typescript
export const useStrategyStore = create((set) => ({
  strategies: [],
  loading: false,
  results: [],
  
  loadStrategies: async () => {
    set({ loading: true });
    const strategies = await api.get('/strategies');
    set({ strategies, loading: false });
  },
  
  executeStrategy: async (id) => {
    const result = await api.post('/strategies/run/single', {
      strategy_id: id
    });
    set(state => ({
      results: [result, ...state.results]
    }));
    return result;
  },
  
  executeAll: async () => {
    const result = await api.post('/strategies/run/all', {});
    set(state => ({
      results: [result, ...state.results]
    }));
    return result;
  }
}));
```

## Design Inspiration

Look at existing components:
- Dashboard layout: Check `web/src/pages/` structure
- Card components: Check `web/src/components/`
- State management: Check `web/src/lib/store.ts`
- API calls: Check `web/src/lib/api.ts`

## Testing Plan

1. **Unit Tests** - Component rendering
2. **Integration Tests** - API calls work
3. **E2E Tests** - Full user flow (create → enable → execute)

## Success Criteria

- [ ] Can view all strategies in dashboard
- [ ] Can execute single strategy and see results
- [ ] Can execute multiple strategies in parallel
- [ ] Can enable/disable strategies
- [ ] Can see execution results in real-time
- [ ] Errors are handled gracefully
- [ ] UI is responsive and intuitive

## Estimated Timeline

- **Dashboard & Cards**: 1-2 hours
- **Execution Buttons**: 1 hour
- **Results Display**: 1-2 hours
- **Parameter Editor**: 1-2 hours
- **Polish & Testing**: 1-2 hours

**Total Phase 3**: 5-9 hours

## Key Files You'll Work With

**Frontend:**
- `web/src/components/` - New dashboard components
- `web/src/lib/api.ts` - Add execution endpoints
- `web/src/pages/` - Add strategy page (if new page)
- `web/src/lib/store.ts` - Strategy state management

**Backend (Reference Only):**
- `backend/app/api/routes/strategies.py` - Strategy CRUD
- `backend/app/api/routes/execution_v2.py` - Execution API

## Commands to Get Started

```bash
# Install dependencies (if needed)
cd web && npm install

# Start dev server
npm run dev

# Create new component
touch src/components/StrategyDashboard.tsx

# Test API
curl -s http://127.0.0.1:8000/strategies | jq .
```

## Notes

- Backend server should be running on port 8000
- All execution is non-blocking (async)
- Results are returned immediately (no polling needed)
- Multiple users can execute independently (no conflicts)
- Failed strategies don't affect others

## You're Ready When

- [ ] Understand the strategy data model (from Phase 1)
- [ ] Know the execution API endpoints (from Phase 2)
- [ ] Can fetch data from `/strategies` endpoint
- [ ] Can call `/strategies/run/single` endpoint
- [ ] Understand state management approach

---

**Phase 3 is Frontend-Only** 🎨

All backend work is complete. Just build the UI to trigger execution!
