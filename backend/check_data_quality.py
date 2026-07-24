import sys
sys.path.insert(0, '/app')
from app.db.session import SessionLocal
from app.db.models_candles import CandleDaily
from sqlalchemy import func, text

db = SessionLocal()

print("=" * 60)
print("  STOCK HISTORIC DATA QUALITY CHECK")
print("=" * 60)

# 1. Basic counts
total = db.query(func.count(CandleDaily.id)).scalar()
symbols_q = db.query(
    CandleDaily.symbol,
    func.count(CandleDaily.id).label('cnt'),
    func.min(CandleDaily.date).label('mn'),
    func.max(CandleDaily.date).label('mx')
).group_by(CandleDaily.symbol).order_by(func.count(CandleDaily.id).desc()).all()

print(f"\n[1] Overview")
print(f"    Total candles : {total:,}")
print(f"    Total symbols : {len(symbols_q)}")
print(f"    ML-ready (500+): {sum(1 for _,c,_,__ in symbols_q if c >= 500)}")
print(f"    Thin (<100)   : {sum(1 for _,c,_,__ in symbols_q if c < 100)}")

# 2. NULL OHLCV
null_q = db.execute(text(
    "SELECT COUNT(*) FROM candles_daily "
    "WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL OR volume IS NULL"
)).scalar()
print(f"\n[2] NULL OHLCV rows       : {null_q}  {'OK' if null_q == 0 else 'PROBLEM'}")

# 3. Zero / negative prices
bad_price = db.execute(text(
    "SELECT COUNT(*) FROM candles_daily "
    "WHERE close <= 0 OR open <= 0 OR high <= 0 OR low <= 0"
)).scalar()
print(f"[3] Zero/negative price   : {bad_price}  {'OK' if bad_price == 0 else 'PROBLEM'}")

# 4. high < low
bad_hl = db.execute(text(
    "SELECT COUNT(*) FROM candles_daily WHERE high < low"
)).scalar()
print(f"[4] high < low            : {bad_hl}  {'OK' if bad_hl == 0 else 'PROBLEM'}")

# 5. close outside high/low
bad_close = db.execute(text(
    "SELECT COUNT(*) FROM candles_daily WHERE close > high OR close < low"
)).scalar()
print(f"[5] close outside hi/lo   : {bad_close}  {'OK' if bad_close == 0 else 'PROBLEM'}")

# 6. Duplicate (symbol, date)
dup_q = db.execute(text(
    "SELECT COUNT(*) FROM ("
    "  SELECT symbol, date FROM candles_daily "
    "  GROUP BY symbol, date HAVING COUNT(*) > 1"
    ") t"
)).scalar()
print(f"[6] Duplicate symbol+date : {dup_q}  {'OK' if dup_q == 0 else 'PROBLEM'}")
if dup_q > 0:
    dups = db.execute(text(
        "SELECT symbol, date, COUNT(*) FROM candles_daily "
        "GROUP BY symbol, date HAVING COUNT(*) > 1 LIMIT 5"
    )).fetchall()
    for row in dups:
        print(f"    {row}")

# 7. Future dates (date > today)
future_q = db.execute(text(
    "SELECT COUNT(*) FROM candles_daily WHERE date > CURRENT_DATE"
)).scalar()
print(f"[7] Future-dated rows     : {future_q}  {'OK' if future_q == 0 else 'PROBLEM'}")

# 8. Very old dates (before 2010)
old_q = db.execute(text(
    "SELECT COUNT(*) FROM candles_daily WHERE date < '2010-01-01'"
)).scalar()
print(f"[8] Pre-2010 rows         : {old_q}  {'OK' if old_q == 0 else 'NOTE'}")

# 9. Date gaps > 10 days for top 10 symbols
print(f"\n[9] Date gaps > 10 days (top 10 symbols):")
gap_issues = 0
for sym, cnt, mn, mx in symbols_q[:10]:
    rows = db.execute(
        text("SELECT date FROM candles_daily WHERE symbol=:s ORDER BY date"),
        {'s': sym}
    ).fetchall()
    dates = [r[0] for r in rows]
    gaps = [
        (str(dates[i]), str(dates[i+1]), (dates[i+1]-dates[i]).days)
        for i in range(len(dates)-1)
        if (dates[i+1]-dates[i]).days > 10
    ]
    status = f"{len(gaps)} gap(s)" if gaps else "OK"
    print(f"    {sym:<20} {cnt:>5} rows  {str(mn)} to {str(mx)}  gaps: {status}")
    if gaps:
        gap_issues += 1
        for g in gaps[:2]:
            print(f"      gap: {g[0]} -> {g[1]} ({g[2]} days)")

# 10. Symbols with data ending more than 30 days ago (stale)
from datetime import date, timedelta
cutoff = date.today() - timedelta(days=30)
stale = [(s, str(mx)) for s, c, mn, mx in symbols_q if mx < cutoff]
print(f"\n[10] Stale symbols (last candle >30d ago): {len(stale)}")
for s, mx in stale[:10]:
    print(f"    {s}: last={mx}")

# 11. Price spike check (single-day return > 50%)
spike_q = db.execute(text("""
    SELECT a.symbol, a.date, a.close, b.close as prev_close,
           ABS(a.close - b.close) / b.close as ret
    FROM candles_daily a
    JOIN candles_daily b ON a.symbol = b.symbol
    WHERE a.date > b.date
      AND ABS(a.close - b.close) / b.close > 0.5
    LIMIT 10
""")).fetchall()
print(f"\n[11] Price spikes >50% single day: {len(spike_q)}")
for row in spike_q[:5]:
    print(f"    {row}")

print("\n" + "=" * 60)
print("  SUMMARY")
print("=" * 60)
issues = sum([
    null_q > 0, bad_price > 0, bad_hl > 0,
    bad_close > 0, dup_q > 0, future_q > 0,
    gap_issues > 0, len(spike_q) > 0
])
if issues == 0:
    print("  All checks passed. Data looks clean.")
else:
    print(f"  {issues} issue(s) found — review above.")

db.close()
