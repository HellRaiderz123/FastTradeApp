"""
Spread Detection Engine
Detects, classifies, and groups option spreads from positions.
Identifies incomplete spreads and naked positions with warnings.
"""

import logging
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from .models import (
    PositionLeg,
    DetectedSpread,
    GroupedPositions,
    SpreadWarning,
    SpreadType,
)

logger = logging.getLogger(__name__)


def _parse_symbol(symbol: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    """
    Parse a Zerodha trading symbol to extract underlying, strike, and option_type.

    Zerodha formats:
      Weekly:  NIFTY + 26 + 2 + 10 + 25800 + PE   → YY + M(1 char) + D(1-2 digits) + strike
      Monthly: NIFTY + 26 + FEB + 25800 + PE       → YY + MON(3 letters) + strike
    
    e.g. 'NIFTY2621025800PE' -> ('NIFTY', 25800, 'PE')
         'BANKNIFTY26FEB51000CE' -> ('BANKNIFTY', 51000, 'CE')
    Returns (underlying, strike, option_type) or (None, None, None) on failure.
    """
    if not symbol:
        return None, None, None

    symbol = symbol.strip().upper()

    # 1. Extract CE/PE suffix
    opt_type = None
    if symbol.endswith("CE"):
        opt_type = "CE"
        body = symbol[:-2]
    elif symbol.endswith("PE"):
        opt_type = "PE"
        body = symbol[:-2]
    else:
        return None, None, None

    # 2. Extract underlying (leading alphabetic chars, e.g. NIFTY, BANKNIFTY)
    i = 0
    while i < len(body) and body[i].isalpha():
        i += 1
    if i == 0 or i >= len(body):
        return None, None, None

    underlying = body[:i]
    rest = body[i:]  # everything between underlying and CE/PE

    # 3. Check for monthly format (contains letters like "26FEB")
    has_letters = any(c.isalpha() for c in rest)
    if has_letters:
        # Monthly: YY(2 digits) + MON(3 letters) + strike
        if len(rest) >= 6:
            strike_str = rest[5:]  # skip "26FEB"
            try:
                return underlying, int(strike_str), opt_type
            except ValueError:
                return underlying, None, opt_type
        return underlying, None, opt_type

    # 4. Weekly format (all digits): YY(2) + M(1) + D(1-2) + strike
    #    Month: '1'-'9' for Jan-Sep, day: 1-31 (no zero-padding)
    if len(rest) < 5:  # min: 2(yr) + 1(month) + 1(day) + 1(strike digit)
        return underlying, None, opt_type

    month_char = rest[2]
    if not month_char.isdigit() or month_char == "0":
        return underlying, None, opt_type

    # Try 1-digit day first (gives longer/larger strike), then 2-digit day
    for day_len in (1, 2):
        day_start = 3
        day_str = rest[day_start : day_start + day_len]
        if not day_str.isdigit():
            continue
        day_val = int(day_str)
        if day_val < 1 or day_val > 31:
            continue

        strike_str = rest[day_start + day_len :]
        if not strike_str or not strike_str.isdigit():
            continue

        strike = int(strike_str)
        # Strike must be in a realistic range for Indian index/stock options
        # (NIFTY ~15000-30000, BANKNIFTY ~40000-60000, stocks can be lower)
        if 100 <= strike <= 200000:
            return underlying, strike, opt_type

    return underlying, None, opt_type


class SpreadDetector:
    """Main spread detection engine"""

    def __init__(self):
        self.min_confidence = 0.70  # Min confidence to report as a spread

    def group_positions(self, position_legs: List[PositionLeg]) -> GroupedPositions:
        """
        Group positions into spreads and identify issues.
        
        Args:
            position_legs: List of individual position legs from open positions
            
        Returns:
            GroupedPositions with spreads, naked, and incomplete spreads
        """
        spreads = []
        matched_leg_ids: set = set()  # Track matched legs by unique (intent_id, index)
        all_warnings = []

        # Assign a unique _leg_uid to each position leg for tracking
        for i, leg in enumerate(position_legs):
            leg._leg_uid = f"{leg.intent_id}#{i}"  # type: ignore[attr-defined]

        # Group by (underlying, expiry) first
        position_groups = self._group_by_symbol(position_legs)

        for (underlying, expiry), legs in position_groups.items():
            if not legs:
                continue

            # Try to detect spreads from this group
            detected = self._detect_spreads_in_group(underlying, expiry, legs)

            for spread in detected:
                spreads.append(spread)
                all_warnings.extend(spread.warnings)
                for leg in spread.legs:
                    uid = getattr(leg, '_leg_uid', None)
                    if uid:
                        matched_leg_ids.add(uid)

        # Identify unmatched positions (naked or incomplete)
        naked_positions, incomplete_pairs = self._find_unmatched_positions(
            position_legs, matched_leg_ids
        )

        # Create warnings for unmatched
        for leg, warning in incomplete_pairs:
            all_warnings.append(warning)

        return GroupedPositions(
            spreads=spreads,
            naked_positions=naked_positions,
            incomplete_spreads=incomplete_pairs,
            total_warnings=all_warnings,
        )

    def _group_by_symbol(
        self, legs: List[PositionLeg]
    ) -> Dict[Tuple[str, Optional[str]], List[PositionLeg]]:
        """Group position legs by (underlying, expiry)"""
        groups: Dict[Tuple[str, Optional[str]], List[PositionLeg]] = defaultdict(list)
        for leg in legs:
            key = (leg.underlying or "UNKNOWN", leg.expiry)
            groups[key].append(leg)
        return groups

    def _detect_spreads_in_group(
        self, underlying: str, expiry: Optional[str], legs: List[PositionLeg]
    ) -> List[DetectedSpread]:
        """Detect all spreads in a group of related positions.

        Complex patterns (3+ legs) are detected first and their legs are
        claimed so that simpler 2-leg detectors don't double-count them.
        """
        detected: List[DetectedSpread] = []
        claimed_uids: set = set()  # legs already claimed by a complex pattern

        # ── Phase 1: complex multi-leg patterns (detect first, higher priority)
        detected.extend(self._detect_iron_condor(underlying, expiry, legs))
        detected.extend(self._detect_butterflies(underlying, expiry, legs))
        detected.extend(self._detect_ratio_spreads(underlying, expiry, legs))

        # Mark legs used by complex patterns
        for spread in detected:
            for leg in spread.legs:
                uid = getattr(leg, '_leg_uid', None)
                if uid:
                    claimed_uids.add(uid)

        # ── Phase 2: simple 2-leg patterns (only unclaimed legs)
        remaining = [l for l in legs if getattr(l, '_leg_uid', None) not in claimed_uids]
        detected.extend(self._detect_call_spreads(underlying, expiry, remaining))
        detected.extend(self._detect_put_spreads(underlying, expiry, remaining))
        detected.extend(self._detect_straddles_strangles(underlying, expiry, remaining))

        return detected

    def _detect_call_spreads(
        self, underlying: str, expiry: Optional[str], legs: List[PositionLeg]
    ) -> List[DetectedSpread]:
        """Detect Bull Call, Bear Call spreads"""
        detected = []
        called_legs = [l for l in legs if l.option_type == "CE"]

        # Bull Call Spread: BUY lower CE + SELL higher CE
        for i, buy_leg in enumerate(called_legs):
            if buy_leg.side != "BUY":
                continue
            for j, sell_leg in enumerate(called_legs):
                if i == j or sell_leg.side != "SELL":
                    continue
                if buy_leg.strike < sell_leg.strike:
                    spread = DetectedSpread(
                        spread_type="BULL_CALL_SPREAD",
                        underlying=underlying,
                        expiry=expiry,
                        legs=[buy_leg, sell_leg],
                        confidence=0.95,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        # Bear Call Spread: SELL lower CE + BUY higher CE
        for i, sell_leg in enumerate(called_legs):
            if sell_leg.side != "SELL":
                continue
            for j, buy_leg in enumerate(called_legs):
                if i == j or buy_leg.side != "BUY":
                    continue
                if sell_leg.strike < buy_leg.strike:
                    spread = DetectedSpread(
                        spread_type="BEAR_CALL_SPREAD",
                        underlying=underlying,
                        expiry=expiry,
                        legs=[sell_leg, buy_leg],
                        confidence=0.95,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        return detected

    def _detect_put_spreads(
        self, underlying: str, expiry: Optional[str], legs: List[PositionLeg]
    ) -> List[DetectedSpread]:
        """Detect Bull Put, Bear Put spreads"""
        detected = []
        put_legs = [l for l in legs if l.option_type == "PE"]

        # Bull Put Spread: SELL higher PE + BUY lower PE
        for i, sell_leg in enumerate(put_legs):
            if sell_leg.side != "SELL":
                continue
            for j, buy_leg in enumerate(put_legs):
                if i == j or buy_leg.side != "BUY":
                    continue
                if sell_leg.strike > buy_leg.strike:
                    spread = DetectedSpread(
                        spread_type="BULL_PUT_SPREAD",
                        underlying=underlying,
                        expiry=expiry,
                        legs=[sell_leg, buy_leg],
                        confidence=0.95,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        # Bear Put Spread: BUY higher PE + SELL lower PE
        for i, buy_leg in enumerate(put_legs):
            if buy_leg.side != "BUY":
                continue
            for j, sell_leg in enumerate(put_legs):
                if i == j or sell_leg.side != "SELL":
                    continue
                if buy_leg.strike > sell_leg.strike:
                    spread = DetectedSpread(
                        spread_type="BEAR_PUT_SPREAD",
                        underlying=underlying,
                        expiry=expiry,
                        legs=[buy_leg, sell_leg],
                        confidence=0.95,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        return detected

    def _detect_iron_condor(
        self, underlying: str, expiry: Optional[str], legs: List[PositionLeg]
    ) -> List[DetectedSpread]:
        """Detect Iron Condor: Bull Put + Bear Call"""
        detected = []
        put_legs = [l for l in legs if l.option_type == "PE"]
        call_legs = [l for l in legs if l.option_type == "CE"]

        # Iron Condor must have 2 PEs (SELL higher, BUY lower) + 2 CEs (SELL lower, BUY higher)
        for sell_put in put_legs:
            if sell_put.side != "SELL":
                continue
            for buy_put in put_legs:
                if buy_put.side != "BUY" or buy_put.strike >= sell_put.strike:
                    continue
                for sell_call in call_legs:
                    if sell_call.side != "SELL":
                        continue
                    for buy_call in call_legs:
                        if (
                            buy_call.side != "BUY"
                            or buy_call.strike <= sell_call.strike
                        ):
                            continue

                        spread = DetectedSpread(
                            spread_type="IRON_CONDOR",
                            underlying=underlying,
                            expiry=expiry,
                            legs=[sell_put, buy_put, sell_call, buy_call],
                            confidence=0.98,
                            warnings=[],
                        )
                        self._calculate_spread_metrics(spread)
                        detected.append(spread)

        return detected

    def _detect_straddles_strangles(
        self, underlying: str, expiry: Optional[str], legs: List[PositionLeg]
    ) -> List[DetectedSpread]:
        """Detect Long/Short Straddle and Strangle"""
        detected = []

        # Find CE and PE pairs
        call_legs = [l for l in legs if l.option_type == "CE"]
        put_legs = [l for l in legs if l.option_type == "PE"]

        # Long Straddle: BUY CE + BUY PE at same/similar strikes
        for ce in call_legs:
            if ce.side != "BUY":
                continue
            for pe in put_legs:
                if pe.side != "BUY":
                    continue
                # Allow some strike proximity (within 100 points for ATM straddle)
                if abs(ce.strike - pe.strike) <= 100:
                    spread_type = "LONG_STRADDLE" if ce.strike == pe.strike else "LONG_STRANGLE"
                    spread = DetectedSpread(
                        spread_type=spread_type,
                        underlying=underlying,
                        expiry=expiry,
                        legs=[ce, pe],
                        confidence=0.95 if ce.strike == pe.strike else 0.85,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        # Short Straddle: SELL CE + SELL PE at same/similar strikes
        for ce in call_legs:
            if ce.side != "SELL":
                continue
            for pe in put_legs:
                if pe.side != "SELL":
                    continue
                if abs(ce.strike - pe.strike) <= 100:
                    spread_type = "SHORT_STRADDLE" if ce.strike == pe.strike else "SHORT_STRANGLE"
                    spread = DetectedSpread(
                        spread_type=spread_type,
                        underlying=underlying,
                        expiry=expiry,
                        legs=[ce, pe],
                        confidence=0.95 if ce.strike == pe.strike else 0.85,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        return detected

    def _detect_butterflies(
        self, underlying: str, expiry: Optional[str], legs: List[PositionLeg]
    ) -> List[DetectedSpread]:
        """Detect Call/Put Butterfly spreads"""
        detected = []

        # Call Butterfly: BUY lower CE + SELL 2x middle CE + BUY higher CE
        call_legs = [l for l in legs if l.option_type == "CE"]
        strikes_by_side = defaultdict(lambda: defaultdict(list))

        for leg in call_legs:
            strikes_by_side[leg.side][leg.strike].append(leg)

        # Check for 3-strike butterfly pattern
        unique_strikes = sorted(set(l.strike for l in call_legs))
        if len(unique_strikes) >= 3:
            for i in range(len(unique_strikes) - 2):
                low_strike = unique_strikes[i]
                mid_strike = unique_strikes[i + 1]
                high_strike = unique_strikes[i + 2]

                # Find legs
                buy_low = next(
                    (l for l in call_legs if l.strike == low_strike and l.side == "BUY"),
                    None,
                )
                sell_mid = [l for l in call_legs if l.strike == mid_strike and l.side == "SELL"]
                buy_high = next(
                    (l for l in call_legs if l.strike == high_strike and l.side == "BUY"),
                    None,
                )

                if buy_low and len(sell_mid) >= 2 and buy_high:
                    spread = DetectedSpread(
                        spread_type="BUTTERFLY_CALL",
                        underlying=underlying,
                        expiry=expiry,
                        legs=[buy_low, sell_mid[0], sell_mid[1], buy_high],
                        confidence=0.90,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        # Put Butterfly: Similar logic for PEs
        put_legs = [l for l in legs if l.option_type == "PE"]
        strikes_by_side = defaultdict(lambda: defaultdict(list))

        for leg in put_legs:
            strikes_by_side[leg.side][leg.strike].append(leg)

        unique_strikes = sorted(set(l.strike for l in put_legs))
        if len(unique_strikes) >= 3:
            for i in range(len(unique_strikes) - 2):
                low_strike = unique_strikes[i]
                mid_strike = unique_strikes[i + 1]
                high_strike = unique_strikes[i + 2]

                buy_low = next(
                    (l for l in put_legs if l.strike == low_strike and l.side == "BUY"),
                    None,
                )
                sell_mid = [l for l in put_legs if l.strike == mid_strike and l.side == "SELL"]
                buy_high = next(
                    (l for l in put_legs if l.strike == high_strike and l.side == "BUY"),
                    None,
                )

                if buy_low and len(sell_mid) >= 2 and buy_high:
                    spread = DetectedSpread(
                        spread_type="BUTTERFLY_PUT",
                        underlying=underlying,
                        expiry=expiry,
                        legs=[buy_low, sell_mid[0], sell_mid[1], buy_high],
                        confidence=0.90,
                        warnings=[],
                    )
                    self._calculate_spread_metrics(spread)
                    detected.append(spread)

        return detected

    def _detect_ratio_spreads(
        self, underlying: str, expiry: Optional[str], legs: List[PositionLeg]
    ) -> List[DetectedSpread]:
        """Detect ratio spreads and backspreads.

        Handles both classical (2 buys at same strike) and split-strike
        (buys at different OTM strikes) ratio backspreads.

        Call Ratio Backspread: SELL 1x lower CE + BUY ≥2x higher CE(s)
        Put Ratio Backspread:  SELL 1x higher PE + BUY ≥2x lower PE(s)
        """
        detected = []

        # ── Call Ratio Backspread ─────────────────────────────────
        call_legs = [l for l in legs if l.option_type == "CE"]
        call_sells = [l for l in call_legs if l.side == "SELL"]
        call_buys = [l for l in call_legs if l.side == "BUY"]

        for sell_leg in call_sells:
            # Find all BUY CEs at strictly higher strikes
            higher_buys = [b for b in call_buys if b.strike > sell_leg.strike]
            if len(higher_buys) >= 2:
                # Ratio backspread: 1 sell + 2+ buys above
                spread = DetectedSpread(
                    spread_type="RATIO_CALL_BACKSPREAD",
                    underlying=underlying,
                    expiry=expiry,
                    legs=[sell_leg] + higher_buys[:2],
                    confidence=0.90,
                    warnings=[],
                )
                self._calculate_spread_metrics(spread)
                detected.append(spread)

        # ── Put Ratio Backspread ──────────────────────────────────
        put_legs = [l for l in legs if l.option_type == "PE"]
        put_sells = [l for l in put_legs if l.side == "SELL"]
        put_buys = [l for l in put_legs if l.side == "BUY"]

        for sell_leg in put_sells:
            # Find all BUY PEs at strictly lower strikes
            lower_buys = [b for b in put_buys if b.strike < sell_leg.strike]
            if len(lower_buys) >= 2:
                # Ratio backspread: 1 sell + 2+ buys below
                spread = DetectedSpread(
                    spread_type="RATIO_PUT_BACKSPREAD",
                    underlying=underlying,
                    expiry=expiry,
                    legs=[sell_leg] + lower_buys[:2],
                    confidence=0.90,
                    warnings=[],
                )
                self._calculate_spread_metrics(spread)
                detected.append(spread)

        return detected

    def _find_unmatched_positions(
        self, all_legs: List[PositionLeg], matched_leg_ids: set
    ) -> Tuple[List[PositionLeg], List[Tuple[PositionLeg, SpreadWarning]]]:
        """Find unmatched positions (naked or incomplete spreads)"""
        unmatched = [
            leg for leg in all_legs
            if getattr(leg, '_leg_uid', None) not in matched_leg_ids
        ]
        
        naked = []
        incomplete = []

        for leg in unmatched:
            # Skip legs with no valid data (couldn't parse)
            if leg.strike == 0 and leg.option_type in ("CE", "PE"):
                # Still warn but mark as data issue
                warning = SpreadWarning(
                    level="WARNING",
                    message=f"Could not parse position data for intent {leg.intent_id}. Check ticket structure.",
                    affected_intent_ids=[leg.intent_id],
                )
                incomplete.append((leg, warning))
                continue

            # Check if this could be part of an incomplete spread
            warning = self._create_position_warning(leg, unmatched)
            if warning:
                incomplete.append((leg, warning))
            else:
                naked.append(leg)

        return naked, incomplete

    def _create_position_warning(
        self, leg: PositionLeg, all_unmatched: List[PositionLeg]
    ) -> Optional[SpreadWarning]:
        """Create warning for unmatched position"""
        opposite_side = "SELL" if leg.side == "BUY" else "BUY"
        same_type = leg.option_type
        same_underlying = leg.underlying
        same_expiry = leg.expiry
        my_uid = getattr(leg, '_leg_uid', None)

        # Look for matching opposite leg (allow same intent_id, just not the exact same leg)
        matching_legs = [
            l for l in all_unmatched
            if getattr(l, '_leg_uid', None) != my_uid
            and l.side == opposite_side
            and l.option_type == same_type
            and l.underlying == same_underlying
            and l.expiry == same_expiry
        ]

        if matching_legs:
            # Incomplete spread detected
            return SpreadWarning(
                level="WARNING",
                message=f"Incomplete spread: {leg.side} {leg.strike} {leg.option_type} is missing its hedge.",
                affected_intent_ids=[leg.intent_id] + [m.intent_id for m in matching_legs],
                missing_legs=[
                    {
                        "side": opposite_side,
                        "strike": leg.strike,
                        "option_type": same_type,
                    }
                ],
            )
        
        # Naked position
        return SpreadWarning(
            level="CRITICAL",
            message=f"⚠️ NAKED {leg.side} {leg.option_type}: Unhedged position! Strike {leg.strike} has unlimited risk.",
            affected_intent_ids=[leg.intent_id],
            missing_legs=[
                {
                    "side": opposite_side,
                    "strike": leg.strike if leg.side == "BUY" else f"{leg.strike} (hedge needed)",
                    "option_type": same_type,
                }
            ],
        )

    @staticmethod
    def _get_unit_price(leg: PositionLeg) -> float:
        """Get per-unit entry price for a leg.
        Prefers leg.entry_price (from ticket data).  Falls back to
        entry_credit / quantity (intent-level total ÷ qty)."""
        if leg.entry_price is not None and leg.entry_price > 0:
            return leg.entry_price
        if leg.entry_credit and leg.quantity and leg.quantity > 0:
            return leg.entry_credit / leg.quantity
        return 0.0

    def _calculate_spread_metrics(self, spread: DetectedSpread):
        """Calculate max profit, loss, and breakeven for a spread.
        All values returned are in absolute rupees (total, not per-unit)."""
        sell_legs = [l for l in spread.legs if l.side == "SELL"]
        buy_legs = [l for l in spread.legs if l.side == "BUY"]

        credit_per_unit = sum(self._get_unit_price(l) for l in sell_legs)
        debit_per_unit = sum(self._get_unit_price(l) for l in buy_legs)
        net_credit = credit_per_unit - debit_per_unit  # positive for credit spreads

        # Use quantity from first leg (all legs in a proper spread should match)
        qty = spread.legs[0].quantity if spread.legs else 1

        # Sort strikes for width calculation
        strikes = sorted(set(l.strike for l in spread.legs))
        width = (strikes[-1] - strikes[0]) if len(strikes) >= 2 else 0

        if spread.spread_type == "BULL_PUT_SPREAD":
            # Credit spread: SELL higher PE + BUY lower PE
            spread.max_profit = round(net_credit * qty, 2)
            spread.max_loss = round((width - net_credit) * qty, 2)
            spread.breakeven_points = [max(strikes) - net_credit] if net_credit else None

        elif spread.spread_type == "BEAR_CALL_SPREAD":
            # Credit spread: SELL lower CE + BUY higher CE
            spread.max_profit = round(net_credit * qty, 2)
            spread.max_loss = round((width - net_credit) * qty, 2)
            spread.breakeven_points = [min(strikes) + net_credit] if net_credit else None

        elif spread.spread_type == "BULL_CALL_SPREAD":
            # Debit spread: BUY lower CE + SELL higher CE
            net_debit = debit_per_unit - credit_per_unit
            spread.max_profit = round((width - net_debit) * qty, 2)
            spread.max_loss = round(net_debit * qty, 2)
            spread.breakeven_points = [min(strikes) + net_debit] if net_debit else None

        elif spread.spread_type == "BEAR_PUT_SPREAD":
            # Debit spread: BUY higher PE + SELL lower PE
            net_debit = debit_per_unit - credit_per_unit
            spread.max_profit = round((width - net_debit) * qty, 2)
            spread.max_loss = round(net_debit * qty, 2)
            spread.breakeven_points = [max(strikes) - net_debit] if net_debit else None

        elif spread.spread_type == "IRON_CONDOR":
            # Net credit from all legs
            put_strikes = sorted(l.strike for l in spread.legs if l.option_type == "PE")
            call_strikes = sorted(l.strike for l in spread.legs if l.option_type == "CE")
            put_width = (put_strikes[-1] - put_strikes[0]) if len(put_strikes) >= 2 else 0
            call_width = (call_strikes[-1] - call_strikes[0]) if len(call_strikes) >= 2 else 0
            max_width = max(put_width, call_width)
            spread.max_profit = round(net_credit * qty, 2)
            spread.max_loss = round((max_width - net_credit) * qty, 2)
            if put_strikes and call_strikes:
                spread.breakeven_points = [
                    put_strikes[-1] - net_credit,  # lower breakeven
                    call_strikes[0] + net_credit,   # upper breakeven
                ]

        elif spread.spread_type in ["SHORT_STRADDLE", "SHORT_STRANGLE"]:
            spread.max_profit = round(net_credit * qty, 2)
            spread.max_loss = None  # theoretically unlimited
            if len(strikes) >= 2:
                spread.breakeven_points = [
                    min(strikes) - net_credit,
                    max(strikes) + net_credit,
                ]
            elif len(strikes) == 1:
                spread.breakeven_points = [
                    strikes[0] - net_credit,
                    strikes[0] + net_credit,
                ]

        elif spread.spread_type in ["LONG_STRADDLE", "LONG_STRANGLE"]:
            net_debit = debit_per_unit - credit_per_unit
            spread.max_loss = round(net_debit * qty, 2)
            spread.max_profit = None  # theoretically unlimited
            if len(strikes) >= 2:
                spread.breakeven_points = [
                    min(strikes) - net_debit,
                    max(strikes) + net_debit,
                ]
            elif len(strikes) == 1:
                spread.breakeven_points = [
                    strikes[0] - net_debit,
                    strikes[0] + net_debit,
                ]

        elif spread.spread_type in ["BUTTERFLY_CALL", "BUTTERFLY_PUT"]:
            net_debit = debit_per_unit - credit_per_unit
            mid_strike = strikes[len(strikes) // 2] if len(strikes) >= 3 else 0
            spread.max_profit = round((strikes[1] - strikes[0] - net_debit) * qty, 2) if len(strikes) >= 3 else 0
            spread.max_loss = round(net_debit * qty, 2)
            if len(strikes) >= 3:
                spread.breakeven_points = [
                    strikes[0] + net_debit,
                    strikes[2] - net_debit,
                ]

        else:
            # Fallback for ratio spreads etc.
            if net_credit > 0:
                spread.max_profit = round(net_credit * qty, 2)
            else:
                spread.max_loss = round(abs(net_credit) * qty, 2)


def _extract_leg_fields(leg_data: Dict, intent: Dict) -> Dict:
    """
    Robustly extract side, option_type, strike, and quantity from a leg dict.
    Handles multiple ticket formats:
      - Strategy engine: {side, strike, type, symbol}
      - Zerodha sync:    {symbol, side, price, qty}  (no strike/type!)
      - Strategy Builder: {type=BUY/SELL, option_type=CE/PE, strike, quantity}
    Falls back to parsing the Zerodha trading symbol when keys are missing.
    """
    # --- side (BUY / SELL) ---
    side = str(leg_data.get("side", "")).upper()
    if side not in ("BUY", "SELL"):
        # Strategy Builder uses "type" for side
        side = str(leg_data.get("type", "BUY")).upper()
        if side not in ("BUY", "SELL"):
            side = "BUY"

    # --- option_type (CE / PE) ---
    option_type = str(leg_data.get("type", "")).upper()
    if option_type not in ("CE", "PE"):
        option_type = str(leg_data.get("option_type", "")).upper()

    # --- strike ---
    strike = leg_data.get("strike")
    if strike is not None:
        try:
            strike = int(float(strike))
        except (ValueError, TypeError):
            strike = None

    # --- quantity ---
    quantity = leg_data.get("quantity") or leg_data.get("qty") or 1
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        quantity = 1

    # --- fallback: parse symbol if strike or option_type still missing ---
    symbol = leg_data.get("symbol", "")
    if (not strike or option_type not in ("CE", "PE")) and symbol:
        parsed_underlying, parsed_strike, parsed_opt = _parse_symbol(symbol)
        if parsed_strike and not strike:
            strike = parsed_strike
        if parsed_opt and option_type not in ("CE", "PE"):
            option_type = parsed_opt
        # If intent has no underlying but symbol does, use it
        if parsed_underlying and not intent.get("underlying"):
            intent["underlying"] = parsed_underlying

    # --- parsed underlying from symbol ---
    parsed_underlying = None
    if symbol:
        pu, _, _ = _parse_symbol(symbol)
        if pu:
            parsed_underlying = pu

    # Determine if this is a derivative leg (option or future)
    is_derivative = False
    sym_upper = symbol.upper() if symbol else ""
    if sym_upper.endswith("CE") or sym_upper.endswith("PE"):
        is_derivative = True
    elif "FUT" in sym_upper:
        is_derivative = True

    # Final defaults
    if option_type not in ("CE", "PE"):
        option_type = "CE"
    if not strike:
        strike = 0

    # --- per-unit entry price ---
    entry_price = leg_data.get("price")
    if entry_price is not None:
        try:
            entry_price = float(entry_price)
        except (ValueError, TypeError):
            entry_price = None

    return {
        "side": side,
        "option_type": option_type,
        "strike": strike,
        "quantity": quantity,
        "symbol": symbol,
        "parsed_underlying": parsed_underlying,
        "is_derivative": is_derivative,
        "entry_price": entry_price,
    }


def detect_spreads(position_intents: List[Dict]) -> GroupedPositions:
    """
    Main entry point: Convert execution intents to position legs and detect spreads.
    
    Args:
        position_intents: List of ExecutionIntent objects serialized to dicts
        
    Returns:
        GroupedPositions with organized spreads and warnings
    """
    detector = SpreadDetector()
    legs = []

    for intent in position_intents:
        ticket = intent.get("ticket") or {}
        intent_legs = ticket.get("legs") or []

        for leg_data in intent_legs:
            fields = _extract_leg_fields(leg_data, intent)

            # Skip non-derivative positions (cash equity / stocks)
            if not fields.get("is_derivative"):
                logger.debug(
                    "Skipping non-derivative leg: symbol=%s intent=%s",
                    fields.get("symbol"), intent.get("intent_id"),
                )
                continue

            # Use parsed underlying instead of intent.underlying
            # because Zerodha sync stores the full trading symbol as underlying
            # e.g. "NIFTY26FEB25650PE" instead of "NIFTY"
            underlying = fields.get("parsed_underlying") or intent.get("underlying") or "UNKNOWN"

            leg = PositionLeg(
                intent_id=intent.get("intent_id", "UNKNOWN"),
                strategy=intent.get("strategy", "UNKNOWN"),
                side=fields["side"],
                option_type=fields["option_type"],
                strike=fields["strike"],
                quantity=fields["quantity"],
                expiry=intent.get("expiry"),
                underlying=underlying,
                entry_credit=intent.get("entry_credit"),
                entry_price=fields.get("entry_price"),
                pnl=intent.get("pnl"),
                unrealized_pnl=intent.get("unrealized_pnl"),
            )
            logger.debug(
                "Parsed leg: %s %s %s (strike=%s, underlying=%s) from intent %s",
                fields["side"], fields["strike"], fields["option_type"],
                fields["strike"], underlying, intent.get("intent_id"),
            )
            legs.append(leg)

    return detector.group_positions(legs)
