"""
Create notification table
"""

from app.db.session import engine
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, MetaData, Table
from app.core.utils.time import now_ist

metadata = MetaData()

notifications = Table(
    'notifications',
    metadata,
    Column('id', Integer, primary_key=True, index=True),
    Column('type', String, index=True),
    Column('title', String),
    Column('message', String),
    Column('priority', String),
    Column('metadata', JSON),
    Column('read', Boolean, default=False, index=True),
    Column('created_at', DateTime(timezone=True), default=now_ist, index=True)
)

def upgrade():
    """Create notifications table"""
    print("Creating notifications table...")
    metadata.create_all(bind=engine)
    print("✅ Notifications table created successfully")

def downgrade():
    """Drop notifications table"""
    print("Dropping notifications table...")
    metadata.drop_all(bind=engine)
    print("✅ Notifications table dropped")

if __name__ == "__main__":
    upgrade()
