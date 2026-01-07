"""Zerodha KiteConnect Service wrapper for market data"""

import logging
from typing import Optional, Dict, Any
from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import get_index_token

logger = logging.getLogger(__name__)


class KiteConnectService:
    """Wrapper service for Zerodha KiteConnect API"""
    
    def __init__(self):
        self.kite = None
        self._initialize()
    
    def _initialize(self):
        """Initialize KiteConnect client"""
        try:
            self.kite = get_kite_client()
            logger.info("KiteConnect client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize KiteConnect: {e}")
            self.kite = None
    
    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get quote data for a symbol
        
        Args:
            symbol: Symbol name (e.g., 'NIFTY', 'BANKNIFTY', or NSE symbol)
        
        Returns:
            Dict with keys: last_price, bid_price, ask_price, iv, open_interest
            Returns None if symbol not found or API fails
        """
        try:
            if not self.kite:
                self._initialize()
            
            if not self.kite:
                return None
            
            # If it's a simple symbol like 'NIFTY', convert to token
            try:
                token = get_index_token(symbol)
            except:
                # If it fails, assume it's already a full NSE symbol
                token = symbol
            
            # Get LTP
            data = self.kite.ltp([token])
            
            # Handle both token (int) and string key responses
            if token not in data and str(token) not in data:
                logger.warning(f"Token {token} not in response: {list(data.keys())}")
                return None
            
            price_data = data.get(token) or data.get(str(token))
            
            if not price_data:
                return None
            
            return {
                "last_price": price_data.get("last_price"),
                "bid_price": price_data.get("bid"),
                "ask_price": price_data.get("ask"),
                "iv": price_data.get("iv"),
                "open_interest": price_data.get("oi"),
                "volume": price_data.get("volume"),
            }
        
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    def get_ltp(self, symbol: str) -> Optional[float]:
        """
        Get Last Trading Price (LTP) for a symbol
        
        Args:
            symbol: Symbol name or token
        
        Returns:
            Last trading price or None
        """
        try:
            quote = self.get_quote(symbol)
            return quote.get("last_price") if quote else None
        except Exception as e:
            logger.error(f"Error fetching LTP for {symbol}: {e}")
            return None
    
    def get_option_chain(self, symbol: str, expiry: str) -> Optional[list]:
        """
        Get option chain data for a symbol and expiry
        
        Args:
            symbol: Underlying symbol
            expiry: Expiry date
        
        Returns:
            List of option data or None
        """
        try:
            if not self.kite:
                self._initialize()
            
            if not self.kite:
                return None
            
            # This would require building instrument tokens for options
            # For now, return None as this requires more complex lookup
            logger.info(f"Option chain requested for {symbol} {expiry}")
            return None
        
        except Exception as e:
            logger.error(f"Error fetching option chain: {e}")
            return None
