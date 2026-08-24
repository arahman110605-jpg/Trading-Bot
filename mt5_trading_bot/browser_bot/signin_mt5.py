import MetaTrader5 as mt5

account = 53016472
password = "1C$Sb3MehAno6R"
server = "ICMarketsSC-Demo"
path = "C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe"

print("=" * 60)
print("LOGGING INTO MT5 TERMINAL GUI...")
print(f"Path: {path}")
print(f"Account: #{account} | Server: {server}")
print("=" * 60)

if not mt5.initialize(path=path):
    print("MT5 Init Failed:", mt5.last_error())
    exit(1)

login_res = mt5.login(login=account, password=password, server=server)
print(f"mt5.login() Result: {login_res}")

acc = mt5.account_info()
if acc is not None:
    print(f"\nSUCCESSFULLY LOGGED IN!")
    print(f"  Account Login:  {acc.login}")
    print(f"  Account Name:   {acc.name}")
    print(f"  Server:         {acc.server}")
    print(f"  Balance:        ${acc.balance:.2f} {acc.currency}")
    print(f"  Equity:         ${acc.equity:.2f}")
    print(f"  Leverage:       1:{acc.leverage}")
else:
    print("Failed to get account details. Error:", mt5.last_error())

mt5.shutdown()
