from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
import pandas as pd

from app.core.backtest.metrics import MetricsCalculator
from app.core.backtest.options_pricing import CandleSeries, fetch_option_series
from app.core.broker.zerodha.instruments import load_instruments
from app.core.broker.zerodha_symbols import build_zerodha_option_symbol
from app.core.data.candles import get_historical_candles
from app.core.market.expiry import get_weekly_expiry_for_date
from app.core.signals.signals import generate_signal_from_candles
from app.core.strategies.option_spread_15m.context import build_market_context
from app.core.strategies.option_spread_15m.decision import decide_strategy
from app.core.strategies.option_spread_15m.strikes import SpreadStrikes, compute_spread_strikes

logger = logging.getLogger(__name__)


def _dt_from_candle(candle: dict) -> datetime:
    d = candle.get("date")
    t = candle.get("time")
    if isinstance(d, date) and isinstance(t, time):
        return datetime.combine(d, t)
    if isinstance(d, date):
        return datetime.combine(d, time(0, 0))
    raise ValueError("Candle missing date/time")


def _lot_size_for_underlying(underlying: str) -> int:
    lot_size_map = {
        "NIFTY": 65,
        "BANKNIFTY": 15,
        "FINNIFTY": 40,
    }
    return int(lot_size_map.get((underlying or "").upper().strip(), 1))


@dataclass
class OptionLeg:
    side: str  # BUY / SELL
    symbol: str


@dataclass
class OptionsTrade:
    entry_ts: datetime
    exit_ts: Optional[datetime]
    underlying: str
    strategy: str
    legs: List[OptionLeg]
    lot_size: int
    lots: int
    entry_credit: float  # per-unit (not * qty)
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None
    max_unrealized_pnl: float = 0.0

    def qty(self) -> int:
        return int(self.lot_size * self.lots)


class OptionsBacktestEngine:
    """Options-aware backtest for credit spreads/condors.

    Prices each option leg using Zerodha historical candles for the contract.

    Limitations:
    - Requires the option contracts (tradingsymbols) to exist in current Zerodha
      instruments dump to resolve instrument_token. This generally works best for
      very recent days / current expiry.
    """

    def __init__(self, strategy_config: Any, db: Session):
        self.config = strategy_config
        self.db = db
        self.trades: List[OptionsTrade] = []
        self.equity_curve: List[float] = []
        self.candles_loaded: int = 0
        self.signal_counts: Dict[str, int] = {"BULL_PUT": 0, "BEAR_CALL": 0, "IRON_CONDOR": 0, "NO_TRADE": 0}

        # Loaded lazily in run() with snapshot support
        self._instruments = pd.DataFrame()

        self._series_cache: Dict[str, CandleSeries] = {}

    def run(self, start_date: date, end_date: date, initial_capital: float = 100000) -> Dict[str, Any]:
        starting_capital = float(initial_capital)
        # Load instruments snapshot (if available) for the backtest start date.
        # This is critical for old backtests because expired contracts are often
        # missing from today's live instruments dump.
        try:
            self._instruments = load_instruments(exchange="NFO", asof_date=start_date)
        except TypeError:
            # Backward compat if signature differs
            self._instruments = load_instruments()

        if getattr(self._instruments, "empty", True):
            logger.warning("⚠️ Instruments list is empty; options backtest will fail")
        underlying = str(self.config.underlying or "").upper().strip()
        if not underlying:
            return {"success": False, "error": "StrategyConfig.underlying missing"}

        lots = int((self.config.parameters or {}).get("lots", 1) or 1)
        risk_mode = str((self.config.parameters or {}).get("risk_mode", "Conservative"))
        min_confidence = float((self.config.parameters or {}).get("min_confidence", 75) or 75)
        capital = float((self.config.parameters or {}).get("capital", initial_capital) or initial_capital)

        tp_pct = float((self.config.parameters or {}).get("tp_pct", 0) or 0)
        sl_pct = float((self.config.parameters or {}).get("sl_pct", 0) or 0)
        trailing_sl_pct = float((self.config.parameters or {}).get("trailing_sl_pct", 0) or 0)

        entry_time_raw = str((self.config.parameters or {}).get("entry_time", "09:20") or "09:20")
        exit_time_raw = str((self.config.parameters or {}).get("exit_time", "15:20") or "15:20")
        try:
            entry_time = time.fromisoformat(entry_time_raw)
        except Exception:
            entry_time = time(9, 20)
        try:
            exit_time = time.fromisoformat(exit_time_raw)
        except Exception:
            exit_time = time(15, 20)

        # Use isolated candle symbol in DB to avoid contaminating TA with other ranges
        backtest_symbol = f"{underlying}__BTOPT__{self.config.id}"

        candles = get_historical_candles(underlying, start_date, end_date, "15minute")
        if not candles:
            return {"success": False, "error": "No underlying candles available"}

        self.candles_loaded = len(candles)

        pricing_missing_count = 0
        pricing_missing_symbols: List[str] = []

        current_equity = float(starting_capital)
        open_trade: Optional[OptionsTrade] = None

        # Pre-calc window for option series fetches
        from_dt = _dt_from_candle(candles[0])
        to_dt = _dt_from_candle(candles[-1])

        # Keep candle history in memory for TA (no DB writes needed)
        _candle_history: List[Dict] = []

        for candle in candles:
            ts = _dt_from_candle(candle)

            # Accumulate candles in memory for TA computation
            _candle_history.append(candle)

            # Generate signal from in-memory candles (100x faster than DB round-trip)
            sig = generate_signal_from_candles(
                candles=_candle_history,
                india_vix=15.0,
                vix_rank=50.0,
                iv_regime="NORMAL",
            )
            confidence = float(sig.get("confidence", 0.0))
            ctx = build_market_context(sig)

            strategy_mode, _reason = decide_strategy(
                sig=sig,
                ctx=ctx,
                confidence=confidence,
                min_confidence=min_confidence,
            )
            self.signal_counts[strategy_mode] = self.signal_counts.get(strategy_mode, 0) + 1

            spot = float(candle.get("close") or 0.0)

            in_entry_window = entry_time <= ts.time() <= exit_time
            past_exit_time = ts.time() >= exit_time

            # If we have an open options position, MTM it every candle
            if open_trade:
                mtm = self._position_mtm(open_trade, ts)
                current_equity = starting_capital + mtm
                if mtm > float(open_trade.max_unrealized_pnl or 0.0):
                    open_trade.max_unrealized_pnl = float(mtm)

            # Entry/exit logic (minimal):
            # - Enter when strategy suggests a supported structure and no open position.
            # - If suggestion changes to a different supported structure, exit+re-enter.
            # - If NO_TRADE, exit the open position.
            should_exit = False
            should_enter = False
            exit_reason: Optional[str] = None

            if open_trade:
                # Forced exit at configured exit_time
                if past_exit_time:
                    should_exit = True
                    exit_reason = "TIME_EXIT"
                else:
                    # Risk exits based on % of entry credit value
                    credit_value = float(open_trade.entry_credit) * float(open_trade.qty())
                    credit_basis = abs(credit_value) if abs(credit_value) > 1e-9 else 1.0

                    if tp_pct > 0:
                        tp_threshold = credit_basis * (tp_pct / 100.0)
                        if mtm >= tp_threshold:
                            should_exit = True
                            exit_reason = "TAKE_PROFIT"

                    if not should_exit and sl_pct > 0:
                        sl_threshold = credit_basis * (sl_pct / 100.0)
                        if mtm <= -sl_threshold:
                            should_exit = True
                            exit_reason = "STOP_LOSS"

                    if not should_exit and trailing_sl_pct > 0 and float(open_trade.max_unrealized_pnl or 0.0) > 0:
                        trail_threshold = credit_basis * (trailing_sl_pct / 100.0)
                        if mtm <= float(open_trade.max_unrealized_pnl) - trail_threshold:
                            should_exit = True
                            exit_reason = "TRAILING_STOP"

                # Signal-based exits (only if no risk/time exit fired)
                if not should_exit:
                    if strategy_mode == "NO_TRADE":
                        should_exit = True
                        exit_reason = "SIGNAL_NO_TRADE"
                    elif strategy_mode != open_trade.strategy and strategy_mode in {"BULL_PUT", "BEAR_CALL", "IRON_CONDOR"}:
                        should_exit = True
                        exit_reason = "SIGNAL_SWITCH"
                        # Only re-enter if still within entry window
                        should_enter = in_entry_window
            else:
                if in_entry_window and strategy_mode in {"BULL_PUT", "BEAR_CALL", "IRON_CONDOR"}:
                    should_enter = True

            if open_trade and should_exit:
                mtm = self._position_mtm(open_trade, ts)
                open_trade.exit_ts = ts
                open_trade.pnl = mtm
                open_trade.exit_reason = exit_reason or "EXIT"
                self.trades.append(open_trade)
                starting_capital = starting_capital + mtm
                current_equity = starting_capital
                open_trade = None

            if should_enter:
                # Build strikes + ticket legs using current spot
                expiry = get_weekly_expiry_for_date(underlying, ts.date())
                strikes = compute_spread_strikes(
                    underlying=underlying,
                    spot=spot,
                    atm=int(round(spot / (50 if underlying == "NIFTY" else 100)) * (50 if underlying == "NIFTY" else 100)),
                    risk_mode=risk_mode,
                    iv_regime=str(ctx.get("iv_regime") or "NORMAL"),
                    recommendation=str(sig.get("recommendation") or "NO_TRADE"),
                )

                legs, lot_size = self._build_legs(underlying, expiry, strategy_mode, strikes)
                try:
                    entry_credit = self._entry_credit(legs, ts, from_dt, to_dt)
                except KeyError as e:
                    # Most common reason: instruments dump does not include expired contracts.
                    pricing_missing_count += 1
                    msg = str(e)
                    for leg in legs:
                        if leg.symbol not in pricing_missing_symbols:
                            pricing_missing_symbols.append(leg.symbol)
                    logger.warning(f"⚠️ Options pricing unavailable at {ts}: {msg}")
                    entry_credit = None

                if entry_credit is None:
                    # Skip entry if we can't price the legs
                    self.equity_curve.append(current_equity)
                    continue

                open_trade = OptionsTrade(
                    entry_ts=ts,
                    exit_ts=None,
                    underlying=underlying,
                    strategy=strategy_mode,
                    legs=legs,
                    lot_size=lot_size,
                    lots=lots,
                    entry_credit=entry_credit,
                    max_unrealized_pnl=0.0,
                )

            # Equity curve (per candle)
            self.equity_curve.append(current_equity)

        # Close any open trade at end
        if open_trade:
            ts = _dt_from_candle(candles[-1])
            mtm = self._position_mtm(open_trade, ts)
            open_trade.exit_ts = ts
            open_trade.pnl = mtm
            open_trade.exit_reason = open_trade.exit_reason or "EOD"
            self.trades.append(open_trade)
            starting_capital = starting_capital + mtm

        final_equity = float(starting_capital)

        # Compute actual trading days for proper annualization
        unique_dates = set()
        for t in self.trades:
            if t.entry_ts:
                unique_dates.add(t.entry_ts.date())
            if t.exit_ts:
                unique_dates.add(t.exit_ts.date())
        trading_days = len(unique_dates) if unique_dates else max(1, len(self.equity_curve) // 26)

        calc = MetricsCalculator(
            initial_capital=float(self.equity_curve[0] if self.equity_curve else initial_capital),
            final_equity=final_equity,
            equity_curve=self.equity_curve,
            trades=self.trades,
            trading_days=trading_days,
        )
        metrics = calc.calculate_all()
        drawdown_periods = calc.calculate_drawdown_periods()

        return {
            "success": True,
            "strategy_config_id": self.config.id,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": float(self.equity_curve[0] if self.equity_curve else initial_capital),
            "final_equity": final_equity,
            "total_return_pct": metrics["total_return_pct"],
            "annual_return_pct": metrics["annual_return_pct"],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "sortino_ratio": metrics["sortino_ratio"],
            "max_drawdown_pct": metrics["max_drawdown_pct"],
            "calmar_ratio": metrics["calmar_ratio"],
            "total_trades": metrics["total_trades"],
            "winning_trades": metrics["winning_trades"],
            "losing_trades": metrics["losing_trades"],
            "win_rate_pct": metrics["win_rate_pct"],
            "profit_factor": metrics["profit_factor"],
            "avg_win": metrics["avg_win"],
            "avg_loss": metrics["avg_loss"],
            "largest_win": metrics["largest_win"],
            "largest_loss": metrics["largest_loss"],
            "total_profit": metrics["total_profit"],
            "total_loss": metrics["total_loss"],
            "peak_equity": metrics["peak_equity"],
            "trades": [
                {
                    "entry_date": t.entry_ts.date().isoformat(),
                    "exit_date": (t.exit_ts.date().isoformat() if t.exit_ts else None),
                    "entry_price": float(t.entry_credit),
                    "exit_price": (
                        float(t.entry_credit - ((t.pnl or 0.0) / float(t.qty())))
                        if t.qty() > 0 and t.pnl is not None
                        else None
                    ),
                    "quantity": t.qty(),
                    "pnl": t.pnl,
                    "pnl_pct": (
                        float((t.pnl / (abs(float(t.entry_credit)) * float(t.qty()))) * 100.0)
                        if t.qty() > 0 and t.pnl is not None and abs(float(t.entry_credit)) > 1e-9
                        else 0.0
                    ),
                    "strategy": t.strategy,
                    "exit_reason": t.exit_reason,
                    "legs": [{"side": l.side, "symbol": l.symbol} for l in t.legs],
                }
                for t in self.trades
            ],
            "equity_curve": self.equity_curve,
            "drawdown_periods": drawdown_periods,
            "candles_loaded": self.candles_loaded,
            "signal_counts": self.signal_counts,
            "pricing_missing_count": pricing_missing_count,
            "pricing_missing_symbols": pricing_missing_symbols[:20],
        }

    def _build_legs(self, underlying: str, expiry: date, mode: str, strikes: SpreadStrikes) -> Tuple[List[OptionLeg], int]:
        lot_size = _lot_size_for_underlying(underlying)

        if not self._instruments.empty:
            df = self._instruments
            try:
                lot_rows = df[(df["name"] == underlying) & (pd.to_datetime(df["expiry"]).dt.date == expiry)]
                if not lot_rows.empty and lot_rows.iloc[0].get("lot_size"):
                    lot_size = int(lot_rows.iloc[0]["lot_size"])
            except Exception:
                pass

        legs: List[OptionLeg] = []

        if mode == "BULL_PUT":
            short_strike, long_strike = strikes["bull"]
            legs = [
                OptionLeg(
                    side="SELL",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(short_strike), option_type="PE"
                    ),
                ),
                OptionLeg(
                    side="BUY",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(long_strike), option_type="PE"
                    ),
                ),
            ]
        elif mode == "BEAR_CALL":
            short_strike, long_strike = strikes["bear"]
            legs = [
                OptionLeg(
                    side="SELL",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(short_strike), option_type="CE"
                    ),
                ),
                OptionLeg(
                    side="BUY",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(long_strike), option_type="CE"
                    ),
                ),
            ]
        elif mode == "IRON_CONDOR":
            short_put, long_put, short_call, long_call = strikes["condor"]
            legs = [
                OptionLeg(
                    side="SELL",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(short_put), option_type="PE"
                    ),
                ),
                OptionLeg(
                    side="BUY",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(long_put), option_type="PE"
                    ),
                ),
                OptionLeg(
                    side="SELL",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(short_call), option_type="CE"
                    ),
                ),
                OptionLeg(
                    side="BUY",
                    symbol=build_zerodha_option_symbol(
                        underlying=underlying, expiry=expiry, strike=int(long_call), option_type="CE"
                    ),
                ),
            ]
        else:
            raise ValueError(f"Unsupported strategy_mode: {mode}")

        return legs, lot_size

    def _get_series(self, symbol: str, from_dt: datetime, to_dt: datetime) -> CandleSeries:
        cached = self._series_cache.get(symbol)
        if cached is not None:
            return cached

        series = fetch_option_series(
            symbol,
            from_dt,
            to_dt,
            interval="15minute",
            instruments_df=(self._instruments if not getattr(self._instruments, "empty", True) else None),
        )
        self._series_cache[symbol] = series
        return series

    def _entry_credit(self, legs: List[OptionLeg], ts: datetime, from_dt: datetime, to_dt: datetime) -> float:
        # credit per unit
        credit = 0.0
        for leg in legs:
            series = self._get_series(leg.symbol, from_dt, to_dt)
            px = series.price_at(ts)
            if leg.side == "SELL":
                credit += px
            else:
                credit -= px
        return float(credit)

    def _position_mtm(self, trade: OptionsTrade, ts: datetime) -> float:
        # Per-unit close debit is: sum(short_px) - sum(long_px)
        debit = 0.0
        # Reuse the entry window for series cache (we always fetch full backtest range)
        from_dt = trade.entry_ts
        to_dt = ts
        # Note: _get_series caches by symbol, so repeated calls are cheap
        for leg in trade.legs:
            series = self._get_series(leg.symbol, from_dt, to_dt)
            px = series.price_at(ts)
            if leg.side == "SELL":
                debit += px
            else:
                debit -= px

        pnl_per_unit = float(trade.entry_credit - debit)
        return pnl_per_unit * trade.qty()
