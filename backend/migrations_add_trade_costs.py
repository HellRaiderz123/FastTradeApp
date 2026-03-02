"""
Migration script to add trade cost tracking tables
"""
from sqlalchemy import create_engine
from app.db.session import Base, DATABASE_URL
from app.db.models_trade_costs import TradeCost, BrokerageConfig

def run_migration():
    """Create the trade cost tracking tables"""
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    print("Creating trade cost tracking tables...")
    print("- trade_costs")
    print("- brokerage_config")
    
    # Create tables
    Base.metadata.create_all(bind=engine, tables=[
        TradeCost.__table__,
        BrokerageConfig.__table__,
    ])
    
    # Insert default Zerodha brokerage config
    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()
    
    existing_config = session.query(BrokerageConfig).filter(BrokerageConfig.is_active == 1).first()
    
    if not existing_config:
        print("\nInserting default Zerodha brokerage configuration...")
        default_config = BrokerageConfig(
            broker_name="Zerodha",
            plan_name="Default",
            equity_delivery_brokerage_pct=0.0,
            equity_delivery_brokerage_flat=0.0,
            equity_intraday_brokerage_pct=0.03,
            equity_intraday_brokerage_cap=20.0,
            fno_brokerage_flat=20.0,
            stt_equity_delivery=0.1,
            stt_equity_intraday=0.025,
            stt_fno_options=0.0625,
            stt_fno_futures=0.0125,
            nse_equity_charge=0.00297,
            nse_fno_charge=0.00173,
            gst_pct=18.0,
            sebi_charges_per_crore=10.0,
            stamp_duty_pct=0.003,
            stamp_duty_cap=300.0,
            is_active=1,
        )
        session.add(default_config)
        session.commit()
        print("✅ Default config created!")
    else:
        print("ℹ️  Brokerage config already exists")
    
    session.close()
    
    print("\n✅ Migration complete!")
    print("\nNew tables created:")
    print("  • trade_costs - Track all trade charges")
    print("  • brokerage_config - Brokerage rate configuration")
    print("\nDefault Zerodha brokerage rates:")
    print("  • Equity delivery: ₹0")
    print("  • Equity intraday: 0.03% or ₹20 (whichever is lower)")
    print("  • F&O: ₹20 flat per order")
    print("  • STT, GST, and other statutory charges configured")

if __name__ == "__main__":
    run_migration()
