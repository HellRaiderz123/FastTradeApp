from sqlalchemy import Column, Boolean
from app.db.session import Base


class SystemControl(Base):
    __tablename__ = "system_control"

    id = Column(Boolean, primary_key=True, default=True)
    trading_enabled = Column(Boolean, default=True)
