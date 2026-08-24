"""
Enhanced Controlled Grid with:
1. Macro 200 EMA Trend Filter (Only Buy in Uptrend, Only Sell in Downtrend)
2. Exit #1: Basket Breakeven & TP ($10)
3. Exit #2: Hard 10% Equity Stop
4. Dynamic ATR-based grid spacing
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import ta

INITIAL_BALANCE = 1000.0
MAX_GRID_LEVELS = 5
LOT_MULTIPLIER = 1.35
BASE_LOT = 0.02
BASKET_TP_USD = 10.0
HARD_STOP_EQUITY_PCT = 0.10
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY"]

def run_enhanced_backtest(symbol: str, count: int = 15000):
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
    if rates is None or len(rates) < 1000:
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    pip_size = 0.0001 if 'JPY' not in symbol else 0.01

    # Indicators
    df['ema200'] = ta.trend.EMAIndicator(close=df['close'], window=200).ema_indicator()
    df['ema20'] = ta.trend.EMAIndicator(close=df['close'], window=20).ema_indicator()
    df['atr'] = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range()

    balance = INITIAL_BALANCE
    equity = INITIAL_BALANCE
    peak_equity = INITIAL_BALANCE
    max_drawdown_usd = 0.0
    max_drawdown_pct = 0.0

    total_baskets = 0
    baskets_won = 0
    baskets_hard_stopped = 0
    open_positions = []
    basket_direction = None

    for i in range(210, len(df)):
        current_bar = df.iloc[i]
        price_close = current_bar['close']
        time_curr = current_bar['time']
        atr_pips = (current_bar['atr'] / pip_size) if not pd.isna(current_bar['atr']) else 15.0
        grid_step = max(12.0, atr_pips * 1.2)

        if open_positions:
            floating_pnl = 0.0
            total_lots = sum(p['lot'] for p in open_positions)
            
            for p in open_positions:
                pips = (price_close - p['open_price']) / pip_size if p['type'] == 'BUY' else (p['open_price'] - price_close) / pip_size
                pip_val = p['lot'] * (10.0 if 'JPY' not in symbol else 1000.0 / price_close)
                floating_pnl += pips * pip_val

            equity = balance + floating_pnl
            if equity > peak_equity:
                peak_equity = equity
            dd_usd = peak_equity - equity
            dd_pct = (dd_usd / peak_equity) * 100.0
            if dd_usd > max_drawdown_usd:
                max_drawdown_usd = dd_usd
            if dd_pct > max_drawdown_pct:
                max_drawdown_pct = dd_pct

            # EXIT #2: HARD 10% EQUITY STOP
            if floating_pnl <= -(balance * HARD_STOP_EQUITY_PCT):
                balance += floating_pnl
                equity = balance
                baskets_hard_stopped += 1
                total_baskets += 1
                open_positions = []
                basket_direction = None
                continue

            # EXIT #1: BASKET BREAKEVEN + TP
            if floating_pnl >= BASKET_TP_USD:
                balance += floating_pnl
                equity = balance
                baskets_won += 1
                total_baskets += 1
                open_positions = []
                basket_direction = None
                continue

            # GRID EXPANSION
            if len(open_positions) < MAX_GRID_LEVELS:
                last_pos = open_positions[-1]
                if basket_direction == 'BUY':
                    pips_against = (last_pos['open_price'] - price_close) / pip_size
                    if pips_against >= grid_step:
                        next_lot = round(last_pos['lot'] * LOT_MULTIPLIER, 2)
                        open_positions.append({'type': 'BUY', 'open_price': price_close, 'lot': next_lot})
                elif basket_direction == 'SELL':
                    pips_against = (price_close - last_pos['open_price']) / pip_size
                    if pips_against >= grid_step:
                        next_lot = round(last_pos['lot'] * LOT_MULTIPLIER, 2)
                        open_positions.append({'type': 'SELL', 'open_price': price_close, 'lot': next_lot})

        else:
            # TREND-ALIGNED ENTRY
            close = current_bar['close']
            ema200 = current_bar['ema200']
            ema20 = current_bar['ema20']
            
            if pd.isna(ema200) or pd.isna(ema20):
                continue

            # Only BUY when strictly in Macro Uptrend (Close > EMA200)
            if close > ema200 and close > ema20 and df['close'].iloc[i-1] <= df['ema20'].iloc[i-1]:
                basket_direction = 'BUY'
                open_positions.append({'type': 'BUY', 'open_price': price_close, 'lot': BASE_LOT})
            # Only SELL when strictly in Macro Downtrend (Close < EMA200)
            elif close < ema200 and close < ema20 and df['close'].iloc[i-1] >= df['ema20'].iloc[i-1]:
                basket_direction = 'SELL'
                open_positions.append({'type': 'SELL', 'open_price': price_close, 'lot': BASE_LOT})

    net_profit = balance - INITIAL_BALANCE
    roi_pct = (net_profit / INITIAL_BALANCE) * 100.0
    win_rate = (baskets_won / total_baskets * 100.0) if total_baskets > 0 else 0.0

    return {
        'symbol': symbol,
        'start_date': df['time'].min().strftime('%Y-%m-%d'),
        'end_date': df['time'].max().strftime('%Y-%m-%d'),
        'final_balance': round(balance, 2),
        'net_profit': round(net_profit, 2),
        'roi_pct': round(roi_pct, 2),
        'total_baskets': total_baskets,
        'baskets_won': baskets_won,
        'baskets_hard_stopped': baskets_hard_stopped,
        'win_rate': round(win_rate, 2),
        'max_drawdown_usd': round(max_drawdown_usd, 2),
        'max_drawdown_pct': round(max_drawdown_pct, 2),
    }

def main():
    if not mt5.initialize(path='C:\\Program Files\\MetaTrader 5\\terminal64.exe', login=5054521327, server='MetaQuotes-Demo'):
        print("MT5 Failed")
        return

    print("=" * 68)
    print("  ENHANCED TREND-ALIGNED GRID + DUAL EXIT (#1 Basket TP + #2 10% Stop)")
    print(f"  Account: $1,000 USD | Max Loss Cap: 10% ($100) | Basket TP: ${BASKET_TP_USD}")
    print("=" * 68)

    results = []
    for sym in SYMBOLS:
        res = run_enhanced_backtest(sym, count=15000)
        if res:
            results.append(res)
            print(f"\n[{sym}] Performance ({res['start_date']} to {res['end_date']}):")
            print(f"  Final Balance:        ${res['final_balance']:.2f} (ROI: {res['roi_pct']:+.2f}%)")
            print(f"  Total Baskets:        {res['total_baskets']}")
            print(f"  Baskets Won (TP):     {res['baskets_won']} ({res['win_rate']}%)")
            print(f"  Baskets Cut (10% SL): {res['baskets_hard_stopped']}")
            print(f"  Max Drawdown:         ${res['max_drawdown_usd']:.2f} ({res['max_drawdown_pct']:.2f}%)")

    print("\n" + "=" * 68)
    total_net = sum(r['net_profit'] for r in results)
    avg_roi = np.mean([r['roi_pct'] for r in results])
    print(f"  Combined Portfolio Net Profit: ${total_net:+.2f}")
    print(f"  Average Portfolio Return:      {avg_roi:+.2f}%")
    print("=" * 68)
    mt5.shutdown()

if __name__ == "__main__":
    main()
