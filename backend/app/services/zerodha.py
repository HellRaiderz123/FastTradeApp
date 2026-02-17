"""Zerodha KiteConnect Service wrapper for market data"""

import logging
from typing import Optional, Dict, Any
from app.core.broker.zerodha.client import get_kite_client
from app.core.broker.zerodha.instruments import get_index_token
from app.core.rate_limiter import zerodha_limiter
from app.core.retry_handler import retry_with_backoff, is_transient_error

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
            # Check cache first
            cache_key = f"ltp:{symbol}"
            cached_data = zerodha_limiter.get_cache(cache_key)
            if cached_data:
                return cached_data
            
            # Rate limit before API call
            zerodha_limiter.acquire_for_quote()
            
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
            
            # Get LTP with retry logic for transient errors
            def fetch_ltp():
                return self.kite.ltp([token])
            
            data = retry_with_backoff(
                func=fetch_ltp,
                max_retries=3,
                base_delay=0.5,
                max_delay=3.0,
                backoff_factor=2.0
            )
            
            if data is None:
                logger.warning(f"Failed to fetch LTP for {symbol} after retries")
                return None
            
            # Handle both token (int) and string key responses
            if token not in data and str(token) not in data:
                logger.warning(f"Token {token} not in response: {list(data.keys())}")
                return None
            
            price_data = data.get(token) or data.get(str(token))
            
            if not price_data:
                return None
            
            result = {
                "last_price": price_data.get("last_price"),
                "bid_price": price_data.get("bid"),
                "ask_price": price_data.get("ask"),
                "iv": price_data.get("iv"),
                "open_interest": price_data.get("oi"),
                "volume": price_data.get("volume"),
            }
            
            # Cache the result
            zerodha_limiter.set_cache(cache_key, result, ttl=1)  # Shorter TTL for LTP
            
            return result
        
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    def get_full_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get full quote data including OHLC for a symbol
        
        Args:
            symbol: Symbol name (e.g., 'NIFTY', 'BANKNIFTY', 'INDIA VIX', 'RELIANCE', 'TCS')
        
        Returns:
            Dict with keys: last_price, ohlc, volume, change, etc.
            Returns None if symbol not found or API fails
        """
        try:
            # Check cache first
            cache_key = f"quote:{symbol}"
            cached_data = zerodha_limiter.get_cache(cache_key)
            if cached_data:
                logger.debug(f"Cache hit: {symbol}")
                return cached_data
            
            # Rate limit before API call
            zerodha_limiter.acquire_for_quote()
            
            if not self.kite:
                self._initialize()
            
            if not self.kite:
                return None
            
            # Normalize symbol for index lookup (remove spaces, uppercase)
            normalized_symbol = symbol.replace(" ", "").upper()
            
            # Map common variations to standard index names
            symbol_map = {
                "NIFTY50": "NIFTY",
                "NIFTY-50": "NIFTY",
                "INDIANVIX": "NIFTYVIX",
                "INDIAVIX": "NIFTYVIX",
                "INDIA-VIX": "NIFTYVIX",
                "BANKNIFTY": "BANKNIFTY",
                "BANK-NIFTY": "BANKNIFTY",
                "FINNIFTY": "FINNIFTY",
                "FIN-NIFTY": "FINNIFTY",
            }
            
            lookup_symbol = symbol_map.get(normalized_symbol, normalized_symbol)
            
            # Check if it's an index (needs instrument token, not NSE:SYMBOL)
            try:
                token = get_index_token(lookup_symbol)
                instrument = token  # Use token directly for indices
                logger.debug(f"Using token {token} for index {symbol} (normalized: {lookup_symbol})")
            except (KeyError, Exception):
                # Not an index, use NSE:SYMBOL format for regular stocks
                instrument = f"NSE:{symbol}"
                logger.debug(f"Using NSE format for stock: {instrument}")
            
            # Get full quote (includes OHLC) with retry logic for transient errors
            def fetch_full_quote():
                return self.kite.quote([instrument])
            
            data = retry_with_backoff(
                func=fetch_full_quote,
                max_retries=3,
                base_delay=0.5,
                max_delay=3.0,
                backoff_factor=2.0
            )
            
            if data is None:
                logger.warning(f"Failed to fetch full quote for {symbol} after retries")
                return None
            
            # Response key depends on whether we used token or exchange:symbol
            if instrument not in data:
                # Try alternate key formats
                if isinstance(instrument, int) and str(instrument) in data:
                    quote_data = data[str(instrument)]
                else:
                    logger.warning(f"Symbol {symbol} (instrument: {instrument}) not in response. Keys: {list(data.keys())}")
                    return None
            else:
                quote_data = data[instrument]
            
            result = {
                "last_price": quote_data.get("last_price"),
                "ohlc": quote_data.get("ohlc", {}),
                "volume": quote_data.get("volume", 0),
                "buy_quantity": quote_data.get("buy_quantity", 0),
                "sell_quantity": quote_data.get("sell_quantity", 0),
                "timestamp": quote_data.get("timestamp"),
                "depth": quote_data.get("depth"),  # Order book: {buy: [...], sell: [...]}
                "oi": quote_data.get("oi", 0),
                "lower_circuit_limit": quote_data.get("lower_circuit_limit"),
                "upper_circuit_limit": quote_data.get("upper_circuit_limit"),
                "last_quantity": quote_data.get("last_quantity", 0),
                "average_price": quote_data.get("average_price", 0),
            }
            
            # Cache the result
            zerodha_limiter.set_cache(cache_key, result, ttl=2)
            
            return result
        
        except Exception as e:
            logger.error(f"Error fetching full quote for {symbol}: {e}")
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
    
    def get_bulk_quotes(self, symbols: list) -> Optional[Dict[str, Any]]:
        """
        Get quotes for multiple symbols at once
        
        Args:
            symbols: List of symbols/instruments:
                     - For stocks: 'RELIANCE', 'TCS', 'INFY'
                     - For options: 'NFO:NIFTY24FEB26000CE'
                     - For indices: 'NIFTY', 'BANKNIFTY', 'INDIA VIX'
        
        Returns:
            Dict with instrument keys containing quote data
            Returns None if API fails or not initialized
        """
        try:
            # Check cache first
            cache_key = f"bulk_quotes:{','.join(sorted(symbols))}"
            cached_data = zerodha_limiter.get_cache(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for bulk quotes: {len(symbols)} symbols")
                return cached_data
            
            # Rate limit before API call
            zerodha_limiter.acquire_for_quote(cost=1)  # Bulk request = 1 token
            
            if not self.kite:
                self._initialize()
            
            if not self.kite:
                return None
            
            # Symbol normalization map (same as get_full_quote)
            symbol_map = {
                "NIFTY50": "NIFTY",
                "NIFTY-50": "NIFTY",
                "INDIANVIX": "NIFTYVIX",
                "INDIAVIX": "NIFTYVIX",
                "INDIA-VIX": "NIFTYVIX",
                "BANKNIFTY": "BANKNIFTY",
                "BANK-NIFTY": "BANKNIFTY",
                "FINNIFTY": "FINNIFTY",
                "FIN-NIFTY": "FINNIFTY",
            }
            
            # Format instruments properly
            instruments = []
            for symbol in symbols:
                # If already has exchange prefix (NFO:, NSE:, etc.), use as-is
                if ':' in symbol:
                    instruments.append(symbol)
                else:
                    # Normalize symbol for index lookup
                    normalized_symbol = symbol.replace(" ", "").upper()
                    lookup_symbol = symbol_map.get(normalized_symbol, normalized_symbol)
                    
                    # Check if it's an index (needs token)
                    try:
                        token = get_index_token(lookup_symbol)
                        instruments.append(token)
                        logger.debug(f"Using token {token} for index {symbol} (normalized: {lookup_symbol})")
                    except (KeyError, Exception):
                        # Regular stock - use NSE:SYMBOL
                        instruments.append(f"NSE:{symbol}")
            
            # Get quotes for all symbols with retry logic for transient errors
            logger.debug(f"Fetching bulk quotes for {len(instruments)} instruments with retry logic")
            
            def fetch_quotes():
                """Inner function to fetch quotes - will be retried on transient errors"""
                return self.kite.quote(instruments)
            
            # Retry with exponential backoff on transient errors (503, timeout, etc.)
            data = retry_with_backoff(
                func=fetch_quotes,
                max_retries=3,
                base_delay=1.0,
                max_delay=5.0,
                backoff_factor=2.0
            )
            
            if data is None:
                logger.error(f"Failed to fetch bulk quotes after retries for {len(instruments)} symbols")
                return None
            
            # Cache the result
            zerodha_limiter.set_cache(cache_key, data, ttl=2)
            
            return data
        
        except Exception as e:
            logger.error(f"Error fetching bulk quotes: {e}")
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
