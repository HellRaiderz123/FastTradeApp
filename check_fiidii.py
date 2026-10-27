import requests
from datetime import datetime

r = requests.get('https://raw.githubusercontent.com/MrChartist/fii-dii-data/main/data/history.json', timeout=15)
data = r.json()

parsed = []
bad = []
for row in data:
    try:
        d = datetime.strptime(row['date'], '%d-%b-%Y').date()
        parsed.append((d, row['date'], row.get('fii_net'), row.get('dii_net'), row.get('fii_idx_fut_long')))
    except Exception as e:
        bad.append((row['date'], str(e)))

parsed.sort()
print('TOTAL records:', len(data))
print('PARSEABLE:', len(parsed))
print('BAD DATES:', bad[:10])
print('FIRST:', parsed[0] if parsed else 'none')
print('LAST 5:')
for p in parsed[-5:]:
    print(' ', p)
print('FNO records (non-null fii_idx_fut_long):', sum(1 for p in parsed if p[4] is not None))
print('Latest FNO record:', next((p for p in reversed(parsed) if p[4] is not None), None))
