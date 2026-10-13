import sqlite3, json

db = sqlite3.connect("trading.db")
cur = db.cursor()

cur.execute("SELECT id, name, entry_conditions FROM condition_strategies")
rows = cur.fetchall()
print("All strategies:")
for r in rows:
    print(f"  id={r[0]}  name={r[1]}")

# Delete any strategy whose entry_conditions contain indicator=Close
to_delete = []
for r in rows:
    try:
        conds = json.loads(r[2]) if isinstance(r[2], str) else (r[2] or [])
        if any(c.get("indicator", "").lower() == "close" for c in conds):
            to_delete.append((r[0], r[1]))
    except Exception:
        pass

print("\nStrategies with indicator=Close (will be deleted):")
for sid, sname in to_delete:
    print(f"  id={sid}  name={sname}")
    cur.execute("DELETE FROM condition_strategies WHERE id=?", (sid,))
    cur.execute("DELETE FROM condition_strategy_backtests WHERE strategy_id=?", (sid,))

db.commit()
db.close()
print("\nDone.")
