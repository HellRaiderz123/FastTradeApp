#!/usr/bin/env python3
"""
Quick Start Guide for Daily Capital Tracking
Run this script for step-by-step setup
"""

import subprocess
import os
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'='*60}")
    print(f"📍 {description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(cmd, shell=True, cwd='backend')
        if result.returncode == 0:
            print(f"✅ {description} - SUCCESS")
            return True
        else:
            print(f"❌ {description} - FAILED")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🚀 DAILY CAPITAL TRACKING - SETUP GUIDE")
    print("="*60)
    
    # Check backend directory
    if not Path('backend').exists():
        print("❌ Error: Not in FastTradeApp root directory")
        sys.exit(1)
    
    # Step 1: Create table
    print("\n📋 Step 1: Creating database table...")
    if run_command("python migrate_daily_capital.py", "Database Migration"):
        print("✅ Table 'daily_capital' created successfully")
    else:
        print("⚠️  Migration may have failed - check backend logs")
        return False
    
    # Step 2: Verify table
    print("\n🔍 Step 2: Verifying table creation...")
    print("Run this to verify:")
    print("  backend> sqlite3 fastrade.db")
    print("  sqlite> SELECT name FROM sqlite_master WHERE type='table' AND name='daily_capital';")
    
    # Step 3: Test endpoints
    print("\n🧪 Step 3: Testing API endpoints...")
    print("\nTest these endpoints:")
    print("  1. GET http://localhost:8000/account/profile")
    print("     → Creates first day's capital record")
    print("")
    print("  2. GET http://localhost:8000/account/daily-capital?days=30")
    print("     → Retrieves capital history")
    print("")
    print("  3. POST http://localhost:8000/account/daily-capital")
    print("     → Manually records capital for a day")
    
    # Step 4: Frontend update
    print("\n🎨 Step 4: Frontend rebuild...")
    print("Automatic - Dashboard will load new data on page refresh")
    
    print("\n" + "="*60)
    print("✅ SETUP COMPLETE!")
    print("="*60)
    print("\nNext Steps:")
    print("1. Restart backend: uvicorn app.main:app --reload")
    print("2. Refresh frontend")
    print("3. Call GET /account/profile to create first capital record")
    print("4. View Portfolio Growth chart on Dashboard")
    print("\nDocumentation: DAILY_CAPITAL_TRACKING.md")

if __name__ == '__main__':
    main()
