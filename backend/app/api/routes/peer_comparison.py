"""
Peer Comparison API
Get fundamental metrics and peer analysis for comparison
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Dict, Any
import logging

from app.db.session import SessionLocal
from app.db.models import Symbol
from app.services.zerodha import KiteConnectService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/peer-comparison", tags=["peer-comparison"])

kite_service = KiteConnectService()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class PeerMetrics:
    """Container for peer metrics"""
    def __init__(self, symbol: str, name: str, sector: str):
        self.symbol = symbol
        self.name = name
        self.sector = sector
        self.ltp = 0.0
        self.change = 0.0
        self.change_percent = 0.0
        self.pe_ratio = None
        self.pb_ratio = None
        self.roe = None
        self.dividend_yield = None
        self.rsi = None
        self.market_cap = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "sector": self.sector,
            "ltp": self.ltp,
            "change": self.change,
            "change_percent": self.change_percent,
            "pe_ratio": self.pe_ratio,
            "pb_ratio": self.pb_ratio,
            "roe": self.roe,
            "dividend_yield": self.dividend_yield,
            "rsi": self.rsi,
            "market_cap": self.market_cap,
        }


@router.get("/stock/{symbol}")
async def get_peer_comparison(symbol: str, db: Session = Depends(get_db)):
    """
    Get peer comparison data for a specific stock
    
    Returns:
        {
            "stock": {
                "symbol": "HDFCBANK",
                "name": "HDFC Bank",
                "sector": "Finance",
                "ltp": 1850.5,
                "change": 25.5,
                "change_percent": 1.4,
                "pe_ratio": 18.5,
                "pb_ratio": 2.1,
                "roe": 14.2,
                "dividend_yield": 1.2,
                "rsi": 65.2,
                "market_cap": 450000.0
            },
            "peers": [
                {
                    "symbol": "ICICIBANK",
                    "name": "ICICI Bank",
                    ...
                },
                ...
            ],
            "sector_avg": {
                "pe_ratio": 17.6,
                "pb_ratio": 2.2,
                "roe": 14.5,
                "dividend_yield": 1.3,
                "rsi": 62.1
            }
        }
    """
    
    try:
        # Find the target stock
        stock = db.query(Symbol).filter(
            func.upper(Symbol.ticker) == symbol.upper()
        ).first()
        
        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
        
        sector = stock.sector or "Unknown"
        
        # Find all peers in same sector
        peers = db.query(Symbol).filter(
            Symbol.sector == sector,
            Symbol.is_active == True,
            Symbol.asset_type == "STOCK"
        ).all()
        
        if not peers:
            peers = [stock]
        
        # Build metrics for main stock and peers
        metrics_list = []
        
        for peer in peers:
            metrics = PeerMetrics(peer.ticker, peer.name, peer.sector or "Unknown")
            metrics.pe_ratio = peer.pe_ratio
            metrics.pb_ratio = peer.pb_ratio
            metrics.roe = peer.roe
            metrics.dividend_yield = peer.dividend_yield
            metrics.market_cap = peer.market_cap
            
            # Fetch live price
            try:
                quote = kite_service.get_full_quote(peer.ticker)
                if quote:
                    metrics.ltp = quote.get("last_price", 0.0)
                    ohlc = quote.get("ohlc", {})
                    prev_close = ohlc.get("close", metrics.ltp)
                    metrics.change = metrics.ltp - prev_close
                    metrics.change_percent = (metrics.change / prev_close * 100) if prev_close else 0
                    
                    # Try to calculate RSI (simplified - would need more data normally)
                    # For now, use a placeholder based on the quote
                    metrics.rsi = 50 + (metrics.change_percent * 2)  # Simple proxy
                    metrics.rsi = max(0, min(100, metrics.rsi))  # Clamp to 0-100
            except Exception as e:
                logger.warning(f"Failed to get quote for {peer.ticker}: {e}")
            
            metrics_list.append(metrics)
        
        # Calculate sector averages
        sector_avg = {
            "pe_ratio": None,
            "pb_ratio": None,
            "roe": None,
            "dividend_yield": None,
            "rsi": None,
        }
        
        # Only average metrics that exist
        pe_values = [m.pe_ratio for m in metrics_list if m.pe_ratio is not None]
        if pe_values:
            sector_avg["pe_ratio"] = sum(pe_values) / len(pe_values)
        
        pb_values = [m.pb_ratio for m in metrics_list if m.pb_ratio is not None]
        if pb_values:
            sector_avg["pb_ratio"] = sum(pb_values) / len(pb_values)
        
        roe_values = [m.roe for m in metrics_list if m.roe is not None]
        if roe_values:
            sector_avg["roe"] = sum(roe_values) / len(roe_values)
        
        div_values = [m.dividend_yield for m in metrics_list if m.dividend_yield is not None]
        if div_values:
            sector_avg["dividend_yield"] = sum(div_values) / len(div_values)
        
        rsi_values = [m.rsi for m in metrics_list if m.rsi is not None]
        if rsi_values:
            sector_avg["rsi"] = sum(rsi_values) / len(rsi_values)
        
        # Find main stock metrics
        main_stock_metrics = next((m for m in metrics_list if m.symbol.upper() == symbol.upper()), None)
        if not main_stock_metrics:
            main_stock_metrics = metrics_list[0]
        
        # Sort peers by market cap (largest first), but keep main stock at top
        peer_list = [m for m in metrics_list if m.symbol.upper() != symbol.upper()]
        peer_list.sort(key=lambda x: x.market_cap or 0, reverse=True)
        
        return {
            "stock": main_stock_metrics.to_dict(),
            "peers": [p.to_dict() for p in peer_list],
            "sector": sector,
            "sector_avg": sector_avg,
            "peer_count": len(peer_list)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in peer comparison: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching peer comparison: {str(e)}")


@router.get("/sectors")
async def get_sectors_list(db: Session = Depends(get_db)):
    """
    Get list of all sectors with stock counts
    
    Returns:
        {
            "sectors": [
                {"name": "Finance", "count": 8, "stocks": ["HDFCBANK", "ICICIBANK", ...]},
                ...
            ]
        }
    """
    
    try:
        # Get all unique sectors
        sector_query = db.query(Symbol.sector, func.count(Symbol.id).label('count')).filter(
            Symbol.is_active == True,
            Symbol.asset_type == "STOCK"
        ).group_by(Symbol.sector).order_by(func.count(Symbol.id).desc()).all()
        
        sectors = []
        for sector_name, count in sector_query:
            if sector_name:
                stocks = db.query(Symbol.ticker).filter(
                    Symbol.sector == sector_name,
                    Symbol.is_active == True
                ).all()
                
                sectors.append({
                    "name": sector_name,
                    "count": count,
                    "stocks": [s[0] for s in stocks]
                })
        
        return {"sectors": sectors}
    except Exception as e:
        logger.error(f"Error fetching sectors: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching sectors: {str(e)}")
