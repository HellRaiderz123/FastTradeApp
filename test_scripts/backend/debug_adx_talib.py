"""
Use TA-Lib style ADX calculation to match professional platforms
"""
import sys
sys.path.insert(0, "/app")

from app.db.session import SessionLocal
from app.db.models_candles import Candle15m
import pandas as pd
import numpy as np

db = SessionLocal()

# Fetch last 100 candles
candles = (
    db.query(Candle15m)
    .filter(Candle15m.symbol == "NIFTY")
    .order_by(Candle15m.timestamp.desc())
    .limit(100)
    .all()
)

# Build DataFrame
df = pd.DataFrame(
    [{
        "close": c.close,
        "high": c.high,
        "low": c.low,
        "open": c.open,
        "volume": c.volume,
    } for c in reversed(candles)]
)

print("=" * 80)
print("ADX CALCULATION: Professional TA-Lib Method")
print("=" * 80)
print()

high = df["high"].values
low = df["low"].values
close = df["close"].values

# Calculate True Range
tr = np.maximum(
    high[1:] - low[1:],
    np.maximum(
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1])
    )
)

# Up and Down moves
up_move = high[1:] - high[:-1]
down_move = low[:-1] - low[1:]

# +DM and -DM
plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

print("Calculating ADX with TA-Lib style smoothing...")
print()

# Wilder's smoothing for ATR
period = 14
atr = np.zeros(len(tr))
atr[period-1] = tr[:period].mean()
for i in range(period, len(tr)):
    atr[i] = (atr[i-1] * (period-1) + tr[i]) / period

# Wilder's smoothing for DMs
plus_dm_smooth = np.zeros(len(plus_dm))
minus_dm_smooth = np.zeros(len(minus_dm))
plus_dm_smooth[period-1] = plus_dm[:period].sum()
minus_dm_smooth[period-1] = minus_dm[:period].sum()

for i in range(period, len(plus_dm)):
    plus_dm_smooth[i] = plus_dm_smooth[i-1] - plus_dm_smooth[i-1]/period + plus_dm[i]
    minus_dm_smooth[i] = minus_dm_smooth[i-1] - minus_dm_smooth[i-1]/period + minus_dm[i]

# +DI and -DI
plus_di = (plus_dm_smooth / atr) * 100
minus_di = (minus_dm_smooth / atr) * 100

# DX
dx = np.abs(plus_di - minus_di) / (plus_di + minus_di) * 100

# ADX
adx = np.zeros(len(dx))
adx[2*period-2] = dx[period-1:2*period-1].mean()
for i in range(2*period-1, len(dx)):
    adx[i] = (adx[i-1] * (period-1) + dx[i]) / period

# Convert to DataFrame for easier viewing
result_df = pd.DataFrame({
    'close': close[1:],
    'tr': tr,
    'atr': atr,
    '+DM': plus_dm_smooth,
    '-DM': minus_dm_smooth,
    '+DI': plus_di,
    '-DI': minus_di,
    'DX': dx,
    'ADX': adx
})

print(f"Latest ADX (TA-Lib method): {adx[-1]:.2f}")
print()
print("Last 10 rows:")
print(result_df.tail(10).to_string())
print()

# Compare
zerodha_adx = 26.33
diff = abs(adx[-1] - zerodha_adx)

print("=" * 80)
print("COMPARISON")
print("-" * 80)
print(f"Zerodha ADX (Chart):      {zerodha_adx:.2f}")
print(f"TA-Lib ADX (Backend):     {adx[-1]:.2f}")
print(f"Difference:               {diff:.2f} points")
print()

if diff < 2.0:
    print("✅ EXCELLENT MATCH! Using correct method")
elif diff < 5.0:
    print("✅ GOOD MATCH! Minor rounding difference")
else:
    print("⚠️  Different results. Might be due to:")
    print("   - Different period for smoothing")
    print("   - Different underlying data")
    print("   - Zerodha using non-standard ADX variant")

db.close()
