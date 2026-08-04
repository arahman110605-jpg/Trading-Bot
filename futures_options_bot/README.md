# ⚡ Futures & Options (F&O) Algorithmic Trading Bot

An automated Python trading bot specifically designed for **NSE Futures & Options (NFO)** trading in Indian markets (NIFTY, BANKNIFTY, FINNIFTY, and F&O Equities).

Supports **Angel One (SmartAPI)** and **Zerodha (Kite Connect)** APIs, option greeks modeling (Black-Scholes), strike selector engine, multi-leg strategies, and a real-time web dashboard.

---

## ✨ Key Features

- **Option Strike Selector**: Automatically computes ATM, ITM (+1 step), or OTM (-1 step) CE/PE options based on underlying spot prices & strike step sizes.
- **Option Greeks Calculator**: Calculates live Delta, Gamma, Theta, Vega, and Implied Volatility (IV) using Black-Scholes model.
- **Expiry Helper**: Automatic weekly/monthly expiry contract calculation for NIFTY, BANKNIFTY, and FINNIFTY.
- **4 Specialized F&O Strategies**:
  1. **Option Buying (Momentum & Breakout)**: ATM/ITM Call & Put buying with trailing stop loss.
  2. **Short Straddle / Strangle**: Premium decay (Theta) capture with strict per-leg stop loss.
  3. **Hedged Spreads (Bull Call / Bear Put / Iron Condor)**: Risk-defined multi-leg option spreads.
  4. **Futures Trend Following**: Futures Long/Short contract trading with ATR trailing stop loss.
- **Paper Trading Simulator**: Test strategies safely with simulated tick execution and live option chain modeling before putting real capital at risk.
- **F&O Risk Manager**: Lot limits, max drawdown limits, % premium SL/Target, and 3:15 PM IST auto square-off.
- **Dedicated Web Dashboard**: Runs on `http://localhost:5001` with real-time WebSocket updates.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Credentials
Copy the `.env.example` file to `.env`:
```bash
copy .env.example .env
```
Fill in your Angel One or Zerodha API credentials.

### 3. Run in Paper Trading Mode (Recommended)
```bash
python main.py --mode paper --symbol NIFTY --strategy all
```

### 4. Launch Live Web Dashboard
Open your browser at: **`http://localhost:5001`**

### 5. Run Live Trading (When Ready)
```bash
python main.py --mode live --symbol NIFTY --strategy option_buying
```

---

## 📊 Directory Overview

- `config.py` — Central F&O settings, lot sizes, step sizes, and risk thresholds.
- `broker/` — Angel One & Zerodha F&O API connectors and Paper Trading broker.
- `utils/` — Black-Scholes option greeks, expiry calendar, analytics exporter.
- `engine/` — Strike selector, position risk manager, and order execution runner.
- `strategies/` — Option buying, short straddle, credit spreads, and futures trend strategies.
- `dashboard/` — Real-time Glassmorphic web dashboard (Port 5001).
