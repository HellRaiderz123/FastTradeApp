import requests, json, os
FUNDAMENTALS_API_KEY = os.getenv("FUNDAMENTALS_API_KEY", "ys_live_f77afa06dd07591242432f9fa22a0d31")
r = requests.get(
    "https://yashsarawgi.me/api/v1/fundamentals/stock",
    params={"symbol": "TCS", "view": "consolidated"},
    headers={"x-api-key": FUNDAMENTALS_API_KEY},
    timeout=15,
)
data = r.json()
stock = data.get("stock") or {}
d = stock.get("data") or {}

print("=== pnl line_items ===")
for row in (d.get("pnl") or []):
    print(row.get("line_item"))

print("\n=== balance_sheet line_items ===")
for row in (d.get("balance_sheet") or []):
    print(row.get("line_item"))

print("\n=== cash_flows line_items ===")
for row in (d.get("cash_flows") or []):
    print(row.get("line_item"))

print("\n=== quarters line_items ===")
for row in (d.get("quarters") or []):
    print(row.get("line_item"))

# Get latest year values for key metrics
pnl = {r["line_item"]: r for r in (d.get("pnl") or [])}
bs = {r["line_item"]: r for r in (d.get("balance_sheet") or [])}

# Find latest year
sales_row = pnl.get("Sales") or {}
years = [k for k in sales_row if k.startswith("Mar") or k == "TTM"]
print("\nYears available:", years[-4:])

latest = "Mar 2026"
sales = float(str(sales_row.get(latest, 0)).replace(",","") or 0)
op = float(str((pnl.get("Operating Profit") or {}).get(latest, 0)).replace(",","") or 0)
np_row = pnl.get("Net Profit") or pnl.get("Profit after tax") or {}
net_profit = float(str(np_row.get(latest, 0)).replace(",","") or 0)
print(f"\nSales: {sales}, OPM: {op/sales*100:.1f}%, NPM: {net_profit/sales*100:.1f}%")

# EPS
eps_row = pnl.get("EPS in Rs") or {}
print("EPS:", eps_row.get(latest))

# D/E
borrowings = float(str((bs.get("Borrowings") or {}).get(latest, 0) or 0))
equity = float(str((bs.get("Equity Capital") or {}).get(latest, 0) or 0))
reserves = float(str((bs.get("Reserves") or {}).get(latest, 0) or 0))
total_equity = equity + reserves
print(f"D/E: {borrowings/total_equity:.2f}" if total_equity else "D/E: N/A")
