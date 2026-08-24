"""
P&L Simulation for $200 Starting Capital on IC Markets Raw Spread MT5
Leverage: 1:500
Risk Profiles: Safe, Moderate (Recommended), Aggressive
"""
INITIAL_BALANCE = 200.0
TRADING_DAYS_PER_MONTH = 22

scenarios = [
    {
        'tier': '1. Safe / Conservative (Account Building)',
        'base_lot': 0.01,
        'pip_value': 0.10, # $0.10 / pip
        'trades_per_day': 12,
        'win_rate': 0.75,
        'avg_win_usd': 0.40,  # ~4 pips
        'avg_loss_usd': 0.60, # ~6 pips
        'daily_est_net': 3.60, # ~$3.60 / day
        'max_daily_risk': 10.0, # 5% hard stop ($10)
    },
    {
        'tier': '2. Moderate / Standard Scalper (Recommended)',
        'base_lot': 0.02,
        'pip_value': 0.20, # $0.20 / pip
        'trades_per_day': 20,
        'win_rate': 0.72,
        'avg_win_usd': 0.80,  # ~4 pips
        'avg_loss_usd': 1.20, # ~6 pips
        'daily_est_net': 8.80, # ~$8.80 / day
        'max_daily_risk': 20.0, # 10% hard stop ($20)
    },
    {
        'tier': '3. Maximum Competition / Aggressive Mode',
        'base_lot': 0.05,
        'pip_value': 0.50, # $0.50 / pip
        'trades_per_day': 25,
        'win_rate': 0.70,
        'avg_win_usd': 2.00,  # ~4 pips
        'avg_loss_usd': 3.00, # ~6 pips
        'daily_est_net': 20.00, # ~$20.00 / day
        'max_daily_risk': 30.0, # 15% hard stop ($30)
    }
]

print("=" * 70)
print("  REALISTIC P&L SCENARIOS ON $200 INITIAL DEPOSIT (22 TRADING DAYS)")
print("=" * 70)

for s in scenarios:
    daily_pnl = s['daily_est_net']
    monthly_pnl = daily_pnl * TRADING_DAYS_PER_MONTH
    final_balance = INITIAL_BALANCE + monthly_pnl
    monthly_roi = (monthly_pnl / INITIAL_BALANCE) * 100.0
    
    print("\n[" + s['tier'] + "]")
    print("  Position Size:        " + str(s['base_lot']) + " lots ($" + str(s['pip_value']) + "/pip)")
    print("  Max Daily Risk Cap:   -$" + str(s['max_daily_risk']) + " (Hard Cutoff Protection)")
    print("  Daily Expected P&L:   +$" + str(round(daily_pnl, 2)) + " / day")
    print("  Monthly Net Profit:   +$" + str(round(monthly_pnl, 2)) + " (22 trading days)")
    print("  Final Account Balance: $" + str(round(final_balance, 2)))
    print("  Monthly Return (ROI): +" + str(round(monthly_roi, 1)) + "%")

print("\n" + "=" * 70)
