path = r'app/services/market_data_service.py'
with open(path, 'rb') as f:
    raw = f.read()

old = b'INDMoneyDataAdapter.get_option_strikes failed: %s", e)\n            return []\n\n\n# '
new = (
    b'INDMoneyDataAdapter.get_option_strikes failed: %s", e)\n'
    b'            return []\n\n'
    b'    def build_option_symbol(self, underlying: str, expiry: date, strike: int, opt_type: str) -> str:\n'
    b'        return f"{underlying.upper()}|{expiry}|{strike}|{opt_type.upper()}"\n'
    b'\n\n# '
)

if old in raw:
    raw = raw.replace(old, new, 1)
    with open(path, 'wb') as f:
        f.write(raw)
    print('OK - inserted build_option_symbol into INDMoneyDataAdapter')
else:
    print('NOT FOUND - checking actual bytes:')
    idx = raw.find(b'INDMoneyDataAdapter.get_option_strikes failed')
    print(repr(raw[idx:idx+80]))
