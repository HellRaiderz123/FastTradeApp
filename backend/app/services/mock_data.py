"""
Mock data generator for development/demo when Zerodha API is not configured
"""
import random
from typing import Dict, List, Any
from app.config.market_config import get_symbols, SECTOR_CLASSIFICATION

def generate_mock_quote(symbol: str, base_price: float = None) -> Dict[str, Any]:
    """
    Generate realistic mock quote data for a symbol
    
    NOTE: These are SIMULATED prices for demo/testing when Zerodha API is not configured.
    Base prices updated as of February 2026 estimates.
    """
    if base_price is None:
        # Base prices for common stocks (February 2026 estimates)
        base_prices = {
            'RELIANCE': 2850, 'TCS': 3950, 'HDFCBANK': 1650, 'INFY': 1820,
            'ICICIBANK': 1150, 'HINDUNILVR': 2650, 'ITC': 485, 'SBIN': 825,
            'BHARTIARTL': 1480, 'KOTAKBANK': 1880, 'LT': 3650, 'AXISBANK': 1150,
            'ASIANPAINT': 2950, 'MARUTI': 12850, 'SUNPHARMA': 1620, 'TITAN': 3580,
            'ULTRACEMCO': 10650, 'BAJFINANCE': 6850, 'WIPRO': 465, 'ONGC': 280,
            'NTPC': 385, 'POWERGRID': 325, 'M&M': 2790, 'TECHM': 1650,
            'TATAMOTORS': 1005, 'TATASTEEL': 165, 'ADANIENT': 2850, 'ADANIPORTS': 1450,
            'JSWSTEEL': 950, 'COALINDIA': 485, 'NESTLEIND': 2650, 'BAJAJFINSV': 1850,
            'DRREDDY': 5950, 'CIPLA': 1485, 'DIVISLAB': 5850, 'APOLLOHOSP': 6450,
            'HCLTECH': 1780, 'INDUSINDBK': 1485, 'SHREECEM': 26500, 'BRITANNIA': 4850,
            'HEROMOTOCO': 4650, 'EICHERMOT': 4950, 'GRASIM': 2485, 'HINDALCO': 650,
            'BPCL': 605, 'TATACONSUM': 1150, 'BAJAJ-AUTO': 9850, 'SBILIFE': 1650,
            'HDFCLIFE': 685, 'UPL': 565
        }
        base_price = base_prices.get(symbol, random.uniform(100, 2000))
    
    # Generate realistic price movements
    change_pct = random.uniform(-3, 3)
    ltp = base_price * (1 + change_pct / 100)
    prev_close = base_price
    volume = random.randint(100000, 5000000)
    avg_volume = volume / random.uniform(0.8, 1.5)
    
    ohlc = {
        'open': prev_close * (1 + random.uniform(-0.015, 0.015)),
        'high': max(ltp, prev_close) * (1 + random.uniform(0, 0.02)),
        'low': min(ltp, prev_close) * (1 - random.uniform(0, 0.02)),
        'close': prev_close
    }
    
    return {
        'last_price': round(ltp, 2),
        'ohlc': {k: round(v, 2) for k, v in ohlc.items()},
        'volume': volume,
        'average_price': round((ohlc['high'] + ohlc['low']) / 2, 2),
        'volume_traded': volume * ltp,
        'buy_quantity': random.randint(10000, 100000),
        'sell_quantity': random.randint(10000, 100000),
        'net_change': round(ltp - prev_close, 2)
    }


def generate_mock_top_movers(symbols: List[str], limit: int = 10) -> Dict[str, List[Dict]]:
    """Generate mock top movers data"""
    stocks_data = []
    
    for symbol in symbols[:limit * 3]:  # Get more than needed to sort
        quote = generate_mock_quote(symbol)
        ltp = quote['last_price']
        prev_close = quote['ohlc']['close']
        change = ltp - prev_close
        change_pct = (change / prev_close) * 100
        
        stocks_data.append({
            'symbol': symbol,
            'ltp': ltp,
            'change': round(change, 2),
            'change_percent': round(change_pct, 2),
            'volume': quote['volume'],
            'prev_close': prev_close
        })
    
    # Sort and categorize
    sorted_by_change = sorted(stocks_data, key=lambda x: x['change_percent'], reverse=True)
    sorted_by_volume = sorted(stocks_data, key=lambda x: x['volume'], reverse=True)
    
    return {
        'gainers': sorted_by_change[:limit],
        'losers': sorted_by_change[-limit:][::-1],
        'most_active': sorted_by_volume[:limit]
    }


def generate_mock_market_breadth(symbols: List[str]) -> Dict[str, Any]:
    """Generate mock market breadth data"""
    total = len(symbols)
    advancing = random.randint(int(total * 0.3), int(total * 0.7))
    declining = random.randint(int((total - advancing) * 0.5), total - advancing)
    unchanged = total - advancing - declining
    
    ad_ratio = advancing / declining if declining > 0 else advancing
    
    breadth_strength = 'Strong' if ad_ratio > 2 else 'Moderate' if ad_ratio > 1 else 'Weak'
    
    return {
        'advancing': advancing,
        'declining': declining,
        'unchanged': unchanged,
        'advance_decline_ratio': round(ad_ratio, 2),
        'new_highs_52w': random.randint(5, 20),
        'new_lows_52w': random.randint(2, 15),
        'breadth_strength': breadth_strength,
        'total_stocks': total
    }


def generate_mock_heatmap(symbols: List[str]) -> List[Dict]:
    """Generate mock heatmap data"""
    stocks = []
    
    for idx, symbol in enumerate(symbols):
        quote = generate_mock_quote(symbol)
        ltp = quote['last_price']
        prev_close = quote['ohlc']['close']
        change_pct = ((ltp - prev_close) / prev_close) * 100
        volume = quote['volume']
        avg_volume = volume / random.uniform(0.8, 1.5)
        
        stocks.append({
            'symbol': symbol,
            'ltp': ltp,
            'change_percent': round(change_pct, 2),
            'volume': volume,
            'volume_ratio': round(volume / avg_volume, 2),
            'market_cap_rank': idx + 1,
            'avg_price': quote['average_price']
        })
    
    return stocks


def generate_mock_sector_performance() -> List[Dict]:
    """Generate mock sector performance data"""
    sectors_data = []
    
    for sector_name, symbols in SECTOR_CLASSIFICATION.items():
        change_pct = random.uniform(-2, 2)
        strength = 'Strong' if change_pct > 1 else 'Moderate' if change_pct > 0 else 'Weak'
        
        # Pick top performers
        top_performers = random.sample(symbols, min(3, len(symbols)))
        
        sectors_data.append({
            'name': sector_name,
            'change_percent': round(change_pct, 2),
            'stocks_count': len(symbols),
            'top_performers': top_performers,
            'strength': strength
        })
    
    return sectors_data


def generate_mock_technicals(symbol: str) -> Dict[str, Any]:
    """Generate mock technical indicators for a symbol"""
    quote = generate_mock_quote(symbol)
    ltp = quote['last_price']
    
    rsi = random.uniform(30, 70)
    adx = random.uniform(15, 40)
    plus_di = random.uniform(15, 35)
    minus_di = random.uniform(15, 35)
    
    # Generate signal based on RSI and ADX
    if rsi > 60 and adx > 25:
        signal = 'BULLISH'
    elif rsi < 40 and adx > 25:
        signal = 'BEARISH'
    else:
        signal = 'NEUTRAL'
    
    patterns = []
    if rsi > 70:
        patterns.append('OVERBOUGHT')
    elif rsi < 30:
        patterns.append('OVERSOLD_REVERSAL')
    
    if adx > 25:
        patterns.append('STRONG_TREND' if plus_di > minus_di else 'STRONG_DOWNTREND')
    
    return {
        'symbol': symbol,
        'ltp': ltp,
        'indicators': {
            'rsi': round(rsi, 2),
            'macd': {
                'macd': round(random.uniform(-10, 10), 2),
                'signal': round(random.uniform(-10, 10), 2),
                'histogram': round(random.uniform(-5, 5), 2)
            },
            'bollinger': {
                'upper': round(ltp * 1.05, 2),
                'middle': round(ltp, 2),
                'lower': round(ltp * 0.95, 2),
                'percent_b': round(random.uniform(0, 1), 2),
                'bandwidth': round(random.uniform(5, 20), 2)
            },
            'adx': {
                'adx': round(adx, 2),
                'plus_di': round(plus_di, 2),
                'minus_di': round(minus_di, 2)
            },
            'volume': {
                'volume': quote['volume'],
                'volume_sma': quote['volume'] * random.uniform(0.8, 1.2),
                'obv': random.randint(1000000, 10000000)
            }
        },
        'swing_pattern': {
            'patterns': patterns,
            'strength': random.randint(50, 90)
        },
        'signal': signal
    }


def generate_mock_swing_opportunities(symbols: List[str], limit: int = 10) -> List[Dict]:
    """Generate mock swing trading opportunities"""
    opportunities = []
    
    strategies = ['momentum_breakout', 'oversold_bounce', 'trend_following', 'volume_surge']
    signals = ['BULLISH', 'BEARISH', 'NEUTRAL']
    
    for symbol in symbols[:limit]:
        quote = generate_mock_quote(symbol)
        ltp = quote['last_price']
        prev_close = quote['ohlc']['close']
        change_pct = ((ltp - prev_close) / prev_close) * 100
        
        rsi = random.uniform(30, 70)
        adx = random.uniform(20, 45)
        volume_spike = random.choice([True, False])
        
        patterns = []
        if rsi > 65:
            patterns.append('MOMENTUM')
        elif rsi < 35:
            patterns.append('OVERSOLD_REVERSAL')
        
        if adx > 25:
            patterns.append('STRONG_TREND')
        
        if volume_spike:
            patterns.append('VOLUME_BREAKOUT')
        
        opportunities.append({
            'symbol': symbol,
            'ltp': ltp,
            'change_percent': round(change_pct, 2),
            'signal': random.choice(signals),
            'strength': random.randint(60, 95),
            'patterns': patterns,
            'indicators': {
                'rsi': round(rsi, 2),
                'adx': round(adx, 2),
                'volume_spike': volume_spike
            },
            'volume': quote['volume'],
            'strategy_match': random.choice(strategies)
        })
    
    # Sort by strength
    opportunities.sort(key=lambda x: x['strength'], reverse=True)
    return opportunities
