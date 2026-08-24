"""
M5 Rapid Scalper Strategy & Real Market P&L Backtest
Simulates high-frequency scalping with small take profit and broker spread deductions.
"""
import sys, os
import pandas as pd
import numpy as np
import ta
import MetaTrader5 as mt5

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from broker.mt5_client import MT5Client
import config

USD_TO_INR = 83.50
START_CAPITAL_INR = 100000.0
START_CAPITAL_USD = START_CAPITAL_INR / USD_TO_INR  # ~$1,197.60

def run_scalper_backtest(symbol="EURUSD", timeframe="M5", bars=5000, spread_pips=1.2, lot_size=0.10):
    client = MT5Client(
        account=config.MT5_ACCOUNT,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
        path=config.MT5_PATH
    )
    if not client.connect():
        print("[ERROR] MT5 connection failed.")
        return

    sym_info = client.get_symbol_info(symbol)
    df = client.get_market_data(symbol, timeframe, count=bars)
    client.disconnect()

    if df is None or len(df) < 200:
        print("[ERROR] Insufficient data.")
        return

    contract_size = sym_info.trade_contract_size if sym_info else 100000
    point = sym_info.point if sym_info else 0.00001
    pip_val = point * 10 if (sym_info.digits in (3, 5)) else point
    spread_cost_usd = (spread_pips * pip_val) * contract_size * lot_size

    # Scalper Indicators: Bollinger Bands (20, 2) + RSI (7) + Fast EMA (50)
    bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_mid'] = bb.bollinger_mavg()
    df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=7).rsi()
    df['ema_trend'] = ta.trend.EMAIndicator(close=df['close'], window=50).ema_indicator()
    df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()

    # Scalper Parameters: Quick TP (e.g., 4-6 pips), SL (8-12 pips)
    tp_pips = 4.0
    sl_pips = 10.0
    tp_dist = tp_pips * pip_val
    sl_dist = sl_pips * pip_val

    balance = START_CAPITAL_USD
    equity_curve = [balance]
    trades = []
    in_pos = False
    pos_type = None
    entry_price = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    entry_time = None

    for i in range(55, len(df) - 1):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        next_row = df.iloc[i + 1]

        if in_pos:
            high = next_row['high']
            low = next_row['low']
            exit_price = None
            res_type = None

            if pos_type == "BUY":
                if low <= stop_loss:
                    exit_price = stop_loss
                    res_type = "LOSS"
                elif high >= take_profit:
                    exit_price = take_profit
                    res_type = "WIN"
                if exit_price is not None:
                    raw_pnl = (exit_price - entry_price) * contract_size * lot_size
                    net_pnl = raw_pnl - spread_cost_usd
                    balance += net_pnl
                    equity_curve.append(balance)
                    trades.append({
                        "type": "BUY", "entry_time": entry_time, "exit_time": next_row['time'],
                        "raw_pnl": raw_pnl, "spread_fee": spread_cost_usd, "net_pnl": net_pnl,
                        "result": res_type
                    })
                    in_pos = False

            elif pos_type == "SELL":
                if high >= stop_loss:
                    exit_price = stop_loss
                    res_type = "LOSS"
                elif low <= take_profit:
                    exit_price = take_profit
                    res_type = "WIN"
                if exit_price is not None:
                    raw_pnl = (entry_price - exit_price) * contract_size * lot_size
                    net_pnl = raw_pnl - spread_cost_usd
                    balance += net_pnl
                    equity_curve.append(balance)
                    trades.append({
                        "type": "SELL", "entry_time": entry_time, "exit_time": next_row['time'],
                        "raw_pnl": raw_pnl, "spread_fee": spread_cost_usd, "net_pnl": net_pnl,
                        "result": res_type
                    })
                    in_pos = False

        if not in_pos:
            # Scalper Entry: Price bounces off Lower BB with RSI < 25 (BUY) or Upper BB with RSI > 75 (SELL)
            buy_signal = (prev['low'] <= prev['bb_lower']) and (row['close'] > row['open']) and (prev['rsi'] < 30)
            sell_signal = (prev['high'] >= prev['bb_upper']) and (row['close'] < row['open']) and (prev['rsi'] > 70)

            if buy_signal:
                in_pos = True
                pos_type = "BUY"
                entry_price = next_row['open']
                entry_time = next_row['time']
                stop_loss = entry_price - sl_dist
                take_profit = entry_price + tp_dist
            elif sell_signal:
                in_pos = True
                pos_type = "SELL"
                entry_price = next_row['open']
                entry_time = next_row['time']
                stop_loss = entry_price + sl_dist
                take_profit = entry_price - tp_dist

    if not trades:
        print("[INFO] No scalper trades generated.")
        return

    tdf = pd.DataFrame(trades)
    total_trades = len(tdf)
    wins = len(tdf[tdf['result'] == "WIN"])
    losses = len(tdf[tdf['result'] == "LOSS"])
    win_rate = (wins / total_trades) * 100
    
    total_gross_pnl = tdf['raw_pnl'].sum()
    total_spread_cost = tdf['spread_fee'].sum()
    total_net_pnl = tdf['net_pnl'].sum()
    net_pnl_inr = total_net_pnl * USD_TO_INR

    start_date = df.iloc[0]['time'].strftime("%Y-%m-%d")
    end_date = df.iloc[-1]['time'].strftime("%Y-%m-%d")

    print("\n" + "=" * 65)
    print(f"[RAPID SCALPER BACKTEST] Symbol: {symbol} ({timeframe})")
    print(f"[DATA PERIOD] {start_date} to {end_date} ({len(df)} candles)")
    print(f"[CAPITAL] Rs {START_CAPITAL_INR:,.0f} ($1,197.60 USD) | Lot Size: {lot_size}")
    print(f"[TARGET] TP: +{tp_pips} pips | SL: -{sl_pips} pips | Spread: {spread_pips} pips")
    print("=" * 65)
    print(f"Total Scalping Trades: {total_trades} (~{total_trades / 20:.1f} trades / month)")
    print(f"Win Rate: {win_rate:.1f}% ({wins} Wins / {losses} Losses)")
    print(f"Gross Profit (Before Spread): ${total_gross_pnl:,.2f} (Rs {total_gross_pnl * USD_TO_INR:,.0f})")
    print(f"Total Broker Spread/Fees Paid: -${total_spread_cost:,.2f} (-Rs {total_spread_cost * USD_TO_INR:,.0f})")
    print(f"Net Final Balance: ${balance:,.2f} (Rs {balance * USD_TO_INR:,.0f} INR)")
    print(f"Net P&L: {'+' if total_net_pnl >= 0 else ''}${total_net_pnl:,.2f} ({'+' if net_pnl_inr >= 0 else ''}Rs {net_pnl_inr:,.0f} INR)")
    print(f"Return on Investment (ROI): {(total_net_pnl / START_CAPITAL_USD) * 100:.1f}%")
    print("=" * 65 + "\n", flush=True)

if __name__ == "__main__":
    run_scalper_backtest("EURUSD", "M5", 5000, spread_pips=1.0, lot_size=0.10)
    run_scalper_backtest("GBPUSD", "M5", 5000, spread_pips=1.2, lot_size=0.10)
