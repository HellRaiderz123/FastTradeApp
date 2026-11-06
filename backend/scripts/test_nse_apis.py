"""
Quick connectivity test for all NSE endpoints used in FastTrade.
Tries alternative paths per endpoint until one returns 200.
Run from backend/: python scripts/test_nse_apis.py
"""
import requests

NSE_BASE = "https://www.nseindia.com"
MAC_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT = 10

# (label, [(path, referer, params), ...]) — tries each until 200
ENDPOINTS = [
    ("VIX - allIndices", [
        ("/api/allIndices", "/market-data-pre-open/", None),
    ]),
    ("Block Deals", [
        ("/api/block-deal", "/market-data-pre-open/block-deal", None),
        ("/api/blockdeals", "/market-data-pre-open/block-deal", None),
    ]),
    ("Bulk Deals", [
        ("/api/bulk-deals", "/market-data-pre-open/bulk-deals", None),
        ("/api/bulkdeals", "/market-data-pre-open/bulk-deals", None),
    ]),
    ("F&O Ban", [
        ("/api/fo-sec-ban", "/market-data-pre-open/fo-sec-ban", None),
        ("/api/foBanList", "/market-data-pre-open/fo-sec-ban", None),
        ("/api/fo-ban-list", "/market-data-pre-open/fo-sec-ban", None),
    ]),
    ("Corporate Actions", [
        ("/api/corporates-corporateActions", "/companies-listing/corporate-filings-corporate-actions", {"index": "equities"}),
    ]),
    ("Board Meetings", [
        ("/api/corporate-board-meetings", "/companies-listing/corporate-filings-board-meetings", {"index": "equities"}),
    ]),
    ("Announcements", [
        ("/api/corporate-announcements", "/companies-listing/corporate-filings-announcements", {"index": "equities"}),
    ]),
    ("Insider / SAST", [
        ("/api/corporate-announcements", "/companies-listing/corporate-filings-announcements", {"index": "sast"}),
    ]),
    ("Short Selling", [
        ("/api/short-selling", "/market-data-pre-open/short-selling", None),
        ("/api/shortselling", "/market-data-pre-open/short-selling", None),
        ("/api/short-sell", "/market-data-pre-open/short-selling", None),
    ]),
    ("Participant OI", [
        ("/api/participant-wise-trading-data", "/market-data-pre-open/derivatives", {"type": "index", "instrument": "FUTSTK"}),
        ("/api/participant-wise-open-interest", "/market-data-pre-open/derivatives", {"type": "index", "instrument": "FUTSTK"}),
        ("/api/participantWiseTradingData", "/market-data-pre-open/derivatives", {"type": "index", "instrument": "FUTSTK"}),
    ]),
    ("Forthcoming Actions", [
        ("/api/corporates-forthcoming", "/companies-listing/corporate-filings-corporate-actions", {"index": "equities"}),
        ("/api/corporates-forthcomingActions", "/companies-listing/corporate-filings-corporate-actions", {"index": "equities"}),
        ("/api/corporatesForthcoming", "/companies-listing/corporate-filings-corporate-actions", {"index": "equities"}),
    ]),
    ("52-Week Highs", [
        ("/api/live-analysis-data", "/market-data-pre-open/", {"index": "52W_HIGH"}),
        ("/api/live-analysis-data", "/market-data-pre-open/", {"index": "HIGH"}),
        ("/api/liveanalysis", "/market-data-pre-open/", {"index": "52W_HIGH"}),
    ]),
    ("52-Week Lows", [
        ("/api/live-analysis-data", "/market-data-pre-open/", {"index": "52W_LOW"}),
        ("/api/live-analysis-data", "/market-data-pre-open/", {"index": "LOW"}),
        ("/api/liveanalysis", "/market-data-pre-open/", {"index": "52W_LOW"}),
    ]),
    ("Market Turnover", [
        ("/api/market-turnover", "/market-data-pre-open/", None),
    ]),
    ("FII/DII Cash", [
        ("/api/fiidiiTradeReact", "/reports-indices-fii-dii-trading-activity", None),
    ]),
]


def nse_get(path, referer, params=None):
    r = requests.get(
        f"{NSE_BASE}{path}",
        headers={
            "User-Agent": MAC_UA,
            "Accept": "application/json, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{NSE_BASE}{referer}",
        },
        params=params,
        timeout=TIMEOUT,
    )
    return r.status_code, r


def data_summary(data) -> str:
    if data is None:
        return "null"
    if isinstance(data, list):
        return f"{len(data)} items"
    if isinstance(data, dict):
        n = len(data.get("data") or data.get("secBanList") or [])
        return f"dict data[{n}]" if n else "dict (empty)"
    return type(data).__name__


print(f"\n{'Label':<28} {'Status':<10} {'Working Path':<48} {'Data'}")
print("-" * 110)

for label, candidates in ENDPOINTS:
    found = False
    for path, referer, params in candidates:
        try:
            status, r = nse_get(path, referer, params)
            if status == 200:
                try:
                    summary = data_summary(r.json())
                except Exception:
                    summary = "non-JSON"
                print(f"{label:<28} {'OK 200':<10} {path:<48} {summary}")
                found = True
                break
        except requests.exceptions.Timeout:
            print(f"{label:<28} {'TIMEOUT':<10} {path}")
            found = True
            break
        except Exception:
            pass
    if not found:
        tried = " | ".join(p for p, _, _ in candidates)
        print(f"{label:<28} {'ALL 404':<10} {tried}")

print()
