def get_ltp(symbols: list[str]) -> dict[str, float]:
    """
    Mock LTP with realistic spread behavior:
    - Short leg higher premium
    - Long leg lower premium
    """
    ltp = {}

    for sym in symbols:
        # crude but effective parsing
        # e.g. 22350PE, 22250PE
        strike = int("".join(filter(str.isdigit, sym)))

        # ATM-ish options have higher premium
        if strike % 100 == 50:        # closer to ATM
            ltp[sym] = 110.0
        else:                         # further OTM hedge
            ltp[sym] = 40.0

    return ltp
