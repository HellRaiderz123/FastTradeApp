"""
Feature #19 — Position Correlation Matrix
Computes rolling correlation between symbols using daily close prices.
Useful for portfolio diversification and risk analysis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models_candles import CandleDaily

logger = logging.getLogger(__name__)


def _load_daily_closes(
    db: Session,
    symbols: List[str],
    days: int = 90,
) -> pd.DataFrame:
    """Load daily close prices for multiple symbols into a wide DataFrame."""
    frames: Dict[str, pd.Series] = {}

    for sym in symbols:
        rows = (
            db.query(CandleDaily.date, CandleDaily.close)
            .filter(CandleDaily.symbol == sym.upper())
            .order_by(CandleDaily.date.desc())
            .limit(days)
            .all()
        )
        if not rows:
            continue
        df = pd.DataFrame([(r.date, float(r.close)) for r in reversed(rows)], columns=["date", sym])
        df.set_index("date", inplace=True)
        frames[sym] = df[sym]

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames.values(), axis=1, join="inner")
    return combined


def compute_correlation_matrix(
    db: Session,
    symbols: List[str],
    *,
    days: int = 90,
    method: str = "pearson",
) -> Dict[str, Any]:
    """
    Compute pairwise correlation matrix from daily returns.
    
    method: 'pearson' | 'spearman' | 'kendall'
    """
    prices = _load_daily_closes(db, symbols, days)
    if prices.empty or prices.shape[1] < 2:
        return {"error": "Need price data for at least 2 symbols", "matrix": {}, "symbols": []}

    # Daily returns
    returns = prices.pct_change().dropna()
    if returns.empty or len(returns) < 10:
        return {"error": "Not enough return data", "matrix": {}, "symbols": []}

    corr = returns.corr(method=method)

    # Convert to JSON-serializable nested dict
    matrix: Dict[str, Dict[str, float]] = {}
    for sym_a in corr.columns:
        matrix[sym_a] = {}
        for sym_b in corr.columns:
            matrix[sym_a][sym_b] = round(float(corr.loc[sym_a, sym_b]), 4)

    # Flat list for heatmap rendering
    heatmap_data: List[Dict[str, Any]] = []
    for i, sym_a in enumerate(corr.columns):
        for j, sym_b in enumerate(corr.columns):
            heatmap_data.append({
                "x": sym_a,
                "y": sym_b,
                "value": round(float(corr.iloc[i, j]), 4),
            })

    # Identify highly correlated pairs (|corr| > 0.7, excluding self)
    high_corr_pairs: List[Dict[str, Any]] = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            val = float(corr.iloc[i, j])
            if abs(val) >= 0.7:
                high_corr_pairs.append({
                    "pair": [cols[i], cols[j]],
                    "correlation": round(val, 4),
                    "strength": "strong_positive" if val > 0.7 else "strong_negative" if val < -0.7 else "moderate",
                })

    high_corr_pairs.sort(key=lambda d: abs(d["correlation"]), reverse=True)

    # Risk metrics
    eigenvalues = np.linalg.eigvalsh(corr.values)
    effective_n = float(np.sum(eigenvalues) ** 2 / np.sum(eigenvalues ** 2))  # effective dimensionality
    avg_corr = float(corr.values[np.triu_indices_from(corr.values, k=1)].mean())

    return {
        "symbols": list(corr.columns),
        "matrix": matrix,
        "heatmap_data": heatmap_data,
        "high_correlation_pairs": high_corr_pairs,
        "method": method,
        "days": days,
        "data_points": len(returns),
        "risk_metrics": {
            "average_correlation": round(avg_corr, 4),
            "effective_dimensionality": round(effective_n, 2),
            "diversification_ratio": round(effective_n / len(cols), 4) if cols else 0,
        },
    }


def compute_rolling_correlation(
    db: Session,
    symbol_a: str,
    symbol_b: str,
    *,
    days: int = 252,
    window: int = 30,
) -> Dict[str, Any]:
    """Compute rolling correlation between two symbols over time."""
    prices = _load_daily_closes(db, [symbol_a, symbol_b], days)
    if prices.empty or prices.shape[1] < 2:
        return {"error": f"Need data for both {symbol_a} and {symbol_b}"}

    returns = prices.pct_change().dropna()
    rolling_corr = returns[symbol_a].rolling(window).corr(returns[symbol_b])
    rolling_corr = rolling_corr.dropna()

    points = [
        {
            "date": str(idx),
            "correlation": round(float(val), 4),
        }
        for idx, val in rolling_corr.items()
    ]

    return {
        "symbol_a": symbol_a,
        "symbol_b": symbol_b,
        "window": window,
        "data_points": len(points),
        "current_correlation": points[-1]["correlation"] if points else None,
        "avg_correlation": round(float(rolling_corr.mean()), 4) if not rolling_corr.empty else None,
        "series": points,
    }


def compute_portfolio_risk(
    db: Session,
    positions: List[Dict[str, Any]],
    *,
    days: int = 90,
) -> Dict[str, Any]:
    """
    Given a list of positions [{symbol, weight}], compute portfolio-level
    variance, VaR, and component risk.
    """
    symbols = [p["symbol"] for p in positions]
    weights_dict = {p["symbol"]: float(p.get("weight", 1.0 / len(positions))) for p in positions}

    prices = _load_daily_closes(db, symbols, days)
    if prices.empty or prices.shape[1] < 2:
        return {"error": "Not enough data"}

    returns = prices.pct_change().dropna()
    cov_matrix = returns.cov() * 252  # annualize

    # Align weights
    valid_symbols = [s for s in symbols if s in returns.columns]
    w = np.array([weights_dict[s] for s in valid_symbols])
    w = w / w.sum()  # normalize

    cov = cov_matrix.loc[valid_symbols, valid_symbols].values
    port_var = float(w @ cov @ w)
    port_vol = float(np.sqrt(port_var))

    # Value at Risk (95%)
    var_95 = float(-1.645 * port_vol / np.sqrt(252))

    # Component risk (marginal contribution)
    marginal = (cov @ w) / port_vol
    component_risk = {}
    for i, s in enumerate(valid_symbols):
        component_risk[s] = {
            "weight": round(float(w[i]), 4),
            "marginal_contribution": round(float(marginal[i]), 6),
            "pct_contribution": round(float(w[i] * marginal[i] / port_vol * 100), 2),
        }

    return {
        "portfolio_volatility_annual": round(port_vol * 100, 2),
        "portfolio_variance": round(port_var, 6),
        "daily_var_95": round(var_95 * 100, 3),
        "component_risk": component_risk,
        "symbols": valid_symbols,
    }
