import requests
from datetime import datetime

# Check the GitHub repo commit info to see when it was last updated
api_url = "https://api.github.com/repos/MrChartist/fii-dii-data/commits?path=data/history.json&per_page=3"
r = requests.get(api_url, timeout=15)
print("GitHub last commits:")
for c in r.json():
    print(" ", c['commit']['committer']['date'], c['commit']['message'][:80])

# Also check if there are other files in the repo
r2 = requests.get("https://api.github.com/repos/MrChartist/fii-dii-data/contents/data", timeout=15)
print("\nFiles in /data:")
for f in r2.json():
    print(" ", f['name'], f.get('size'), 'bytes')

# Check the live API endpoint directly
print("\nTrying live API:")
try:
    r3 = requests.get("https://fii-diidata.mrchartist.com/api/history?days=5", timeout=10)
    print("Status:", r3.status_code)
    if r3.status_code == 200:
        print("Data:", r3.json())
except Exception as e:
    print("Failed:", e)
