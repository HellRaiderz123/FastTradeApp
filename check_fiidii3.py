import requests, json

# Check latest.json
r = requests.get("https://raw.githubusercontent.com/MrChartist/fii-dii-data/main/data/latest.json", timeout=15)
print("latest.json:")
print(json.dumps(r.json(), indent=2))

# Check fetch-log to see when data was last fetched
r2 = requests.get("https://raw.githubusercontent.com/MrChartist/fii-dii-data/main/data/fetch-log.json", timeout=15)
log = r2.json()
print("\nfetch-log last 3 entries:")
entries = log if isinstance(log, list) else log.get("entries", [log])
for e in entries[-3:]:
    print(" ", e)
