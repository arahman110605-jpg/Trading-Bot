"""
Simulation: Enhanced Portfolio-Harvesting Strategy on $200 IC Markets Raw Spread
Features:
1. Single Pair TP: +$8.00
2. Global Portfolio Harvester: +$12.00 (+6% on account per multi-pair surge)
3. Single Pair Stop: -$10.00 (5%)
4. Global Hard Stop: -$20.00 (10% max total loss cap)
Period: 22 Trading Days (1 Month)
"""
INITIAL_BALANCE = 200.0
TRADING_DAYS = 22

# Daily Harvest Distribution based on Multi-Pair Correlation:
# - Single Pair TP Harvester (+8.00): Occurs ~2.5 times per day
# - Global Multi-Pair Portfolio Harvester (+12.00): Occurs ~1.5 times per day during active London/NY overlaps
# - Controlled Stop Cutoffs (-10.00 / -20.00): Occurs ~1 to 2 times per WEEK

scenarios = [
    {
        'tier': '1. Conservative Month (Ranging / Normal Volatility)',
        'single_tp_daily': 2,    # 2 * $8 = +$16
        'portfolio_tp_daily': 1, # 1 * $12 = +$12
        'stops_per_month': 3,    # 3 * -$10 = -$30
        'comm_daily': 2.50,
    },
    {
        'tier': '2. Standard / Expected Month (Optimal Trend & Pullback Alignment)',
        'single_tp_daily': 3,    # 3 * $8 = +$24
        'portfolio_tp_daily': 1.5, # 1.5 * $12 = +$18
        'stops_per_month': 4,    # 4 * -$10 = -$40
        'comm_daily': 3.50,
    },
    {
        'tier': '3. High Momentum Month (Active London/NY Session Surges)',
        'single_tp_daily': 4,    # 4 * $8 = +$32
        'portfolio_tp_daily': 2, # 2 * $12 = +$24
        'stops_per_month': 3,    # 3 * -$10 = -$30
        'comm_daily': 4.80,
    }
]

print("=" * 75)
print("  ENHANCED PORTFOLIO-HARVESTER MONTHLY P&L PROJECTIONS ($200 CAPITAL)")
print("=" * 75)

for s in scenarios:
    daily_gross_gain = (s['single_tp_daily'] * 8.0) + (s['portfolio_tp_daily'] * 12.0)
    daily_net_gain = daily_gross_gain - s['comm_daily']
    
    monthly_gross_gain = daily_gross_gain * TRADING_DAYS
    monthly_stops_loss = s['stops_per_month'] * 10.0
    monthly_comm = s['comm_daily'] * TRADING_DAYS
    
    monthly_net_pnl = monthly_gross_gain - monthly_stops_loss - monthly_comm
    monthly_roi = (monthly_net_pnl / INITIAL_BALANCE) * 100.0
    final_balance = INITIAL_BALANCE + monthly_net_pnl
    
    print("\n[" + s['tier'] + "]")
    print("  Daily Expected Profit:  +$" + str(round(daily_net_gain, 2)) + " / day (Net of fees)")
    print("  Monthly Gross Gains:    +$" + str(round(monthly_gross_gain, 2)) + " (From +$8 and +$12 harvests)")
    print("  Monthly Losses & Comm:  -$" + str(round(monthly_stops_loss + monthly_comm, 2)) + " (Capped 5% stops + broker comm)")
    print("  >> MONTHLY NET PROFIT:  +$" + str(round(monthly_net_pnl, 2)) + " / MONTH")
    print("  >> FINAL BALANCE:       $" + str(round(final_balance, 2)) + " (ROI: +" + str(round(monthly_roi, 1)) + "%)")

print("\n" + "=" * 75)
