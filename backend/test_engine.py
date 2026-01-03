from app.core.strategies.option_spread_15m.engine import run_option_spread

payload = {
    "underlying": "NIFTY",
    "interval": "15minute",
    "use_ml": True,
    "min_confidence": 75,
    "risk_mode": "Conservative",
    "lots": 1,
    "capital": 100000,
}

res = run_option_spread(payload)
print(res)
