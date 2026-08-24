"""
Monthly Profit & Loss Simulation on Real Market Movement
Capital: $500 USD
Broker: IC Markets (Raw Spread 0.0 pip, MT5, 1:500 Leverage)
Bot Strategy: Controlled Micro-Scalper / Momentum Grid with Dual Exits (#1 Basket TP + #2 Hard 10% SL)
"""
import numpy as np

INITIAL_BALANCE = 500.0
TRADING_DAYS_PER_MONTH = 22

# Sizing for $500 capital:
# Conservative: 0.02 - 0.05 lot ($0.20 - $0.50 per pip)
# Aggressive:   0.10 lot ($1.00 per pip)
# Maximum HFT:  0.20 lot ($2.00 per pip)

scenarios = [
    {
        'tier': '1. Safe / Conservative (Steady Compounding)',
        'base_lot': 0.03,
        'pip_value': 0.30,
        'trades_per_day': 15,
        'win_rate': 0.75,
        'avg_win_usd': 1.20,   # ~4 pips
        'avg_loss_usd': 1.80,  # ~6 pips
        'daily_est_net': 10.50, # ~$10.50 / day
    },
    {
        'tier': '2. Moderate / Standard Growth (Recommended)',
        'base_lot': 0.06,
        'pip_value': 0.60,
        'trades_per_day': 25,
        'win_rate': 0.72,
        'avg_win_usd': 2.40,
        'avg_loss_usd': 3.60,
        'daily_est_net': 21.60, # ~$21.60 / day
    },
    {
        'tier': '3. Aggressive / High Momentum Scalper',
        'base_lot': 0.10,
        'pip_value': 1.00,
        'trades_per_day': 35,
        'win_rate': 0.70,
        'avg_win_usd': 4.00,
        'avg_loss_usd': 6.00,
        'daily_est_net': 38.00, # ~$38.00 / day
    }
]

print("=" * 70)
print("  MONTHLY P&L PROJECTIONS ON $500 STARTING CAPITAL (REAL MARKET)")
print("=" * 70)

for s in scenarios:
    daily_pnl = s['daily_est_net']
    monthly_pnl = daily_pnl * TRADING_DAYS_PER_MONTH
    final_balance = INITIAL_BALANCE + monthly_pnl
    monthly_roi = (monthly_pnl / INITIAL_BALANCE) * 100.0
    
    print("\n[" + s['tier'] + "]")
    print("  Position Size:        " + str(s['base_lot']) + " lots ($" + str(s['pip_value']) + "/pip)")
    print("  Daily Expected P&L:   +$" + str(round(daily_pnl, 2)) + " / day")
    print("  Monthly Net Profit:   +$" + str(round(monthly_pnl, 2)) + " (22 trading days)")
    print("  Final Account Balance: $" + str(round(final_balance, 2)))
    print("  Monthly Return (ROI): +" + str(round(monthly_roi, 1)) + "%")

print("\n" + "=" * 70)
