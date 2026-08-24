import MetaTrader5 as mt5

mt5.initialize()
acc = mt5.account_info()
print("Account:", acc.login)
print("Balance: " + str(round(acc.balance, 2)))
print("Equity: " + str(round(acc.equity, 2)))
print("Net Profit: " + str(round(acc.profit, 2)))

for s in ["USDJPY", "GBPUSD", "EURUSD"]:
    pos = mt5.positions_get(symbol=s)
    if pos:
        pnl = sum(p.profit for p in pos)
        lots = sum(p.volume for p in pos)
        print(s + " -> Orders: " + str(len(pos)) + " | Lots: " + str(round(lots, 2)) + " | P&L: $" + str(round(pnl, 2)))

mt5.shutdown()
