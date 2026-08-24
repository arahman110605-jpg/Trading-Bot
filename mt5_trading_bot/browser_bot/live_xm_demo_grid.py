"""
LIVE XM DEMO BOT: Trend-Aligned Controlled Grid + Dual Exit Engine
- Account: 1301984092 ($10,000 Balance)
- Clean standard symbols: EURUSD and GBPUSD
- Exit #1: Basket Target Profit / Breakeven ($50 per basket)
- Exit #2: Hard 10% Equity Drawdown Kill-Switch ($1,000 max risk)
"""
import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
import ta
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [XM_GridBot]: %(message)s"
)
logger = logging.getLogger("XM_GridBot")

# ── RISK & STRATEGY CONFIG ──
MAGIC_NUMBER = 999111
BASE_LOT = 0.10                  # Sized for $10,000 balance
LOT_MULTIPLIER = 1.35
MAX_GRID_LEVELS = 5
BASKET_TP_USD = 50.0             # Exit #1: Close entire basket at +$50 profit (0.5% gain)
HARD_STOP_EQUITY_PCT = 0.10      # Exit #2: Cut everything if floating loss hits 10% of balance ($1,000)
CHECK_INTERVAL_SEC = 5           # Scan every 5 seconds
SYMBOLS = ["EURUSD", "GBPUSD"]

def connect_mt5():
    if not mt5.initialize():
        logger.error(f"MT5 initialization failed: {mt5.last_error()}")
        return False
        
    acc = mt5.account_info()
    if acc is None:
        logger.error(f"Failed to get account info: {mt5.last_error()}")
        return False
        
    logger.info(f"Connected to MT5: #{acc.login} | Name: {acc.name} | Balance: ${acc.balance:.2f} | Leverage: 1:{acc.leverage} | Server: {acc.server}")
    
    # Ensure symbols are visible in Market Watch
    for sym in SYMBOLS:
        info = mt5.symbol_info(sym)
        if info is not None and not info.visible:
            mt5.symbol_select(sym, True)
            
    return True

def get_open_basket(symbol: str):
    positions = mt5.positions_get(symbol=symbol)
    if not positions:
        return []
    return [p for p in positions if p.magic == MAGIC_NUMBER]

def close_all_positions(positions, reason="BASKET_CLOSE"):
    for pos in positions:
        pos_type = pos.type
        lot = pos.volume
        ticket = pos.ticket
        sym = pos.symbol
        
        tick = mt5.symbol_info_tick(sym)
        if not tick:
            continue
            
        close_price = tick.bid if pos_type == 0 else tick.ask
        req_type = mt5.ORDER_TYPE_SELL if pos_type == 0 else mt5.ORDER_TYPE_BUY
        
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": sym,
            "volume": lot,
            "type": req_type,
            "position": ticket,
            "price": close_price,
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": f"CG_{reason}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        res = mt5.order_send(req)
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            logger.warning(f"Failed to close ticket {ticket}: {res.comment}")
        else:
            logger.info(f"Closed ticket {ticket} ({sym} {lot}L) @ {close_price} | Reason: {reason}")

def open_order(symbol: str, order_type: str, lot: float, comment="Grid"):
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return False
    
    price = tick.ask if order_type == "BUY" else tick.bid
    req_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
    
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": req_type,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": f"CG_{comment}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Order failed {symbol} {order_type} {lot}L: {res.comment}")
        return False
    logger.info(f"ORDER EXECUTED: {symbol} {order_type} {lot}L @ {price} ({comment}) | Ticket: {res.order}")
    return True

def analyze_and_trade():
    acc = mt5.account_info()
    if not acc:
        return
    
    balance = acc.balance
    
    for sym in SYMBOLS:
        basket = get_open_basket(sym)
        pip_size = 0.0001 if "JPY" not in sym else 0.01
        tick = mt5.symbol_info_tick(sym)
        if not tick:
            continue
            
        current_price = (tick.bid + tick.ask) / 2.0
        
        # ── 1. MANAGE EXISTING BASKET ──
        if basket:
            total_profit = sum(p.profit for p in basket)
            total_lots = sum(p.volume for p in basket)
            basket_type = "BUY" if basket[0].type == 0 else "SELL"
            
            # EXIT #2: HARD 10% EQUITY STOP KILL-SWITCH
            hard_stop_usd = -(balance * HARD_STOP_EQUITY_PCT)
            if total_profit <= hard_stop_usd:
                logger.warning(f"🚨 HARD 10% STOP TRIGGERED for {sym}! Floating P&L: ${total_profit:.2f} <= ${hard_stop_usd:.2f}")
                close_all_positions(basket, reason="10PCT_HARD_STOP")
                continue
                
            # EXIT #1: BASKET BREAKEVEN + TP TARGET
            if total_profit >= BASKET_TP_USD:
                logger.info(f"🎉 BASKET TP HIT for {sym}! Profit: ${total_profit:.2f} >= ${BASKET_TP_USD:.2f}")
                close_all_positions(basket, reason="BASKET_TP_HIT")
                continue
                
            # GRID EXPANSION
            if len(basket) < MAX_GRID_LEVELS:
                last_pos = sorted(basket, key=lambda x: x.time)[-1]
                last_price = last_pos.price_open
                
                rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 50)
                if rates is not None and len(rates) >= 20:
                    df = pd.DataFrame(rates)
                    atr = ta.volatility.AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14).average_true_range().iloc[-1]
                    grid_step_pips = max(12.0, (atr / pip_size) * 1.2)
                else:
                    grid_step_pips = 15.0
                
                if basket_type == "BUY":
                    pips_against = (last_price - current_price) / pip_size
                    if pips_against >= grid_step_pips:
                        next_lot = round(last_pos.volume * LOT_MULTIPLIER, 2)
                        logger.info(f"Grid Level {len(basket)+1} triggered for {sym} BUY (Price moved -{pips_against:.1f} pips)")
                        open_order(sym, "BUY", next_lot, comment=f"L{len(basket)+1}")
                elif basket_type == "SELL":
                    pips_against = (current_price - last_price) / pip_size
                    if pips_against >= grid_step_pips:
                        next_lot = round(last_pos.volume * LOT_MULTIPLIER, 2)
                        logger.info(f"Grid Level {len(basket)+1} triggered for {sym} SELL (Price moved -{pips_against:.1f} pips)")
                        open_order(sym, "SELL", next_lot, comment=f"L{len(basket)+1}")
                        
        # ── 2. NEW BASKET ENTRY (TREND-ALIGNED M5) ──
        else:
            rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M5, 0, 250)
            if rates is None or len(rates) < 220:
                continue
            
            df = pd.DataFrame(rates)
            c = df['close']
            df['ema200'] = ta.trend.EMAIndicator(close=c, window=200).ema_indicator()
            df['ema20'] = ta.trend.EMAIndicator(close=c, window=20).ema_indicator()
            
            curr = df.iloc[-1]
            prev = df.iloc[-2]
            
            if pd.isna(curr['ema200']) or pd.isna(curr['ema20']):
                continue
                
            # BUY: Macro Uptrend (Price > EMA200) and EMA20 crossover
            if curr['close'] > curr['ema200'] and curr['close'] > curr['ema20'] and prev['close'] <= prev['ema20']:
                logger.info(f"🎯 NEW BASKET SIGNAL: {sym} BUY | Macro Uptrend (Close > EMA200)")
                open_order(sym, "BUY", BASE_LOT, comment="L1_Entry")
            # SELL: Macro Downtrend (Price < EMA200) and EMA20 crossover
            elif curr['close'] < curr['ema200'] and curr['close'] < curr['ema20'] and prev['close'] >= prev['ema20']:
                logger.info(f"🎯 NEW BASKET SIGNAL: {sym} SELL | Macro Downtrend (Close < EMA200)")
                open_order(sym, "SELL", BASE_LOT, comment="L1_Entry")

def main():
    if not connect_mt5():
        return
        
    logger.info("=" * 65)
    logger.info("  XM CONTROLLED GRID BOT IS RUNNING ON LIVE DEMO")
    logger.info(f"  Pairs: {SYMBOLS} | Base Lot: {BASE_LOT} | Basket TP: ${BASKET_TP_USD} | Hard SL: 10%")
    logger.info("=" * 65)
    
    while True:
        try:
            analyze_and_trade()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    main()
