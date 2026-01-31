from sqlalchemy import Column, Integer, String, Float, Date
from app.db.models import Base


class FinanceTransaction(Base):
    __tablename__ = "finance_transactions"

    id = Column(Integer, primary_key=True, index=True)

    tran_date = Column(Date, nullable=False)
    description = Column(String, nullable=False)

    debit = Column(Float, default=0)
    credit = Column(Float, default=0)
    balance = Column(Float, default=0)

    category = Column(String, default="Uncategorized")
    source = Column(String, default="AXIS")  # AXIS / HDFC / ICICI
