#!/usr/bin/env python
import os
import json
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(".env")
load_dotenv(dotenv_path=env_path, override=True)

try:
    from app.core.broker.zerodha.client import get_kite_client
    kite = get_kite_client()
    
    margins = kite.margins()
    
    print("Full Margins Response:")
    print(json.dumps(margins, indent=2, default=str))
    
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
