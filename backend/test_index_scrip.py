import requests
from datetime import datetime, timezone

from app.core.broker.indstocks.market_data import _access_token

t = _access_token()
scrip = "NSE_40000001"

# Try different intervals and date ranges
tests = [
    ("60minute", datetime(2026, 10, 20), datetime(2026, 10, 26)),
    ("60minute", datetime(2026, 10, 1),  datetime(2026, 10, 15)),
    ("1day",     datetime(2026, 9, 1),   datetime(2026, 10, 26)),
    ("5minute",  datetime(2026, 10, 25), datetime(2026, 10, 26)),
]

for interval, from_dt, to_dt in tests:
    from_ms = int(from_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    to_ms   = int(to_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    r = requests.get(
        f"https://api.indstocks.com/market/historical/{interval}",
        params={"scrip-codes": scrip, "start_time": from_ms, "end_time": to_ms},
        headers={"Authorization": t},
        timeout=15,
    )
    body = r.json() if r.status_code == 200 else {}
    candles = (body.get("data") or {}).get(scrip, {}).get("candles") or []
    print(f"{interval} {from_dt.date()} to {to_dt.date()}: HTTP {r.status_code}, candles={len(candles)}")
    if candles:
        print(f"  first={candles[0]}, last={candles[-1]}")
    elif r.status_code != 200:
        print("  ->", r.text[:300])
    else:
        print("  -> full body:", str(body)[:300])
