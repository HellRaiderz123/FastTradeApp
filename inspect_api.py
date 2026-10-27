import requests, json, os
FUNDAMENTALS_API_KEY = os.getenv("FUNDAMENTALS_API_KEY", "ys_live_f77afa06dd07591242432f9fa22a0d31")
r = requests.get(
    "https://yashsarawgi.me/api/v1/fundamentals/stock",
    params={"symbol": "TCS", "view": "consolidated"},
    headers={"x-api-key": FUNDAMENTALS_API_KEY},
    timeout=15,
)
print("status:", r.status_code)
data = r.json()
stock = data.get("stock") or {}
print("stock keys:", list(stock.keys()))
# Print each key's type/sample
for k, v in stock.items():
    if isinstance(v, dict):
        print(f"\n{k} (dict keys):", list(v.keys())[:20])
        print(json.dumps(v, indent=2)[:800])
    elif isinstance(v, list):
        print(f"\n{k} (list len={len(v)}):", json.dumps(v[:2], indent=2)[:600])
    else:
        print(f"\n{k}:", str(v)[:200])
