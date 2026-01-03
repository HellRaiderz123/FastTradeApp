from app.services.market_data import *

spot = get_spot("NIFTY")
atm = pick_atm_strike("NIFTY", spot)
chain = get_option_chain("NIFTY")
ltp = get_option_ltp([chain.iloc[0]["tradingsymbol"]])
chain_oi = enrich_chain_with_live_oi(chain, atm, "NIFTY")

print("Spot:", spot)
print("ATM:", atm)
print(chain.head())
print("LTP:", ltp)
print(chain_oi.head())
