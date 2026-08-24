"""
MT5 Strategy Backtesting Utility
Tests Trend Momentum Strategy against historical MT5 candlestick data.
"""
import sys
import os
import pandas as pd
import numpy as np

# Adjust path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from broker.mt5_client import MT5Client
from strategies.trend_momentum_strategy import TrendMomentumStrategy
import config

def run_backtest(symbol: str = "EURUSD", timeframe: str = "H1", bars: int = 2000):
    client = MT5Client(
        account=config.MT5_ACCOUNT,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
        path=config.MT5_PATH
    )

    if not client.connect():
        print("[ERROR] Could not connect to MT5 for backtest.")
        return

    print("\n==================================================")
    print(f"[BACKTEST] Symbol: {symbol} | Timeframe: {timeframe} | Bars: {bars}")
    print("==================================================")

    df = client.get_market_data(symbol, timeframe, count=bars)
    client.disconnect()

    if df is None or len(df) < 250:
        print("[ERROR] Insufficient data received from MT5.")
        return

    strategy = TrendMomentumStrategy(
        ema_fast=config.EMA_FAST,
        ema_slow=config.EMA_SLOW,
        ema_trend=config.EMA_TREND,
        rsi_period=config.RSI_PERIOD,
        rsi_buy_min=config.RSI_BUY_MIN,
        rsi_buy_max=config.RSI_BUY_MAX,
        rsi_sell_min=config.RSI_SELL_MIN,
        rsi_sell_max=config.RSI_SELL_MAX,
        atr_period=config.ATR_PERIOD,
        atr_sl_mult=config.ATR_SL_MULTIPLIER,
        atr_tp_mult=config.ATR_TP_MULTIPLIER,
    )

    df = strategy.calculate_indicators(df)
    
    trades = []
    in_position = False
    pos_type = None
    entry_price = 0.0
    entry_time = None
    stop_loss = 0.0
    take_profit = 0.0

    for i in range(config.EMA_TREND + 5, len(df) - 1):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        next_row = df.iloc[i + 1]

        # Check existing trade exit
        if in_position:
            high = next_row['high']
            low = next_row['low']

            if pos_type == "BUY":
                if low <= stop_loss:
                    pnl = stop_loss - entry_price
                    trades.append({"type": "BUY", "entry": entry_price, "exit": stop_loss, "pnl": pnl, "result": "LOSS", "entry_time": entry_time, "exit_time": next_row['time']})
                    in_position = False
                elif high >= take_profit:
                    pnl = take_profit - entry_price
                    trades.append({"type": "BUY", "entry": entry_price, "exit": take_profit, "pnl": pnl, "result": "WIN", "entry_time": entry_time, "exit_time": next_row['time']})
                    in_position = False

            elif pos_type == "SELL":
                if high >= stop_loss:
                    pnl = entry_price - stop_loss
                    trades.append({"type": "SELL", "entry": entry_price, "exit": stop_loss, "pnl": pnl, "result": "LOSS", "entry_time": entry_time, "exit_time": next_row['time']})
                    in_position = False
                elif low <= take_profit:
                    pnl = entry_price - take_profit
                    trades.append({"type": "SELL", "entry": entry_price, "exit": take_profit, "pnl": pnl, "result": "WIN", "entry_time": entry_time, "exit_time": next_row['time']})
                    in_position = False

        # If not in position, check for entry signal
        if not in_position:
            signal = strategy.check_signal_from_row(row, prev, next_open=next_row['open'])
            if signal:
                in_position = True
                pos_type = signal["signal"]
                entry_price = signal["price"]
                entry_time = next_row['time']
                stop_loss = signal["stop_loss"]
                take_profit = signal["take_profit"]

    if not trades:
        print("No trades generated during this backtest window.")
        return

    tdf = pd.DataFrame(trades)
    total_trades = len(tdf)
    wins = len(tdf[tdf['result'] == "WIN"])
    losses = len(tdf[tdf['result'] == "LOSS"])
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    total_profit = tdf[tdf['pnl'] > 0]['pnl'].sum()
    total_loss = abs(tdf[tdf['pnl'] < 0]['pnl'].sum())
    profit_factor = (total_profit / total_loss) if total_loss > 0 else np.nan
    net_pnl = tdf['pnl'].sum()

    print(f"Total Trades: {total_trades}")
    print(f"Wins: {wins} | Losses: {losses}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Net Points P&L: {net_pnl:.5f}")
    print("--------------------------------------------------\n", flush=True)

if __name__ == "__main__":
    symbols = ["XAUUSD", "GBPUSD", "USDJPY"]
    for s in symbols:
        run_backtest(s, "H1", 2000)
