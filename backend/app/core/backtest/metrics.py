"""
Metrics Calculator - Performance metrics for backtests
"""

import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from datetime import date

logger = logging.getLogger(__name__)


class MetricsCalculator:
    """Calculate trading performance metrics"""
    
    def __init__(
        self,
        initial_capital: float,
        final_equity: float,
        equity_curve: List[float],
        trades: List[Any],
        risk_free_rate: float = 0.05,
    ):
        self.initial_capital = initial_capital
        self.final_equity = final_equity
        self.equity_curve = equity_curve
        self.trades = trades
        self.risk_free_rate = risk_free_rate
    
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
            "win_rate_pct": round((winning_trades / total_trades * 100) if total_trades > 0 else 0, 2),
            "profit_factor": round((total_profit / total_loss) if total_loss > 0 else 0, 2),
            "avg_win": round(sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0, 2),
            "avg_loss": round(sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0, 2),
            "largest_win": round(max(winning_pnls) if winning_pnls else 0, 2),
            "largest_loss": round(min(losing_pnls) if losing_pnls else 0, 2),
            "total_profit": round(total_profit, 2),
            "total_loss": round(total_loss, 2),
            "peak_equity": round(max(self.equity_curve) if self.equity_curve else self.initial_capital, 2),
        }
    
    def _calculate_total_return(self) -> float:
        """Total return percentage"""
        if self.initial_capital == 0:
            return 0
        return ((self.final_equity - self.initial_capital) / self.initial_capital) * 100
    
    def _calculate_annual_return(self) -> float:
        """Annualized return percentage"""
        # Simplified: assume 252 trading days
        days = 252
        total_return = self._calculate_total_return() / 100
        
        if total_return <= -1:
            return 0
        
        annual_return = (1 + total_return) ** (252 / max(1, len(self.equity_curve))) - 1
        return annual_return * 100
    
    def _calculate_sharpe_ratio(self, periods_per_year: int = 252) -> float:
        """
        Sharpe Ratio = (Mean Return - Risk Free Rate) / Std Dev of Returns
        """
        if len(self.equity_curve) < 2:
            return 0
        
        # Calculate daily returns
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0
        
        # Annualize
        mean_return = np.mean(returns) * periods_per_year
        std_return = np.std(returns) * np.sqrt(periods_per_year)
        
        sharpe = (mean_return - self.risk_free_rate) / std_return if std_return > 0 else 0
        return max(-10, min(10, sharpe))  # Clamp to -10 to 10
    
    def _calculate_sortino_ratio(self, periods_per_year: int = 252) -> float:
        """
        Sortino Ratio = (Mean Return - Risk Free Rate) / Downside Deviation
        Similar to Sharpe but only penalizes downside volatility
        """
        if len(self.equity_curve) < 2:
            return 0
        
        # Calculate daily returns
        returns = np.diff(self.equity_curve) / self.equity_curve[:-1]
        
        if len(returns) == 0:
            return 0
        
        # Downside deviation (only negative returns)
        negative_returns = returns[returns < 0]
        downside_dev = np.std(negative_returns) if len(negative_returns) > 0 else 0
        downside_dev *= np.sqrt(periods_per_year)
        
        mean_return = np.mean(returns) * periods_per_year
        
        sortino = (mean_return - self.risk_free_rate) / downside_dev if downside_dev > 0 else 0
        return max(-10, min(10, sortino))  # Clamp to -10 to 10
    
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
        Calmar Ratio = Annual Return / Max Drawdown
        """
        max_dd = self._calculate_max_drawdown() / 100
        
        if max_dd == 0:
            return 0
        
        calmar = annual_return_pct / max_dd
        return max(-10, min(10, calmar))  # Clamp to -10 to 10
    
    def calculate_drawdown_periods(self) -> List[Dict[str, Any]]:
        """
        Calculate drawdown periods - when equity was declining
        """
        drawdown_periods = []
        peak = self.equity_curve[0] if self.equity_curve else 0
        peak_date = 0
        trough = peak
        trough_date = 0
        in_drawdown = False
        
        for i, equity in enumerate(self.equity_curve):
            if equity > peak:
                # New peak
                if in_drawdown:
                    # End of drawdown period
                    drawdown_pct = ((peak - trough) / peak * 100) if peak > 0 else 0
                    drawdown_periods.append({
                        "start": peak_date,
                        "end": trough_date,
                        "peak": peak,
                        "trough": trough,
                        "drawdown_pct": round(drawdown_pct, 2),
                    })
                    in_drawdown = False
                
                peak = equity
                peak_date = i
                trough = peak
                trough_date = i
            else:
                # Declining
                if not in_drawdown:
                    in_drawdown = True
                
                if equity < trough:
                    trough = equity
                    trough_date = i
        
        return drawdown_periods
