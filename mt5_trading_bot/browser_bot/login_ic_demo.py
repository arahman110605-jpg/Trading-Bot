import MetaTrader5 as mt5
import sys

account_id = 53016472
password = "1C$Sb3MehAno6R"
server = "ICMarketsSC-Demo"

print(f"Connecting to {server} (#{account_id})...")
if not mt5.initialize():
    print("Failed to initialize MT5:", mt5.last_error())
    sys.exit(1)

res = mt5.login(login=account_id, password=password, server=server)
if not res:
    print("Login failed. Last error:", mt5.last_error())
else:
    print("SUCCESSFULLY LOGGED IN!")
    acc = mt5.account_info()
    print(f"Account: #{acc.login} | Name: {acc.name} | Server: {acc.server}")
    print(f"Balance: ${acc.balance:.2f} {acc.currency} | Equity: ${acc.equity:.2f} | Leverage: 1:{acc.leverage}")

mt5.shutdown()
