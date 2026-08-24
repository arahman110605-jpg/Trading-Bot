"""
Real Historical Market Simulation with Rs 1,00,000 ($1,200 USD) Capital
Tests both 0.10 Fixed Lot and Dynamic Compounding Risk Model on XAUUSD (Gold).
"""
import sys
import os
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from broker.mt5_client import MT5Client
from strategies.trend_momentum_strategy import TrendMomentumStrategy
import config

USD_TO_INR = 83.50
STARTING_CAPITAL_INR = 100000.0
STARTING_CAPITAL_USD = STARTING_CAPITAL_INR / USD_TO_INR  # ~$1,197.60 USD

def run_large_capital_simulation(symbol="XAUUSD", timeframe="H1", bars=5000):
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
        print(f"[ERROR] Could not fetch data for {symbol}.")
        return

    contract_size = sym_info.trade_contract_size if sym_info else 100
    start_date = df.iloc[0]['time'].strftime("%Y-%m-%d")
    end_date = df.iloc[-1]['time'].strftime("%Y-%m-%d")

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

    # -------------------------------------------------------------
    # Simulation 1: Fixed 0.10 Lots
    # -------------------------------------------------------------
    def simulate(mode="fixed", risk_pct=1.0, fixed_lot=0.10):
        balance = STARTING_CAPITAL_USD
        equity_curve = [balance]
        trades = []
        in_pos = False
        pos_type = None
        entry_price = 0.0
        entry_time = None
        stop_loss = 0.0
        take_profit = 0.0
        trade_lot = fixed_lot

        for i in range(config.EMA_TREND + 5, len(df) - 1):
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
                        pnl_usd = (exit_price - entry_price) * contract_size * trade_lot
                        balance += pnl_usd
                        equity_curve.append(balance)
                        trades.append({
                            "type": "BUY", "entry_time": entry_time, "exit_time": next_row['time'],
                            "entry": entry_price, "exit": exit_price, "lot": trade_lot,
                            "pnl_usd": pnl_usd, "pnl_inr": pnl_usd * USD_TO_INR, "balance": balance, "result": res_type
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
                        pnl_usd = (entry_price - exit_price) * contract_size * trade_lot
                        balance += pnl_usd
                        equity_curve.append(balance)
                        trades.append({
                            "type": "SELL", "entry_time": entry_time, "exit_time": next_row['time'],
                            "entry": entry_price, "exit": exit_price, "lot": trade_lot,
                            "pnl_usd": pnl_usd, "pnl_inr": pnl_usd * USD_TO_INR, "balance": balance, "result": res_type
                        })
                        in_pos = False

            if not in_pos:
                signal = strategy.check_signal_from_row(row, prev, next_open=next_row['open'])
                if signal:
                    in_pos = True
                    pos_type = signal["signal"]
                    entry_price = signal["price"]
                    entry_time = next_row['time']
                    stop_loss = signal["stop_loss"]
                    take_profit = signal["take_profit"]
                    
                    if mode == "compounding":
                        # 1.0% risk per trade
                        risk_amt = balance * (risk_pct / 100.0)
                        sl_dist = abs(entry_price - stop_loss)
                        trade_lot = max(0.01, round(risk_amt / (sl_dist * contract_size), 2))
                    else:
                        trade_lot = fixed_lot

        return balance, equity_curve, pd.DataFrame(trades)

    print("\n" + "=" * 65)
    print(f"[LARGE CAPITAL SIMULATION] Instrument: {symbol} (H1)")
    print(f"[DATA PERIOD] {start_date} to {end_date} (5000 candles)")
    print(f"[STARTING CAPITAL] Rs {STARTING_CAPITAL_INR:,.0f} INR (${STARTING_CAPITAL_USD:,.2f} USD)")
    print("=" * 65)

    # 1. Standard Fixed Lot (0.10 Lot)
    b_fix, eq_fix, tdf_fix = simulate(mode="fixed", fixed_lot=0.10)
    net_usd_fix = b_fix - STARTING_CAPITAL_USD
    net_inr_fix = net_usd_fix * USD_TO_INR
    wins_fix = len(tdf_fix[tdf_fix['result'] == "WIN"])
    losses_fix = len(tdf_fix[tdf_fix['result'] == "LOSS"])
    wr_fix = (wins_fix / len(tdf_fix)) * 100
    
    cum_max = pd.Series(eq_fix).cummax()
    dd_fix = abs(((pd.Series(eq_fix) - cum_max) / cum_max * 100).min())

    print("\n>>> MODEL A: Standard Risk Model (0.10 Fixed Lot)")
    print(f"  • Total Trades: {len(tdf_fix)} (Wins: {wins_fix} | Losses: {losses_fix})")
    print(f"  • Win Rate: {wr_fix:.1f}%")
    print(f"  • Max Account Drawdown: {dd_fix:.1f}%")
    print(f"  • Final Account Balance: Rs {b_fix * USD_TO_INR:,.0f} (${b_fix:,.2f})")
    print(f"  • Net Profit: +Rs {net_inr_fix:,.0f} (+${net_usd_fix:,.2f})")
    print(f"  • Return on Investment (ROI): +{(net_usd_fix / STARTING_CAPITAL_USD) * 100:.1f}%")

    # 2. Dynamic Compounding (1.0% Risk / Trade)
    b_comp, eq_comp, tdf_comp = simulate(mode="compounding", risk_pct=1.0)
    net_usd_comp = b_comp - STARTING_CAPITAL_USD
    net_inr_comp = net_usd_comp * USD_TO_INR
    cum_max_c = pd.Series(eq_comp).cummax()
    dd_comp = abs(((pd.Series(eq_comp) - cum_max_c) / cum_max_c * 100).min())

    print("\n>>> MODEL B: Dynamic Compounding Model (1.0% Risk Per Trade)")
    print(f"  • Total Trades: {len(tdf_comp)}")
    print(f"  • Max Account Drawdown: {dd_comp:.1f}% (Conservative & Low Risk)")
    print(f"  • Final Account Balance: Rs {b_comp * USD_TO_INR:,.0f} (${b_comp:,.2f})")
    print(f"  • Net Profit: +Rs {net_inr_comp:,.0f} (+${net_usd_comp:,.2f})")
    print(f"  • Return on Investment (ROI): +{(net_usd_comp / STARTING_CAPITAL_USD) * 100:.1f}%")

    # Monthly breakdown for 0.10 Lot
    tdf_fix['month'] = pd.to_datetime(tdf_fix['exit_time']).dt.to_period('M')
    monthly = tdf_fix.groupby('month')['pnl_usd'].agg(['sum', 'count']).reset_index()
    monthly.columns = ['Month', 'Net_USD', 'Trades']
    monthly['Net_INR'] = monthly['Net_USD'] * USD_TO_INR

    print("\nMonthly Breakdown (0.10 Lot / Model A):")
    for _, m in monthly.tail(8).iterrows():
        sign = "+" if m['Net_INR'] >= 0 else "-"
        print(f"  * {m['Month']}: {sign}Rs {abs(m['Net_INR']):,.0f} ({sign}${abs(m['Net_USD']):,.2f}) across {int(m['Trades'])} trades")

    print("=" * 65 + "\n", flush=True)

if __name__ == "__main__":
    run_large_capital_simulation("XAUUSD", "H1", 5000)
