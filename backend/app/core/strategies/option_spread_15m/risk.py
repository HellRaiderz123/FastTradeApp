def risk_check(short_strike, long_strike, spot, capital, lot_size, lots, iv_regime):
    if iv_regime == "LOW":
        min_dist, max_risk = 0.5, 4
    elif iv_regime == "NORMAL":
        min_dist, max_risk = 0.6, 2
    else:
        min_dist, max_risk = 0.8, 1

    dist = abs(short_strike - spot) / spot * 100
    if dist < min_dist:
        return False, "Strike too close to ATM"

    width = abs(short_strike - long_strike)
    max_loss = width * lot_size * lots
    if (max_loss / capital) * 100 > max_risk:
        return False, "Risk exceeds capital limit"

    return True, ""
