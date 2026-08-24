"""
Simulation & Mathematical Limits:
High-Frequency Sub-Second / 1-Second VPS Micro-Scalping Engine
Account Capital: $1,000 USD
Leverage: 100:1 / 500:1 / 1000:1 (XM Ultra Low)
"""
INITIAL_BALANCE = 1000.0

scenarios = [
    {
        'mode': '1. Conservative / Low Risk (0.05 Lot)',
        'lot': 0.05,
        'pip_value': 0.50,
        'trades_per_day': 40,
        'win_rate': 0.72,
        'avg_win_pips': 1.8,
        'avg_loss_pips': 1.5,
        'spread_commission_pips': 0.4
    },
    {
        'mode': '2. Aggressive Scalper (0.20 Lot)',
        'lot': 0.20,
        'pip_value': 2.00,
        'trades_per_day': 60,
        'win_rate': 0.70,
        'avg_win_pips': 1.8,
        'avg_loss_pips': 1.5,
        'spread_commission_pips': 0.4
    },
    {
        'mode': '3. Maximum Competition / HFT Risk (0.50 Lot)',
        'lot': 0.50,
        'pip_value': 5.00,
        'trades_per_day': 80,
        'win_rate': 0.68,
        'avg_win_pips': 2.0,
        'avg_loss_pips': 1.8,
        'spread_commission_pips': 0.4
    },
    {
        'mode': '4. Theoretical Upper Bound / Max Leverage (1.00 Lot)',
        'lot': 1.00,
        'pip_value': 10.00,
        'trades_per_day': 100,
        'win_rate': 0.70,
        'avg_win_pips': 2.0,
        'avg_loss_pips': 1.8,
        'spread_commission_pips': 0.4
    }
]

print("=" * 75)
print("  24-HOUR DAILY P&L LIMITS ON $1,000 CAPITAL (1-SECOND / VPS ENGINE)")
print("=" * 75)

for s in scenarios:
    trades = s['trades_per_day']
    wins = int(trades * s['win_rate'])
    losses = trades - wins
    
    win_usd = (s['avg_win_pips'] - s['spread_commission_pips']) * s['pip_value']
    loss_usd = (s['avg_loss_pips'] + s['spread_commission_pips']) * s['pip_value']
    
    daily_gross_win = wins * win_usd
    daily_gross_loss = losses * loss_usd
    daily_net_pnl = daily_gross_win - daily_gross_loss
    daily_roi = (daily_net_pnl / INITIAL_BALANCE) * 100.0
    
    print("\n[" + s['mode'] + "]")
    print("  Position Size:        " + str(s['lot']) + " lots ($" + str(s['pip_value']) + "/pip)")
    print("  24h Micro-Trades:     " + str(trades) + " trades (" + str(wins) + " Wins / " + str(losses) + " Losses @ " + str(int(s['win_rate']*100)) + "% win rate)")
    print("  Average Win / Loss:   +$" + str(round(win_usd, 2)) + " / -$" + str(round(loss_usd, 2)) + " per trade")
    print("  >> DAILY NET P&L:     +$" + str(round(daily_net_pnl, 2)) + " / DAY")
    print("  >> DAILY RETURN (ROI): " + str(round(daily_roi, 1)) + "% per 24 hours")

print("\n" + "=" * 75)
