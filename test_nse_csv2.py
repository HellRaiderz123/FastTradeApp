import requests

# Moneycontrol FII DII - try correct endpoint
urls = [
    "https://priceapi.moneycontrol.com/pricefeed/notapplicable/fiidii/1",
    "https://priceapi.moneycontrol.com/pricefeed/nse/fiidii/0",
    "https://priceapi.moneycontrol.com/pricefeed/nse/fiidii/1",
    # Groww public API
    "https://groww.in/v1/api/stocks_data/v1/fii_dii",
    # Tickertape
    "https://api.tickertape.in/market/fii-dii",
    # Screener
    "https://www.screener.in/api/company/search/?q=NIFTY",
    # NSE India reports page direct JSON
    "https://www.nseindia.com/api/fiidiiTradeReact",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}

for url in urls:
    try:
        r = requests.get(url, timeout=10, headers=headers)
        print(f"{url[:65]} -> {r.status_code} ({len(r.content)} bytes)")
        if r.status_code == 200 and len(r.content) > 50:
            print("  Preview:", r.text[:300])
    except Exception as e:
        print(f"{url[:65]} -> ERROR: {e}")
