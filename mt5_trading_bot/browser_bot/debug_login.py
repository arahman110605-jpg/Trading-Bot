import MetaTrader5 as mt5
import sys

account = 1301984092
password = "Iron@458700"
server = "XMGlobal-MT5 6"
path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"

print("Initializing MT5...")
if not mt5.initialize(path=path):
    print("Init failed:", mt5.last_error())
    sys.exit(1)

print(f"Logging into {server} (#{account})...")
res = mt5.login(login=account, password=password, server=server)
if not res:
    print("Login call returned False. Error:", mt5.last_error())
else:
    print("Login call returned True!")

acc = mt5.account_info()
if acc is None:
    print("Account info is None. Error:", mt5.last_error())
else:
    print(f"Logged in successfully: #{acc.login} | Name: {acc.name} | Balance: ${acc.balance} | Server: {acc.server}")

mt5.shutdown()
