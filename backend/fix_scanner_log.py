"""Fix corrupted AutoTraderLog calls in condition_scanner.py and condition_scanner_scheduler.py"""
import re

# ── Fix 1: condition_scanner.py ──────────────────────────────────────────────
path1 = '/app/app/api/routes/condition_scanner.py'
with open(path1, 'r', encoding='utf-8') as f:
    text = f.read()

# The corrupted line has literal \r\n (4 chars) instead of real newlines
# Match the whole corrupted AutoTraderLog(...) block on one line
pattern1 = re.compile(
    r'log = AutoTraderLog\(\\r\\n\s+strategy=strategy_name,\\r\\n\s+action="ENTRY",\\r\\n\s+underlying=symbol,\\r\\n\s+reason=f"[^"]*",\\r\\n\s+details=order,\\r\\n\s+severity="SUCCESS"[^)]+\)'
)

replacement1 = '''log = AutoTraderLog(
            strategy=strategy_name,
            action="ENTRY",
            underlying=symbol,
            reason=f"{direction} @ {ltp} qty={quantity} mode={mode}",
            details=order,
            severity="SUCCESS" if "FAILED" not in str(order.get("status", "")) else "ERROR",
        )'''

new_text, count = pattern1.subn(replacement1, text)
if count:
    with open(path1, 'w', encoding='utf-8') as f:
        f.write(new_text)
    print(f'condition_scanner.py: fixed {count} occurrence(s)')
else:
    print('condition_scanner.py: pattern not matched, trying fallback...')
    # Fallback: find the line index and replace it
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if 'log = AutoTraderLog(' in line and r'\r\n' in line:
            lines[i] = (
                '        log = AutoTraderLog(\n'
                '            strategy=strategy_name,\n'
                '            action="ENTRY",\n'
                '            underlying=symbol,\n'
                '            reason=f"{direction} @ {ltp} qty={quantity} mode={mode}",\n'
                '            details=order,\n'
                '            severity="SUCCESS" if "FAILED" not in str(order.get("status", "")) else "ERROR",\n'
                '        )\n'
            )
            with open(path1, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            print(f'condition_scanner.py: fixed via fallback at line {i+1}')
            break
    else:
        print('condition_scanner.py: nothing to fix (already clean?)')

# ── Fix 2: condition_scanner_scheduler.py ───────────────────────────────────
path2 = '/app/app/core/condition_scanner_scheduler.py'
with open(path2, 'r', encoding='utf-8') as f:
    text2 = f.read()

pattern2 = re.compile(
    r'log = AutoTraderLog\(\\r\\n\s+strategy=strategy_name,\\r\\n\s+action="AUTO_ENTRY",\\r\\n\s+symbol=symbol,\\r\\n\s+direction=direction,\\r\\n\s+price=ltp,\\r\\n\s+quantity=quantity,\\r\\n\s+execution_mode=mode,\\r\\n\s+details=json\.dumps\(order\),\\r\\n\s+timestamp=datetime\.now\(\),\\r\\n\s+\)'
)

replacement2 = '''log = AutoTraderLog(
            strategy=strategy_name,
            action="AUTO_ENTRY",
            underlying=symbol,
            reason=f"{direction} @ {ltp} qty={quantity} mode={mode}",
            details=order,
            severity="SUCCESS" if "FAILED" not in str(order.get("status", "")) else "ERROR",
        )'''

new_text2, count2 = pattern2.subn(replacement2, text2)
if count2:
    with open(path2, 'w', encoding='utf-8') as f:
        f.write(new_text2)
    print(f'condition_scanner_scheduler.py: fixed {count2} occurrence(s)')
else:
    print('condition_scanner_scheduler.py: pattern not matched, trying fallback...')
    lines2 = text2.splitlines(keepends=True)
    for i, line in enumerate(lines2):
        if 'log = AutoTraderLog(' in line and r'\r\n' in line:
            lines2[i] = (
                '        log = AutoTraderLog(\n'
                '            strategy=strategy_name,\n'
                '            action="AUTO_ENTRY",\n'
                '            underlying=symbol,\n'
                '            reason=f"{direction} @ {ltp} qty={quantity} mode={mode}",\n'
                '            details=order,\n'
                '            severity="SUCCESS" if "FAILED" not in str(order.get("status", "")) else "ERROR",\n'
                '        )\n'
            )
            with open(path2, 'w', encoding='utf-8') as f:
                f.writelines(lines2)
            print(f'condition_scanner_scheduler.py: fixed via fallback at line {i+1}')
            break
    else:
        print('condition_scanner_scheduler.py: nothing to fix (already clean?)')

# ── Verify ───────────────────────────────────────────────────────────────────
print('\n--- Verify condition_scanner.py ---')
import subprocess
result = subprocess.run(['grep', '-n', 'AutoTraderLog', path1], capture_output=True, text=True)
print(result.stdout)

print('--- Verify scheduler ---')
result2 = subprocess.run(['grep', '-n', 'AutoTraderLog', path2], capture_output=True, text=True)
print(result2.stdout)
