#!/usr/bin/env python
"""
Test script to verify margin calculation using Zerodha basket_order_margins API.

This simulates what happens when you execute a Bull Put spread in ZERODHA_DRY_RUN mode.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(".env")
load_dotenv(dotenv_path=env_path, override=True)

try:
    from app.core.broker.zerodha.client import get_kite_client
    
    kite = get_kite_client()
    
    print("=" * 80)
    print("🧪 TESTING MARGIN CALCULATION FOR BULL PUT SPREAD")
    print("=" * 80)
    print()
    
    # Example: Bull Put Spread - SELL 25900 PE, BUY 25700 PE
    # This is similar to your current position
    orders = [
        {
            "exchange": "NFO",
            "tradingsymbol": "NIFTY2501625900PE",  # Example symbol
            "transaction_type": "SELL",
            "quantity": 50,  # 1 lot
        },
        {
            "exchange": "NFO",
            "tradingsymbol": "NIFTY2501625700PE",  # Example symbol
            "transaction_type": "BUY",
            "quantity": 50,  # 1 lot
        },
    ]
    
    print("📋 Orders:")
    for i, order in enumerate(orders, 1):
        print(f"   Leg {i}: {order['transaction_type']} {order['quantity']} x {order['tradingsymbol']}")
    print()
    
    # Format for basket_order_margins API
    basket = []
    product = os.getenv("ZERODHA_PRODUCT", "NRML")
    
    for o in orders:
        basket.append({
            "exchange": o["exchange"],
            "tradingsymbol": o["tradingsymbol"],
            "transaction_type": o["transaction_type"],
            "variety": "regular",
            "product": product,
            "order_type": "MARKET",
            "quantity": int(o["quantity"]),
        })
    
    print(f"🔧 Configuration: PRODUCT={product}")
    print()
    print("🌐 Calling Zerodha basket_order_margins API...")
    
    # Get margin calculation from Zerodha
    margin_response = kite.basket_order_margins(basket)
    
    print()
    print("✅ Margin Response:")
    print("-" * 80)
    
    import json
    print(json.dumps(margin_response, indent=2, default=str))
    
    print()
    print("-" * 80)
    
    # Extract total margin
    if isinstance(margin_response, dict):
        final = margin_response.get("final", {})
        total_margin = final.get("total", 0.0)
        
        print()
        print("💰 MARGIN SUMMARY:")
        print(f"   Total Margin Required: ₹{total_margin:,.2f}")
        print()
        
        # Show per-order margins
        orders_data = margin_response.get("orders", [])
        if orders_data:
            print("📊 Per-Leg Breakdown:")
            for i, order_margin in enumerate(orders_data, 1):
                leg_margin = order_margin.get("total", 0.0)
                leg_type = order_margin.get("type", "")
                print(f"   Leg {i} ({orders[i-1]['transaction_type']} {orders[i-1]['tradingsymbol']})")
                print(f"   Margin: ₹{leg_margin:,.2f}")
                print()
        
        print("=" * 80)
        print("✅ Margin calculation successful!")
        print()
        print(f"When you execute this spread in ZERODHA_DRY_RUN or ZERODHA_LIVE:")
        print(f"  • Premium: Will show the credit collected (e.g., ₹3,227)")
        print(f"  • Margin: Will show ₹{total_margin:,.2f} (blocked capital)")
        print()
        print("The margin is the ACTUAL capital impact - this is what Zerodha locks.")
        print("=" * 80)
    
except Exception as e:
    import traceback
    print()
    print("❌ Error:")
    print(traceback.format_exc())
    print()
    print("Note: This test requires:")
    print("  1. Valid Zerodha credentials in .env")
    print("  2. Market to be open (or use valid expired symbols for testing)")
    print("  3. Correct tradingsymbols (format: NIFTYYYMMDDSTRIKETYPE)")
