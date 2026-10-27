import requests, json, os
FUNDAMENTALS_API_KEY = os.getenv("FUNDAMENTALS_API_KEY", "ys_live_f77afa06dd07591242432f9fa22a0d31")
r = requests.get(
    "https://yashsarawgi.me/api/v1/fundamentals/stock",
    params={"symbol": "TCS", "view": "consolidated"},
    headers={"x-api-key": FUNDAMENTALS_API_KEY},
    timeout=15,
)
data = r.json()
stock = data.get("stock") or {}
d = stock.get("data") or {}

print("=== other_ratios ===")
print(json.dumps(d.get("other_ratios"), indent=2)[:3000])

print("\n=== pnl (first 3 rows) ===")
pnl = d.get("pnl") or []
print(json.dumps(pnl[:3], indent=2))

print("\n=== balance_sheet (first 3 rows) ===")
bs = d.get("balance_sheet") or []
print(json.dumps(bs[:3], indent=2))

print("\n=== consolidated schedules keys ===")
cs = stock.get("consolidated") or {}
sched = cs.get("schedules") or {}
print(list(sched.keys()))
for k, v in sched.items():
    print(f"\n{k}:", json.dumps(v[:2] if isinstance(v, list) else v, indent=2)[:600])

print("\n=== key_points ===")
print(str(stock.get("key_points", ""))[:1000])
