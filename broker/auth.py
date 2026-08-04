"""
broker/auth.py — Zerodha Kite Connect authentication flow.

On first run:
  1. Opens the Kite login URL in your browser
  2. After login, Kite redirects to your callback URL with `request_token`
  3. Paste the request_token here (or it can be extracted from the redirect URL)
  4. The access token is saved to `.env` for subsequent runs
"""

import os
import webbrowser
from datetime import date
from dotenv import set_key

from kiteconnect import KiteConnect
from utils.logger import get_logger

import config

log = get_logger("Auth")

ENV_FILE = ".env"
TOKEN_DATE_KEY = "TOKEN_DATE"
ACCESS_TOKEN_KEY = "KITE_ACCESS_TOKEN"


def get_kite_session() -> KiteConnect:
    """
    Returns an authenticated KiteConnect instance.
    Handles token refresh automatically.
    """
    kite = KiteConnect(api_key=config.KITE_API_KEY)

    # Check if today's token is already saved
    saved_token = config.KITE_ACCESS_TOKEN
    saved_date  = os.getenv("TOKEN_DATE", "")

    if saved_token and saved_date == date.today().isoformat():
        log.info("Using saved access token (valid for today)")
        kite.set_access_token(saved_token)
        return kite

    # Need fresh login
    log.info("Access token not found or expired. Starting login flow...")
    login_url = kite.login_url()
    log.info("Opening Kite login URL: %s", login_url)
    webbrowser.open(login_url)

    print("\n" + "="*60)
    print("  KITE LOGIN REQUIRED")
    print("="*60)
    print("1. Complete login in the browser that just opened.")
    print("2. After login, you'll be redirected to a URL like:")
    print("   http://localhost/?request_token=XXXXXXXXXX&action=login&status=success")
    print("3. Copy the 'request_token' value from the URL.\n")

    request_token = input("Paste the request_token here: ").strip()

    try:
        data = kite.generate_session(request_token, api_secret=config.KITE_API_SECRET)
        access_token = data["access_token"]

        # Persist to .env
        _save_env(ACCESS_TOKEN_KEY, access_token)
        _save_env(TOKEN_DATE_KEY, date.today().isoformat())

        kite.set_access_token(access_token)
        log.info("✓ Authentication successful! Token saved.")
        return kite

    except Exception as e:
        log.error("Authentication failed: %s", e)
        raise


def _save_env(key: str, value: str):
    """Save a key=value pair to the .env file."""
    if not os.path.exists(ENV_FILE):
        open(ENV_FILE, "w").close()
    set_key(ENV_FILE, key, value)
