import sys
sys.path.insert(0, ".")
try:
    import app.main
    print("OK - app.main imported successfully")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
