"""
DEBUG: Compare TA Engine output vs Zerodha chart values
Verify ADX and RSI calculations are correct
"""
import sys
sys.path.insert(0, "/app")

from app.db.session import SessionLocal
from app.db.models_candles import Candle15m
from app.core.signals.ta_engine import compute_adx, compute_rsi
import pandas as pd

db = SessionLocal()

# Fetch last 100 candles
candles = (
    db.query(Candle15m)
    .filter(Candle15m.symbol == "NIFTY")
    .order_by(Candle15m.timestamp.desc())
    .limit(100)
    .all()
)

print("=" * 80)
print("🔍 DEBUGGING ADX & RSI CALCULATIONS")
print("=" * 80)
print()

print(f"✅ Found {len(candles)} candles")
if len(candles) > 0:
    print(f"📅 Latest candle: {candles[0].timestamp}")
    print(f"📅 Oldest candle: {candles[-1].timestamp}")
print()

# Show raw candles (latest first as fetched)
print("=" * 80)
print("RAW CANDLE DATA (AS FETCHED - Latest first)")
print("=" * 80)
print("Timestamp | Open | High | Low | Close | Volume")
for i, c in enumerate(candles[:10]):  # Show latest 10
    print(f"{c.timestamp} | {c.open:.2f} | {c.high:.2f} | {c.low:.2f} | {c.close:.2f} | {c.volume}")
print()

# Build DataFrame THE WAY TA ENGINE DOES IT
print("=" * 80)
print("DATAFRAME CONSTRUCTION (reversed)")
print("=" * 80)

df = pd.DataFrame(
    [{
        "close": c.close,
        "high": c.high,
        "low": c.low,
        "open": c.open,
        "volume": c.volume,
    } for c in reversed(candles)]  # ← NOTE: reversed
)

print(f"DataFrame shape: {df.shape}")
print()
print("First 5 rows (oldest):")
print(df[["open", "high", "low", "close"]].head(5))
print()
print("Last 5 rows (newest):")
print(df[["open", "high", "low", "close"]].tail(5))
print()

# Verify data order
print("=" * 80)
print("DATA ORDER VERIFICATION")
print("=" * 80)
print(f"First row (index 0) close: {df['close'].iloc[0]}")
print(f"Last row (index {len(df)-1}) close: {df['close'].iloc[-1]}")
print()
if df['close'].iloc[0] < df['close'].iloc[-1]:
    print("✅ Data is in chronological order (oldest → newest)")
else:
    print("❌ Data might be reversed!")
print()

# Calculate indicators
print("=" * 80)
print("INDICATOR CALCULATIONS")
print("=" * 80)

df["adx"] = compute_adx(df)
df["rsi"] = compute_rsi(df["close"])

latest_adx = df["adx"].iloc[-1]
latest_rsi = df["rsi"].iloc[-1]

print(f"Latest ADX (backend): {latest_adx:.2f}")
print(f"Latest RSI (backend): {latest_rsi:.2f}")
print()

# Compare with Zerodha values
zerodha_adx = 26.33
zerodha_rsi = 57.96

print(f"Expected ADX (Zerodha): {zerodha_adx:.2f}")
print(f"Expected RSI (Zerodha): {zerodha_rsi:.2f}")
print()

adx_diff = abs(latest_adx - zerodha_adx)
rsi_diff = abs(latest_rsi - zerodha_rsi)

print(f"ADX Difference: {adx_diff:.2f} points ({'✅ OK' if adx_diff < 1.0 else '❌ WRONG'})")
print(f"RSI Difference: {rsi_diff:.2f} points ({'✅ OK' if rsi_diff < 5.0 else '❌ WRONG'})")
print()

# Debug ADX calculation step by step
print("=" * 80)
print("ADX CALCULATION DEBUG (Step by Step)")
print("=" * 80)

high = df["high"]
low = df["low"]
close = df["close"]

# True Range
tr1 = high - low
tr2 = abs(high - close.shift())
tr3 = abs(low - close.shift())
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

print("True Range (last 5):")
print(tr.tail(5).values)
print()

atr = tr.rolling(14).mean()
print("ATR (last 5):")
print(atr.tail(5).values)
print()

# Directional Movement
up = high.diff()
down = low.diff() * -1

print("Up Movement (last 5):")
print(up.tail(5).values)
print()
print("Down Movement (last 5):")
print(down.tail(5).values)
print()

pos_dm = up.copy()
pos_dm[up <= down] = 0
pos_dm[up < 0] = 0

neg_dm = down.copy()
neg_dm[down <= up] = 0
neg_dm[down < 0] = 0

print("Positive DM (last 5):")
print(pos_dm.tail(5).values)
print()
print("Negative DM (last 5):")
print(neg_dm.tail(5).values)
print()

pos_di = (pos_dm.rolling(14).sum() / atr) * 100
neg_di = (neg_dm.rolling(14).sum() / atr) * 100

print("Positive DI (last 5):")
print(pos_di.tail(5).values)
print()
print("Negative DI (last 5):")
print(neg_di.tail(5).values)
print()

di_diff = abs(pos_di - neg_di)
di_sum = pos_di + neg_di
di_ratio = di_diff / di_sum
adx_manual = di_ratio.rolling(14).mean() * 100

print("DI Ratio (last 5):")
print(di_ratio.tail(5).values)
print()
print("ADX Manual (last 5):")
print(adx_manual.tail(5).values)
print()

# Debug RSI calculation
print("=" * 80)
print("RSI CALCULATION DEBUG (Step by Step)")
print("=" * 80)

delta = close.diff()
print("Price Change (last 5):")
print(delta.tail(5).values)
print()

gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()

print("Average Gain (last 5):")
print(gain.tail(5).values)
print()
print("Average Loss (last 5):")
print(loss.tail(5).values)
print()

rs = gain / loss
rsi_manual = 100 - (100 / (1 + rs))

print("RS Ratio (last 5):")
print(rs.tail(5).values)
print()
print("RSI Manual (last 5):")
print(rsi_manual.tail(5).values)
print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()

if adx_diff < 1.0 and rsi_diff < 5.0:
    print("✅ ADX and RSI calculations are CORRECT")
    print("✅ Fresh candle data is properly ingested")
    print("✅ No issues found")
elif adx_diff > 10 or rsi_diff > 10:
    print("❌ MAJOR calculation error detected")
    print("❌ Possible causes:")
    print("   1. Data ordering issue (reversed incorrectly)")
    print("   2. Wrong period for moving averages")
    print("   3. Formula implementation bug")
    print("   4. Missing/null values in data")
else:
    print("⚠️  MINOR calculation difference")
    print("⚠️  Could be due to rounding or data lag")

db.close()
