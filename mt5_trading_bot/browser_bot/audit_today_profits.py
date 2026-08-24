import MetaTrader5 as mt5
import datetime

mt5.initialize()
acc = mt5.account_info()
print("Account:", acc.login)
print("Balance: $" + str(round(acc.balance, 2)))
print("Equity: $" + str(round(acc.equity, 2)))
print("Floating P&L: $" + str(round(acc.profit, 2)))

now = datetime.datetime.now()
start = now - datetime.timedelta(days=1)
deals = mt5.history_deals_get(start, now)
if deals:
    print("\n--- CLOSED DEALS TODAY ---")
    tot = 0.0
    for d in deals:
        if d.entry == 1:
            print("Symbol: " + str(d.symbol) + " | Volume: " + str(d.volume) + " | Profit: $" + str(round(d.profit, 2)) + " | Comment: " + str(d.comment))
            tot += d.profit
    print("---------------------------------")
    print("TOTAL NET PROFIT REALIZED: +$" + str(round(tot, 2)))

positions = mt5.positions_get()
print("\nActive Open Positions: " + str(len(positions) if positions else 0))

mt5.shutdown()
