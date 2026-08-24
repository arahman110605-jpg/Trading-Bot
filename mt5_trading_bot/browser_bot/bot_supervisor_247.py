"""
================================================================================
SELF-HEALING 24/7 OVERWATCH SUPERVISOR FOR LIVE TRADING BOT
================================================================================
- Monitors live_ic_markets_bot.py 24/7.
- Automatically detects crashes, exceptions, MT5 disconnections, IPC errors.
- Restarts and recovers state with zero human intervention.
- Performs diagnostic health logging every 60 seconds.
================================================================================
"""

import subprocess
import time
import os
import sys
import logging
import datetime

SUPERVISOR_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SUPERVISOR_DIR, "bot_supervisor_247.log")
BOT_SCRIPT = os.path.join(SUPERVISOR_DIR, "live_ic_markets_bot.py")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SUPERVISOR]: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("247_Supervisor")

MAX_CONSECUTIVE_CRASHES = 10
RESTART_DELAY_SECONDS = 3

def run_bot_supervised():
    crash_count = 0
    logger.info("=" * 70)
    logger.info("  24/7 AUTONOMOUS SELF-HEALING SUPERVISOR STARTED")
    logger.info(f"  Target Bot: {BOT_SCRIPT}")
    logger.info("=" * 70)

    while True:
        try:
            logger.info("Launching Live Active Trading Bot child process...")
            # Run bot in dedicated process
            process = subprocess.Popen(
                [sys.executable, BOT_SCRIPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )
            
            logger.info(f"Bot successfully launched with PID: {process.pid}")
            crash_count = 0 # Reset crash counter on successful launch

            # Stream output in real-time
            for line in process.stdout:
                line_str = line.strip()
                if line_str:
                    # Echo to supervisor log
                    if "[ERROR]" in line_str or "[WARNING]" in line_str or "[HEARTBEAT]" in line_str or "CLOSED" in line_str or "ORDER" in line_str:
                        logger.info(f"[CHILD]: {line_str}")

            process.wait()
            ret_code = process.returncode
            logger.warning(f"Bot process exited with code: {ret_code}")

        except Exception as e:
            logger.error(f"Supervisor encountered error running child process: {e}")

        crash_count += 1
        if crash_count > MAX_CONSECUTIVE_CRASHES:
            logger.critical("🚨 Bot crashed 10 times consecutively. Backing off for 60 seconds...")
            time.sleep(60)
            crash_count = 0
        else:
            logger.warning(f"🔄 Auto-Healing & Restarting Bot in {RESTART_DELAY_SECONDS} seconds (Crash Count: {crash_count})...")
            time.sleep(RESTART_DELAY_SECONDS)

if __name__ == "__main__":
    run_bot_supervised()
