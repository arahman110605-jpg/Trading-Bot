import MetaTrader5 as mt5

mt5.initialize()
acc = mt5.account_info()
print("Balance: $" + str(round(acc.balance, 2)))
print("Equity: $" + str(round(acc.equity, 2)))
print("Floating P&L: $" + str(round(acc.profit, 2)))
print("Total Account Gain since Start: +$" + str(round(acc.equity - 200.0, 2)) + " (+" + str(round(((acc.equity - 200.0) / 200.0) * 100, 1)) + "%)")

positions = mt5.positions_get()
if positions:
    print("\n--- OPEN POSITIONS DETAIL ---")
    for p in positions:
        direction = "BUY" if p.type == 0 else "SELL"
        print(f"Symbol: {p.symbol:<8} | Dir: {direction:<5} | Lots: {p.volume} | Open: {p.price_open:.5f} | Current: {p.price_current:.5f} | P&L: ${p.profit:+.2f}")
mt5.shutdown()
