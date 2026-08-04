import sys
sys.path.insert(0, '/app')
from app.db.session import SessionLocal
from app.db.models_intent import ExecutionIntent
from app.core.execution.base import get_ticket
from app.core.market.ltp import get_ltp

db = SessionLocal()
intents = db.query(ExecutionIntent).filter(ExecutionIntent.status == 'EXECUTED').all()
for i in intents:
    ticket = get_ticket(i)
    lot_size = ticket.get('lot_size', 1)
    lots = ticket.get('lots', 1)
    ticket_qty = int(lot_size) * int(lots)
    legs = ticket.get('legs', [])
    symbols = [leg.get('symbol') or '' for leg in legs]
    ltp_map = get_ltp(symbols)
    print(f"\n{i.underlying}: lot_size={lot_size} lots={lots} ticket_qty={ticket_qty}")
    pnl = 0.0
    for leg in legs:
        sym = leg.get('symbol')
        entry = leg.get('price') or leg.get('premium')
        current = ltp_map.get(sym)
        raw_qty = leg.get('qty', leg.get('quantity'))
        side = (leg.get('side') or leg.get('action') or '').upper()
        # replicate _resolve_leg_qty
        if raw_qty is None:
            leg_qty = max(1, ticket_qty)
        else:
            value = int(raw_qty)
            if value <= 0:
                leg_qty = max(1, ticket_qty)
            elif value <= 10 and ticket_qty > 1:
                leg_qty = value * ticket_qty
            else:
                leg_qty = value
        sign = 1.0 if side == 'SELL' else -1.0
        if entry and current and float(current) > 0:
            leg_pnl = (float(entry) - float(current)) * sign * leg_qty
        else:
            leg_pnl = 0
        pnl += leg_pnl
        print(f"  leg: sym={sym} side={side} entry={entry} current={current} raw_qty={raw_qty} leg_qty={leg_qty} sign={sign} leg_pnl={leg_pnl}")
    print(f"  TOTAL pnl={round(pnl,2)}")
db.close()
