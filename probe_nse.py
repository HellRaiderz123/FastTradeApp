import requests

s = requests.Session()
s.headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
s.get('https://www.nseindia.com', timeout=15)
ref = 'https://www.nseindia.com/market-data-pre-open/'
ref2 = 'https://www.nseindia.com/companies-listing/corporate-filings-corporate-actions'

paths = [
    # 52 week
    ('/api/live-analysis-data?index=52W_HIGH', ref),
    ('/api/live-analysis-data?index=HIGH_52', ref),
    ('/api/live-analysis-data?index=yearHighLow', ref),
    ('/api/live-analysis-data?index=52wHigh', ref),
    ('/api/live-analysis-data?index=top-gainers', ref),
    ('/api/live-analysis-data?index=NIFTY', ref),
    # short selling
    ('/api/short-selling', ref),
    ('/api/short-sell-data', ref),
    ('/api/short-selling-data', ref),
    # participant OI
    ('/api/participant-wise-trading-data?type=index&instrument=FUTIDX', ref),
    ('/api/participant-wise-open-interest-data?type=index&instrument=FUTIDX', ref),
    ('/api/participant-wise-trading-data?type=index&instrument=FUTSTK', ref),
    # forthcoming
    ('/api/corporates-forthcoming?index=equities', ref2),
    ('/api/corporates-forthcoming-actions?index=equities', ref2),
    ('/api/corporate-forthcoming?index=equities', ref2),
    # market turnover (already works)
    ('/api/market-turnover', ref),
]

for p, r in paths:
    resp = s.get('https://www.nseindia.com' + p, headers={'Referer': r}, timeout=15)
    print(resp.status_code, p[:80])
