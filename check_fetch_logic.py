import requests

for fname in ['scripts/fetch_data.js', 'scripts/fetch_nsdl.js', 'server.js']:
    r = requests.get(f"https://raw.githubusercontent.com/MrChartist/fii-dii-data/main/{fname}", timeout=15)
    print(f"\n{'='*60}")
    print(f"FILE: {fname}")
    print('='*60)
    print(r.text[:4000])
