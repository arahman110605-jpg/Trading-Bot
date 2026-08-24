"""
1-Year (12-Month) Compounding Growth Projection:
Asymmetric Trend-Expansion & Tight-Lock Trailing Engine
Starting Capital: $200.00 USD

Mathematical Dynamics with Asymmetric Expansion:
- Loser Invalidation: Capped early at -$1.20 to -$2.20 (~1R)
- Standard Breakeven Scenarios: Locks +0.3R buffer (+$0.70 to $1.20)
- Trend Expansion Winners: Instead of fixed +$8, runner trades expand to +4R, +6R, +8R (+$12.00 to +$25.00+ on 0.02 base lot)
- Profit Retention Efficiency: Tight-lock trailing captures 82% to 91% of peak MFE.

Dynamic Compounding Model:
- Base Lot scales by +0.01 lot for every $100 increase in balance.
"""

STARTING_CAPITAL = 200.0
TRADING_MONTHS = 12

scenarios = [
    {
        'tier': '1. Conservative Market (Low Trend Frequency / Higher Chop)',
        'monthly_roi': 0.38,
        'description': 'Mostly standard +1.5R to +2R exits, few multi-session trend runners.'
    },
    {
        'tier': '2. Expected / Baseline Trend-Expansion Regime (Standard Flow)',
        'monthly_roi': 0.62,
        'description': 'Balanced market flow with 3-4 large asymmetric +5R/+6R trend runners per week.'
    },
    {
        'tier': '3. High Momentum Trend Surges (London / NY Session Breakouts)',
        'monthly_roi': 0.88,
        'description': 'Strong directional multi-pair trends with full +6R/+8R TP expansions.'
    }
]

print("=" * 88)
print("  1-YEAR COMPOUNDING TRAJECTORY: ASYMMETRIC TREND-EXPANSION & TIGHT-LOCK ENGINE ($200)")
print("=" * 88)

for sc in scenarios:
    balance = STARTING_CAPITAL
    print(f"\n--- {sc['tier']} ---")
    print(f"Market Assumption: {sc['description']}")
    print(f"{'Month':<8}{'Start Balance':<18}{'Monthly Profit':<18}{'End Balance':<18}{'Lot Size':<12}{'Max Risk (1R)':<15}")
    print("-" * 88)
    
    for m in range(1, TRADING_MONTHS + 1):
        start_bal = balance
        lot_size = max(0.02, round((start_bal / 10000.0) * 1.0, 2))
        risk_per_trade = round(lot_size * 12.0, 2)
        profit = start_bal * sc['monthly_roi']
        balance = start_bal + profit
        print(f"M{m:<7}${start_bal:<17,.2f}+${profit:<16,.2f}${balance:<17,.2f}{lot_size:<12.2f}${risk_per_trade:<14.2f}")
        
    total_net = balance - STARTING_CAPITAL
    multiplier = balance / STARTING_CAPITAL
    print(f"\n>> 12-MONTH RESULT: Final Account Balance = ${balance:,.2f}")
    print(f">> Total Realized Profit: +${total_net:,.2f} ({multiplier:,.1f}x Capital Growth)")

print("\n" + "=" * 88)
