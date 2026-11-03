"""Sync data from Neon to local PostgreSQL."""
from sqlalchemy import create_engine, text

NEON_URL = "postgresql://neondb_owner:npg_FE5ZcbnaoA6q@ep-dry-cake-a11w18of.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
LOCAL_URL = "postgresql://fasttrade:your_new_password@db:5432/fasttrade"

TABLES_TO_SYNC = [
    "candles_daily",
    "candles_15m", 
    "candles_1h",
    "candles_5m",
    "auto_trader_log",
    "signal_outcomes",
    "execution_intents",
    "daily_capital",
    "condition_strategies",
    "strategy_runs",
    "backtest_results",
    "backtest_trades",
    "watchlists",
    "symbols",
    "vix_historic",
    "fii_dii_daily",
]

def sync_table(table_name: str, neon_engine, local_engine, batch_size: int = 5000):
    print(f"\n--- Syncing {table_name} ---")
    
    try:
        with neon_engine.connect() as neon_conn:
            count = neon_conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            print(f"  Neon has {count} rows")
            
            if count == 0:
                print("  Skipping (empty)")
                return
            
            result = neon_conn.execute(text(f"SELECT * FROM {table_name}"))
            columns = list(result.keys())
            rows = result.fetchall()
        
        with local_engine.connect() as local_conn:
            local_conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
            local_conn.commit()
            
            inserted = 0
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                data = [dict(zip(columns, row)) for row in batch]
                
                if data:
                    cols = ", ".join([f'"{c}"' for c in columns])
                    placeholders = ", ".join([f":{c}" for c in columns])
                    stmt = text(f'INSERT INTO {table_name} ({cols}) VALUES ({placeholders})')
                    local_conn.execute(stmt, data)
                    local_conn.commit()
                    inserted += len(batch)
                    print(f"  Inserted {inserted}/{count} rows")
            
            print(f"  Done: {inserted} rows synced")
    except Exception as e:
        print(f"  ERROR: {e}")

def main():
    print("Connecting to Neon...")
    neon_engine = create_engine(NEON_URL)
    
    print("Connecting to local PostgreSQL...")
    local_engine = create_engine(LOCAL_URL)
    
    for table in TABLES_TO_SYNC:
        sync_table(table, neon_engine, local_engine)
    
    print("\n=== Sync complete ===")

if __name__ == "__main__":
    main()
