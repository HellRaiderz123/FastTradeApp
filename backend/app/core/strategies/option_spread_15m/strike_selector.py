def compute_strikes(atm, spot, step, risk_mode, iv_regime):
    width = step * (2 if risk_mode == "Conservative" else 1)
    short_offset = step if risk_mode == "Conservative" else 0

    if iv_regime == "LOW":
        short_offset = max(short_offset, step * 2)
        width = max(width, step * 2)

    return {
        "bull": (atm - short_offset, atm - short_offset - width),
        "bear": (atm + short_offset, atm + short_offset + width),
        "width": width
    }
