"""Test mock data generation"""
from app.services.mock_data import generate_mock_top_movers
from app.config.market_config import get_symbols

print("Testing mock data generation...")
symbols = get_symbols('NIFTY50')
print(f"Got {len(symbols)} NIFTY50 symbols")

data = generate_mock_top_movers(symbols, 5)
print(f"Generated {len(data['gainers'])} gainers")
print(f"Generated {len(data['losers'])} losers")
print(f"Generated {len(data['most_active'])} most active")
print("\nSample gainer:", data['gainers'][0])
print("Mock data generation successful!")
