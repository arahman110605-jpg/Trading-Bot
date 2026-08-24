import MetaTrader5 as mt5

account = 53016472
password = "1C$Sb3MehAno6R"
server = "ICMarketsSC-Demo"
path = "C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe"

print("Initializing MT5 with credentials...")
init_res = mt5.initialize(path=path, login=account, password=password, server=server)
print("Init with login result:", init_res)

acc = mt5.account_info()
if acc:
    print(f"SUCCESS! Logged into {acc.server} | Account #{acc.login} | Name: {acc.name} | Balance: ${acc.balance:.2f} {acc.currency}")
else:
    print("Failed to get account info. Error:", mt5.last_error())

mt5.shutdown()
