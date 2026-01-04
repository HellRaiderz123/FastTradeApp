from typing import Dict, Any, List
from app.core.utils.time import now_ist
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol


class ZerodhaExecutionAdapter:
    def __init__(self, kite_client, dry_run: bool = True):
        self.kite = kite_client
        self.dry_run = dry_run

    def execute(self, intent) -> Dict[str, Any]:
        orders = self._build_orders(intent)

        if self.dry_run:
            # 🔒 SAFE validation call
            self.kite.instruments("NFO")  # fails if token invalid
            return {
                "mode": "ZERODHA_DRY_RUN",
                "orders": orders,
                "created_at": now_ist().isoformat(),
            }

        # 🔴 LIVE (later)
        # place orders via kite.place_order(...)
        raise NotImplementedError

    def exit(self, intent) -> Dict[str, Any]:
        exit_orders = self._build_exit_orders(intent)

        if self.dry_run:
            return {
                "mode": "ZERODHA_DRY_RUN",
                "exit_orders": exit_orders,
                "exited_at": now_ist().isoformat(),
            }

        raise NotImplementedError

    def _build_orders(self, intent):
        orders = []

        ticket = intent.ticket
        lots = ticket["lots"]
        lot_size = ticket["lot_size"]

        qty = lots * lot_size

        for leg in ticket["legs"]:
            tradingsymbol = build_zerodha_option_symbol(
                underlying=intent.underlying,
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

    # ✅ OPTIONAL but recommended
    def _build_exit_orders(self, intent) -> List[Dict[str, Any]]:
        ticket = intent.ticket
        lots = ticket["lots"]
        lot_size = ticket["lot_size"]
        qty = lots * lot_size

        exit_orders = []

        for leg in ticket["legs"]:
            exit_orders.append({
                "tradingsymbol": self._map_symbol(
                    underlying=intent.underlying,
                    strike=leg["strike"],
                    opt_type=leg["type"],
                ),
                "exchange": "NFO",
                "transaction_type": "BUY" if leg["side"] == "SELL" else "SELL",
                "quantity": qty,
                "order_type": "MARKET",
                "product": "NRML",
                "validity": "DAY",
            })

        return exit_orders

    def _map_symbol(self, underlying: str, strike: int, opt_type: str) -> str:
        """
        TEMP mapping — replace with expiry-aware mapping later
        """
        # Example placeholder
        return f"{underlying}{strike}{opt_type}"
    
    def mtm(self, intent) -> float:
        """
        READ-ONLY MTM using Zerodha LTP
        No orders, no execution
        """

        ticket = intent.ticket
        symbols = []

        for leg in ticket["legs"]:
            symbols.append(f"NFO:{leg['symbol']}")

        # Zerodha LTP fetch
        ltp_map = self.kite.ltp(symbols)

        pnl = 0.0

        for leg in ticket["legs"]:
            sym = f"NFO:{leg['symbol']}"
            price = ltp_map[sym]["last_price"]

            qty = ticket["lot_size"] * ticket["lots"]

            if leg["side"] == "SELL":
                pnl += price * qty
            else:
                pnl -= price * qty

        return pnl