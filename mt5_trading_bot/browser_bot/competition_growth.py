import math

balance    = 905.0
target     = 1500.0
leverage   = 100
margin_pct = 0.90
price      = 1.162
atr_pips   = 10
sl_mult    = 1.2
tp_mult    = 2.5

print("=== MAX RISK PATH: $905 to $1500 (90% margin) ===")
b = balance
trade = 0
while b < target and trade < 10:
    trade += 1
    lots    = round(math.floor((b * margin_pct / (100000 * price / leverage)) / 0.01) * 0.01, 2)
    pip_val = lots * 10
    win     = round(tp_mult * atr_pips * pip_val, 2)
    loss    = round(sl_mult * atr_pips * pip_val, 2)
    b_win   = round(b + win, 2)
    b_loss  = round(b - loss, 2)
    print("Trade #" + str(trade) + " | $" + str(b) + " | " + str(lots) + "L | WIN: +$" + str(win) + " -> $" + str(b_win) + " | LOSS: -$" + str(loss) + " -> $" + str(b_loss))
    b = b_win

print("CONSECUTIVE WINS NEEDED: " + str(trade))
print("")
print("=== REALISTIC SCENARIOS (60% win rate) ===")
lots0 = round(math.floor((905 * margin_pct / (100000 * price / leverage)) / 0.01) * 0.01, 2)
pip_v = lots0 * 10
avg_w = round(tp_mult * atr_pips * pip_v, 2)
avg_l = round(sl_mult * atr_pips * pip_v, 2)
print("Lots: " + str(lots0) + " | Win/trade: +$" + str(avg_w) + " | Loss/trade: -$" + str(avg_l))
print("")

rows = [(3,2,1),(4,3,1),(5,3,2),(6,4,2),(7,5,2),(8,5,3),(10,6,4),(12,8,4),(15,10,5)]
for total, wins, losses in rows:
    pnl = round(wins * avg_w - losses * avg_l, 2)
    bal = round(905 + pnl, 2)
    flag = " <<< TARGET!" if bal >= target else ""
    print("  " + str(total) + " trades | " + str(wins) + "W " + str(losses) + "L | PnL: $" + str(pnl) + " | Balance: $" + str(bal) + flag)
