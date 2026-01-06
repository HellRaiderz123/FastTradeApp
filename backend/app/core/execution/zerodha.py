from typing import Dict, Any, List
from app.core.utils.time import now_ist
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol


class ZerodhaExecutionAdapter:
    def __init__(self, kite_client, dry_run: bool = True):
        self.kite = kite_client
        self.dry_run = dry_run

    # ============================
    # EXECUTION (DRY-RUN ONLY)
    # ============================
    def execute(self, intent) -> Dict[str, Any]:
        orders = self._build_orders(intent)

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "orders": orders,
                "created_at": now_ist().isoformat(),
            }

        # 🔴 LIVE execution to be added later
        raise NotImplementedError("Live Zerodha execution not enabled")

    # ============================
    # EXIT
    # ============================
    def exit(self, intent) -> Dict[str, Any]:
        exit_orders = self._build_exit_orders(intent)

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "exit_orders": exit_orders,
                "exited_at": now_ist().isoformat(),
            }

        raise NotImplementedError("Live Zerodha exit not enabled")

    # ============================
    # ORDER BUILDERS
    # ============================
    def _build_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = intent.ticket
        qty = ticket["lots"] * ticket["lot_size"]

        orders = []

        for leg in ticket["legs"]:
            tradingsymbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
                expiry=intent.expiry,          # ✅ REQUIRED
                strike=leg["strike"],
                option_type=leg["type"],
            )

            orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "SELL" if leg["side"] == "SELL" else "BUY",
                "quantity": qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return orders

    def _build_exit_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = intent.ticket
        qty = ticket["lots"] * ticket["lot_size"]

        exit_orders = []

        for leg in ticket["legs"]:
            tradingsymbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
                expiry=intent.expiry,
                strike=leg["strike"],
                option_type=leg["type"],
            )

            exit_orders.append({
                "tradingsymbol": tradingsymbol,
                "exchange": "NFO",
                "transaction_type": "BUY" if leg["side"] == "SELL" else "SELL",
                "quantity": qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return exit_orders

    # ============================
    # MTM (READ ONLY)
    # ============================
    def mtm(self, intent) -> float:
        """
        Mark-to-market PnL using Zerodha LTP.
        Requires entry_price per leg.
        """

        ticket = intent.ticket
        qty = ticket["lot_size"] * ticket["lots"]

        symbols = []
        for leg in ticket["legs"]:
            symbols.append(f"NFO:{leg['symbol']}")

        ltp_map = self.kite.ltp(symbols)

        pnl = 0.0

        for leg in ticket["legs"]:
            sym = f"NFO:{leg['symbol']}"
            ltp = ltp_map[sym]["last_price"]
            entry = leg["entry_price"]  # ✅ MUST exist

            if leg["side"] == "SELL":
                pnl += (entry - ltp) * qty
            else:
                pnl += (ltp - entry) * qty

        return pnl
