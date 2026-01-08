import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.db.session import engine

with engine.connect() as conn:
    result = conn.execute(text('PRAGMA table_info(execution_intents)'))
    for r in result:
        print(f"{r[1]}: {r[2]}")
