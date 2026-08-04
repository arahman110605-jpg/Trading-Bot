"""
utils/logger.py — Colored, structured logging for the trading bot.
"""

import logging
import os
import sys
from datetime import datetime

try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False

import config


def setup_logger(name: str = "TradingBot") -> logging.Logger:
    """Set up and return a configured logger."""
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))

    if logger.handlers:
        return logger  # Already configured

    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # ── Console handler (colored if available) ──
    if HAS_COLORLOG:
        color_fmt = (
            "%(log_color)s%(asctime)s | %(levelname)-8s%(reset)s | "
            "%(cyan)s%(name)s%(reset)s | %(message)s"
        )
        console_handler = colorlog.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            colorlog.ColoredFormatter(
                color_fmt,
                datefmt=datefmt,
                log_colors={
                    "DEBUG":    "white",
                    "INFO":     "green",
                    "WARNING":  "yellow",
                    "ERROR":    "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    # ── File handler ──
    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


# Singleton root logger
logger = setup_logger("TradingBot")


def get_logger(name: str) -> logging.Logger:
    """Get a child logger inheriting root config."""
    return logging.getLogger(f"TradingBot.{name}")
