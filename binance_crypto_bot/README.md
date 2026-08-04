# ⚡ Binance Crypto & Web3 Trading Bot

A high-performance Python algorithmic trading bot for **Binance Spot, USD-M Futures, and Web3 Decentralized Exchanges (PancakeSwap/Uniswap)**.

---

## ✨ Key Features

- **Binance CEX Support**: Trade Spot & Futures with configurable leverage (1x – 20x).
- **Web3 DEX Integration**: Execute token swaps on **PancakeSwap** (BNB Smart Chain) or **Uniswap** (Ethereum/Polygon) via `web3.py`.
- **Binance Testnet & Paper Trading**: Safely test strategies using Binance Testnet or simulated Paper Trading mode.
- **4 Crypto Trading Strategies**:
  1. **EMA Crossover**: Trend-following fast/slow moving average strategy.
  2. **RSI Divergence**: Overbought/Oversold momentum strategy.
  3. **Grid Trading**: Quantitative grid orders for volatile/ranging crypto markets.
  4. **MACD Scalping**: High-frequency momentum scalper with Bollinger Bands confirmation.
- **Crypto Risk Management**: Automated position sizing, ATR stop loss, liquidation guard, and max daily loss cutoff.
- **Real-Time Web Dashboard**: Flask-powered dark theme dashboard on `http://localhost:5002` showing live balances, tickers, positions, and emergency controls.

---

## 📁 Folder Architecture

```
binance_crypto_bot/
├── .env.example              # API credentials & Web3 private key template
├── README.md                 # Setup & usage documentation
├── config.py                 # Central configuration
├── main.py                   # Main CLI entry point
├── requirements.txt          # Dependencies
├── broker/
│   ├── binance_client.py     # Binance Spot & Futures REST/WebSocket wrapper
│   ├── web3_dex_client.py   # Web3 PancakeSwap/Uniswap DEX client
│   └── paper_crypto_broker.py # Crypto paper trading simulator
├── engine/
│   ├── order_executor.py     # Order execution across CEX & DEX
│   ├── risk_manager.py       # Leverage, SL/TP, and liquidation guard
│   └── strategy_runner.py    # Multi-symbol event loop
├── strategies/
│   ├── base_strategy.py      # Abstract strategy class
│   ├── ema_crossover.py      # Fast/Slow EMA crossover
│   ├── rsi_divergence.py     # RSI momentum
│   ├── grid_trading.py       # Quantitative grid trading
│   └── macd_scalping.py      # MACD + Bollinger Bands scalper
├── dashboard/
│   ├── app.py                # Flask server
│   ├── templates/index.html  # Dashboard UI
│   └── static/               # Stylesheets and frontend scripts
└── utils/
    ├── indicators.py         # EMA, RSI, MACD, ATR, Bollinger Bands
    └── logger.py             # Custom logging
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials (Optional for Paper Mode)

Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```

For Binance Live/Testnet or Web3, add your keys to `.env`:
```ini
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret
BINANCE_TESTNET=true

WEB3_RPC_URL=https://bsc-dataseed.binance.org/
WEB3_PRIVATE_KEY=your_private_key
```

### 3. Run in Paper Trading Mode

Test strategies risk-free on BTC and ETH:
```bash
python main.py --mode paper --symbols BTCUSDT,ETHUSDT
```

Open your browser at **http://localhost:5002** to view the live dashboard!

### 4. Run Futures or Web3 DEX Mode

Run Binance Futures with 5x leverage:
```bash
python main.py --mode paper --broker binance_futures --leverage 5
```

Run Web3 DEX Mode:
```bash
python main.py --mode paper --broker web3_dex
```

---

## 🖥️ Command-Line Arguments

| Argument | Options / Format | Default | Description |
|---|---|---|---|
| `--mode` | `paper`, `live` | `paper` | Trading mode |
| `--broker` | `binance_spot`, `binance_futures`, `web3_dex` | `binance_spot` | Broker connector |
| `--symbols` | Comma-separated (e.g. `BTCUSDT,ETHUSDT`) | `BTCUSDT,ETHUSDT` | Crypto watchlist |
| `--strategy` | `ema_crossover`, `rsi_divergence`, `grid_trading`, `macd_scalping`, `all` | `all` | Strategy selection |
| `--leverage` | Integer (1–20) | `5` | Futures leverage |
| `--capital` | Float | `1000.0` | Initial capital in USDT |
| `--port` | Port number | `5002` | Dashboard web port |
| `--no-dashboard` | Flag | `False` | Run headless without web server |
