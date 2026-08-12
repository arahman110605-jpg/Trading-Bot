# ⚡ Delta Exchange Options & Binance Crypto Bot

A high-performance Python algorithmic trading bot for **Delta Exchange Crypto Options (BTC & ETH Options: Call/Put Buying, Short Straddles, Credit Spreads, Black-Scholes Greeks)** alongside **Binance Spot, USD-M Futures, and Web3 DEXs**.

---

## ✨ Key Features

- **Delta Exchange Options Trading**:
  - Real REST API client with HMAC-SHA256 authentication.
  - Supports **Call & Put Option Buying**, **Delta-Neutral Short Straddles**, and **Defined-Risk Credit Spreads**.
  - **Black-Scholes Options Engine**: Calculates theoretical option price, Delta $\Delta$, Gamma $\Gamma$, Theta $\Theta$, and Vega $\mathcal{V}$.
  - **Option Chain Resolver**: Automatically selects At-The-Money (ATM) and Out-Of-The-Money (OTM) strike prices.
- **Binance CEX & Web3 DEX**: Support for Binance Spot, USD-M Futures, and Web3 PancakeSwap/Uniswap DEX token swaps.
- **Crypto Risk Management**: Position sizing, Stop-Loss on option premium, and Max Daily Loss Guard.
- **Interactive Options Dashboard**: Real-time Flask dashboard on `http://localhost:5002` showing option contracts, strikes, premiums, Greeks, and trade logs.

---

## 🚀 Quick Start Guide

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Credentials

Add your Delta Exchange API credentials in `.env`:
```ini
DELTA_API_KEY=your_delta_api_key
DELTA_API_SECRET=your_delta_api_secret
DELTA_BASE_URL=https://api.delta.exchange
TRADING_MODE=paper
BROKER_TYPE=delta_options
CAPITAL=60.0
```

### 3. Run Delta Exchange Option Trading in Paper Mode

Test Delta Options risk-free on BTC:
```bash
python main.py --mode paper --broker delta_options --symbols BTC
```

Open **`http://localhost:5002`** in your browser to view the interactive dashboard!

### 4. Run Live Mode on Delta Exchange

When ready for live trading:
```bash
python main.py --mode live --broker delta_options --symbols BTC --capital 60
```
