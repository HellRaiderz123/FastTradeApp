from sqlalchemy import Column, Boolean, Integer
from app.db.session import Base


class SystemControl(Base):
    __tablename__ = "system_control"

    id = Column(Integer, primary_key=True, default=1)
    trading_enabled = Column(Boolean, default=True)
