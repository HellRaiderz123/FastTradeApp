"""One-off: create notification_settings table on Neon DB."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

NEON_URL = "postgresql+psycopg2://neondb_owner:npg_FE5ZcbnaoA6q@ep-dry-cake-a11w18of-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
os.environ["DATABASE_URL"] = NEON_URL

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from app.db.session import engine, Base
from app.db.models_notification_settings import NotificationSettings  # noqa: F401

Base.metadata.create_all(bind=engine, tables=[NotificationSettings.__table__])

from app.db.session import SessionLocal
db = SessionLocal()
count = db.query(NotificationSettings).count()
db.close()
print(f"notification_settings table created. existing rows: {count}")
