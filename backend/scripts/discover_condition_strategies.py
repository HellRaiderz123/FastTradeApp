from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv


def _bootstrap_path() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    env_path = backend_dir / ".env"
    load_dotenv(dotenv_path=env_path, override=False)


_bootstrap_path()

from app.api.routes.condition_scanner import (  # noqa: E402
    BacktestRequest,
    _load_strategies,
    _next_id,
    _run_backtest_for_strategy_payload,
    _save_strategies,
)
from app.core.condition_strategy_lab import generate_candidate_strategies, score_backtest_summary  # noqa: E402
from app.core.condition_strategy_lab import (  # noqa: E402
    expand_strategies_with_exit_variants,
    generate_exit_param_combinations,
    select_diverse_top,
    strategy_family,
)
from app.db.session import SessionLocal  # noqa: E402


def _parse_float_csv(value: str) -> list[float]:
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and rank condition-scanner strategies.")
    parser.add_argument("--timeframe", default="Day", choices=["Day", "1 Hour", "15 Min", "5 Min", "1 Min"])
    parser.add_argument("--universe", default="NIFTY50")
    parser.add_argument("--max-candidates", type=int, default=120)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--initial-capital", type=float, default=100000.0)
    parser.add_argument("--position-size-pct", type=float, default=10.0)
    parser.add_argument("--max-per-family", type=int, default=1)
    parser.add_argument("--fill-remaining", action="store_true", help="Allow family repeats if strict diversity cannot fill top-N.")
    parser.add_argument("--min-annual-return", type=float, default=0.0, help="Filter out strategies below this annual return percent.")
    parser.add_argument("--optimize-exits", action="store_true", help="Run SL/TP/TSL sweep on shortlisted base strategies.")
    parser.add_argument("--exit-optimize-on-top", type=int, default=20, help="How many base strategies to take into exit optimization sweep.")
    parser.add_argument("--sl-grid", default="1.5,2,2.5,3,4,5", help="Comma-separated SL %% values for optimization.")
    parser.add_argument("--tp-grid", default="4,6,8,10,12,15,18", help="Comma-separated TP %% values for optimization.")
    parser.add_argument("--tsl-grid", default="0,0.5,1,1.5,2,2.5,3", help="Comma-separated TSL %% values for optimization.")
    parser.add_argument("--max-exit-combos", type=int, default=50, help="Maximum SL/TP/TSL combos per base strategy.")
    parser.add_argument("--save-top", action="store_true")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker threads for backtesting (default: 4).")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text summary.")
    args = parser.parse_args()

    # Thread-local DB sessions so each worker thread gets its own SQLAlchemy session
    _thread_local = threading.local()

    def _get_thread_db() -> object:
        if not hasattr(_thread_local, "db"):
            _thread_local.db = SessionLocal()
        return _thread_local.db

    def _backtest_worker(candidate: dict, req: object, idx: int, total: int) -> dict:
        db_thread = _get_thread_db()
        result = _run_backtest_for_strategy_payload(candidate, req, db_thread)
        print(f"  [{idx}/{total}] {candidate.get('name', '?')}", flush=True)
        return {
            "strategy": candidate,
            "summary": result.get("summary") or {},
            "score": score_backtest_summary(result.get("summary") or {}),
            "final_capital": result.get("final_capital"),
            "error": result.get("error"),
        }

    n_workers = max(1, args.workers)

    db = SessionLocal()
    try:
        candidates = generate_candidate_strategies(
            timeframe=args.timeframe,
            universe=args.universe,
            max_candidates=args.max_candidates,
        )
        req = BacktestRequest(
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            position_size_pct=args.position_size_pct,
        )

        total_candidates = len(candidates)
        print(f"Testing {total_candidates} candidates with {n_workers} worker(s)...", flush=True)
        ranked_base = []
        if n_workers > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
                future_map = {
                    executor.submit(_backtest_worker, candidate, req, idx, total_candidates): candidate
                    for idx, candidate in enumerate(candidates, 1)
                }
                for future in concurrent.futures.as_completed(future_map):
                    ranked_base.append(future.result())
        else:
            for idx, candidate in enumerate(candidates, 1):
                result = _run_backtest_for_strategy_payload(candidate, req, db)
                print(f"  [{idx}/{total_candidates}] {candidate.get('name', '?')}", flush=True)
                ranked_base.append(
                    {
                        "strategy": candidate,
                        "summary": result.get("summary") or {},
                        "score": score_backtest_summary(result.get("summary") or {}),
                        "final_capital": result.get("final_capital"),
                        "error": result.get("error"),
                    }
                )

        ranked_base.sort(
            key=lambda item: (
                item["score"],
                float((item.get("summary") or {}).get("total_return_pct") or 0.0),
                float((item.get("summary") or {}).get("sharpe_ratio") or 0.0),
            ),
            reverse=True,
        )

        ranked = ranked_base
        exit_opt_summary = {
            "enabled": bool(args.optimize_exits),
            "base_tested": len(ranked_base),
            "shortlisted": 0,
            "combos_per_base": 0,
            "variants_tested": 0,
        }

        if args.optimize_exits and ranked_base:
            shortlist_n = max(1, int(args.exit_optimize_on_top))
            shortlisted_items = ranked_base[:shortlist_n]
            shortlisted_strategies = [item["strategy"] for item in shortlisted_items]

            sl_values = _parse_float_csv(args.sl_grid)
            tp_values = _parse_float_csv(args.tp_grid)
            tsl_values = _parse_float_csv(args.tsl_grid)
            exit_combos = generate_exit_param_combinations(
                sl_values=sl_values,
                tp_values=tp_values,
                tsl_values=tsl_values,
                max_combos=max(0, int(args.max_exit_combos)),
            )

            variant_strategies = expand_strategies_with_exit_variants(
                shortlisted_strategies,
                exit_combos=exit_combos,
            )

            total_variants = len(variant_strategies)
            print(f"Exit sweep: testing {total_variants} variants with {n_workers} worker(s)...", flush=True)
            ranked_variants = []
            if n_workers > 1:
                with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
                    future_map = {
                        executor.submit(_backtest_worker, variant, req, idx, total_variants): variant
                        for idx, variant in enumerate(variant_strategies, 1)
                    }
                    for future in concurrent.futures.as_completed(future_map):
                        ranked_variants.append(future.result())
            else:
                for idx, variant in enumerate(variant_strategies, 1):
                    result = _run_backtest_for_strategy_payload(variant, req, db)
                    print(f"  [{idx}/{total_variants}] {variant.get('name', '?')}", flush=True)
                    ranked_variants.append(
                        {
                            "strategy": variant,
                            "summary": result.get("summary") or {},
                            "score": score_backtest_summary(result.get("summary") or {}),
                            "final_capital": result.get("final_capital"),
                            "error": result.get("error"),
                        }
                    )

            ranked_variants.sort(
                key=lambda item: (
                    item["score"],
                    float((item.get("summary") or {}).get("annual_return_pct") or 0.0),
                    -float((item.get("summary") or {}).get("max_drawdown_pct") or 0.0),
                    float((item.get("summary") or {}).get("sharpe_ratio") or 0.0),
                ),
                reverse=True,
            )
            ranked = ranked_variants
            exit_opt_summary = {
                "enabled": True,
                "base_tested": len(ranked_base),
                "shortlisted": len(shortlisted_strategies),
                "combos_per_base": len(exit_combos),
                "variants_tested": len(ranked_variants),
            }

        if args.min_annual_return > 0:
            ranked = [
                item
                for item in ranked
                if float((item.get("summary") or {}).get("annual_return_pct") or 0.0) >= args.min_annual_return
            ]
        top_items = select_diverse_top(
            ranked,
            top_n=args.top,
            max_per_family=max(1, int(args.max_per_family)),
            fill_remaining=bool(args.fill_remaining),
        )

        saved = []
        if args.save_top and top_items:
            from app.db.models_condition_strategy import ConditionStrategy, ConditionStrategyBacktest
            from app.core.utils.time import now_ist
            existing_names = {name for (name,) in db.query(ConditionStrategy.name).all()}
            for rank, item in enumerate(top_items, start=1):
                strategy = dict(item["strategy"])
                base_name = strategy["name"]
                save_name = base_name
                suffix = 2
                while save_name in existing_names:
                    save_name = f"{base_name} #{suffix}"
                    suffix += 1

                row = ConditionStrategy(
                    name=save_name,
                    description=f"[LAB] rank #{rank} | score={item['score']} | return={item['summary'].get('total_return_pct')}%",
                    strategy_type=strategy.get("strategy_type", "Equity Swing"),
                    direction=strategy.get("direction", "BUY"),
                    timeframe=strategy.get("timeframe", "Day"),
                    universe=strategy.get("universe", "NIFTY50"),
                    instruments=strategy.get("instruments", []),
                    entry_conditions=strategy.get("entry_conditions", []),
                    exit_config=strategy.get("exit_config", {}),
                    is_active=True,
                    auto_scan_enabled=False,
                    auto_amount=10000.0,
                )
                db.add(row)
                db.flush()
                bt = ConditionStrategyBacktest(
                    strategy_id=row.id,
                    strategy_name=save_name,
                    start_date=args.start_date or "",
                    end_date=args.end_date or "",
                    initial_capital=args.initial_capital,
                    final_capital=item.get("final_capital"),
                    result={"summary": item["summary"], "strategy": strategy},
                )
                db.add(bt)
                db.flush()
                row.last_backtest_at = now_ist()
                row.last_backtest_id = bt.id
                existing_names.add(save_name)
                saved.append({"id": row.id, "name": save_name, "rank": rank})
            db.commit()

        payload = {
            "generated_count": len(candidates),
            "tested_count": len(ranked),
            "exit_optimization": exit_opt_summary,
            "top": [
                {
                    "rank": index,
                    "score": item["score"],
                    "name": item["strategy"]["name"],
                    "family": strategy_family(item["strategy"]),
                    "summary": item["summary"],
                    "final_capital": item["final_capital"],
                    "error": item["error"],
                }
                for index, item in enumerate(top_items, start=1)
            ],
            "saved": saved,
        }

        if args.json:
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(f"Generated {payload['generated_count']} candidates and tested {payload['tested_count']}.")
            if exit_opt_summary["enabled"]:
                print(
                    "Exit optimization: "
                    f"base_tested={exit_opt_summary['base_tested']}, "
                    f"shortlisted={exit_opt_summary['shortlisted']}, "
                    f"combos_per_base={exit_opt_summary['combos_per_base']}, "
                    f"variants_tested={exit_opt_summary['variants_tested']}"
                )
            if args.min_annual_return > 0:
                print(f"Applied annual return filter: >= {args.min_annual_return}%")
            for item in payload["top"]:
                summary = item["summary"]
                print(
                    f"#{item['rank']} {item['name']} | score={item['score']} | "
                    f"family={item['family']} | "
                    f"return={summary.get('total_return_pct', 0)}% | "
                    f"sharpe={summary.get('sharpe_ratio', 0)} | trades={summary.get('total_trades', 0)}"
                )
            if saved:
                print(f"Saved {len(saved)} strategies to DB (visible in CreateScanner)")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())