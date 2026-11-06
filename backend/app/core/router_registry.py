"""
Router Registration Module

Extracted from main.py to reduce complexity.
Handles all FastAPI router registration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import Depends

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


def register_all_routers(app: "FastAPI") -> None:
    """
    Register all API routers with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    from app.core.auth import require_authenticated_user

    # Import all routers
    from app.api.option_spread import router as option_spread_router
    from app.api.system_control import router as system_router
    import os as _os
    _ml_enabled = _os.getenv("ML_ENABLED", "true").lower() != "false"

    from app.api.routes import (
        journal,
        intent,
        execute,
        account,
        strategies,
        execution_v2,
        settings,
        backtest,
        greeks,
        market,
        suggestions,
        stock_suggestions,
        screener,
        options,
        options_real,
        ws_positions,
        notifications,
        websocket_routes,
        health,
        market_dashboard,
        swing_scanner,
        sentiment,
        config_routes,
        news,
        twitter,
        economic_calendar,
        market_depth,
        alerts,
        stock_news,
        timeframe_suggestions,
        peer_comparison,
        safety,
        candles,
        zerodha_broker,
        indmoney_broker,
        broker as broker_routes,
        position_suggestions,
        auto_trader as auto_trader_routes,
        auth,
        trade_costs,
        watchlists,
        condition_scanner,
        reconcile,
        analytics,
        marketplace,
        ai_chat,
        alexa,
        simple_ai,
        ai_analysis,
        holdings as holdings_routes,
        quant,
        fundamentals as fundamentals_routes,
        fii_dii as fii_dii_routes,
        nse_data as nse_data_routes,
        filing_analysis as filing_analysis_routes,
    )
    if _ml_enabled:
        from app.api.routes import ml
    from app.api.routes.paper_mtm import router as paper_mtm_router
    from app.api.routes.exit import router as exit_router
    from app.api.routes.auto_exit import router as auto_exit_router
    from app.api.routes.finance import router as finance_router
    from app.api.routes.scalp_trading import router as scalp_router

    # Auth dependency for protected routes
    auth_dep = [Depends(require_authenticated_user)]

    # ─── Option Spread Router ─────────────────────────────────────────────────
    app.include_router(
        option_spread_router,
        prefix="/strategy",
        tags=["Option Spreads"],
        dependencies=auth_dep,
    )

    # ─── Core Routes ──────────────────────────────────────────────────────────
    app.include_router(auth.router)  # No auth required for login
    app.include_router(journal.router, dependencies=auth_dep)
    app.include_router(intent.router, dependencies=auth_dep)
    app.include_router(execute.router, dependencies=auth_dep)
    app.include_router(account.router, dependencies=auth_dep)
    app.include_router(strategies.router, dependencies=auth_dep)
    app.include_router(execution_v2.router, dependencies=auth_dep)
    app.include_router(settings.router, dependencies=auth_dep)
    app.include_router(backtest.router, dependencies=auth_dep)
    app.include_router(greeks.router, dependencies=auth_dep)
    app.include_router(market.router, dependencies=auth_dep)
    app.include_router(screener.router, dependencies=auth_dep)
    app.include_router(options.router, dependencies=auth_dep)
    app.include_router(options_real.router, dependencies=auth_dep)
    app.include_router(suggestions.router, dependencies=auth_dep)
    app.include_router(stock_suggestions.router, dependencies=auth_dep)

    # ─── WebSocket Routes (no auth for WS handshake) ──────────────────────────
    app.include_router(ws_positions.router)
    app.include_router(websocket_routes.router)

    # ─── Health Routes (no auth for monitoring) ───────────────────────────────
    app.include_router(health.router)

    # ─── Protected Routes ─────────────────────────────────────────────────────
    app.include_router(alerts.router, dependencies=auth_dep)
    app.include_router(paper_mtm_router, dependencies=auth_dep)
    app.include_router(exit_router, dependencies=auth_dep)
    app.include_router(auto_exit_router, dependencies=auth_dep)
    app.include_router(system_router, dependencies=auth_dep)
    app.include_router(scalp_router, dependencies=auth_dep)
    if _ml_enabled:
        app.include_router(ml.router, dependencies=auth_dep)
    app.include_router(notifications.router, dependencies=auth_dep)
    app.include_router(finance_router, dependencies=auth_dep)
    app.include_router(market_dashboard.router, dependencies=auth_dep)
    app.include_router(swing_scanner.router, dependencies=auth_dep)
    app.include_router(sentiment.router, dependencies=auth_dep)
    app.include_router(news.router, dependencies=auth_dep)
    app.include_router(twitter.router, dependencies=auth_dep)
    app.include_router(economic_calendar.router, dependencies=auth_dep)
    app.include_router(market_depth.router, dependencies=auth_dep)
    app.include_router(config_routes.router, dependencies=auth_dep)
    app.include_router(stock_news.router, dependencies=auth_dep)
    app.include_router(timeframe_suggestions.router, dependencies=auth_dep)
    app.include_router(peer_comparison.router, dependencies=auth_dep)
    app.include_router(safety.router, dependencies=auth_dep)
    app.include_router(candles.router, dependencies=auth_dep)
    app.include_router(zerodha_broker.router, dependencies=auth_dep)
    app.include_router(indmoney_broker.router, dependencies=auth_dep)
    app.include_router(broker_routes.router, dependencies=auth_dep)
    app.include_router(position_suggestions.router, dependencies=auth_dep)
    app.include_router(auto_trader_routes.router, dependencies=auth_dep)
    app.include_router(trade_costs.router, dependencies=auth_dep)
    app.include_router(watchlists.router, dependencies=auth_dep)
    app.include_router(condition_scanner.router, dependencies=auth_dep)
    app.include_router(reconcile.router, dependencies=auth_dep)
    app.include_router(analytics.router, dependencies=auth_dep)
    app.include_router(marketplace.router, dependencies=auth_dep)
    app.include_router(ai_chat.router, dependencies=auth_dep)
    app.include_router(simple_ai.router, dependencies=auth_dep)
    app.include_router(ai_analysis.router, dependencies=auth_dep)
    app.include_router(holdings_routes.router, dependencies=auth_dep)
    app.include_router(quant.router, dependencies=auth_dep)
    app.include_router(fundamentals_routes.router, dependencies=auth_dep)
    app.include_router(fii_dii_routes.router, dependencies=auth_dep)
    app.include_router(nse_data_routes.router, dependencies=auth_dep)
    app.include_router(filing_analysis_routes.router, dependencies=auth_dep)

    # ─── Alexa (uses its own auth) ────────────────────────────────────────────
    app.include_router(alexa.router)

    logger.info("✅ All routers registered (including Phase 5 features + Quant APIs)")
