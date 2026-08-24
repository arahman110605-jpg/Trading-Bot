import MetaTrader5 as mt5

if not mt5.initialize():
    print("Failed to initialize MT5:", mt5.last_error())
else:
    acc = mt5.account_info()
    if acc is not None:
        mode_str = "REAL / LIVE" if acc.trade_mode == 0 else ("DEMO" if acc.trade_mode == 2 else "CONTEST")
        print("=== ACTIVE MT5 ACCOUNT DETECTED ===")
        print(f"Account Number: {acc.login}")
        print(f"Account Name:   {acc.name}")
        print(f"Broker Server:  {acc.server}")
        print(f"Company:        {acc.company}")
        print(f"Currency:       {acc.currency}")
        print(f"Balance:        ${acc.balance:.2f}")
        print(f"Equity:         ${acc.equity:.2f}")
        print(f"Leverage:       1:{acc.leverage}")
        print(f"Trade Mode:     {mode_str}")
    else:
        print("MT5 Initialized, but no account is currently logged in.")
    mt5.shutdown()
