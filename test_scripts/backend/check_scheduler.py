import requests, time

r1 = requests.get("http://localhost:8000/auto-trader/status", timeout=5)
d1 = r1.json()
t1 = d1.get("last_scan_at", "N/A")
status = d1.get("status")
interval = d1.get("scan_interval_seconds")
print(f"T1: {t1}  status={status}  interval={interval}")
print("Waiting 35 seconds...")
time.sleep(35)
r2 = requests.get("http://localhost:8000/auto-trader/status", timeout=5)
d2 = r2.json()
t2 = d2.get("last_scan_at", "N/A")
print(f"T2: {t2}")
if t1 != t2:
    print("SCHEDULER IS RUNNING - timestamp changed!")
else:
    print("SCHEDULER NOT RUNNING - same timestamp after 35s")
