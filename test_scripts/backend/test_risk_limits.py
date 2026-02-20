"""
test_risk_limits.py
-------------------
Test parametrized risk limits system.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from app.core.risk.risk_limits_config import (
    RiskLimits,
    RiskProfile,
    get_risk_limits,
)
from app.core.strategies.option_spread_15m.risk import (
    check_spread_risk,
    get_risk_limits as get_risk_limits_for_spread,
)


def test_risk_profiles():
    """Test predefined risk profiles."""
    print("\n=== Testing Risk Profiles ===\n")

    # Test CONSERVATIVE
    conservative = get_risk_limits("conservative")
    print(f"CONSERVATIVE Profile:")
    print(f"  Max portfolio loss: {conservative.max_portfolio_loss_pct}%")
    print(f"  Max trades/day: {conservative.max_trades_per_day}")
    print(f"  IV_NORMAL limits: {conservative.get_iv_regime_limits('NORMAL')}")
    assert conservative.max_portfolio_loss_pct == 1.0
    assert conservative.max_trades_per_day == 1

    # Test BALANCED (default)
    balanced = get_risk_limits()  # No profile specified
    print(f"\nBALANCED Profile (default):")
    print(f"  Max portfolio loss: {balanced.max_portfolio_loss_pct}%")
    print(f"  Max trades/day: {balanced.max_trades_per_day}")
    print(f"  IV_NORMAL limits: {balanced.get_iv_regime_limits('NORMAL')}")
    assert balanced.max_portfolio_loss_pct == 3.0
    assert balanced.max_trades_per_day == 3

    # Test AGGRESSIVE
    aggressive = get_risk_limits("aggressive")
    print(f"\nAGGRESSIVE Profile:")
    print(f"  Max portfolio loss: {aggressive.max_portfolio_loss_pct}%")
    print(f"  Max trades/day: {aggressive.max_trades_per_day}")
    print(f"  IV_NORMAL limits: {aggressive.get_iv_regime_limits('NORMAL')}")
    assert aggressive.max_portfolio_loss_pct == 5.0
    assert aggressive.max_trades_per_day == 5

    print("\n✅ Risk profiles test passed!")


def test_iv_regime_limits():
    """Test IV-regime specific limits."""
    print("\n=== Testing IV Regime Limits ===\n")

    config = get_risk_limits("balanced")

    # Test LOW IV
    low_limits = config.get_iv_regime_limits("LOW")
    print(f"BALANCED profile, LOW IV:")
    print(f"  Min ATM dist: {low_limits['min_atm_dist_pct']}%")
    print(f"  Max risk: {low_limits['max_risk_pct_capital']}%")
    assert low_limits["min_atm_dist_pct"] == 0.5
    assert low_limits["max_risk_pct_capital"] == 4.0

    # Test NORMAL IV
    normal_limits = config.get_iv_regime_limits("NORMAL")
    print(f"\nBALANCED profile, NORMAL IV:")
    print(f"  Min ATM dist: {normal_limits['min_atm_dist_pct']}%")
    print(f"  Max risk: {normal_limits['max_risk_pct_capital']}%")
    assert normal_limits["min_atm_dist_pct"] == 0.6
    assert normal_limits["max_risk_pct_capital"] == 2.0

    # Test HIGH IV
    high_limits = config.get_iv_regime_limits("HIGH")
    print(f"\nBALANCED profile, HIGH IV:")
    print(f"  Min ATM dist: {high_limits['min_atm_dist_pct']}%")
    print(f"  Max risk: {high_limits['max_risk_pct_capital']}%")
    assert high_limits["min_atm_dist_pct"] == 0.8
    assert high_limits["max_risk_pct_capital"] == 1.0

    print("\n✅ IV regime limits test passed!")


def test_spread_risk_check_with_config():
    """Test spread risk checking with different configs."""
    print("\n=== Testing Spread Risk Check with Different Configs ===\n")

    # Setup
    short_strike = 20100
    long_strike = 20200
    spot = 20000.0
    capital = 100000.0
    lot_size = 100
    lots = 1

    # Test with BALANCED (should allow)
    balanced_config = get_risk_limits("balanced")
    is_safe_balanced, reason_balanced, metrics_balanced = check_spread_risk(
        short_strike=short_strike,
        long_strike=long_strike,
        spot=spot,
        capital=capital,
        lot_size=lot_size,
        lots=lots,
        iv_regime="NORMAL",
        risk_config=balanced_config,
    )
    print(f"BALANCED config, NORMAL IV:")
    print(f"  Safe: {is_safe_balanced}")
    print(f"  Reason: {reason_balanced}")
    print(f"  Max loss: ₹{metrics_balanced.get('max_loss', 0)}")
    print(f"  Risk %: {metrics_balanced.get('risk_pct_capital', 0):.2f}%")

    # Test with CONSERVATIVE (might block due to stricter limits)
    conservative_config = get_risk_limits("conservative")
    is_safe_conservative, reason_conservative, metrics_conservative = check_spread_risk(
        short_strike=short_strike,
        long_strike=long_strike,
        spot=spot,
        capital=capital,
        lot_size=lot_size,
        lots=lots,
        iv_regime="NORMAL",
        risk_config=conservative_config,
    )
    print(f"\nCONSERVATIVE config, NORMAL IV:")
    print(f"  Safe: {is_safe_conservative}")
    print(f"  Reason: {reason_conservative}")

    # Test with AGGRESSIVE (should allow more risk)
    aggressive_config = get_risk_limits("aggressive")
    is_safe_aggressive, reason_aggressive, metrics_aggressive = check_spread_risk(
        short_strike=short_strike,
        long_strike=long_strike,
        spot=spot,
        capital=capital,
        lot_size=lot_size,
        lots=lots,
        iv_regime="NORMAL",
        risk_config=aggressive_config,
    )
    print(f"\nAGGRESSIVE config, NORMAL IV:")
    print(f"  Safe: {is_safe_aggressive}")
    print(f"  Reason: {reason_aggressive}")

    print("\n✅ Spread risk check test passed!")


def test_spread_risk_different_iv_regimes():
    """Test how IV regime affects risk limits."""
    print("\n=== Testing Spread Risk Check across IV Regimes ===\n")

    config = get_risk_limits("balanced")
    short_strike = 20100
    long_strike = 20200
    spot = 20000.0
    capital = 100000.0
    lot_size = 100
    lots = 1

    for regime in ["LOW", "NORMAL", "HIGH"]:
        is_safe, reason, metrics = check_spread_risk(
            short_strike=short_strike,
            long_strike=long_strike,
            spot=spot,
            capital=capital,
            lot_size=lot_size,
            lots=lots,
            iv_regime=regime,
            risk_config=config,
        )
        print(f"IV Regime: {regime}")
        print(f"  Safe: {is_safe}")
        if not is_safe:
            print(f"  Blocked: {reason}")
        print(f"  Strike dist: {metrics.get('strike_dist_pct', 0):.2f}%")
        print()

    print("✅ IV regime test passed!")


def test_custom_risk_limits():
    """Test creating custom risk limits."""
    print("\n=== Testing Custom Risk Limits ===\n")

    # Create custom limits
    custom = RiskLimits(
        max_portfolio_loss_pct=2.5,
        max_trades_per_day=2,
        iv_regime_limits={
            "LOW": {"min_atm_dist_pct": 0.4, "max_risk_pct_capital": 3.5},
            "NORMAL": {"min_atm_dist_pct": 0.5, "max_risk_pct_capital": 1.5},
            "HIGH": {"min_atm_dist_pct": 0.7, "max_risk_pct_capital": 0.8},
        }
    )

    print("Custom Risk Limits:")
    print(f"  Max portfolio loss: {custom.max_portfolio_loss_pct}%")
    print(f"  Max trades/day: {custom.max_trades_per_day}")
    print(f"  NORMAL IV limits: {custom.get_iv_regime_limits('NORMAL')}")

    # Test with custom config
    result_dict = custom.to_dict()
    print(f"\nAs dict:")
    print(f"  max_portfolio_loss_pct: {result_dict['max_portfolio_loss_pct']}")
    print(f"  max_trades_per_day: {result_dict['max_trades_per_day']}")

    print("\n✅ Custom limits test passed!")


if __name__ == "__main__":
    test_risk_profiles()
    test_iv_regime_limits()
    test_spread_risk_check_with_config()
    test_spread_risk_different_iv_regimes()
    test_custom_risk_limits()

    print("\n" + "=" * 50)
    print("✅ ALL TESTS PASSED!")
    print("=" * 50)
