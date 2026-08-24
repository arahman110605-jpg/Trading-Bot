"""
Weekly 5-Day (Monday to Friday) Simulation for $200 IC Markets Demo Account
Trading Pairs: EURUSD, GBPUSD, USDJPY
Exit #1: Basket TP (+$8.00 / cycle)
Exit #2: Hard 10% Drawdown Cutoff (-$20.00 / day)
"""
INITIAL_BALANCE = 200.0
TRADING_DAYS = 5 # Mon - Fri

# Realistic Weekly Scenarios based on 5-day cycle:
# Total baskets expected across 3 pairs: 15 to 25 baskets over 5 days
scenarios = [
    {
        'tier': 'Conservative Week (Low Volatility / Normal Flow)',
        'baskets_per_week': 14,
        'baskets_won': 13, # 13 wins * $8 = +$104
        'baskets_stopped': 1, # 1 cutoff * $20 = -$20
        'commission_estimate': 8.0,
    },
    {
        'tier': 'Standard / Expected Week (Optimal European + US Sessions)',
        'baskets_per_week': 20,
        'baskets_won': 18, # 18 wins * $8 = +$144
        'baskets_stopped': 2, # 2 cutoffs * $20 = -$40
        'commission_estimate': 12.0,
    },
    {
        'tier': 'High-Momentum Trending Week (Strong Breakouts & Smooth Reversals)',
        'baskets_per_week': 26,
        'baskets_won': 25, # 25 wins * $8 = +$200
        'baskets_stopped': 1, # 1 cutoff * $20 = -$20
        'commission_estimate': 16.0,
    }
]

print("=" * 75)
print("  WEEKLY (MON - FRI) P&L PROJECTIONS ON $200 IC MARKETS DEMO ACCOUNT")
print("=" * 75)

for s in scenarios:
    gross_wins = s['baskets_won'] * 8.0
    gross_losses = s['baskets_stopped'] * 20.0
    net_pnl = gross_wins - gross_losses - s['commission_estimate']
    weekly_roi = (net_pnl / INITIAL_BALANCE) * 100.0
    final_balance = INITIAL_BALANCE + net_pnl
    
    print("\n[" + s['tier'] + "]")
    print("  Completed Baskets:    " + str(s['baskets_per_week']) + " (" + str(s['baskets_won']) + " Wins @ +$8.00 / " + str(s['baskets_stopped']) + " Loss Cuts @ -$20.00)")
    print("  Gross Profit:         +$" + str(round(gross_wins, 2)))
    print("  Gross Loss & Comm:    -$" + str(round(gross_losses + s['commission_estimate'], 2)))
    print("  >> WEEKLY NET P&L:    +$" + str(round(net_pnl, 2)) + " (5 Trading Days)")
    print("  >> EXPECTED BALANCE:  $" + str(round(final_balance, 2)) + " (ROI: +" + str(round(weekly_roi, 1)) + "%)")

print("\n" + "=" * 75)
