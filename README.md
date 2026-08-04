# 🤖 Zerodha Intraday Trading Bot

A fully automated Python trading bot for NSE/BSE equities using the **Zerodha Kite Connect API**.

## ✨ Features

- **4 Intraday Strategies**: EMA Crossover, RSI, VWAP, Supertrend
- **Risk Management**: ATR-based SL/Target, max daily loss, position sizing
- **Auto Square-Off**: All positions closed by 3:15 PM IST
- **Paper Trading Mode**: Test safely before going live
- **Live Web Dashboard**: Real-time P&L, positions, signals, trade log
- **WebSocket Updates**: Dashboard refreshes in real-time without page reload

---

## 🚀 Quick Start

### Step 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Configure

Copy the env template and fill in your settings:
```bash
copy .env.example .env
```

Edit `config.py` or `.env` to set:
- `KITE_API_KEY` and `KITE_API_SECRET` (for live mode)
- `CAPITAL` — your trading capital in ₹
- `WATCHLIST` — stocks to scan

### Step 3 — Run in Paper Mode (recommended first)

```bash
python main.py --mode paper
```

### Step 4 — Open Dashboard

Visit: **http://localhost:5000**

### Step 5 — Go Live (when ready)

```bash
python main.py --mode live
```
This will open a browser for Zerodha login. After logging in, paste the `request_token` from the redirect URL.

---

## 📁 Project Structure

```
trading-bot/
├── main.py              ← Entry point
├── config.py            ← All settings
├── .env                 ← API keys (never commit!)
├── broker/
│   ├── auth.py          ← Kite Connect authentication
│   └── kite_client.py   ← Order & data API wrapper
├── strategies/
│   ├── ema_crossover.py ← EMA 9/21 crossover
│   ├── rsi_strategy.py  ← RSI mean reversion
│   ├── vwap_strategy.py ← VWAP momentum
│   └── supertrend.py    ← Supertrend trend follower
├── engine/
│   ├── strategy_runner.py ← Main trading loop
│   ├── order_manager.py   ← Trade lifecycle
│   └── risk_manager.py    ← Risk & position sizing
├── dashboard/
│   ├── server.py          ← Flask + SocketIO server
│   ├── templates/index.html
│   └── static/            ← CSS & JS
└── utils/
    ├── logger.py          ← Colored logging
    └── trade_journal.py   ← SQLite trade database
```

---

## ⚙️ Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---|---|---|
| `TRADING_MODE` | `"paper"` | `"paper"` or `"live"` |
| `CAPITAL` | `100000` | Trading capital (₹) |
| `RISK_PER_TRADE_PCT` | `1.5` | Risk per trade (% of capital) |
| `MAX_DAILY_LOSS_PCT` | `4.0` | Daily loss limit (%) |
| `MAX_OPEN_POSITIONS` | `3` | Max simultaneous trades |
| `CANDLE_INTERVAL` | `"5minute"` | Chart timeframe |
| `WATCHLIST` | 10 stocks | Stocks to scan |

---

## 📊 Strategies

| Strategy | Entry | Exit |
|---|---|---|
| **EMA Crossover** | EMA9 crosses EMA21 (+ RSI filter) | ATR-based SL/Target |
| **RSI** | RSI exits oversold/overbought zone | ATR-based SL/Target |
| **VWAP** | Price bounces through VWAP | ATR-based SL/Target |
| **Supertrend** | Supertrend direction flip | ATR-based SL/Target |

---

## 🔑 Getting a Kite Connect API Key

1. Go to [kite.trade](https://kite.trade)
2. Log in with your Zerodha credentials
3. Click **"Create App"**
4. Set redirect URL to `http://localhost` (or any URL)
5. Get your **API Key** and **API Secret**
6. Subscription: ₹2,000/month (or 60-day free trial)

---

## ⚠️ Risk Disclaimer

> This software is for educational purposes. Automated trading carries significant financial risk. Always test in paper mode first. Past performance does not guarantee future results. The authors are not responsible for any financial losses.

---

## 🛡️ Safety Features

- ✅ Paper mode by default — no real orders unless you explicitly set `--mode live`
- ✅ Max daily loss limit — bot auto-stops when daily loss exceeds threshold
- ✅ Auto square-off — all positions closed by 3:15 PM IST
- ✅ Position size limits — never risks more than configured % per trade
- ✅ No new entries after 2:45 PM — avoids late-day volatility
