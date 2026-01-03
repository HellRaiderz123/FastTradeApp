from app.services.signals import recommend_smart_option
from app.core.strategies.option_spread_15m.context import build_market_context

sig = recommend_smart_option("NIFTY")
ctx = build_market_context(sig)

print("Signal:", sig)
print("Context:", ctx)
