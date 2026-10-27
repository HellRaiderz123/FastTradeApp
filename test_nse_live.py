import requests, json

NSE_HOME = "https://www.nseindia.com/"
NSE_CASH = "https://www.nseindia.com/api/fiidiiTradeReact"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/reports-indices-fii-dii-trading-activity",
}

# Step 1: get cookie
print("Getting NSE session cookie...")
r = requests.get(NSE_HOME, headers=HEADERS, timeout=10)
cookies_raw = r.headers.get("set-cookie", "")
cookie_str = "; ".join([c.split(";")[0].strip() for c in cookies_raw.split(",") if "=" in c.split(";")[0]])
print("Cookie:", cookie_str[:100])

# Step 2: fetch cash data
print("\nFetching cash data...")
r2 = requests.get(NSE_CASH, headers={**HEADERS, "Cookie": cookie_str}, timeout=25)
print("Status:", r2.status_code)
if r2.status_code == 200:
    data = r2.json()
    print("Type:", type(data), "Len:", len(data) if isinstance(data, list) else "N/A")
    if isinstance(data, list) and data:
        print("First row keys:", list(data[0].keys()))
        print("First row:", json.dumps(data[0], indent=2))
        print("Last row:", json.dumps(data[-1], indent=2))
else:
    print("Response:", r2.text[:500])

# Step 3: try F&O CSV for today
from datetime import datetime
today = datetime.utcnow()
date_part = today.strftime("%d%m%Y")
fao_url = f"https://nsearchives.nseindia.com/content/nsccl/fao_participant_oi_{date_part}_b.csv"
print(f"\nFetching F&O CSV: {fao_url}")
r3 = requests.get(fao_url, headers={**HEADERS, "Cookie": cookie_str}, timeout=15)
print("F&O Status:", r3.status_code)
if r3.status_code == 200:
    print("F&O CSV first 500 chars:", r3.text[:500])
