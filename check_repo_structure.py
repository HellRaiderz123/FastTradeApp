import requests, json

# List all files in the repo root
r = requests.get("https://api.github.com/repos/MrChartist/fii-dii-data/contents/", timeout=15)
print("Root files:")
for f in r.json():
    print(f"  [{f['type']}] {f['name']} ({f.get('size',0)} bytes)")

# Check if there's a src or scripts folder
for folder in ['src', 'scripts', 'fetchers', 'lib', 'agents']:
    r2 = requests.get(f"https://api.github.com/repos/MrChartist/fii-dii-data/contents/{folder}", timeout=10)
    if r2.status_code == 200:
        print(f"\n{folder}/:")
        for f in r2.json():
            print(f"  {f['name']}")
