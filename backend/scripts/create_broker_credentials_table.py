"""One-off: create broker_credentials table on Neon DB."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

NEON_URL = "postgresql+psycopg2://neondb_owner:npg_FE5ZcbnaoA6q@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
os.environ["DATABASE_URL"] = NEON_URL

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.db.session import engine, Base
from app.db.models_broker_credentials import BrokerCredentials  # noqa: F401

Base.metadata.create_all(bind=engine, tables=[BrokerCredentials.__table__])

from app.db.session import SessionLocal
db = SessionLocal()
count = db.query(BrokerCredentials).count()
db.close()
print(f"broker_credentials table created. existing rows: {count}")
