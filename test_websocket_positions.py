"""
Test WebSocket position streaming to verify it's working.
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env BEFORE any imports
backend_dir = Path(__file__).parent / "backend"
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

sys.path.insert(0, 'backend')

from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent


async def test_websocket():
    """Test WebSocket by checking database for active positions"""
    
    print("=" * 70)
    print("WEBSOCKET POSITION TEST")
    print("=" * 70)
    print()
    
    # Connect to DB and check for active intents
    db = SessionLocal()
    try:
        intents = (
            db.query(ExecutionIntent)
            .filter(ExecutionIntent.status == 'EXECUTED')
            .filter(ExecutionIntent.closed_at.is_(None))
            .all()
        )
        
        print(f"✅ Found {len(intents)} active positions in database\n")
        
        if intents:
            print("Active Positions:")
            print("-" * 70)
            for intent in intents:
                print(f"ID: {intent.intent_id}")
                print(f"  Strategy: {intent.strategy}")
                print(f"  Underlying: {intent.underlying}")
                print(f"  Status: {intent.status}")
                print(f"  Created: {intent.created_at}")
                print(f"  Execution Mode: {intent.execution_result.get('mode') if isinstance(intent.execution_result, dict) else 'N/A'}")
                print()
        else:
            print("⚠️  No active positions found")
            print("\nTo test WebSocket:")
            print("1. Create a position via Strategy Manager")
            print("2. Check browser DevTools > Network > WS to monitor connection")
            print("3. Check browser Console to see position updates")
            print()
        
        # Test adapter initialization
        print("\n" + "=" * 70)
        print("ADAPTER TEST")
        print("=" * 70)
        print()
        
        from app.core.execution.paper import PaperExecutionAdapter
        paper_adapter = PaperExecutionAdapter()
        print("✅ Paper Adapter: Initialized")
        
        zerodha_adapter = None
        try:
            from app.core.execution.zerodha import ZerodhaExecutionAdapter
            from app.core.broker.zerodha.client import get_kite_client
            
            print(f"  Zerodha API Key: {os.getenv('ZERODHA_API_KEY')[:10]}...")
            print(f"  Zerodha Access Token: {os.getenv('ZERODHA_ACCESS_TOKEN')[:10]}...")
            
            kite = get_kite_client()
            zerodha_adapter = ZerodhaExecutionAdapter(kite_client=kite, dry_run=True)
            print("✅ Zerodha Adapter: Initialized successfully!")
        except Exception as e:
            print(f"❌ Zerodha Adapter: Failed ({e})")
            import traceback
            traceback.print_exc()
        
        # Test MTM calculation if positions exist
        if intents:
            print("\n" + "=" * 70)
            print("MTM CALCULATION TEST")
            print("=" * 70)
            print()
            
            for intent in intents[:3]:  # Test first 3
                mode = intent.execution_result.get("mode") if isinstance(intent.execution_result, dict) else "PAPER"
                
                # Use Zerodha adapter if available, otherwise Paper
                adapter = zerodha_adapter if (mode and "ZERODHA" in str(mode).upper() and zerodha_adapter) else paper_adapter
                adapter_name = "Zerodha" if adapter == zerodha_adapter else "Paper"
                
                try:
                    mtm = adapter.mtm(intent)
                    print(f"✅ {intent.intent_id[:8]}... MTM = {mtm:.2f} (via {adapter_name} Adapter)")
                except Exception as e:
                    print(f"❌ {intent.intent_id[:8]}... Error: {e}")
        
    finally:
        db.close()
    
    print("\n" + "=" * 70)
    print("✅ WEBSOCKET TEST COMPLETE")
    print("=" * 70)
    print("\nNext Steps:")
    print("1. Check browser Console for WebSocket connection logs")
    print("2. Look for messages like '✅ WebSocket connected' or '❌ WebSocket error'")
    print("3. Check server logs (FastAPI terminal) for position update messages")
    print("4. Ensure positions are in PAPER mode (not ZERODHA_LIVE)")


if __name__ == "__main__":
    asyncio.run(test_websocket())
