from datetime import date, timedelta

def _is_last_weekday_of_month(expiry: date) -> bool:
    """Return True if expiry is the last occurrence of its weekday in the month."""
    return (expiry + timedelta(days=7)).month != expiry.month

def format_zerodha_expiry(expiry: date) -> str:
    """
    Format expiry date for Zerodha symbol construction.
    
    Monthly: 2026-01-29 → 26JAN
    Weekly:  2026-02-10 → 26210  (YY + M + D, no zero-padding on month/day)
    Weekly:  2026-02-17 → 26217  
    Weekly:  2026-12-03 → 261203 (YY + M + D)
    """
    if _is_last_weekday_of_month(expiry):
        # Monthly format: YYMMMM (e.g., 26JAN)
        return expiry.strftime("%y%b").upper()
    
    # Weekly format: YYMD where single-digit month/day have NO zero padding
    # Feb 10, 2026 → 26 + 2 + 10 → 26210 (not 260210)
    year = expiry.year % 100  # Last 2 digits of year
    month = expiry.month      # Month as 1-12 (no zero padding)
    day = expiry.day          # Day as 1-31 (no zero padding)
    return f"{year}{month}{day}"

# Test with BANKNIFTY expiries
print("=" * 70)
print("TESTING format_zerodha_expiry FOR BANKNIFTY")
print("=" * 70)

# Feb 18, 2026 (Wednesday) - should be WEEKLY
feb_18 = date(2026, 2, 18)
is_last = _is_last_weekday_of_month(feb_18)
formatted = format_zerodha_expiry(feb_18)
print(f"\n1. Feb 18, 2026 (Wednesday)")
print(f"   Is last weekday of month? {is_last}")
print(f"   Formatted: {formatted}")
print(f"   Full symbol: BANKNIFTY{formatted}61100CE")

# Feb 25, 2026 (Wednesday) - should be MONTHLY
feb_25 = date(2026, 2, 25)
is_last_25 = _is_last_weekday_of_month(feb_25)
formatted_25 = format_zerodha_expiry(feb_25)
print(f"\n2. Feb 25, 2026 (Wednesday)")
print(f"   Is last weekday of month? {is_last_25}")
print(f"   Formatted: {formatted_25}")
print(f"   Full symbol: BANKNIFTY{formatted_25}61100CE")

# March 4, 2026 (Wednesday) - should be WEEKLY
mar_4 = date(2026, 3, 4)
is_last_mar4 = _is_last_weekday_of_month(mar_4)
formatted_mar4 = format_zerodha_expiry(mar_4)
print(f"\n3. March 4, 2026 (Wednesday)")
print(f"   Is last weekday of month? {is_last_mar4}")
print(f"   Formatted: {formatted_mar4}")
print(f"   Full symbol: BANKNIFTY{formatted_mar4}61100CE")

print("\n" + "=" * 70)
print("COMPARISON WITH USER'S SYMBOLS")
print("=" * 70)
print(f"\nUser reported: BANKNIFTY2621861100CE")
print(f"Our format:    BANKNIFTY{formatted}61100CE")
if f"BANKNIFTY{formatted}61100CE" == "BANKNIFTY2621861100CE":
    print("✅ FORMATS MATCH! Symbol is correct.")
else:
    print("❌ FORMATS DON'T MATCH!")

print("\n💡 If LTP is ₹0, the issue might be:")
print("   1. This expiry hasn't started trading yet (too far in advance)")
print("   2. Market data fetch is failing")
print("   3. Need to verify against actual Zerodha instruments.csv")
