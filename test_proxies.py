import requests, urllib.parse, json

NSE_CASH = "https://www.nseindia.com/api/fiidiiTradeReact"

# Test allorigins
proxy = f"https://api.allorigins.win/get?url={urllib.parse.quote(NSE_CASH, safe='')}"
print("Trying allorigins:", proxy[:80])
r = requests.get(proxy, timeout=30)
print("Status:", r.status_code)
body = r.json()
print("Status field:", body.get("status"))
contents = body.get("contents", "")
print("Contents length:", len(contents) if contents else 0)
print("Contents preview:", (contents or "")[:300])

# Test corsproxy.io
proxy2 = f"https://corsproxy.io/?{urllib.parse.quote(NSE_CASH, safe='')}"
print("\nTrying corsproxy.io:")
try:
    r2 = requests.get(proxy2, timeout=15)
    print("Status:", r2.status_code)
    print("Preview:", r2.text[:300])
except Exception as e:
    print("Failed:", e)

# Test thingproxy
proxy3 = f"https://thingproxy.freeboard.io/fetch/{NSE_CASH}"
print("\nTrying thingproxy:")
try:
    r3 = requests.get(proxy3, timeout=15)
    print("Status:", r3.status_code)
    print("Preview:", r3.text[:300])
except Exception as e:
    print("Failed:", e)
