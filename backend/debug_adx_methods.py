"""
Compare two ADX calculation methods:
1. Current: Simple rolling average (what backend uses)
2. Wilder's: Exponential smoothing (what Zerodha likely uses)
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
print("ADX CALCULATION: COMPARING METHODS")
print("=" * 80)
print()

high = df["high"]
low = df["low"]
close = df["close"]
period = 14

# True Range
tr1 = high - low
tr2 = abs(high - close.shift())
tr3 = abs(low - close.shift())
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

# =====================================================
# METHOD 1: Simple Rolling Average (Current Backend)
# =====================================================
print("METHOD 1: Simple Rolling Average (Current Backend)")
print("-" * 80)

atr_simple = tr.rolling(period).mean()

up = high.diff()
down = low.diff() * -1
pos_dm = up.copy()
pos_dm[up <= down] = 0
pos_dm[up < 0] = 0
neg_dm = down.copy()
neg_dm[down <= up] = 0
neg_dm[down < 0] = 0

pos_di_simple = (pos_dm.rolling(period).sum() / atr_simple) * 100
neg_di_simple = (neg_dm.rolling(period).sum() / atr_simple) * 100

di_diff_simple = abs(pos_di_simple - neg_di_simple)
di_sum_simple = pos_di_simple + neg_di_simple
di_ratio_simple = di_diff_simple / di_sum_simple
adx_simple = di_ratio_simple.rolling(period).mean() * 100

print(f"ADX (latest): {adx_simple.iloc[-1]:.2f}")
print(f"ADX (last 5): {adx_simple.tail(5).values}")
print()

# =====================================================
# METHOD 2: Wilder's Smoothing (True ADX)
# =====================================================
print("METHOD 2: Wilder's Smoothing (True ADX - Professional Standard)")
print("-" * 80)

# Wilder's ATR
atr_wilder = pd.Series(index=df.index, dtype=float)
atr_wilder.iloc[0] = tr.iloc[0:period].mean()
for i in range(period, len(df)):
    atr_wilder.iloc[i] = (atr_wilder.iloc[i-1] * (period - 1) + tr.iloc[i]) / period

# Wilder's DM
pos_dm_wilder = pd.Series(index=df.index, dtype=float)
neg_dm_wilder = pd.Series(index=df.index, dtype=float)
pos_dm_wilder.iloc[0] = up.iloc[0:period][up.iloc[0:period] > 0].sum()
neg_dm_wilder.iloc[0] = down.iloc[0:period][down.iloc[0:period] > 0].sum()

for i in range(period, len(df)):
    pos_dm_wilder.iloc[i] = (pos_dm_wilder.iloc[i-1] * (period - 1) + max(0, up.iloc[i])) / period
    neg_dm_wilder.iloc[i] = (neg_dm_wilder.iloc[i-1] * (period - 1) + max(0, down.iloc[i])) / period

# DI with Wilder's
pos_di_wilder = (pos_dm_wilder / atr_wilder) * 100
neg_di_wilder = (neg_dm_wilder / atr_wilder) * 100

di_diff_wilder = abs(pos_di_wilder - neg_di_wilder)
di_sum_wilder = pos_di_wilder + neg_di_wilder
di_ratio_wilder = di_diff_wilder / di_sum_wilder

# ADX with Wilder's smoothing
adx_wilder = pd.Series(index=df.index, dtype=float)
adx_wilder.iloc[period*2-1] = di_ratio_wilder.iloc[period:period*2].mean() * 100
for i in range(period*2, len(df)):
    adx_wilder.iloc[i] = (adx_wilder.iloc[i-1] * (period - 1) + di_ratio_wilder.iloc[i] * 100) / period

print(f"ADX (latest): {adx_wilder.iloc[-1]:.2f}")
print(f"ADX (last 5): {adx_wilder.tail(5).values}")
print()

# =====================================================
# COMPARISON WITH ZERODHA
# =====================================================
print("=" * 80)
print("COMPARISON WITH ZERODHA")
print("-" * 80)

zerodha_adx = 26.33

print(f"Zerodha ADX (Chart):           {zerodha_adx:.2f}")
print(f"Simple Rolling Average:        {adx_simple.iloc[-1]:.2f} (diff: {abs(adx_simple.iloc[-1] - zerodha_adx):.2f})")
print(f"Wilder's Smoothing:            {adx_wilder.iloc[-1]:.2f} (diff: {abs(adx_wilder.iloc[-1] - zerodha_adx):.2f})")
print()

simple_diff = abs(adx_simple.iloc[-1] - zerodha_adx)
wilders_diff = abs(adx_wilder.iloc[-1] - zerodha_adx)

if wilders_diff < simple_diff:
    print("✅ WILDER'S SMOOTHING matches Zerodha better!")
    print("   → Backend should use Wilder's method instead of simple rolling average")
else:
    print("⚠️  Neither method perfectly matches Zerodha")
    print("   → Possible reasons:")
    print("      1. Zerodha uses different period")
    print("      2. Zerodha has different data timeframe")
    print("      3. Zerodha uses different calculation altogether")

db.close()
