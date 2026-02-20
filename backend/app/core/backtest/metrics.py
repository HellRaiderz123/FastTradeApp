"""
Metrics Calculator - Performance metrics for backtests
"""

import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from datetime import date
from collections import defaultdict

logger = logging.getLogger(__name__)


def _aggregate_to_daily_returns(equity_curve: List[float], candles_per_day: int = 26) -> np.ndarray:
    """
    Convert a candle-level equity curve to daily returns.
    
    For 15-minute candles, there are ~26 candles per trading day (9:15-15:30).
    We take the LAST equity value of each day-chunk as the daily close.
    """
    if len(equity_curve) < 2:
        return np.array([])

    # Sample at end-of-day boundaries
    daily_equity = []
    for i in range(0, len(equity_curve), candles_per_day):
        # Take last point in this day's chunk
        end_idx = min(i + candles_per_day, len(equity_curve)) - 1
        daily_equity.append(equity_curve[end_idx])

    # Always include the very last point
    if daily_equity[-1] != equity_curve[-1]:
        daily_equity.append(equity_curve[-1])

    if len(daily_equity) < 2:
        return np.array([])

    arr = np.array(daily_equity, dtype=float)
    returns = np.diff(arr) / arr[:-1]
    # Remove any nan/inf from flat equity periods
    returns = returns[np.isfinite(returns)]
    return returns


class MetricsCalculator:
    """Calculate trading performance metrics"""
    
    def __init__(
        self,
        initial_capital: float,
        final_equity: float,
        equity_curve: List[float],
        trades: List[Any],
        risk_free_rate: float = 0.065,  # India ~6.5% risk-free (10Y govt bond)
        trading_days: int = 0,          # Actual trading days in backtest period
    ):
        self.initial_capital = initial_capital
        self.final_equity = final_equity
        self.equity_curve = equity_curve
        self.trades = trades
        self.risk_free_rate = risk_free_rate
        # If trading_days not provided, estimate from equity curve
        # (26 candles per day for 15-min data)
        self.trading_days = trading_days if trading_days > 0 else max(1, len(equity_curve) // 26)
    
    def calculate_all(self) -> Dict[str, Any]:
        """Calculate all metrics at once"""
        total_return_pct = self._calculate_total_return()
        annual_return_pct = self._calculate_annual_return()
        
        winning_trades = len([t for t in self.trades if t.pnl and t.pnl > 0])
        losing_trades = len([t for t in self.trades if t.pnl and t.pnl < 0])
        total_trades = len(self.trades)
        
        winning_pnls = [t.pnl for t in self.trades if t.pnl and t.pnl > 0]
        losing_pnls = [t.pnl for t in self.trades if t.pnl and t.pnl < 0]
        
        total_profit = sum(winning_pnls) if winning_pnls else 0
        total_loss = abs(sum(losing_pnls)) if losing_pnls else 0
        
        # Expectancy = (win_rate × avg_win) - (loss_rate × avg_loss)
        win_rate = (winning_trades / total_trades) if total_trades > 0 else 0
        avg_win_val = (sum(winning_pnls) / len(winning_pnls)) if winning_pnls else 0
        avg_loss_val = abs(sum(losing_pnls) / len(losing_pnls)) if losing_pnls else 0
        expectancy = (win_rate * avg_win_val) - ((1 - win_rate) * avg_loss_val)

        return {
            "total_return_pct": round(total_return_pct, 2),
            "annual_return_pct": round(annual_return_pct, 2),
            "sharpe_ratio": round(self._calculate_sharpe_ratio(), 2),
            "sortino_ratio": round(self._calculate_sortino_ratio(), 2),
            "max_drawdown_pct": round(self._calculate_max_drawdown(), 2),
            "calmar_ratio": round(self._calculate_calmar_ratio(annual_return_pct), 2),
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate_pct": round(win_rate * 100, 2),
            "profit_factor": round((total_profit / total_loss) if total_loss > 0 else (999.0 if total_profit > 0 else 0), 2),
            "avg_win": round(avg_win_val, 2),
            "avg_loss": round(-avg_loss_val, 2),  # Return as negative for clarity
            "largest_win": round(max(winning_pnls) if winning_pnls else 0, 2),
            "largest_loss": round(min(losing_pnls) if losing_pnls else 0, 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "peak_equity": round(max(self.equity_curve) if self.equity_curve else self.initial_capital, 2),
            "expectancy": round(expectancy, 2),
        }
    
    def _calculate_total_return(self) -> float:
        """Total return percentage"""
        if self.initial_capital == 0:
            return 0
        return ((self.final_equity - self.initial_capital) / self.initial_capital) * 100
    
    def _calculate_annual_return(self) -> float:
        """
        Annualized return percentage.
        Uses actual trading days (not equity curve length) for proper scaling.
        """
        total_return = self._calculate_total_return() / 100
        
        if total_return <= -1:
            return -100.0
        
        # Use actual trading days for annualization
        days = max(1, self.trading_days)
        annual_return = (1 + total_return) ** (252.0 / days) - 1
        return annual_return * 100
    
    def _calculate_sharpe_ratio(self) -> float:
        """
        Sharpe Ratio = (Mean Daily Return - Daily Risk Free Rate) / Std Dev of Daily Returns
        Annualized by multiplying by sqrt(252).
        
        Uses DAILY returns (aggregated from candle-level equity curve).
        """
        daily_returns = _aggregate_to_daily_returns(self.equity_curve)
        
        if len(daily_returns) < 2:
            return 0
        
        if np.std(daily_returns) == 0:
            return 0
        
        daily_rf = self.risk_free_rate / 252.0
        excess_returns = daily_returns - daily_rf
        
        sharpe = (np.mean(excess_returns) / np.std(daily_returns)) * np.sqrt(252)
        return max(-10, min(10, float(sharpe)))
    
    def _calculate_sortino_ratio(self) -> float:
        """
        Sortino Ratio = (Mean Daily Return - Daily Risk Free Rate) / Downside Deviation
        Only penalizes downside volatility. Annualized by sqrt(252).
        """
        daily_returns = _aggregate_to_daily_returns(self.equity_curve)
        
        if len(daily_returns) < 2:
            return 0
        
        daily_rf = self.risk_free_rate / 252.0
        
        # Downside deviation: std of returns below target (risk-free rate)
        downside_returns = daily_returns[daily_returns < daily_rf]
        if len(downside_returns) == 0:
            return 10.0  # All positive — excellent
        
        downside_dev = np.std(downside_returns) * np.sqrt(252)
        mean_annual_return = np.mean(daily_returns) * 252
        
        if downside_dev == 0:
            return 0
        
        sortino = (mean_annual_return - self.risk_free_rate) / downside_dev
        return max(-10, min(10, float(sortino)))
    
    def _calculate_max_drawdown(self) -> float:
        """
        Max Drawdown = (Peak Equity - Trough) / Peak Equity * 100
        """
        if len(self.equity_curve) == 0:
            return 0
        
        peak = self.equity_curve[0]
        max_dd = 0
        
        for equity in self.equity_curve:
            if equity > peak:
                peak = equity
            
            drawdown = (peak - equity) / peak if peak > 0 else 0
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd * 100
    
    def _calculate_calmar_ratio(self, annual_return_pct: float) -> float:
        """
        Calmar Ratio = Annual Return % / Max Drawdown %
        Both numerator and denominator are in percentage.
        """
        max_dd_pct = self._calculate_max_drawdown()
        
        if max_dd_pct == 0:
            return 0
        
        calmar = annual_return_pct / max_dd_pct
        return max(-10, min(10, calmar))
    
    def calculate_drawdown_periods(self) -> List[Dict[str, Any]]:
        """
        Calculate drawdown periods - when equity was declining.
        Records all drawdowns including one that's active at the end.
        """
        if not self.equity_curve:
            return []

        drawdown_periods = []
        peak = self.equity_curve[0]
        peak_idx = 0
        trough = peak
        trough_idx = 0
        in_drawdown = False
        
        for i, equity in enumerate(self.equity_curve):
            if equity > peak:
                # New peak — close any active drawdown
                if in_drawdown:
                    drawdown_pct = ((peak - trough) / peak * 100) if peak > 0 else 0
                    if drawdown_pct > 0.01:  # Only record meaningful drawdowns
                        drawdown_periods.append({
                            "start": peak_idx,
                            "end": trough_idx,
                            "recovery": i,
                            "peak": round(peak, 2),
                            "trough": round(trough, 2),
                            "drawdown_pct": round(drawdown_pct, 2),
                        })
                    in_drawdown = False
                
                peak = equity
                peak_idx = i
                trough = peak
                trough_idx = i
            else:
                if not in_drawdown and equity < peak:
                    in_drawdown = True
                
                if equity < trough:
                    trough = equity
                    trough_idx = i
        
        # Record final drawdown if backtest ends in a drawdown
        if in_drawdown:
            drawdown_pct = ((peak - trough) / peak * 100) if peak > 0 else 0
            if drawdown_pct > 0.01:
                drawdown_periods.append({
                    "start": peak_idx,
                    "end": trough_idx,
                    "recovery": None,  # Not recovered yet
                    "peak": round(peak, 2),
                    "trough": round(trough, 2),
                    "drawdown_pct": round(drawdown_pct, 2),
                })
        
        return drawdown_periods
