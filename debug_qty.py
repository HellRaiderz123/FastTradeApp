import sys
sys.path.insert(0, '/app')
from app.core.execution.paper import PaperExecutionAdapter

def test(label, leg_qty_val, lot_size, lots):
    ticket_qty = lot_size * lots
    leg = {"qty": leg_qty_val, "side": "SELL", "symbol": "TEST"}
    result = PaperExecutionAdapter._resolve_leg_qty(leg, ticket_qty)
    expected = lot_size * lots  # always should be total shares
    status = "OK" if result == expected else f"WRONG (expected {expected})"
    print(f"{label}: leg.qty={leg_qty_val} lot_size={lot_size} lots={lots} ticket_qty={ticket_qty} -> resolved={result} {status}")

# Stock cases (lot_size=1)
test("Stock qty=shares",     6,  1, 6)    # NESTLEIND: qty=6, lots=6 -> should be 6
test("Stock qty=1",          1,  1, 1)    # single stock

# Option cases (lot_size > 1, qty stored as total shares after execute())
test("NIFTY 1lot qty=75",   75, 75, 1)   # qty already total
test("NIFTY 2lot qty=150", 150, 75, 2)   # qty already total
test("BANKNIFTY 1lot",      15, 15, 1)
test("BANKNIFTY 2lot",      30, 15, 2)

# Option edge case: qty stored as lot count (old-style tickets)
test("NIFTY lot-count=1",    1, 75, 1)   # qty=1 means 1 lot -> should resolve to 75
test("NIFTY lot-count=2",    2, 75, 2)   # qty=2 means 2 lots -> should resolve to 150
test("NIFTY lot-count=1 2lots", 1, 75, 2) # qty=1 lot, ticket=2lots -> ambiguous
