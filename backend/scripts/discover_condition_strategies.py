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
from app.core.market.scheduler import (  # noqa: E402
    _discovery_timeframes,
    _interleave_discovery_candidates,
    _load_discovery_state,
    _merge_discovery_leaderboard,
    _save_discovery_state,
    _slice_discovery_batch,
)


def _parse_float_csv(value: str) -> list[float]:
    return [float(x.strip()) for x in value.split(",") if x.strip()]


def _parse_timeframes_csv(value: str | None) -> list[str]:
    valid = {"Day", "1 Hour", "15 Min", "5 Min", "1 Min"}
    if not value:
        return []
    resolved = []
    for item in value.split(","):
        timeframe = item.strip()
        if timeframe in valid and timeframe not in resolved:
            resolved.append(timeframe)
    return resolved


def _prepare_discovery_batch(
    *,
    timeframe: str,
    timeframes: list[str],
    universe: str,
    max_candidates: int,
    batch_size: int,
    resume_progress: bool,
    start_offset: int | None = None,
    progress_state: dict | None = None,
    candidates_by_timeframe: dict[str, list[dict]] | None = None,
) -> tuple[list[dict], dict, str]:
    resolved_timeframes = list(timeframes or [timeframe])
    state_key = f"{universe}|{'|'.join(resolved_timeframes)}"

    if candidates_by_timeframe is None:
        candidates_by_timeframe = {
            tf: generate_candidate_strategies(
                timeframe=tf,
                universe=universe,
                max_candidates=max_candidates,
            )
            for tf in resolved_timeframes
        }

    if len(resolved_timeframes) > 1:
        candidate_pool = _interleave_discovery_candidates(candidates_by_timeframe)
    else:
        candidate_pool = list(candidates_by_timeframe.get(resolved_timeframes[0]) or [])
    candidate_pool = candidate_pool[:max_candidates]

    effective_batch_size = max(1, int(batch_size or len(candidate_pool) or 1))
    cursor = int(start_offset or 0)
    if resume_progress and start_offset is None and progress_state:
        state_row = ((progress_state.get("strategy_batches") or {}).get(state_key) or {})
        cursor = int(state_row.get("next_offset", 0) or 0)

    if resume_progress or effective_batch_size < len(candidate_pool):
        batch_meta = _slice_discovery_batch(
            candidate_pool,
            start_offset=cursor,
            batch_size=effective_batch_size,
        )
        selected = list(batch_meta.get("items") or [])
    else:
        selected = candidate_pool
        batch_meta = {
            "items": list(selected),
            "total": len(candidate_pool),
            "start_offset": 0,
            "end_offset": len(candidate_pool),
            "next_offset": 0,
            "completed_cycle": True,
        }

    return selected, batch_meta, state_key


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and rank condition-scanner strategies.")
    parser.add_argument("--timeframe", default="Day", choices=["Day", "1 Hour", "15 Min", "5 Min", "1 Min"])
    parser.add_argument("--timeframes", default=None, help="Optional comma-separated timeframes for a shared mixed batch, e.g. 'Day,1 Hour,15 Min'.")
    parser.add_argument("--universe", default="NIFTY50")
    parser.add_argument("--max-candidates", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=0, help="When using shared progress, test only this many candidates in the current batch.")
    parser.add_argument("--resume-progress", action="store_true", help="Use the same persisted discovery cursor as the scheduler so manual runs advance the shared batch state.")
    parser.add_argument("--start-offset", type=int, default=None, help="Optional manual candidate offset override for the current run.")
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

    resolved_timeframes = _parse_timeframes_csv(args.timeframes)
    if not resolved_timeframes:
        resolved_timeframes = _discovery_timeframes() if args.resume_progress else [args.timeframe]

    progress_state = _load_discovery_state() if args.resume_progress else {"version": 1, "runs": 0, "strategy_batches": {}}
    requested_batch_size = int(args.batch_size or 0)
    if args.resume_progress and requested_batch_size <= 0:
        requested_batch_size = max(int((progress_state.get("strategy_batches") or {}).get(f"{args.universe}|{'|'.join(resolved_timeframes)}", {}).get("last_batch_tested", 0) or 0), 0)
        if requested_batch_size <= 0:
            requested_batch_size = 50

    db = SessionLocal()
    try:
        candidates_by_timeframe = {
            tf: generate_candidate_strategies(
                timeframe=tf,
                universe=args.universe,
                max_candidates=args.max_candidates,
            )
            for tf in resolved_timeframes
        }
        candidates, batch_meta, state_key = _prepare_discovery_batch(
            timeframe=args.timeframe,
            timeframes=resolved_timeframes,
            universe=args.universe,
            max_candidates=args.max_candidates,
            batch_size=requested_batch_size,
            resume_progress=bool(args.resume_progress),
            start_offset=args.start_offset,
            progress_state=progress_state,
            candidates_by_timeframe=candidates_by_timeframe,
        )

        req = BacktestRequest(
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            position_size_pct=args.position_size_pct,
        )

        total_candidates = len(candidates)
        if args.resume_progress:
            print(
                "Shared discovery batch: "
                f"state_key={state_key} | "
                f"range={batch_meta.get('start_offset', 0) + 1}-{batch_meta.get('end_offset', 0)} / {batch_meta.get('total', total_candidates)} | "
                f"next={batch_meta.get('next_offset', 0)}",
                flush=True,
            )
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

        state_row = dict((progress_state.get("strategy_batches") or {}).get(state_key) or {}) if args.resume_progress else {}
        rolling_top_results = _merge_discovery_leaderboard(
            state_row.get("rolling_top_results") or [],
            ranked,
            top_n=max(args.top, 5),
        )
        tested_count = len(ranked)

        if args.min_annual_return > 0:
            ranked = [
                item
                for item in ranked
                if float((item.get("summary") or {}).get("annual_return_pct") or 0.0) >= args.min_annual_return
            ]
        qualified_count = len(ranked)
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

        if args.resume_progress:
            from app.core.utils.time import now_ist

            state_row = dict((progress_state.get("strategy_batches") or {}).get(state_key) or {})
            state_row.update(
                {
                    "last_run_at": now_ist().isoformat(),
                    "last_run_source": "manual_script",
                    "next_offset": batch_meta.get("next_offset", 0),
                    "pool_total": batch_meta.get("total", len(candidates)),
                    "last_batch_start": batch_meta.get("start_offset", 0),
                    "last_batch_end": batch_meta.get("end_offset", len(candidates)),
                    "last_batch_tested": len(candidates),
                    "saved_count": len(saved),
                    "saved_names": [item.get("name") for item in saved],
                    "completed_cycle": bool(batch_meta.get("completed_cycle")),
                    "cycle_count": int(state_row.get("cycle_count", 0) or 0) + (1 if batch_meta.get("completed_cycle") else 0),
                    "top_results": [
                        {
                            "name": item["strategy"]["name"],
                            "timeframe": item["strategy"].get("timeframe"),
                            "score": item["score"],
                            "annual_return_pct": (item.get("summary") or {}).get("annual_return_pct"),
                            "max_drawdown_pct": (item.get("summary") or {}).get("max_drawdown_pct"),
                        }
                        for item in top_items
                    ],
                    "rolling_top_results": rolling_top_results[: max(args.top, 5)],
                }
            )
            progress_state.setdefault("strategy_batches", {})[state_key] = state_row
            progress_state["runs"] = int(progress_state.get("runs", 0) or 0) + 1
            _save_discovery_state(progress_state)

        payload = {
            "generated_count": len(candidates),
            "tested_count": tested_count,
            "qualified_count": qualified_count,
            "discovery_batch": {
                "enabled": bool(args.resume_progress),
                "state_key": state_key if args.resume_progress else None,
                "timeframes": resolved_timeframes,
                "start_offset": batch_meta.get("start_offset", 0),
                "end_offset": batch_meta.get("end_offset", len(candidates)),
                "next_offset": batch_meta.get("next_offset", 0),
                "completed_cycle": bool(batch_meta.get("completed_cycle", True)),
                "total_pool": batch_meta.get("total", len(candidates)),
            },
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
            "best_so_far_top": [
                {
                    "rank": index,
                    **row,
                }
                for index, row in enumerate(rolling_top_results[:5], start=1)
            ],
            "saved": saved,
        }

        if args.json:
            print(json.dumps(payload, indent=2, default=str))
        else:
            print(
                f"Generated {payload['generated_count']} candidates and tested {payload['tested_count']} "
                f"(qualified after filters: {payload['qualified_count']})."
            )
            if payload["discovery_batch"]["enabled"]:
                print(
                    "Shared progress: "
                    f"range={payload['discovery_batch']['start_offset'] + 1}-{payload['discovery_batch']['end_offset']} / {payload['discovery_batch']['total_pool']} | "
                    f"next={payload['discovery_batch']['next_offset']} | "
                    f"cycle_complete={payload['discovery_batch']['completed_cycle']}"
                )
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
            if payload["top"]:
                print("Current batch qualified top results:")
            for item in payload["top"]:
                summary = item["summary"]
                print(
                    f"#{item['rank']} {item['name']} | score={item['score']} | "
                    f"family={item['family']} | "
                    f"return={summary.get('total_return_pct', 0)}% | "
                    f"sharpe={summary.get('sharpe_ratio', 0)} | trades={summary.get('total_trades', 0)}"
                )
            if payload["best_so_far_top"]:
                print("Rolling best-so-far top 5:")
                for item in payload["best_so_far_top"]:
                    print(
                        f"#{item['rank']} {item['name']} [{item.get('timeframe')}] | "
                        f"score={item.get('score')} | annual={item.get('annual_return_pct')}% | "
                        f"dd={item.get('max_drawdown_pct')}% | trades={item.get('total_trades')}"
                    )
            if saved:
                print(f"Saved {len(saved)} strategies to DB (visible in CreateScanner)")

        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())