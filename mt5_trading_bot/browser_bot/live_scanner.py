"""
Continuous Live MT5 Signal Bridge — Competition Mode
Tuned for high-frequency signal generation on M5 candles.
Dynamically sizes lots from available margin.
"""
import MetaTrader5 as mt5
import pandas as pd
import sys, time, logging, urllib.request, json, math

sys.path.insert(0, 'd:/trading bot/mt5_trading_bot')
import ta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s]: %(message)s")
logger = logging.getLogger("LiveScanner")

BRIDGE_URL    = "http://localhost:8765/inject_signal"
SCAN_SYMBOLS  = ["EURUSD", "GBPUSD", "USDJPY"]
SCAN_INTERVAL = 15          # seconds between scans
MARGIN_USE    = 0.90        # 90% of free margin — MAX COMPETITION MODE
MIN_LOTS      = 0.01
MAX_LOTS      = 5.00
MT5_PATH      = 'C:\\Program Files\\MetaTrader 5\\terminal64.exe'
MT5_LOGIN     = 5054521327
MT5_SERVER    = 'MetaQuotes-Demo'
TIMEFRAME     = mt5.TIMEFRAME_M5   # M5 for more signals

last_signal_key = {}

# ── Competition-tuned indicators ──
def get_signal(df: pd.DataFrame, symbol: str):
    if len(df) < 220:
        return None

    df = df.copy()
    c = df['close']

    # EMAs
    df['ema5']   = ta.trend.EMAIndicator(close=c, window=5).ema_indicator()
    df['ema13']  = ta.trend.EMAIndicator(close=c, window=13).ema_indicator()
    df['ema200'] = ta.trend.EMAIndicator(close=c, window=200).ema_indicator()

    # RSI
    df['rsi'] = ta.momentum.RSIIndicator(close=c, window=14).rsi()

    # MACD
    macd = ta.trend.MACD(close=c, window_fast=12, window_slow=26, window_sign=9)
    df['macd_diff'] = macd.macd_diff()

    # ATR for SL/TP
    df['atr'] = ta.volatility.AverageTrueRange(
        high=df['high'], low=df['low'], close=df['close'], window=14
    ).average_true_range()

    curr = df.iloc[-2]
    prev = df.iloc[-3]
    price = df.iloc[-1]['close']

    if pd.isna(curr['ema200']) or pd.isna(curr['atr']) or curr['atr'] <= 0:
        return None

    atr = curr['atr']

    # ── BUY: Close > EMA200, EMA5 crosses above EMA13, RSI 35-65, MACD+
    bull_cross = (curr['ema5'] > curr['ema13']) and (prev['ema5'] <= prev['ema13'])
    rsi_ok_buy = 35 <= curr['rsi'] <= 65
    if curr['close'] > curr['ema200'] and bull_cross and curr['macd_diff'] > 0 and rsi_ok_buy:
        return {
            'signal':     'BUY',
            'price':      price,
            'stop_loss':  round(price - atr * 1.2, 5),
            'take_profit':round(price + atr * 2.5, 5),
            'reason':     f"EMA5x13 Bull | RSI {curr['rsi']:.1f} | MACD+"
        }

    # ── SELL: Close < EMA200, EMA5 crosses below EMA13, RSI 35-65, MACD-
    bear_cross = (curr['ema5'] < curr['ema13']) and (prev['ema5'] >= prev['ema13'])
    rsi_ok_sell = 35 <= curr['rsi'] <= 65
    if curr['close'] < curr['ema200'] and bear_cross and curr['macd_diff'] < 0 and rsi_ok_sell:
        return {
            'signal':     'SELL',
            'price':      price,
            'stop_loss':  round(price + atr * 1.2, 5),
            'take_profit':round(price - atr * 2.5, 5),
            'reason':     f"EMA5x13 Bear | RSI {curr['rsi']:.1f} | MACD-"
        }

    return None


def calculate_lots(symbol: str, price: float) -> float:
    acc = mt5.account_info()
    if not acc:
        return 0.10

    sym_info = mt5.symbol_info(symbol)
    if not sym_info:
        return 0.10

    free           = min(acc.margin_free, acc.equity) * MARGIN_USE
    contract_size  = sym_info.trade_contract_size
    leverage       = acc.leverage
    margin_per_lot = (contract_size * price) / leverage
    lot_step       = sym_info.volume_step

    if margin_per_lot <= 0:
        return MIN_LOTS

    lots = math.floor((free / margin_per_lot) / lot_step) * lot_step
    lots = round(max(MIN_LOTS, min(lots, MAX_LOTS)), 2)
    logger.info(
        f"[MARGIN] Free: ${acc.margin_free:.2f} | "
        f"Leverage: 1:{leverage} | Margin/lot: ${margin_per_lot:.2f} | Lots: {lots}"
    )
    return lots


def inject_signal(payload: dict):
    try:
        req = urllib.request.Request(
            BRIDGE_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        return json.loads(urllib.request.urlopen(req, timeout=5).read())
    except Exception as e:
        logger.error(f"Inject failed: {e}")
        return None


def main():
    if not mt5.initialize(path=MT5_PATH, login=MT5_LOGIN, server=MT5_SERVER):
        logger.error("MT5 init failed!")
        return

    acc = mt5.account_info()
    logger.info(f"Connected: #{acc.login} | Balance: ${acc.balance:.2f} | Leverage: 1:{acc.leverage}")
    logger.info(f"Scanning: {SCAN_SYMBOLS} | Timeframe: M5 | Every {SCAN_INTERVAL}s | Margin: {MARGIN_USE*100:.0f}%")
    logger.info("Competition mode active — waiting for EMA crossover signals...")

    while True:
        try:
            for sym in SCAN_SYMBOLS:
                rates = mt5.copy_rates_from_pos(sym, TIMEFRAME, 0, 250)
                if rates is None or len(rates) < 220:
                    logger.warning(f"{sym}: insufficient data ({len(rates) if rates is not None else 0} bars)")
                    continue

                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.rename(columns={'tick_volume': 'volume'}, inplace=True)

                sig = get_signal(df, sym)
                if not sig:
                    continue

                # Deduplicate by signal direction + rounded price
                sig_key = f"{sym}_{sig['signal']}_{round(sig['price'], 4)}"
                if last_signal_key.get(sym) == sig_key:
                    continue

                last_signal_key[sym] = sig_key

                # Calculate lots from live margin
                lots = calculate_lots(sym, sig['price'])

                logger.info(
                    f"SIGNAL >> {sym}: {sig['signal']} @ {sig['price']:.5f} | "
                    f"Lots: {lots} | SL: {sig['stop_loss']} | TP: {sig['take_profit']} | {sig['reason']}"
                )

                payload = {
                    'symbol':      sym,
                    'signal':      sig['signal'],
                    'price':       sig['price'],
                    'stop_loss':   sig['stop_loss'],
                    'take_profit': sig['take_profit'],
                    'lots':        lots,
                    'reason':      sig['reason'],
                    'timestamp':   time.time()
                }

                result = inject_signal(payload)
                if result:
                    logger.info(f"Bridge updated: {result['status']} | {sym} {sig['signal']} {lots} lots")

        except Exception as e:
            logger.error(f"Scanner error: {e}")

        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    main()
