def decide_strategy(sig, market_mode, iv_regime, confidence, min_conf):
    bias = sig["technical_analysis"]["bias"]
    rec = sig["recommendation"]

    take_bull = rec == "BUY_CE" or (bias == "BULLISH" and rec != "BUY_PE")
    take_bear = rec == "BUY_PE" or (bias == "BEARISH" and rec != "BUY_CE")

    if market_mode == "TRENDING" and iv_regime in ["LOW", "NORMAL"]:
        spread_min_conf = 65 if iv_regime == "LOW" else min_conf
        if confidence >= spread_min_conf:
            if take_bull:
                return "BULL_PUT", "Trending + bullish bias"
            if take_bear:
                return "BEAR_CALL", "Trending + bearish bias"

    if market_mode == "RANGE" and iv_regime == "HIGH":
        return "IRON_CONDOR", "Range + high IV"

    return "NO_TRADE", "Capital protection"
