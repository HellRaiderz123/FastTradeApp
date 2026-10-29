import requests

s = requests.Session()
s.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
s.get('https://www.nseindia.com', timeout=15)

# NSE known working API paths from their website JS
paths = [
    # Gainers/Losers/52W - allIndices or equity stockIndices
    ('/api/equity-stockIndices?index=NIFTY%2050', '/market-data-pre-open/'),
    ('/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O', '/market-data-pre-open/'),
    # Short selling - NSE archives
    ('/api/short-selling?date=28-10-2026', '/market-data-pre-open/short-selling'),
    # Participant OI - correct path
    ('/api/participant-wise-trading-data?type=index&instrument=FUTIDX&from=01-10-2026&to=28-10-2026', '/market-data-pre-open/derivatives'),
    # Forthcoming - correct path  
    ('/api/corporates-forthcoming?index=equities&from_date=28-10-2026&to_date=28-11-2026', '/companies-listing/corporate-filings-corporate-actions'),
    # 52 week via allIndices
    ('/api/allIndices', '/market-data-pre-open/'),
    # Market status
    ('/api/marketStatus', '/market-data-pre-open/'),
    # Advance decline
    ('/api/advance-decline', '/market-data-pre-open/'),
    # Top gainers losers
    ('/api/live-analysis-variations?index=gainers&limit=10', '/market-data-pre-open/'),
    ('/api/live-analysis-variations?index=loosers&limit=10', '/market-data-pre-open/'),
    ('/api/live-analysis-variations?index=52W_HIGH&limit=10', '/market-data-pre-open/'),
    ('/api/live-analysis-variations?index=52W_LOW&limit=10', '/market-data-pre-open/'),
]

for p, ref in paths:
    resp = s.get('https://www.nseindia.com' + p, headers={'Referer': 'https://www.nseindia.com' + ref}, timeout=15)
    preview = ''
    if resp.status_code == 200:
        try:
            d = resp.json()
            if isinstance(d, list): preview = f'list[{len(d)}]'
            elif isinstance(d, dict): preview = str(list(d.keys()))[:60]
        except: preview = resp.text[:50]
    print(resp.status_code, p[:80], preview)
