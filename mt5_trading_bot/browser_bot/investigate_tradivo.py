import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import sys

account_id = 413887630
password = "2@Tradivobot"
server = "Exness-MT5Trial6"

print(f"Connecting to {server} with account {account_id}...")
# Try connecting directly
connected = mt5.initialize(
    path="C:\\Program Files\\MetaTrader 5\\terminal64.exe",
    login=account_id,
    password=password,
    server=server
)

if not connected:
    err = mt5.last_error()
    print(f"Direct connection with server '{server}' failed: {err}")
    print("Let's try finding Exness servers or searching...")
    # Let's check what servers or account info we get
else:
    acc_info = mt5.account_info()
    if acc_info is not None:
        print("\n=== ACCOUNT DETAILS ===")
        print(f"Name: {acc_info.name}")
        print(f"Company / Broker: {acc_info.company} / {acc_info.server}")
        print(f"Currency: {acc_info.currency}")
        print(f"Leverage: 1:{acc_info.leverage}")
        print(f"Balance: {acc_info.balance:.2f} {acc_info.currency}")
        print(f"Equity: {acc_info.equity:.2f} {acc_info.currency}")
        print(f"Margin: {acc_info.margin:.2f}")
        print(f"Free Margin: {acc_info.margin_free:.2f}")
        print(f"Profit (Floating): {acc_info.profit:.2f}")
        
        # Check Open Positions
        positions = mt5.positions_get()
        print(f"\n=== OPEN POSITIONS ({len(positions) if positions else 0}) ===")
        if positions:
            for p in positions:
                print(f"  Ticket: {p.ticket} | Symbol: {p.symbol} | Type: {'BUY' if p.type==0 else 'SELL'} | Lots: {p.volume} | Open Price: {p.price_open} | Current: {p.price_current} | SL: {p.sl} | TP: {p.tp} | Profit: {p.profit:.2f}")

        # Check Order / Deals History
        from_date = datetime.now() - timedelta(days=365)
        to_date = datetime.now() + timedelta(days=1)
        deals = mt5.history_deals_get(from_date, to_date)
        
        print(f"\n=== TRADING HISTORY (Deals: {len(deals) if deals else 0}) ===")
        if deals:
            df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
            df_deals['time'] = pd.to_datetime(df_deals['time'], unit='s')
            
            # Filter trade deals (entry / exit)
            trade_deals = df_deals[df_deals['entry'].isin([0, 1])] # in, out
            print(f"Total Trade Deals: {len(trade_deals)}")
            print(f"First Deal Date: {df_deals['time'].min()}")
            print(f"Last Deal Date: {df_deals['time'].max()}")
            
            total_profit = df_deals['profit'].sum()
            deposits = df_deals[df_deals['type'] == 2]['profit'].sum() # type 2 = balance deposit
            print(f"Total Deposits / Withdrawals: {deposits:.2f}")
            print(f"Net Trading Profit: {total_profit - deposits:.2f}")
            
            # Show summary by symbol
            print("\nProfit By Symbol:")
            print(df_deals.groupby('symbol')['profit'].agg(['count', 'sum']).sort_values('sum', ascending=False))
            
            # Show last 10 deals
            print("\nLast 10 Deals:")
            print(df_deals[['time', 'symbol', 'type', 'entry', 'volume', 'price', 'profit', 'comment']].tail(10))
            
            # Check lot sizes over time (to detect Martingale)
            print("\nLot Size Distribution:")
            print(df_deals['volume'].value_counts().head(10))
            
    else:
        print("Logged in, but could not get account info.")

mt5.shutdown()
