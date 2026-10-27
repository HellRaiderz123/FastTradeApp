import sys
sys.path.insert(0, '/app')

print("=== News test ===")
try:
    from app.services.trading_agents import _get_news_items
    news = _get_news_items(limit=3)
    print(f"News items fetched: {len(news)}")
    if news:
        print("First headline:", str(news[0].get('title',''))[:80])
    else:
        print("No news items (RSS feeds may be empty or unreachable)")
except Exception as e:
    print(f"FAIL: {e}")

print()
print("=== Fundamentals test (DRREDDY) ===")
try:
    from app.services.trading_agents import _get_fundamental_data
    fund = _get_fundamental_data('DRREDDY')
    print("Source:", fund.get('source'))
    print("Provider symbol:", fund.get('provider_symbol'))
    f = fund.get('fundamentals', {})
    print("PE:", f.get('pe_ratio'), "| PB:", f.get('pb_ratio'), "| ROE:", f.get('roe_pct'))
except Exception as e:
    print(f"FAIL: {e}")

print()
print("=== VIX test ===")
try:
    from app.services.trading_agents import _get_vix
    vix = _get_vix()
    print("VIX:", vix)
except Exception as e:
    print(f"FAIL: {e}")

print()
print("=== Provider LTP test (DRREDDY) ===")
try:
    from app.core.market.provider import fetch_ltp
    prices = fetch_ltp(['DRREDDY', 'NIFTY'])
    print("Prices:", prices)
except Exception as e:
    print(f"FAIL: {e}")
