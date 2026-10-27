import asyncio, httpx, os

async def main():
    # 1. Test NSE directly with Mac UA (no session)
    print("=== NSE direct with Mac UA ===")
    mac_ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        try:
            r = await c.get(
                "https://www.nseindia.com/api/corporate-announcements?index=equities",
                headers={"User-Agent": mac_ua, "Accept": "application/json", "Referer": "https://www.nseindia.com/"}
            )
            print(f"Status: {r.status_code}, len: {len(r.content)}")
            if r.status_code == 200:
                data = r.json()
                rows = data if isinstance(data, list) else data.get("data", [])
                print(f"Rows: {len(rows)}")
                if rows:
                    print("First row keys:", list(rows[0].keys()))
                    print("Sample:", rows[0])
        except Exception as e:
            print(f"Error: {e}")

    # 2. Test BSE API
    print("\n=== BSE API ===")
    from datetime import datetime
    today_str = datetime.now().strftime("%Y%m%d")
    bse_headers = {
        "User-Agent": mac_ua,
        "Accept": "application/json",
        "Referer": "https://www.bseindia.com/corporates/ann.html",
        "Origin": "https://www.bseindia.com",
    }
    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
        try:
            r = await c.get(
                "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w",
                params={"pageno":"1","strCat":"-1","strPrevDate":today_str,"strScrip":"","strSearch":"P","strToDate":today_str,"strType":"C","subcategory":""},
                headers=bse_headers
            )
            print(f"Status: {r.status_code}, len: {len(r.content)}")
            if r.status_code == 200:
                data = r.json()
                rows = data.get("Table", [])
                print(f"Rows: {len(rows)}")
                if rows:
                    print("First row keys:", list(rows[0].keys()))
                    print("Sample:", rows[0])
        except Exception as e:
            print(f"Error: {e}")

    # 3. Test newsdata.io /news endpoint with q= param
    print("\n=== newsdata.io /news with q= ===")
    key = os.getenv("NEWSDATA_API_KEY", "")
    if key:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://newsdata.io/api/1/news",
                params={"apikey": key, "q": "TCS Tata Consultancy", "country": "in", "language": "en", "category": "business"}
            )
            print(f"Status: {r.status_code}")
            data = r.json()
            print(f"API status: {data.get('status')}")
            results = data.get("results", [])
            print(f"Results: {len(results)}")
            if results:
                print("First:", results[0].get("title", "")[:80])
    else:
        print("No API key")

asyncio.run(main())
