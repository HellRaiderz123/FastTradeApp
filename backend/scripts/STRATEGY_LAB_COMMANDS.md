# Strategy Lab — Run Commands

Script: `/app/scripts/discover_condition_strategies.py`
Backtest period used in all examples: `2023-09-11 → 2026-03-23`

---

## All Arguments

| Argument | Default | Description |
|---|---|---|
| `--timeframe` | `Day` | `Day`, `1 Hour`, `15 Min`, `5 Min`, `1 Min` |
| `--universe` | `NIFTY50` | Stock universe |
| `--max-candidates` | `120` | How many strategies to generate and test |
| `--top` | `5` | How many top strategies to show/save |
| `--start-date` | None | Backtest start date `YYYY-MM-DD` |
| `--end-date` | None | Backtest end date `YYYY-MM-DD` |
| `--initial-capital` | `100000` | Starting capital |
| `--position-size-pct` | `10.0` | % of capital per trade |
| `--max-per-family` | `1` | Max strategies from same indicator family in top N |
| `--fill-remaining` | flag | Allow family repeats if top N can't be filled strictly |
| `--min-annual-return` | `0.0` | Filter out strategies below this annual return % |
| `--optimize-exits` | flag | Run SL/TP/TSL sweep on top base strategies |
| `--exit-optimize-on-top` | `20` | How many base strategies to take into exit sweep |
| `--sl-grid` | `1.5,2,2.5,3,4,5` | SL % values to test |
| `--tp-grid` | `4,6,8,10,12,15,18` | TP % values to test |
| `--tsl-grid` | `0,0.5,1,1.5,2,2.5,3` | TSL % values to test (use `0` to disable TSL) |
| `--max-exit-combos` | `50` | Max SL/TP/TSL combos per base strategy |
| `--workers` | `4` | Parallel threads for backtesting |
| `--save-top` | flag | Save top N strategies to DB |
| `--json` | flag | Print output as JSON instead of text |

---

## Daily Timeframe

### 1. Quick test — no exit optimization (fastest)
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe Day \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --save-top
```

### 2. Fixed SL/TP only — no TSL (recommended based on observation)
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe Day \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --tsl-grid 0 \
  --sl-grid 2,3,4,5 \
  --tp-grid 6,8,10,12,15 \
  --save-top
```

### 3. Wider SL/TP sweep — more combos
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe Day \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --tsl-grid 0 \
  --sl-grid 1.5,2,2.5,3,4,5,6 \
  --tp-grid 5,8,10,12,15,18,20 \
  --max-exit-combos 100 \
  --exit-optimize-on-top 30 \
  --save-top
```

### 4. With TSL included — let the script decide best combo
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe Day \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --sl-grid 2,3,4,5 \
  --tp-grid 6,8,10,12,15 \
  --tsl-grid 0,1,2,3 \
  --save-top
```

### 5. High quality filter — only strategies with 20%+ annual return
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe Day \
  --max-candidates 500 \
  --top 10 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --tsl-grid 0 \
  --sl-grid 2,3,4,5 \
  --tp-grid 6,8,10,12,15 \
  --min-annual-return 20 \
  --fill-remaining \
  --save-top
```

### 6. Diverse top — max 1 per indicator family
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe Day \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --tsl-grid 0 \
  --sl-grid 2,3,4,5 \
  --tp-grid 6,8,10,12,15 \
  --max-per-family 1 \
  --save-top
```

---

## Hourly Timeframe

> Hourly needs tighter SL/TP since moves per candle are smaller than daily.

### 1. Quick test — no exit optimization
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe "1 Hour" \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --save-top
```

### 2. Fixed SL/TP only — no TSL (recommended)
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe "1 Hour" \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --tsl-grid 0 \
  --sl-grid 0.5,1,1.5,2,2.5 \
  --tp-grid 1.5,2,3,4,5,6 \
  --save-top
```

### 3. Wider sweep — more combos
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe "1 Hour" \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --tsl-grid 0 \
  --sl-grid 0.5,1,1.5,2,3 \
  --tp-grid 2,3,4,5,6,8,10 \
  --max-exit-combos 100 \
  --exit-optimize-on-top 30 \
  --save-top
```

### 4. With TSL — let script decide
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe "1 Hour" \
  --max-candidates 300 \
  --top 5 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --sl-grid 0.5,1,1.5,2 \
  --tp-grid 2,3,4,5,6 \
  --tsl-grid 0,0.5,1,1.5 \
  --save-top
```

### 5. High quality filter — 25%+ annual return
```
docker exec -it fasttrade-backend python3 /app/scripts/discover_condition_strategies.py \
  --timeframe "1 Hour" \
  --max-candidates 500 \
  --top 10 \
  --start-date 2023-09-11 \
  --end-date 2026-03-23 \
  --workers 8 \
  --optimize-exits \
  --tsl-grid 0 \
  --sl-grid 0.5,1,1.5,2,2.5 \
  --tp-grid 2,3,4,5,6,8 \
  --min-annual-return 25 \
  --fill-remaining \
  --save-top
```

---

## Tips

- `--tsl-grid 0` disables TSL entirely — fixed SL+TP only, generally better returns on daily
- `--workers 8` speeds up backtesting significantly, safe to go up to 8-12
- `--fill-remaining` prevents empty results if strict family diversity can't fill top N
- `--max-exit-combos` limits combos per base strategy — increase if you want exhaustive sweep
- Omit `--save-top` to do a dry run and just see results without saving to DB
- Add `--json` to get machine-readable output
