"""
Test the expiry date parsing fix
"""
from datetime import date
from app.core.execution.zerodha import _parse_expiry

def test_expiry_parsing():
    print("="*60)
    print("Testing Expiry Date Parsing")
    print("="*60)
    
    # Test 1: String format
    print("\n1️⃣ Test String Format (YYYY-MM-DD)")
    expiry_str = "2026-01-15"
    result = _parse_expiry(expiry_str)
    print(f"   Input: '{expiry_str}'")
    print(f"   Output: {result}")
    print(f"   Type: {type(result)}")
    assert isinstance(result, date), "Should return date object"
    assert result == date(2026, 1, 15), "Should parse correctly"
    print("   ✅ PASSED")
    
    # Test 2: Date object
    print("\n2️⃣ Test Date Object Input")
    expiry_date = date(2026, 1, 15)
    result = _parse_expiry(expiry_date)
    print(f"   Input: {expiry_date}")
    print(f"   Output: {result}")
    print(f"   Type: {type(result)}")
    assert result == expiry_date, "Should return same date object"
    print("   ✅ PASSED")
    
    # Test 3: None input
    print("\n3️⃣ Test None Input")
    result = _parse_expiry(None)
    print(f"   Input: None")
    print(f"   Output: {result}")
    assert result is None, "Should return None"
    print("   ✅ PASSED")
    
    # Test 4: Invalid string
    print("\n4️⃣ Test Invalid String")
    result = _parse_expiry("invalid-date")
    print(f"   Input: 'invalid-date'")
    print(f"   Output: {result}")
    assert result is None, "Should return None for invalid input"
    print("   ✅ PASSED")
    
    # Test 5: Test with strftime (what was failing)
    print("\n5️⃣ Test strftime() Call")
    expiry_str = "2026-01-15"
    result = _parse_expiry(expiry_str)
    formatted = result.strftime("%y%b").upper()
    print(f"   Input: '{expiry_str}'")
    print(f"   Formatted: {formatted}")
    assert formatted == "26JAN", "Should format correctly"
    print("   ✅ PASSED")
    
    print("\n" + "="*60)
    print("✅ All expiry parsing tests passed!")
    print("="*60)

if __name__ == "__main__":
    test_expiry_parsing()
