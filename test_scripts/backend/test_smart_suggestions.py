"""Quick test: smart suggestions API"""
import requests
import json

r = requests.get("http://localhost:8000/positions/smart-suggestions")
print("Status:", r.status_code)
data = r.json()
print("Suggestions count:", len(data.get("suggestions", {})))
print("Spread suggestions:", len(data.get("spread_suggestions", [])))
print("Has warnings:", data.get("has_warnings"))
print("Critical count:", data.get("critical_count"))
print()

for iid, advice in data.get("suggestions", {}).items():
    sev = advice.get("severity", "?")
    act = advice.get("action", "?")
    reason = advice.get("reason", "")[:120]
    bias = advice.get("current_signal_bias", "?")
    conf = advice.get("current_confidence", 0)
    print(f"  [{sev}] {act}")
    print(f"    Reason: {reason}")
    print(f"    Signal: {bias} ({conf}% conf)")
    print(f"    Position bias: {advice.get('position_bias', '?')}")
    print()

for ss in data.get("spread_suggestions", []):
    print(f"  SPREAD: {ss.get('spread_type')} / {ss.get('underlying')}")
    adv = ss.get("advice", {})
    print(f"    -> {adv.get('action')} [{adv.get('severity')}]")
    print(f"    -> {adv.get('reason', '')[:120]}")
    print()
