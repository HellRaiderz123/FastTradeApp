"""
DEBUG: Check actual indicator calculations vs manual computation
"""
import sys
sys.path.insert(0, "/app")

from app.db.session import SessionLocal
from app.db.models_candles import Candle15m
from app.core.signals.ta_engine import compute_adx, compute_rsi
import pandas as pd
from datetime import datetime

db = SessionLocal()

# Fetch last 100 candles
candles = (
    db.query(Candle15m)
    .filter(Candle15m.symbol == "NIFTY")
    .order_by(Candle15m.timestamp.desc())
    .limit(100)
    .all()
)

print(f"✅ Found {len(candles)} candles")
print(f"📅 Candle range: {candles[-1].timestamp} → {candles[0].timestamp}")
print()

# Build dataframe
df = pd.DataFrame(
    [{
        "close": c.close,
        "high": c.high,
        "low": c.low,
        "open": c.open,
        "volume": c.volume,
    } for c in reversed(candles)]
)

print("=" * 70)
print("CANDLE DATA (LAST 5)")
print("=" * 70)
print(df[["open", "high", "low", "close", "volume"]].tail(5))
print()

# Calculate ADX
df["adx"] = compute_adx(df)
print("=" * 70)
print("ADX CALCULATION DEBUG")
print("=" * 70)
print(f"ADX values (last 10):")
print(df["adx"].tail(10).values)
print(f"Latest ADX: {df['adx'].iloc[-1]:.2f}")
print()

# Calculate RSI
df["rsi"] = compute_rsi(df["close"])
print("=" * 70)
print("RSI CALCULATION DEBUG")
print("=" * 70)
print(f"RSI values (last 10):")
print(df["rsi"].tail(10).values)
print(f"Latest RSI: {df['rsi'].iloc[-1]:.2f}")
print()

# Manual ADX check
print("=" * 70)
print("MANUAL ADX VERIFICATION")
print("=" * 70)
high = df["high"]
low = df["low"]
close = df["close"]

# True Range calculation
tr1 = high - low
tr2 = abs(high - close.shift())
tr3 = abs(low - close.shift())
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr = tr.rolling(14).mean()

print(f"True Range (last 5):")
print(tr.tail(5).values)
print(f"ATR (last 5):")
print(atr.tail(5).values)
print()

# Directional Movement
up = high.diff()
down = low.diff() * -1
pos_dm = up.copy()
pos_dm[up <= down] = 0
pos_dm[up < 0] = 0
neg_dm = down.copy()
neg_dm[down <= up] = 0
neg_dm[down < 0] = 0

pos_di = (pos_dm.rolling(14).sum() / atr) * 100
neg_di = (neg_dm.rolling(14).sum() / atr) * 100

print(f"Positive DI (last 5):")
print(pos_di.tail(5).values)
print(f"Negative DI (last 5):")
print(neg_di.tail(5).values)
print()

di_diff = abs(pos_di - neg_di)
di_sum = pos_di + neg_di
di_ratio = di_diff / di_sum
adx_manual = di_ratio.rolling(14).mean() * 100

print(f"ADX Manual (last 5):")
print(adx_manual.tail(5).values)
print(f"ADX Latest (manual): {adx_manual.iloc[-1]:.2f}")
print()

# Manual RSI check
print("=" * 70)
print("MANUAL RSI VERIFICATION")
print("=" * 70)
delta = close.diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = -delta.clip(upper=0).rolling(14).mean()
rs = gain / loss
rsi_manual = 100 - (100 / (1 + rs))

print(f"Gains (last 5):")
print(gain.tail(5).values)
print(f"Losses (last 5):")
print(loss.tail(5).values)
print(f"RSI Manual (last 5):")
print(rsi_manual.tail(5).values)
print(f"RSI Latest (manual): {rsi_manual.iloc[-1]:.2f}")
print()

# Summary
print("=" * 70)
print("🔍 SUMMARY")
print("=" * 70)
print(f"Calculated ADX: {df['adx'].iloc[-1]:.2f} (Expected: ~26)")
print(f"Calculated RSI: {df['rsi'].iloc[-1]:.2f} (Expected: ~64)")
print()
print("✅ If values match manual calculation → TA engine is CORRECT")
print("❌ If values DON'T match → TA engine has BUG")
print("⚠️  If both are wrong → CANDLE DATA might be stale/incorrect")

db.close()
