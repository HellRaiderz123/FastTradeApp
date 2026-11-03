"""Sync remaining tables with proper JSON handling."""
import json
from sqlalchemy import create_engine, text

NEON_URL = "postgresql://neondb_owner:npg_FE5ZcbnaoA6q@ep-dry-cake-a11w18of.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
LOCAL_URL = "postgresql://fasttrade:your_new_password@db:5432/fasttrade"

# Tables with JSON columns that need serialization
JSON_COLUMNS = {
    "strategy_configs": ["parameters"],
    "notifications": ["metadata"],
}

TABLES_TO_SYNC = [
    "strategy_configs",
    "notifications",
]

def sync_table(table_name: str, neon_engine, local_engine, batch_size: int = 500):
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
        
        # Convert rows to dicts and handle JSON columns
        json_cols = JSON_COLUMNS.get(table_name, [])
        data_list = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            # Serialize JSON columns
            for col in json_cols:
                if col in row_dict and row_dict[col] is not None:
                    if isinstance(row_dict[col], (dict, list)):
                        row_dict[col] = json.dumps(row_dict[col])
            data_list.append(row_dict)
        
        with local_engine.connect() as local_conn:
            local_conn.execute(text(f"TRUNCATE TABLE {table_name} CASCADE"))
            local_conn.commit()
            
            inserted = 0
            for i in range(0, len(data_list), batch_size):
                batch = data_list[i:i+batch_size]
                
                if batch:
                    cols = ", ".join([f'"{c}"' for c in columns])
                    placeholders = ", ".join([f":{c}" for c in columns])
                    stmt = text(f'INSERT INTO {table_name} ({cols}) VALUES ({placeholders})')
                    local_conn.execute(stmt, batch)
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
