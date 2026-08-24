"""
Playwright Standalone XM Competitions Automated Runner
Launches or attaches to Chrome, navigates to the XM Competitions Arena,
and continuously runs the Trend-Momentum Strategy directly in the browser.
"""
import sys
import os
import time
import asyncio
import logging
from playwright.async_api import async_playwright

# Adjust path to import core strategy modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broker.mt5_client import MT5Client
from strategies.trend_momentum_strategy import TrendMomentumStrategy
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [PlaywrightBot]: %(message)s")
logger = logging.getLogger("PlaywrightBot")

COMPETITION_URL = "https://my.xm.com/competitions"
DEFAULT_LOT_SIZE = "0.10"

async def run_browser_trader():
    logger.info("Initializing Playwright Browser Bot for XM Competitions...")

    # Initialize MT5 Market Data Client
    client = MT5Client(
        account=config.MT5_ACCOUNT,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
        path=config.MT5_PATH
    )

    if not client.connect():
        logger.error("Failed to connect MT5 Client. Make sure MT5 is open.")
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

    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_user_data")
    os.makedirs(user_data_dir, exist_ok=True)

    async with async_playwright() as p:
        # Launch persistent browser so login session is preserved
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            viewport={"width": 1440, "height": 900},
            args=["--disable-blink-features=AutomationControlled"]
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()
        await page.goto(COMPETITION_URL)
        logger.info("Browser opened. Navigate/login to the active competition arena.")

        symbols = ["EURUSD", "GBPUSD", "USDJPY", "GOLD"]
        last_traded_time = {}

        while True:
            try:
                for sym in symbols:
                    df = client.get_market_data(sym, timeframe_str="M15", count=250)
                    if df is None or len(df) < 220:
                        continue

                    sig = strategy.generate_signal(df)
                    if sig:
                        action = sig["signal"]
                        price = sig["price"]
                        sl = sig["stop_loss"]
                        tp = sig["take_profit"]

                        sig_key = f"{sym}_{action}"
                        if sig_key in last_traded_time and (time.time() - last_traded_time[sig_key] < 900):
                            continue

                        logger.info(f"⚡ [COMPETITION SIGNAL] {action} {sym} @ {price} | TP: {tp} | SL: {sl}")

                        # Check if volume input is present on the page
                        vol_input = await page.query_selector('input[placeholder*="Volume"], input[type="number"]')
                        if vol_input:
                            await vol_input.fill(DEFAULT_LOT_SIZE)
                            await asyncio.sleep(0.3)

                        # Click Buy / Sell button
                        btn_selector = f'button:has-text("{action}"), div[role="button"]:has-text("{action}")'
                        btn = await page.query_selector(btn_selector)
                        if btn:
                            await btn.click()
                            await asyncio.sleep(0.4)

                        # Submit Order
                        submit_btn = await page.query_selector('button:has-text("Place Order"), button:has-text("Confirm")')
                        if submit_btn:
                            await submit_btn.click()
                            logger.info(f"✅ Trade placed on web: {action} {sym} ({DEFAULT_LOT_SIZE} lots)")
                            last_traded_time[sig_key] = time.time()

                await asyncio.sleep(10)
            except Exception as err:
                logger.error(f"Tick error: {err}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_browser_trader())
