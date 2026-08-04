"""
logger.py — Colorized Logging Utility for F&O Bot.
"""

import logging
import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, Fore.WHITE)
        record.msg = f"{color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)


def setup_logger(name: str = "FO_BOT", log_file: str = "fo_bot.log") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        c_handler = logging.StreamHandler()
        f_handler = logging.FileHandler(log_file)

        formatter = ColoredFormatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
        file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        c_handler.setFormatter(formatter)
        f_handler.setFormatter(file_formatter)

        logger.addHandler(c_handler)
        logger.addHandler(f_handler)

    return logger

logger = setup_logger()
