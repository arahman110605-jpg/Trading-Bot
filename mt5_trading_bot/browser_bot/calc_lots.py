import MetaTrader5 as mt5, math, urllib.request, json, time

# Simulate with competition account balance
balance     = 942.00
free_margin = 942.00
leverage    = 100
price       = 1.16100   # current EURUSD approx
contract    = 100_000
margin_pct  = 0.75

margin_per_lot = (contract * price) / leverage
available      = free_margin * margin_pct
lots           = math.floor((available / margin_per_lot) / 0.01) * 0.01
lots           = round(max(0.01, min(lots, 5.0)), 2)

print("=" * 40)
print("  XM COMPETITION LOT CALCULATOR")
print("=" * 40)
print(f"  Balance:        ${balance:.2f}")
print(f"  Free Margin:    ${free_margin:.2f}")
print(f"  Leverage:       1:{leverage}")
print(f"  EURUSD Price:   {price:.5f}")
print(f"  Margin/lot:     ${margin_per_lot:.2f}")
print(f"  Using {margin_pct*100:.0f}%:        ${available:.2f}")
print(f"  OPTIMAL LOTS:   {lots}")
print(f"  Est. Pip value: ${lots * 10:.2f} per pip")
print(f"  20-pip profit:  ${lots * 10 * 20:.2f}")
print(f"  50-pip profit:  ${lots * 10 * 50:.2f}")
print("=" * 40)

# Now inject this as a test signal
payload = {
    'symbol': 'EURUSD',
    'signal': 'BUY',
    'price': price,
    'stop_loss': round(price - 0.00320, 5),
    'take_profit': round(price + 0.00800, 5),
    'lots': lots,
    'reason': f'Test @ $942 balance — {lots} lots auto-sized',
    'timestamp': time.time()
}

req = urllib.request.Request(
    'http://localhost:8765/inject_signal',
    data=json.dumps(payload).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(req)
result = json.loads(res.read())
print(f"\n  Signal injected: {result['status']}")
print(f"  Lots sent to browser: {lots}")
