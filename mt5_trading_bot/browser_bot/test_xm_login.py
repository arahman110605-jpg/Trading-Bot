import MetaTrader5 as mt5
import sys

account_id = 1301984092
password = "Iron@458700"

# Common XM MT5 server names
xm_servers = [
    "XMGlobal-MT5",
    "XMGlobal-MT5 2",
    "XMGlobal-MT5 3",
    "XMGlobal-MT5 4",
    "XMGlobal-MT5 5",
    "XMGlobal-MT5 6",
    "XMGlobal-Demo",
    "XMGlobal-Demo 2",
    "XMGlobal-Demo 3",
    "XMGlobal-Demo 4",
    "XMGlobal-Demo 5",
    "XMGlobal-Demo 6",
    "XMGlobal-Demo 7",
    "XMGlobal-Demo 8",
    "XM-MT5",
    "XM-Demo"
]

print(f"Connecting MT5 Terminal...")
if not mt5.initialize(path="C:\\Program Files\\MetaTrader 5\\terminal64.exe"):
    print("Failed to initialize MT5:", mt5.last_error())
    sys.exit(1)

logged_in = False
for srv in xm_servers:
    print(f"Trying server: {srv}...")
    res = mt5.login(login=account_id, password=password, server=srv)
    if res:
        print(f"\nSUCCESS! Logged into {srv}")
        acc = mt5.account_info()
        print(f"Account: #{acc.login} | Name: {acc.name} | Balance: ${acc.balance:.2f} | Leverage: 1:{acc.leverage} | Server: {acc.server}")
        logged_in = True
        break
    else:
        err = mt5.last_error()

if not logged_in:
    print("\nCould not automatically match the exact server name.")
    print("Please click on 'MetaTrader Login Details' on your XM screen to see the exact server name (e.g. XMGlobal-MT5 3 / XMGlobal-Demo 2).")

mt5.shutdown()
