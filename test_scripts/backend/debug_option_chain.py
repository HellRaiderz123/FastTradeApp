"""
Debug option chain filtering
"""
import os
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load credentials
os.environ["ZERODHA_API_KEY"] = "el4pv3dwria188j9"
os.environ["ZERODHA_ACCESS_TOKEN"] = "ZJpem2D1TftS74vXWFSI3cOuaa9uQOa8"
os.environ["EXECUTION_MODE"] = "ZERODHA_DRY_RUN"

from app.core.broker.zerodha.instruments import load_instruments
from app.core.market.expiry import get_next_weekly_expiry

logger.info("Loading instruments from Zerodha...")
instruments = load_instruments()
logger.info(f"✅ Loaded {len(instruments)} instruments")

# Check columns
logger.info(f"Columns: {instruments.columns.tolist()}")

# Check NIFTY instruments
nifty_inst = instruments[instruments["name"] == "NIFTY"]
logger.info(f"\n✅ NIFTY instruments: {len(nifty_inst)}")
logger.info(f"   Sample:\n{nifty_inst.head()}")

# Check expiry values
logger.info(f"\n📅 Unique expiry values in Zerodha:")
expiry_vals = instruments["expiry"].unique()
logger.info(f"   Count: {len(expiry_vals)}")
logger.info(f"   Sample: {sorted([str(e) for e in expiry_vals[:5]])}")

# Get next expiry
next_expiry = get_next_weekly_expiry()
logger.info(f"\n📅 Next weekly expiry from app: {next_expiry} (type: {type(next_expiry)})")
logger.info(f"   As Timestamp: {pd.Timestamp(next_expiry)}")

# Check NIFTY options for next expiry
nifty_opts = instruments[
    (instruments["name"] == "NIFTY")
    & (instruments["expiry"] == pd.Timestamp(next_expiry))
    & (instruments["segment"] == "NFO-OPT")
]
logger.info(f"\n✅ NIFTY options for next expiry: {len(nifty_opts)}")

# Try different approaches
logger.info(f"\n--- Trying different expiry formats ---")

# Approach 1: Exact match
nifty_opts_1 = instruments[
    (instruments["name"] == "NIFTY")
    & (instruments["segment"] == "NFO-OPT")
]
logger.info(f"Approach 1 (no expiry filter): {len(nifty_opts_1)} strikes")
if not nifty_opts_1.empty:
    logger.info(f"   Expiries in result: {nifty_opts_1['expiry'].unique()}")

# Approach 2: Convert both to string
nifty_opts_2 = instruments[
    (instruments["name"] == "NIFTY")
    & (instruments["expiry"].astype(str) == str(pd.Timestamp(next_expiry).date()))
    & (instruments["segment"] == "NFO-OPT")
]
logger.info(f"Approach 2 (string date match): {len(nifty_opts_2)} strikes")

# Approach 3: Check first few NIFTY options
logger.info(f"\n--- Sample NIFTY OPT records ---")
sample_opts = instruments[(instruments["name"] == "NIFTY") & (instruments["segment"] == "NFO-OPT")].head()
for idx, row in sample_opts.iterrows():
    logger.info(f"   {row['tradingsymbol']}: expiry={row['expiry']} (type: {type(row['expiry'])})")
