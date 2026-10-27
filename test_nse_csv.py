import requests

# NSE provides historical FII/DII data as CSV — no Akamai protection
urls = [
    # NSE bulk data download — no session needed
    "https://nsearchives.nseindia.com/content/fo/fii_stats.csv",
    "https://nsearchives.nseindia.com/content/fo/fii_stats_2026.csv",
    # NSE FII DII historical CSV
    "https://www1.nseindia.com/content/fo/fii_stats.csv",
    # Moneycontrol public API
    "https://priceapi.moneycontrol.com/pricefeed/notapplicable/fiidii/0",
    # Trendlyne
    "https://trendlyne.com/macro/fii-dii/",
]

for url in urls:
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        print(f"{url[:70]} -> {r.status_code} ({len(r.content)} bytes)")
        if r.status_code == 200:
            print("  Preview:", r.text[:200])
    except Exception as e:
        print(f"{url[:70]} -> ERROR: {e}")
