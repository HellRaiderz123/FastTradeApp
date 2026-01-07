"""
Backtest API Routes
"""

import logging
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import SessionLocal
from app.db.models import StrategyConfig, BacktestResult, BacktestTrade
from app.core.backtest.engine import BacktestEngine
from app.core.backtest.options_engine import OptionsBacktestEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtest"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================
# REQUEST/RESPONSE MODELS
# ============================

class BacktestRequest(BaseModel):
    """Request to run a backtest"""
    strategy_config_id: int
    start_date: date
    end_date: date
    initial_capital: float = 100000
    mode: str = "auto"  # auto | proxy | options


class BacktestResultResponse(BaseModel):
    """Backtest result response"""
    id: int
    strategy_config_id: int
    start_date: date
    end_date: date
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    
    class Config:
        from_attributes = True


# ============================
# ENDPOINTS
# ============================

@router.post("/run", summary="Run backtest for a strategy")
def run_backtest(
    request: BacktestRequest,
    db: Session = Depends(get_db),
):
    """
    Run a backtest on historical data
    
    Args:
        strategy_config_id: ID of the strategy to backtest
        start_date: Start date for backtest
        end_date: End date for backtest
        initial_capital: Starting capital (default 100000)
    
    Returns:
        Backtest result with performance metrics
    """
    try:
        logger.info(f"🔄 Running backtest for strategy {request.strategy_config_id}")
        
        # Load strategy config
        config = db.query(StrategyConfig).filter_by(id=request.strategy_config_id).first()
        
        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"Strategy {request.strategy_config_id} not found"
            )
        
        mode = (request.mode or "auto").lower().strip()
        if mode not in {"auto", "proxy", "options"}:
            raise HTTPException(status_code=400, detail="Invalid mode. Use auto|proxy|options")

        use_options = mode == "options" or (mode == "auto" and config.strategy_type == "option_spread_15m")

        if use_options:
            try:
                engine = OptionsBacktestEngine(config, db)
                result = engine.run(
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_capital=request.initial_capital,
                )

                # If we couldn't price anything, don't pretend it succeeded.
                pricing_missing_count = int(result.get("pricing_missing_count", 0) or 0)
                total_trades = int(result.get("total_trades", 0) or 0)
                if result.get("success") and pricing_missing_count > 0 and total_trades == 0:
                    msg = (
                        "Options backtest unavailable for this date range because option contracts "
                        "weren't found in the current Zerodha instruments dump (expired expiry). "
                        "Use Mode=Proxy for older periods, or backtest recent/current expiry periods in Mode=Options."
                    )
                    if mode == "options":
                        return {
                            "success": False,
                            "error": msg,
                            "strategy_config_id": request.strategy_config_id,
                            "pricing_missing_count": pricing_missing_count,
                            "pricing_missing_symbols": result.get("pricing_missing_symbols", []),
                        }

                    logger.warning(f"⚠️ {msg} Falling back to proxy.")
                    engine = BacktestEngine(config, db)
                    result = engine.run(
                        start_date=request.start_date,
                        end_date=request.end_date,
                        initial_capital=request.initial_capital,
                    )
                    result["warning"] = msg
                    result["mode_used"] = "proxy_fallback"
                elif result.get("success") and pricing_missing_count > 0:
                    result["warning"] = (
                        "Some option legs could not be priced (missing instruments). "
                        "Results may be incomplete."
                    )
                    result["mode_used"] = "options"
            except KeyError as e:
                # Old expiries often aren't present in the current instruments dump.
                msg = str(e)
                logger.warning(f"⚠️ Options backtest pricing unavailable: {msg}")
                if mode == "options":
                    return {
                        "success": False,
                        "error": (
                            "Options backtest failed: option contract not found in current instruments. "
                            "This usually happens when backtesting older expiries (e.g., 2024) without an instruments snapshot. "
                            f"Details: {msg}"
                        ),
                        "strategy_config_id": request.strategy_config_id,
                    }

                # mode == auto -> fallback to proxy backtest
                engine = BacktestEngine(config, db)
                result = engine.run(
                    start_date=request.start_date,
                    end_date=request.end_date,
                    initial_capital=request.initial_capital,
                )
                result["warning"] = (
                    "Fell back to proxy backtest because options pricing was unavailable for this date range. "
                    f"Details: {msg}"
                )
                result["mode_used"] = "proxy_fallback"
        else:
            engine = BacktestEngine(config, db)
            result = engine.run(
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
            )
        
        if not result.get("success"):
            logger.error(f"❌ Backtest failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error"),
                "strategy_config_id": request.strategy_config_id,
            }
        
        # Save result to database
        try:
            bt_result = BacktestResult(
                strategy_config_id=request.strategy_config_id,
                start_date=request.start_date,
                end_date=request.end_date,
                initial_capital=request.initial_capital,
                total_return_pct=result.get("total_return_pct"),
                annual_return_pct=result.get("annual_return_pct"),
                sharpe_ratio=result.get("sharpe_ratio"),
                sortino_ratio=result.get("sortino_ratio"),
                max_drawdown_pct=result.get("max_drawdown_pct"),
                calmar_ratio=result.get("calmar_ratio"),
                total_trades=result.get("total_trades", 0),
                winning_trades=result.get("winning_trades", 0),
                losing_trades=result.get("losing_trades", 0),
                win_rate_pct=result.get("win_rate_pct"),
                profit_factor=result.get("profit_factor"),
                total_profit=result.get("total_profit"),
                total_loss=result.get("total_loss"),
                avg_win=result.get("avg_win"),
                avg_loss=result.get("avg_loss"),
                largest_win=result.get("largest_win"),
                largest_loss=result.get("largest_loss"),
                final_equity=result.get("final_equity"),
                peak_equity=result.get("peak_equity"),
                trades=result.get("trades"),
                equity_curve=result.get("equity_curve"),
                drawdown_periods=result.get("drawdown_periods"),
                status="completed",
            )
            
            db.add(bt_result)
            db.commit()
            db.refresh(bt_result)
            
            logger.info(f"✅ Backtest saved to database with ID {bt_result.id}")
            
            # Add result details to response
            result["id"] = bt_result.id
            
        except Exception as e:
            logger.warning(f"⚠️ Could not save backtest to DB: {e}")
            # Still return results even if save fails
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Backtest error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/results/{backtest_id}", summary="Get backtest result")
def get_backtest_result(
    backtest_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a saved backtest result by ID
    """
    try:
        result = db.query(BacktestResult).filter_by(id=backtest_id).first()
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Backtest result {backtest_id} not found"
            )
        
        return {
            "id": result.id,
            "strategy_config_id": result.strategy_config_id,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "initial_capital": result.initial_capital,
            "total_return_pct": result.total_return_pct,
            "annual_return_pct": result.annual_return_pct,
            "sharpe_ratio": result.sharpe_ratio,
            "sortino_ratio": result.sortino_ratio,
            "max_drawdown_pct": result.max_drawdown_pct,
            "calmar_ratio": result.calmar_ratio,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate_pct": result.win_rate_pct,
            "profit_factor": result.profit_factor,
            "total_profit": result.total_profit,
            "total_loss": result.total_loss,
            "avg_win": result.avg_win,
            "avg_loss": result.avg_loss,
            "largest_win": result.largest_win,
            "largest_loss": result.largest_loss,
            "final_equity": result.final_equity,
            "peak_equity": result.peak_equity,
            "trades": result.trades,
            "equity_curve": result.equity_curve,
            "drawdown_periods": result.drawdown_periods,
            "status": result.status,
            "created_at": result.created_at,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy/{strategy_config_id}", summary="List backtests for strategy")
def list_strategy_backtests(
    strategy_config_id: int,
    db: Session = Depends(get_db),
):
    """
    Get all backtest results for a strategy
    """
    try:
        results = db.query(BacktestResult)\
            .filter_by(strategy_config_id=strategy_config_id)\
            .order_by(BacktestResult.created_at.desc())\
            .all()
        
        return [
            {
                "id": r.id,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "total_return_pct": r.total_return_pct,
                "sharpe_ratio": r.sharpe_ratio,
                "max_drawdown_pct": r.max_drawdown_pct,
                "total_trades": r.total_trades,
                "win_rate_pct": r.win_rate_pct,
                "created_at": r.created_at,
            }
            for r in results
        ]
    
    except Exception as e:
        logger.error(f"❌ Error listing backtests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare", summary="Compare multiple backtests")
def compare_backtests(
    backtest_ids: list[int],
    db: Session = Depends(get_db),
):
    """
    Compare multiple backtest results
    """
    try:
        results = db.query(BacktestResult)\
            .filter(BacktestResult.id.in_(backtest_ids))\
            .all()
        
        if len(results) == 0:
            raise HTTPException(status_code=404, detail="No backtests found")
        
        comparison = []
        for r in results:
            comparison.append({
                "id": r.id,
                "strategy_config_id": r.strategy_config_id,
                "total_return_pct": r.total_return_pct,
                "sharpe_ratio": r.sharpe_ratio,
                "sortino_ratio": r.sortino_ratio,
                "max_drawdown_pct": r.max_drawdown_pct,
                "calmar_ratio": r.calmar_ratio,
                "win_rate_pct": r.win_rate_pct,
                "profit_factor": r.profit_factor,
                "total_trades": r.total_trades,
            })
        
        return {
            "best_return": max(comparison, key=lambda x: x["total_return_pct"]),
            "best_sharpe": max(comparison, key=lambda x: x["sharpe_ratio"]),
            "best_win_rate": max(comparison, key=lambda x: x["win_rate_pct"]),
            "all_results": comparison,
        }
    
    except Exception as e:
        logger.error(f"❌ Error comparing backtests: {e}")
        raise HTTPException(status_code=500, detail=str(e))
