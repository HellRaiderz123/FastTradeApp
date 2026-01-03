from .decision import decide_strategy
from .strike_selector import compute_strikes
from .risk import risk_check
from .models import SpreadTicket, SpreadLeg, StrategyResult

def run_option_spread(context):
    mode, reason = decide_strategy(
        context["signal"],
        context["market_mode"],
        context["iv_regime"],
        context["confidence"],
        context["min_conf"]
    )

    if mode == "NO_TRADE":
        return StrategyResult(
            strategy_mode="NO_TRADE",
            approved=False,
            reason=reason,
            ticket=None,
            metrics={},
            blocked_by=[]
        )

    strikes = compute_strikes(
        context["atm"],
        context["spot"],
        context["step"],
        context["risk_mode"],
        context["iv_regime"]
    )

    short, long = strikes["bull"] if mode == "BULL_PUT" else strikes["bear"]
    ok, err = risk_check(
        short, long,
        context["spot"],
        context["capital"],
        context["lot_size"],
        context["lots"],
        context["iv_regime"]
    )

    if not ok:
        return StrategyResult(
            strategy_mode=mode,
            approved=False,
            reason=err,
            ticket=None,
            metrics={},
            blocked_by=[err]
        )

    ticket = SpreadTicket(
        strategy=mode,
        underlying=context["underlying"],
        lot_size=context["lot_size"],
        lots=context["lots"],
        legs=[
            SpreadLeg(side="SELL", symbol="AUTO", strike=short, opt_type="PE" if mode=="BULL_PUT" else "CE"),
            SpreadLeg(side="BUY", symbol="AUTO", strike=long, opt_type="PE" if mode=="BULL_PUT" else "CE"),
        ]
    )

    return StrategyResult(
        strategy_mode=mode,
        approved=True,
        reason="Approved",
        ticket=ticket,
        metrics={"width": strikes["width"]},
        blocked_by=[]
    )
