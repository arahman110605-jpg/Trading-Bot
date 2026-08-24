"""
Simulation: Increasing Trade Frequency from 20 -> 50 -> 100 trades/day
Account: $200 USD on IC Markets Raw Spread
Commission: $0.07 per 0.01 lot ($7/lot round turn)
Base Lot: 0.02 lot ($0.14 commission per trade)
"""
INITIAL_BALANCE = 200.0
TRADING_DAYS = 22

trade_frequencies = [
    {
        'title': '1. Standard Frequency (20 trades/day)',
        'trades_day': 20,
        'win_rate': 0.72,
        'avg_win_pips': 4.0,
        'avg_loss_pips': 5.0,
    },
    {
        'title': '2. High Frequency (50 trades/day)',
        'trades_day': 50,
        'win_rate': 0.68, # Win rate slightly drops as lower-quality signals are taken
        'avg_win_pips': 3.5,
        'avg_loss_pips': 4.5,
    },
    {
        'title': '3. Ultra-HFT / 1-Sec Scalper (100 trades/day)',
        'trades_day': 100,
        'win_rate': 0.65, # More noise on micro-ticks
        'avg_win_pips': 2.5,
        'avg_loss_pips': 3.5,
    }
]

print("=" * 75)
print("  EFFECT OF INCREASING TRADE FREQUENCY ON $200 CAPITAL (22 TRADING DAYS)")
print("=" * 75)

for f in trade_frequencies:
    t_day = f['trades_day']
    wr = f['win_rate']
    wins = int(t_day * wr)
    losses = t_day - wins
    
    # Lot: 0.02 ($0.20/pip)
    pip_val = 0.20
    comm_per_trade = 0.14 # IC Markets Raw Spread commission for 0.02 lot
    
    gross_win_day = wins * (f['avg_win_pips'] * pip_val)
    gross_loss_day = losses * (f['avg_loss_pips'] * pip_val)
    comm_day = t_day * comm_per_trade
    
    net_daily = gross_win_day - gross_loss_day - comm_day
    net_monthly = net_daily * TRADING_DAYS
    final_balance = INITIAL_BALANCE + net_monthly
    monthly_roi = (net_monthly / INITIAL_BALANCE) * 100.0
    
    print("\n[" + f['title'] + "]")
    print("  Daily Volume:         " + str(t_day) + " trades (" + str(wins) + " Wins / " + str(losses) + " Losses @ " + str(int(wr*100)) + "% win rate)")
    print("  Daily Commission:     -$" + str(round(comm_day, 2)) + " / day")
    print("  Daily Net P&L:        +$" + str(round(net_daily, 2)) + " / day")
    print("  Monthly Net Profit:   +$" + str(round(net_monthly, 2)) + " (22 trading days)")
    print("  Final Account Balance: $" + str(round(final_balance, 2)) + " (ROI: +" + str(round(monthly_roi, 1)) + "%)")

print("\n" + "=" * 75)
