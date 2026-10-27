import requests, json

# Check agent_runs.json to understand fetch logic
r = requests.get("https://raw.githubusercontent.com/MrChartist/fii-dii-data/main/data/agent_runs.json", timeout=15)
print("agent_runs.json:")
print(json.dumps(r.json(), indent=2)[:3000])
