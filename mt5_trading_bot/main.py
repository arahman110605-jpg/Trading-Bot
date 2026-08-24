"""
MetaTrader 5 Automated Trading Bot - Main Runner
Executes the Trend Momentum & Pullback Strategy in real-time.
"""
import sys
import os
import time
import logging
from datetime import datetime

# Adjust sys.path to resolve local packages
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from broker.mt5_client import MT5Client
from strategies.trend_momentum_strategy import TrendMomentumStrategy
from engine.risk_manager import RiskManager
from engine.trade_manager import TradeManager
import config

# Setup logging
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs"), exist_ok=True)
log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "mt5_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MT5Bot")

class MT5TradingBot:
    def __init__(self):
        self.client = MT5Client(
            account=config.MT5_ACCOUNT,
            password=config.MT5_PASSWORD,
            server=config.MT5_SERVER,
            path=config.MT5_PATH
        )
        self.strategy = TrendMomentumStrategy(
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
        self.risk_manager = RiskManager(
            max_risk_percent=config.MAX_RISK_PER_TRADE_PERCENT,
            default_lot_size=config.DEFAULT_LOT_SIZE,
            use_fixed_lot=config.USE_FIXED_LOT,
            max_open_trades_total=config.MAX_OPEN_TRADES_TOTAL,
            max_open_trades_per_symbol=config.MAX_OPEN_TRADES_PER_SYMBOL,
            max_spread_pips=config.MAX_ALLOWED_SPREAD_PIPS
        )
        self.trade_manager = TradeManager(
            client=self.client,
            enable_trailing_stop=config.ENABLE_TRAILING_STOP,
            trailing_trigger_atr=config.TRAILING_TRIGGER_ATR,
            trailing_step_atr=config.TRAILING_STEP_ATR
        )
        self.running = False

    def start(self):
        """Main bot execution loop"""
        logger.info("Initializing MetaTrader 5 Trading Bot...")
        if not self.client.connect():
            logger.error("Failed to connect to MT5 Terminal. Exiting.")
            return

        account_info = self.client.get_account_info()
        logger.info(
            f"Logged In: Login #{account_info.get('login')} ({account_info.get('name')}) | "
            f"Server: {account_info.get('server')} | Balance: {account_info.get('balance')} {account_info.get('currency')} | "
            f"Equity: {account_info.get('equity')} {account_info.get('currency')}"
        )
        logger.info(f"Target Symbols: {', '.join(config.SYMBOLS)} | Timeframe: {config.TIMEFRAME}")
        logger.info(f"Lot Size: {config.DEFAULT_LOT_SIZE} (Fixed: {config.USE_FIXED_LOT}) | Magic: {config.MAGIC_NUMBER}")

        self.running = True
        logger.info("Bot started successfully. Listening for signals...")

        while self.running:
            try:
                self.tick()
                time.sleep(config.SLEEP_INTERVAL_SECONDS)
            except KeyboardInterrupt:
                logger.info("Shutdown requested by user.")
                break
            except Exception as e:
                logger.exception(f"Unexpected error in bot tick: {e}")
                time.sleep(5)

        self.client.disconnect()
        logger.info("MT5 Trading Bot has stopped.")

    def tick(self):
        """Runs one scan cycle across all configured symbols"""
        account_info = self.client.get_account_info()
        if not account_info:
            return

        open_positions = self.client.get_open_positions(magic=config.MAGIC_NUMBER)
        latest_atrs = {}

        for symbol in config.SYMBOLS:
            sym_info = self.client.get_symbol_info(symbol)
            if sym_info is None:
                continue

            # Fetch candle data
            df = self.client.get_market_data(symbol, timeframe_str=config.TIMEFRAME, count=250)
            if df is None or len(df) < 220:
                continue

            latest_bar_time = df.iloc[-1]['time']
            if not hasattr(self, 'last_traded_bar'):
                self.last_traded_bar = {}

            # Generate Signal
            signal = self.strategy.generate_signal(df)

            if signal and "atr" in signal:
                latest_atrs[symbol] = signal["atr"]

            # If signal exists and this candle hasn't been traded yet, check risk criteria & execute
            if signal and (self.last_traded_bar.get(symbol) != latest_bar_time):
                can_trade = self.risk_manager.can_open_trade(
                    symbol=symbol,
                    open_positions=open_positions,
                    sym_info=sym_info,
                    account_info=account_info
                )

                if can_trade:
                    action = signal["signal"]
                    entry_p = signal["price"]
                    sl = signal["stop_loss"]
                    tp = signal["take_profit"]
                    reason = signal["reason"]

                    lot_size = self.risk_manager.calculate_lot_size(
                        account_info=account_info,
                        sym_info=sym_info,
                        entry_price=entry_p,
                        stop_loss=sl
                    )

                    logger.info(
                        f"[SIGNAL FOUND] {action} {symbol} @ {entry_p} | SL: {sl:.5f} | TP: {tp:.5f} | "
                        f"Lot: {lot_size} | Reason: {reason}"
                    )

                    order_id = self.client.open_order(
                        symbol=symbol,
                        order_type=action,
                        lot_size=lot_size,
                        stop_loss=sl,
                        take_profit=tp,
                        magic=config.MAGIC_NUMBER,
                        comment="TrendMomentum Bot"
                    )

                    self.last_traded_bar[symbol] = latest_bar_time

                    if order_id:
                        # Refresh open positions
                        open_positions = self.client.get_open_positions(magic=config.MAGIC_NUMBER)

        # Dynamic Trailing Stop updates
        if open_positions and latest_atrs:
            self.trade_manager.update_trailing_stops(open_positions, latest_atrs)

if __name__ == "__main__":
    bot = MT5TradingBot()
    bot.start()
