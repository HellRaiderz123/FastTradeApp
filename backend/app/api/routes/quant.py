"""
Quant API Endpoints — Cash and Options quantitative analysis.

Phase 5: FastAPI endpoints for CashQuantReport and OptionsQuantReport.
"""

import logging
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/quant", tags=["Quantitative Analysis"])


class CashQuantResponse(BaseModel):
    """Response model for cash equity quant analysis."""
    symbol: str
    timestamp: str
    # ORB
    orb_high: float
    orb_low: float
    orb_breakout: str
    # RVOL
    rvol: float
    rvol_signal: str
    # VWAP
    vwap: float
    vwap_upper_1sd: float
    vwap_lower_1sd: float
    vwap_upper_2sd: float
    vwap_lower_2sd: float
    price_vs_vwap: str
    # Relative Strength
    rs_vs_nifty_5d: float
    rs_vs_sector_5d: float
    # Regime
    hurst_exponent: float
    regime: str
    zscore_20: float
    bb_width_percentile: float
    # ATR
    atr_14: float
    suggested_stop_loss: float
    position_size_lots: int
    # Delivery
    delivery_pct: float
    institutional_accumulation: bool


class OptionsQuantResponse(BaseModel):
    """Response model for options quant analysis."""
    underlying: str
    spot: float
    timestamp: str
    # ATM
    atm_strike: float
    # Greeks
    atm_ce_delta: float
    atm_ce_gamma: float
    atm_ce_theta: float
    atm_ce_vega: float
    atm_pe_delta: float
    atm_pe_gamma: float
    atm_pe_theta: float
    atm_pe_vega: float
    # IV
    atm_iv: float
    iv_percentile: float
    iv_rank: float
    # OI
    pcr_oi: float
    pcr_change_oi: float
    max_pain: float
    call_wall: float
    put_wall: float
    # GEX
    net_gex: float
    gex_regime: str
    # Recommendation
    recommended_structure: str
    structure_rationale: str


@router.get("/cash/{symbol}", response_model=CashQuantResponse)
async def get_cash_quant_report(
    symbol: str,
    db: Session = Depends(get_db),
) -> CashQuantResponse:
    """
    Get quantitative analysis report for a cash equity.
    
    Includes: ORB, RVOL, VWAP bands, Relative Strength, Hurst Exponent,
    Z-Score, Bollinger Width Percentile, ATR position sizing, Delivery %.
    """
    try:
        from app.services.quant_bots import get_cash_quant_bot
        from app.db.models_candles import Candle5m, CandleDaily
        
        symbol = symbol.upper()
        bot = get_cash_quant_bot()
        
        # Fetch 5m candles (today)
        candles_5m = (
            db.query(Candle5m)
            .filter(Candle5m.symbol == symbol)
            .order_by(Candle5m.timestamp.desc())
            .limit(100)
            .all()
        )
        candles_5m_data = [
            {
                "ts": c.timestamp.isoformat() if c.timestamp else None,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in reversed(candles_5m)
        ]
        
        # Fetch daily candles
        candles_daily = (
            db.query(CandleDaily)
            .filter(CandleDaily.symbol == symbol)
            .order_by(CandleDaily.date.desc())
            .limit(252)
            .all()
        )
        candles_daily_data = [
            {
                "date": str(c.date),
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in reversed(candles_daily)
        ]
        
        # Fetch Nifty candles for RS
        nifty_candles = (
            db.query(CandleDaily)
            .filter(CandleDaily.symbol == "NIFTY")
            .order_by(CandleDaily.date.desc())
            .limit(60)
            .all()
        )
        nifty_data = [
            {"close": c.close}
            for c in reversed(nifty_candles)
        ]
        
        # Get delivery data
        delivery_pct = 0.0
        try:
            from app.services.indian_market_data_service import get_delivery_data_sync
            delivery = get_delivery_data_sync(symbol)
            if delivery:
                delivery_pct = delivery.delivery_pct
        except Exception:
            pass
        
        # Run analysis
        report = bot.analyze(
            symbol=symbol,
            candles_5m=candles_5m_data,
            candles_daily=candles_daily_data,
            nifty_candles=nifty_data,
            delivery_pct=delivery_pct,
        )
        
        return CashQuantResponse(
            symbol=report.symbol,
            timestamp=report.timestamp.isoformat(),
            orb_high=report.orb_high,
            orb_low=report.orb_low,
            orb_breakout=report.orb_breakout,
            rvol=report.rvol,
            rvol_signal=report.rvol_signal,
            vwap=report.vwap,
            vwap_upper_1sd=report.vwap_upper_1sd,
            vwap_lower_1sd=report.vwap_lower_1sd,
            vwap_upper_2sd=report.vwap_upper_2sd,
            vwap_lower_2sd=report.vwap_lower_2sd,
            price_vs_vwap=report.price_vs_vwap,
            rs_vs_nifty_5d=report.rs_vs_nifty_5d,
            rs_vs_sector_5d=report.rs_vs_sector_5d,
            hurst_exponent=report.hurst_exponent,
            regime=report.regime,
            zscore_20=report.zscore_20,
            bb_width_percentile=report.bb_width_percentile,
            atr_14=report.atr_14,
            suggested_stop_loss=report.suggested_stop_loss,
            position_size_lots=report.position_size_lots,
            delivery_pct=report.delivery_pct,
            institutional_accumulation=report.institutional_accumulation,
        )
        
    except Exception as e:
        logger.exception("Cash quant analysis failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/{symbol}", response_model=OptionsQuantResponse)
async def get_options_quant_report(
    symbol: str,
    expiry: Optional[str] = Query(None, description="Expiry date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> OptionsQuantResponse:
    """
    Get quantitative analysis report for options.
    
    Includes: Greeks, IV Percentile/Rank, PCR, Max Pain, Call/Put Walls,
    Net GEX, GEX Regime, Recommended Structure.
    """
    try:
        from app.services.quant_bots import get_options_quant_bot
        from app.services.indian_market_data_service import get_nse_option_chain_sync
        from app.services.zerodha import KiteConnectService
        
        symbol = symbol.upper()
        bot = get_options_quant_bot()
        
        # Get spot price
        kite = KiteConnectService()
        quote = kite.get_full_quote(symbol)
        spot = float(quote.get("last_price", 0)) if quote else 0.0
        
        if spot <= 0:
            raise HTTPException(status_code=400, detail=f"Could not fetch spot price for {symbol}")
        
        # Get option chain from NSE
        chain_data = get_nse_option_chain_sync(symbol, expiry)
        if not chain_data:
            raise HTTPException(status_code=400, detail=f"Could not fetch option chain for {symbol}")
        
        # Convert to list of dicts
        option_chain = [
            {
                "strike": s.strike,
                "ce_oi": s.ce_oi,
                "ce_change_oi": s.ce_change_oi,
                "ce_volume": s.ce_volume,
                "ce_iv": s.ce_iv / 100 if s.ce_iv > 1 else s.ce_iv,  # Normalize IV
                "ce_ltp": s.ce_ltp,
                "pe_oi": s.pe_oi,
                "pe_change_oi": s.pe_change_oi,
                "pe_volume": s.pe_volume,
                "pe_iv": s.pe_iv / 100 if s.pe_iv > 1 else s.pe_iv,
                "pe_ltp": s.pe_ltp,
            }
            for s in chain_data.strikes
        ]
        
        # Parse expiry date
        if expiry:
            expiry_date = date.fromisoformat(expiry)
        else:
            # Use nearest expiry from chain
            from datetime import datetime
            try:
                expiry_date = datetime.strptime(chain_data.expiry, "%d-%b-%Y").date()
            except ValueError:
                expiry_date = date.today()
        
        # Get historical IV for IVP/IVR (from VIX as proxy)
        historical_iv = None
        try:
            from app.db.models_candles import CandleDaily
            vix_candles = (
                db.query(CandleDaily)
                .filter(CandleDaily.symbol == "INDIA VIX")
                .order_by(CandleDaily.date.desc())
                .limit(252)
                .all()
            )
            if vix_candles:
                historical_iv = [c.close / 100 for c in vix_candles if c.close]
        except Exception:
            pass
        
        # Run analysis
        report = bot.analyze(
            underlying=symbol,
            spot=spot,
            option_chain=option_chain,
            expiry_date=expiry_date,
            historical_iv=historical_iv,
        )
        
        return OptionsQuantResponse(
            underlying=report.underlying,
            spot=report.spot,
            timestamp=report.timestamp.isoformat(),
            atm_strike=report.atm_strike,
            atm_ce_delta=report.atm_ce_delta,
            atm_ce_gamma=report.atm_ce_gamma,
            atm_ce_theta=report.atm_ce_theta,
            atm_ce_vega=report.atm_ce_vega,
            atm_pe_delta=report.atm_pe_delta,
            atm_pe_gamma=report.atm_pe_gamma,
            atm_pe_theta=report.atm_pe_theta,
            atm_pe_vega=report.atm_pe_vega,
            atm_iv=report.atm_iv,
            iv_percentile=report.iv_percentile,
            iv_rank=report.iv_rank,
            pcr_oi=report.pcr_oi,
            pcr_change_oi=report.pcr_change_oi,
            max_pain=report.max_pain,
            call_wall=report.call_wall,
            put_wall=report.put_wall,
            net_gex=report.net_gex,
            gex_regime=report.gex_regime,
            recommended_structure=report.recommended_structure,
            structure_rationale=report.structure_rationale,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Options quant analysis failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-check")
async def check_trade_risk(
    symbol: str,
    delta: float = Query(0.0, description="Position delta"),
    is_intraday: bool = Query(True, description="Is intraday trade"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Run risk checks for a potential trade.
    
    Checks: Portfolio Greeks limits, VIX kill-switch, Time-of-day guard.
    """
    try:
        from app.core.risk.enhanced_guards import get_risk_guard_manager
        from app.services.zerodha import KiteConnectService
        
        manager = get_risk_guard_manager()
        
        # Get current VIX
        current_vix = None
        try:
            kite = KiteConnectService()
            vix_quote = kite.get_full_quote("INDIA VIX")
            if vix_quote:
                current_vix = float(vix_quote.get("last_price", 0))
        except Exception:
            pass
        
        result = manager.check_new_trade(
            db=db,
            symbol=symbol.upper(),
            delta=delta,
            current_vix=current_vix,
            is_intraday=is_intraday,
        )
        
        return {
            "symbol": symbol.upper(),
            "allowed": result["allowed"],
            "size_multiplier": result["size_multiplier"],
            "warnings": result["warnings"],
            "blocks": result["blocks"],
            "current_vix": current_vix,
        }
        
    except Exception as e:
        logger.exception("Risk check failed for %s", symbol)
        raise HTTPException(status_code=500, detail=str(e))
