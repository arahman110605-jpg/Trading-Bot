"""
Deep Historical Market Data Analysis & P&L Simulation
Pulls real historical market data from MT5 over thousands of candles and simulates
exact dollar and INR P&L for a ₹10,000 ($120 USD) account with 0.01 lot sizing.
"""
import sys
import os
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

# Adjust path to import local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from broker.mt5_client import MT5Client
from strategies.trend_momentum_strategy import TrendMomentumStrategy
import config

USD_TO_INR = 83.50
STARTING_CAPITAL_USD = 120.0  # ~10,000 INR
LOT_SIZE = 0.01

def run_deep_historical_analysis(symbol="XAUUSD", timeframe="H1", bars=6000):
    client = MT5Client(
        account=config.MT5_ACCOUNT,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
        path=config.MT5_PATH
    )

    if not client.connect():
        print("[ERROR] Could not connect to MT5.")
        return

    sym_info = client.get_symbol_info(symbol)
    df = client.get_market_data(symbol, timeframe, count=bars)
    client.disconnect()

    if df is None or len(df) < 300:
        print(f"[ERROR] Could not fetch sufficient data for {symbol}.")
        return

    digits = sym_info.digits if sym_info else 2
    point = sym_info.point if sym_info else 0.01
    contract_size = sym_info.trade_contract_size if sym_info else (100 if "XAU" in symbol else 100000)

    start_date = df.iloc[0]['time'].strftime("%Y-%m-%d")
    end_date = df.iloc[-1]['time'].strftime("%Y-%m-%d")

    print(f"\n" + "=" * 65)
    print(f"[REAL MARKET ANALYSIS] Symbol: {symbol} ({timeframe})")
    print(f"[PERIOD] {start_date} to {end_date} ({len(df)} candles)")
    print(f"[CAPITAL] Starting Capital: ${STARTING_CAPITAL_USD:.2f} (Rs {STARTING_CAPITAL_USD * USD_TO_INR:,.0f} INR) | Fixed Lot: {LOT_SIZE}")
    print("=" * 65)

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

    balance = STARTING_CAPITAL_USD
    equity_curve = [balance]
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

        # Manage active position
        if in_position:
            high = next_row['high']
            low = next_row['low']

            exit_price = None
            result_type = None

            if pos_type == "BUY":
                if low <= stop_loss:
                    exit_price = stop_loss
                    result_type = "LOSS"
                elif high >= take_profit:
                    exit_price = take_profit
                    result_type = "WIN"

                if exit_price is not None:
                    # Profit in USD = (Exit - Entry) * Contract Size * Lot Size
                    pnl_points = exit_price - entry_price
                    pnl_usd = pnl_points * contract_size * LOT_SIZE
                    balance += pnl_usd
                    equity_curve.append(balance)
                    trades.append({
                        "symbol": symbol,
                        "type": "BUY",
                        "entry_time": entry_time,
                        "exit_time": next_row['time'],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_usd": pnl_usd,
                        "pnl_inr": pnl_usd * USD_TO_INR,
                        "balance_after": balance,
                        "result": result_type
                    })
                    in_position = False

            elif pos_type == "SELL":
                if high >= stop_loss:
                    exit_price = stop_loss
                    result_type = "LOSS"
                elif low <= take_profit:
                    exit_price = take_profit
                    result_type = "WIN"

                if exit_price is not None:
                    # Profit in USD = (Entry - Exit) * Contract Size * Lot Size
                    pnl_points = entry_price - exit_price
                    pnl_usd = pnl_points * contract_size * LOT_SIZE
                    balance += pnl_usd
                    equity_curve.append(balance)
                    trades.append({
                        "symbol": symbol,
                        "type": "SELL",
                        "entry_time": entry_time,
                        "exit_time": next_row['time'],
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl_usd": pnl_usd,
                        "pnl_inr": pnl_usd * USD_TO_INR,
                        "balance_after": balance,
                        "result": result_type
                    })
                    in_position = False

        # If not in position, evaluate entry
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
        print("[INFO] No trades generated in this window.")
        return

    tdf = pd.DataFrame(trades)
    total_trades = len(tdf)
    wins = len(tdf[tdf['result'] == "WIN"])
    losses = len(tdf[tdf['result'] == "LOSS"])
    win_rate = (wins / total_trades) * 100
    
    total_profit_usd = tdf[tdf['pnl_usd'] > 0]['pnl_usd'].sum()
    total_loss_usd = abs(tdf[tdf['pnl_usd'] < 0]['pnl_usd'].sum())
    profit_factor = (total_profit_usd / total_loss_usd) if total_loss_usd > 0 else np.nan
    net_profit_usd = balance - STARTING_CAPITAL_USD
    net_profit_inr = net_profit_usd * USD_TO_INR
    roi_percent = (net_profit_usd / STARTING_CAPITAL_USD) * 100

    # Max Drawdown calculation
    eq_series = pd.Series(equity_curve)
    cum_max = eq_series.cummax()
    drawdown = (eq_series - cum_max) / cum_max * 100
    max_drawdown_pct = abs(drawdown.min())

    avg_win_usd = tdf[tdf['result'] == "WIN"]['pnl_usd'].mean() if wins > 0 else 0
    avg_loss_usd = abs(tdf[tdf['result'] == "LOSS"]['pnl_usd'].mean()) if losses > 0 else 0

    print(f"Total Trades Executed: {total_trades}")
    print(f"Win Rate: {win_rate:.1f}% ({wins} Wins / {losses} Losses)")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Avg Winning Trade: +${avg_win_usd:.2f} (+Rs {avg_win_usd * USD_TO_INR:.0f})")
    print(f"Avg Losing Trade: -${avg_loss_usd:.2f} (-Rs {avg_loss_usd * USD_TO_INR:.0f})")
    print(f"Max Account Drawdown: {max_drawdown_pct:.1f}%")
    print(f"Final Account Balance: ${balance:.2f} (Rs {balance * USD_TO_INR:,.0f} INR)")
    print(f"Net P&L: +${net_profit_usd:.2f} (+Rs {net_profit_inr:,.0f} INR) -> Return: +{roi_percent:.1f}%")
    print("-" * 65)

    # Monthly breakdown
    tdf['month'] = pd.to_datetime(tdf['exit_time']).dt.to_period('M')
    monthly = tdf.groupby('month')['pnl_usd'].agg(['sum', 'count']).reset_index()
    monthly.columns = ['Month', 'Net_USD', 'Trades']
    monthly['Net_INR'] = monthly['Net_USD'] * USD_TO_INR
    print("\nMonthly Performance Breakdown:")
    for _, m_row in monthly.tail(8).iterrows():
        pnl_str = f"+${m_row['Net_USD']:.2f} (+Rs {m_row['Net_INR']:.0f})" if m_row['Net_USD'] >= 0 else f"-${abs(m_row['Net_USD']):.2f} (-Rs {abs(m_row['Net_INR']):.0f})"
        print(f"  * {m_row['Month']}: {pnl_str} across {int(m_row['Trades'])} trades")
    print("=" * 65 + "\n", flush=True)

if __name__ == "__main__":
    for sym in ["XAUUSD", "GBPUSD", "EURUSD"]:
        run_deep_historical_analysis(sym, "H1", 5000)
