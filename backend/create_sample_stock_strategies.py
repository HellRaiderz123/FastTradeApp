#!/usr/bin/env python3
"""
Create Sample Stock Strategies
This script creates example stock strategies for NIFTY 50 stocks via the API.
"""

import requests
import json
from typing import Dict, Any

# API Configuration
API_BASE = "http://localhost:8000/api"
STRATEGIES_ENDPOINT = f"{API_BASE}/strategies"


def create_strategy(
    name: str,
    description: str,
    strategy_type: str,
    underlying: str,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a single strategy configuration"""
    payload = {
        "name": name,
        "description": description,
        "strategy_type": strategy_type,
        "underlying": underlying,
        "parameters": parameters
    }
    
    try:
        response = requests.post(STRATEGIES_ENDPOINT, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"✅ Created: {name}")
        return result
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            print(f"⚠️  Already exists: {name}")
        else:
            print(f"❌ Failed to create {name}: {e}")
        return {}
    except Exception as e:
        print(f"❌ Error creating {name}: {e}")
        return {}


def main():
    """Create sample stock strategies"""
    print("🚀 Creating sample stock strategies...\n")
    
    strategies = [
        {
            "name": "RELIANCE Momentum 15m",
            "description": "Momentum-based strategy for RELIANCE using RSI and moving averages",
            "strategy_type": "stock_momentum_15m",
            "underlying": "RELIANCE",
            "parameters": {
                "min_confidence": 65,
                "rsi_threshold": 50,
                "risk_percent": 2.0,
                "reward_multiple": 1.5
            }
        },
        {
            "name": "TCS Trend Following 15m",
            "description": "Trend following strategy for TCS using ADX and directional indicators",
            "strategy_type": "stock_trend_following_15m",
            "underlying": "TCS",
            "parameters": {
                "min_confidence": 70,
                "adx_threshold": 25,
                "risk_percent": 2.5,
                "reward_multiple": 2.0
            }
        },
        {
            "name": "INFY Mean Reversion 15m",
            "description": "Mean reversion strategy for INFY using Bollinger Bands",
            "strategy_type": "stock_mean_reversion_15m",
            "underlying": "INFY",
            "parameters": {
                "min_confidence": 60,
                "bb_period": 20,
                "bb_std": 2.0,
                "risk_percent": 1.5,
                "reward_multiple": 2.0
            }
        },
        {
            "name": "Universal Stock Momentum",
            "description": "Generic momentum strategy that works for any NIFTY 50 stock",
            "strategy_type": "stock_momentum_15m",
            "underlying": "",  # Empty = works for all stocks
            "parameters": {
                "min_confidence": 70,
                "rsi_threshold": 55,
                "risk_percent": 2.0,
                "reward_multiple": 1.5
            }
        },
        {
            "name": "ICICIBANK Aggressive Momentum",
            "description": "Higher risk momentum strategy for ICICIBANK",
            "strategy_type": "stock_momentum_15m",
            "underlying": "ICICIBANK",
            "parameters": {
                "min_confidence": 60,
                "rsi_threshold": 50,
                "risk_percent": 3.0,
                "reward_multiple": 2.0
            }
        },
        {
            "name": "SBIN Conservative Trend",
            "description": "Conservative trend following for SBIN with tight risk management",
            "strategy_type": "stock_trend_following_15m",
            "underlying": "SBIN",
            "parameters": {
                "min_confidence": 75,
                "adx_threshold": 30,
                "risk_percent": 1.5,
                "reward_multiple": 2.5
            }
        },
        {
            "name": "HDFCBANK Balanced Momentum",
            "description": "Balanced momentum strategy for HDFCBANK",
            "strategy_type": "stock_momentum_15m",
            "underlying": "HDFCBANK",
            "parameters": {
                "min_confidence": 68,
                "rsi_threshold": 52,
                "risk_percent": 2.2,
                "reward_multiple": 1.8
            }
        },
        {
            "name": "WIPRO Mean Reversion",
            "description": "Mean reversion strategy for WIPRO using Bollinger Bands",
            "strategy_type": "stock_mean_reversion_15m",
            "underlying": "WIPRO",
            "parameters": {
                "min_confidence": 65,
                "bb_period": 20,
                "bb_std": 2.0,
                "risk_percent": 2.0,
                "reward_multiple": 1.8
            }
        },
        {
            "name": "HCLTECH Quick Momentum",
            "description": "Fast-moving momentum strategy for HCLTECH",
            "strategy_type": "stock_momentum_15m",
            "underlying": "HCLTECH",
            "parameters": {
                "min_confidence": 55,
                "rsi_threshold": 48,
                "risk_percent": 1.8,
                "reward_multiple": 1.5
            }
        },
        {
            "name": "KOTAKBANK Trend Rider",
            "description": "Aggressive trend following for KOTAKBANK",
            "strategy_type": "stock_trend_following_15m",
            "underlying": "KOTAKBANK",
            "parameters": {
                "min_confidence": 72,
                "adx_threshold": 28,
                "risk_percent": 2.8,
                "reward_multiple": 2.2
            }
        }
    ]
    
    # Create each strategy
    created = 0
    for strategy in strategies:
        result = create_strategy(**strategy)
        if result:
            created += 1
    
    print(f"\n✨ Summary: Created {created}/{len(strategies)} strategies")
    
    # List all stock strategies
    print("\n📋 Fetching all stock strategies...\n")
    try:
        response = requests.get(STRATEGIES_ENDPOINT)
        response.raise_for_status()
        all_strategies = response.json()
        
        # Filter stock strategies
        stock_strategies = [
            s for s in all_strategies 
            if s['strategy_type'].startswith('stock_')
        ]
        
        if stock_strategies:
            print(f"Found {len(stock_strategies)} stock strategies:\n")
            for s in stock_strategies:
                status = "🟢 Enabled" if s.get('enabled') else "🔴 Disabled"
                underlying = s.get('underlying') or "All Stocks"
                print(f"  {status} | {s['name']}")
                print(f"           Type: {s['strategy_type']}")
                print(f"           Underlying: {underlying}")
                print()
        else:
            print("No stock strategies found.")
            
    except Exception as e:
        print(f"❌ Failed to list strategies: {e}")


if __name__ == "__main__":
    main()
