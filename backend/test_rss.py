import sys
sys.path.insert(0, '/app')

from app.services.rss_feed_service import NSERSSFeedService

svc = NSERSSFeedService()

print(f"Total feeds configured: {len(svc.NSE_FEEDS)}")
print("Feeds:")
for k, v in svc.NSE_FEEDS.items():
    print(f"  {k}: {v}")

print()
print("Testing each feed individually...")
results = {}
for key, url in svc.NSE_FEEDS.items():
    items = svc.fetch_feed(url, key, timeout=8)
    results[key] = len(items)
    status = "OK" if items else "EMPTY/FAIL"
    sample = items[0]['title'][:60] if items else "—"
    print(f"  [{status}] {key}: {len(items)} items | {sample}")

print()
print("Testing fetch_all_feeds (parallel + dedup)...")
all_items = svc.fetch_all_feeds()
print(f"Total unique items after dedup: {len(all_items)}")

sources = {}
for item in all_items:
    s = item.get('source', 'unknown')
    sources[s] = sources.get(s, 0) + 1
print("By source:")
for s, c in sorted(sources.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c}")

cats = {}
for item in all_items:
    c = item.get('category', 'unknown')
    cats[c] = cats.get(c, 0) + 1
print("By category:")
for c, n in sorted(cats.items(), key=lambda x: -x[1]):
    print(f"  {c}: {n}")
