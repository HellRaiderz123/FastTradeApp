import requests

r = requests.get("https://raw.githubusercontent.com/MrChartist/fii-dii-data/main/scripts/fetch_data.js", timeout=15)
# Print from line 100 onwards to get the actual fetch/parse logic
lines = r.text.split('\n')
print('\n'.join(lines[100:300]))
