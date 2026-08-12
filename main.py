"""
main.py — Trading Bot Entry Point

Usage:
  python main.py                  # Paper trading mode (default, single bot)
  python main.py --mode paper     # Explicit paper mode
  python main.py --mode live      # Live trading (requires API key)
  python main.py --no-dashboard   # Run without web dashboard

Multi-Bot Mode (8 bots, shared data hub):
  Set MULTI_BOT_MODE=true in .env or Render environment variables
  then run: python main.py
"""

import argparse
import os
import sys
import threading
import time
from datetime import datetime

# ── Windows UTF-8 console fix ─────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass  # Python < 3.7 fallback
else:
    # Set timezone to IST for Render/Docker Linux environments
    os.environ["TZ"] = "Asia/Kolkata"
    try:
        time.tzset()
    except AttributeError:
        pass

# ── Logging setup first ───────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)

from utils.logger import get_logger, setup_logger
setup_logger()  # init root logger
log = get_logger("Main")

import config

# ── Arg parsing ───────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="Zerodha Intraday Trading Bot")
    parser.add_argument(
        "--mode", choices=["paper", "live"], default=None,
        help="Trading mode: paper (simulate) or live (real orders)"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Demo mode: use simulated market data (no API key needed)"
    )
    parser.add_argument(
        "--no-dashboard", action="store_true",
        help="Run without the web dashboard"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Demo mode forces paper + simulated data
    if args.demo:
        config.TRADING_MODE = "paper"
        log.info("DEMO MODE active — using simulated market data")
    elif args.mode:
        config.TRADING_MODE = args.mode

    print_banner()
    log.info("Starting Trading Bot | mode=%s | date=%s",
             config.TRADING_MODE.upper(), datetime.now().strftime("%Y-%m-%d"))

    # ── Validate config ───────────────────────────────────────────────────────
    if config.TRADING_MODE == "live":
        if config.KITE_API_KEY == "your_api_key_here":
            log.error("LIVE mode requires a real KITE_API_KEY in config.py or .env!")
            print("\n  ⚠  Set your Kite API key in config.py or create a .env file.")
            print("     See README.md for instructions.\n")
            sys.exit(1)

    # ── Broker / Auth ─────────────────────────────────────────────────────────
    kite_instance = None
    demo_feed     = None

    if args.demo:
        # Use simulated market data — no API key needed
        from data.demo_feed import DemoMarket
        demo_feed = DemoMarket(
            symbols=config.WATCHLIST,
            candle_interval_sec=30,   # New candle every 30 seconds (sped up)
        )
        # Speed up scan interval for demo mode
        config.CANDLE_INTERVAL = "demo"
        log.info("Demo feed ready — candles every 30 seconds")

    elif config.TRADING_MODE == "live":
        log.info("Authenticating with Zerodha Kite Connect...")
        try:
            from broker.auth import get_kite_session
            kite_instance = get_kite_session()
        except Exception as e:
            log.error("Authentication failed: %s", e)
            log.info("Falling back to paper mode.")
            config.TRADING_MODE = "paper"

    # ── Broker Client Selection ───────────────────────────────────────────────
    if config.BROKER == "angel":
        from broker.angel_client import AngelClient
        broker_client = AngelClient(demo_feed=demo_feed)
        log.info("Broker active: Angel One (SmartAPI - FREE)")
    else:
        from broker.kite_client import KiteClient
        broker_client = KiteClient(kite=kite_instance, demo_feed=demo_feed)
        log.info("Broker active: Zerodha (Kite Connect)")

    # ── Core components ───────────────────────────────────────────────────────
    from utils.trade_journal import TradeJournal
    from engine.risk_manager import RiskManager
    from engine.order_manager import OrderManager
    from engine.strategy_runner import StrategyRunner

    journal   = TradeJournal()
    risk_mgr  = RiskManager(journal=journal)
    order_mgr = OrderManager(kite=broker_client, risk=risk_mgr, journal=journal)

    # ── Multi-Bot Mode (8 independent bots, shared data hub) ─────────────────
    if config.MULTI_BOT_MODE:
        log.info("MULTI-BOT MODE enabled — launching 8 bots with shared MarketDataHub")
        from engine.multi_bot_manager import MultiBotManager

        def _on_update():
            pass  # Dashboard update hook (wired in after dashboard init)

        multi_manager = MultiBotManager(on_update_callback=_on_update)

        # ── Dashboard (multi-bot mode) ──────────────────────────────────
        if not args.no_dashboard:
            from dashboard.server import init_dashboard, run_dashboard
            init_dashboard(None, order_mgr, journal, multi_manager=multi_manager)
            dashboard_thread = threading.Thread(target=run_dashboard, daemon=True, name="Dashboard")
            dashboard_thread.start()
            log.info("Dashboard running at http://localhost:%d (Multi-Bot Arena)", config.DASHBOARD_PORT)

        print_banner(multi_bot=True)
        multi_manager.start()

        log.info("All 8 bots running. Press Ctrl+C to stop.")
        print("\n  " + "="*58)
        print(f"  Dashboard : http://localhost:{config.DASHBOARD_PORT}")
        print(f"  Arena     : http://localhost:{config.DASHBOARD_PORT}/arena")
        print(f"  Mode      : MULTI-BOT (8 bots | 1 API connection)")
        print(f"  Capital   : INR {8 * 100000:,} (8 x INR 1,00,000)")
        print("  " + "="*58 + "\n")

        try:
            while True:
                time.sleep(30)
        except KeyboardInterrupt:
            log.info("Ctrl+C received. Shutting down all bots...")
            multi_manager.stop()
            log.info("Multi-bot shutdown complete.")
        return

    # ── Single-Bot Mode (original behaviour) ────────────────────────────
    runner    = StrategyRunner(kite=broker_client, order_mgr=order_mgr, risk_mgr=risk_mgr)

    # In demo mode, use faster tick interval (30 sec)
    if args.demo:
        runner.tick_secs = 30
        log.info("Demo: scan interval set to 30 seconds")

    # ── Dashboard ─────────────────────────────────────────────────────────────
    dashboard_thread = None
    if not args.no_dashboard:
        from dashboard.server import init_dashboard, run_dashboard
        init_dashboard(runner, order_mgr, journal)

        dashboard_thread = threading.Thread(
            target=run_dashboard,
            daemon=True,
            name="Dashboard",
        )
        dashboard_thread.start()
        log.info("✓ Dashboard running at http://localhost:%d", config.DASHBOARD_PORT)
    else:
        log.info("Dashboard disabled (--no-dashboard flag set)")

    # ── Check market hours ────────────────────────────────────────────────────
    if args.demo:
        # Demo mode ignores market hours — always runs
        log.info("Demo mode: bypassing market hours check")
        runner.start()
    elif not risk_mgr.is_market_open():
        log.warning(
            "Market is currently CLOSED. Bot is ready but won't place trades.\n"
            "   Market hours: Mon-Fri 09:15 - 15:15 IST\n"
            "   Dashboard is still accessible for configuration."
        )
    else:
        log.info("Market is OPEN. Starting bot immediately.")
        runner.start()

    # ── Keep alive ────────────────────────────────────────────────────────────
    log.info("Bot running. Press Ctrl+C to stop.")
    demo_label = " [DEMO - Simulated Data]" if args.demo else ""
    print("\n  " + "="*58)
    print(f"  Dashboard : http://localhost:{config.DASHBOARD_PORT}")
    print(f"  Mode      : {config.TRADING_MODE.upper()}{demo_label}")
    print(f"  Capital   : INR {config.CAPITAL:,}")
    print(f"  Watchlist : {', '.join(config.WATCHLIST[:5])}{'...' if len(config.WATCHLIST) > 5 else ''}")
    print("  " + "="*58 + "\n")

    try:
        while True:
            # Check if market opened (for when bot starts before market hours)
            if (not args.demo
                    and not runner._running
                    and risk_mgr.is_market_open()
                    and runner.status == "STOPPED"):
                log.info("Market opened. Starting strategy runner...")
                risk_mgr.reset_daily()
                runner.start()

            time.sleep(30)

    except KeyboardInterrupt:
        log.info("Ctrl+C received. Shutting down...")
        runner.stop()

        if order_mgr.get_open_positions():
            log.warning("Warning: You have %d open positions!", len(order_mgr.get_open_positions()))
            answer = input("Square off all positions before exit? [y/N]: ").strip().lower()
            if answer == "y":
                order_mgr.square_off_all()
                log.info("All positions squared off.")

        log.info("Bot shutdown complete. Goodbye!")


def print_banner(multi_bot: bool = False):
    if multi_bot:
        banner = """
  ███╗   ███╗██╗   ██╗██╗  ████████╗██╗    ██████╗  ██████╗ ████████╗
  ████╗ ████║██║   ██║██║  ╚══██╔══╝██║    ██╔══██╗██╔═══██╗╚══██╔══╝
  ██╔████╔██║██║   ██║██║     ██║   ██║    ██████╔╝██║   ██║   ██║
  ██║╚██╔╝██║██║   ██║██║     ██║   ██║    ██╔══██╗██║   ██║   ██║
  ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║    ██████╔╝╚██████╔╝   ██║
  ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝    ╚═════╝  ╚═════╝    ╚═╝

    8 Bot Arena  |  5 Equity + 3 Options  |  1 Angel One Connection
    """
    else:
        banner = """
  ████████╗██████╗  █████╗ ██████╗ ███████╗██████╗  ██████╗ ████████╗
     ██╔══╝██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝
     ██║   ██████╔╝███████║██║  ██║█████╗  ██████╔╝██║   ██║   ██║
     ██║   ██╔══██╗██╔══██║██║  ██║██╔══╝  ██╔══██╗██║   ██║   ██║
     ██║   ██║  ██║██║  ██║██████╔╝███████╗██████╔╝╚██████╔╝   ██║
     ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚══════╝╚═════╝  ╚═════╝    ╚═╝

    Zerodha Intraday Bot  |  NSE + BSE Equities  |  4 Strategies
    """
    print(banner)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        import time
        print("\n" + "="*50)
        print("FATAL ERROR CRASHED MAIN THREAD:")
        print("="*50)
        traceback.print_exc()
        print("="*50)
        print("Sleeping for 10 minutes before exiting to prevent rapid crash loops on Render...")
        try:
            time.sleep(600)
        except:
            pass
        sys.exit(1)
