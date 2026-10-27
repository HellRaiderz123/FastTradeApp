import asyncio, os
from app.services.nse_news_service import NSENewsService

async def main():
    svc = NSENewsService()

    print("=== Testing NSE announcements ===")
    try:
        items = await svc.fetch_nse_announcements()
        print(f"Total items: {len(items)}")
        for i in items[:3]:
            print(f"  symbol={i.symbol} | source={i.source} | high_impact={i.is_high_impact}")
            print(f"  headline: {i.headline[:80]}")
    except Exception as e:
        print(f"NSE fetch error: {e}")

    print("\n=== Testing BSE announcements ===")
    try:
        items = await svc.fetch_bse_announcements()
        print(f"Total items: {len(items)}")
        for i in items[:3]:
            print(f"  symbol={i.symbol} | source={i.source} | high_impact={i.is_high_impact}")
            print(f"  headline: {i.headline[:80]}")
    except Exception as e:
        print(f"BSE fetch error: {e}")

    print("\n=== Testing stock-news (newsdata.io) for TCS ===")
    from app.api.routes.stock_news import fetch_newsdata_io
    NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "")
    print(f"NEWSDATA_API_KEY set: {bool(NEWSDATA_API_KEY)}")
    if NEWSDATA_API_KEY:
        articles = await fetch_newsdata_io("TCS", 5)
        print(f"Articles: {len(articles)}")
        for a in articles[:2]:
            print(f"  {a['title'][:80]}")
    else:
        print("  Skipped — no API key")

asyncio.run(main())
