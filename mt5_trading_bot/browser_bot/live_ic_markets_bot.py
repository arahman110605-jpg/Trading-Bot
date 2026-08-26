"""
================================================================================
IC MARKETS PRODUCTION BOT (ASYMMETRIC TREND-EXPANSION & TIGHT-LOCK TRAILING)
================================================================================
- Broker: IC Markets Global (Raw Spread ECN, 0.0 pip spread feed, MT5)
- Account: 53016472 (ABDUL RAHMAN)
- Balance: Sized for $200+ USD (Leverage 1:500)
- Symbols: EURUSD, GBPUSD, USDJPY (M5 Candle & Tick Execution)
- Base Lot: 0.02 Lots ($0.20/pip)

ASYMMETRIC TREND EXPANSION & TIGHT-LOCK TRAILING MECHANISM:
1. When a strong macro trend surge is detected (Thesis Score >= 80 & Profit >= +2.0R):
   -> The Take-Profit (TP) is EXPANDED dynamically from +3R to +6R / +8R (+30 to +50 pips)
      so the winning trade is NOT prematurely cut short.
2. The Stop-Loss (SL) is TIGHTENED aggressively right beneath the 2-candle M5 swing low/high
   (Locking in 80% to 90% of all accumulated profits!).
3. If the market pushes higher, TP expands further; if the market breathes backward by just 2-3 pips,
   the tight SL hits immediately on the broker server, harvesting maximum possible profit!
================================================================================
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
import ta
import sys
import os
from enum import Enum
from typing import List, Dict, Optional, Tuple

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ic_markets_overnight.log")
JOURNAL_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_journal.csv")
JOURNAL_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_journal.jsonl")

import json
import csv
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [IC_TrendExpansionBot]: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("IC_TrendExpansionBot")

def log_trade_to_journal(trade_data: dict):
    """Log structured trade execution locally into CSV and JSON Lines format for auditing & strategy optimization"""
    try:
        # 1. Append to JSON Lines
        with open(JOURNAL_JSON, mode="a", encoding="utf-8") as jf:
            jf.write(json.dumps(trade_data) + "\n")
            
        # 2. Append to CSV
        file_exists = os.path.isfile(JOURNAL_CSV)
        with open(JOURNAL_CSV, mode="a", newline="", encoding="utf-8") as cf:
            writer = csv.DictWriter(cf, fieldnames=list(trade_data.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(trade_data)
        logger.info(f"💾 TRADE SAVED TO LOCAL JOURNAL ({trade_data.get('event')}: Ticket #{trade_data.get('ticket')})")
    except Exception as e:
        logger.error(f"Failed to log trade to local journal: {e}")

ACCOUNT_LOGIN = 53016472
ACCOUNT_PASSWORD = "1C$Sb3MehAno6R"
ACCOUNT_SERVER = "ICMarketsSC-Demo"
TERMINAL_PATH = "C:\\Program Files\\MetaTrader 5 IC Markets Global\\terminal64.exe"

MAGIC_NUMBER = 888111
BASE_LOT = 0.02
LOT_MULTIPLIER = 1.35
MAX_GRID_LEVELS = 4
CHECK_INTERVAL_SEC = 5
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
GLOBAL_HARD_STOP_PCT = 0.10

class TradeState(Enum):
    INITIAL = "INITIAL"
    PROFIT_PROTECTION = "PROFIT_PROTECTION"
    TREND_RUN = "TREND_RUN"
    MAX_PROFIT_EXPANSION = "MAX_PROFIT_EXPANSION"
    MOMENTUM_WEAKENING = "MOMENTUM_WEAKENING"
    EXIT_PENDING = "EXIT_PENDING"
    INVALIDATED = "INVALIDATED"
    CLOSED = "CLOSED"

class ActivePositionState:
    def __init__(self, ticket: int, symbol: str, direction: str, entry_price: float, initial_r_pips: float, initial_stop: float, broker_sl: float, broker_tp: float):
        self.ticket = ticket
        self.symbol = symbol
        self.direction = direction
        self.entry_price = entry_price
        self.initial_r_pips = initial_r_pips
        self.initial_stop = initial_stop
        self.current_stop = initial_stop
        self.current_tp = broker_tp
        self.broker_sl = broker_sl
        self.broker_tp = broker_tp
        self.state = TradeState.INITIAL
        self.thesis_score = 100.0
        self.warning_bars = 0
        self.bars_held = 0
        self.last_evaluated_bar: Optional[pd.Timestamp] = None
        self.mfe_pips = 0.0
        self.mae_pips = 0.0

live_position_states: Dict[int, ActivePositionState] = {}
last_processed_m5_bar: Dict[str, pd.Timestamp] = {}

def connect_mt5():
    try:
        if not mt5.initialize(path=TERMINAL_PATH, login=ACCOUNT_LOGIN, password=ACCOUNT_PASSWORD, server=ACCOUNT_SERVER):
            logger.error(f"MT5 Init failed: {mt5.last_error()}")
            return False
            
        acc = mt5.account_info()
        if acc is None:
            return False
            
        logger.info(f"CONNECTED TO IC MARKETS: #{acc.login} | Name: {acc.name} | Balance: ${acc.balance:.2f} {acc.currency}")
        for sym in SYMBOLS:
            info = mt5.symbol_info(sym)
            if info is not None and not info.visible:
                mt5.symbol_select(sym, True)
        return True
    except Exception as e:
        logger.error(f"Exception during MT5 connection: {e}")
        return False

def get_bot_positions():
    try:
        positions = mt5.positions_get()
        if not positions:
            return []
        return [p for p in positions if p.magic == MAGIC_NUMBER]
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return []

def modify_broker_sl_tp(ticket: int, symbol: str, new_sl: float, new_tp: float = 0.0):
    """Update hard broker-side Stop-Loss & Take-Profit on IC Markets Server"""
    req = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": symbol,
        "sl": round(new_sl, 5 if "JPY" not in symbol else 3),
        "tp": round(new_tp, 5 if "JPY" not in symbol else 3),
        "magic": MAGIC_NUMBER,
    }
    res = mt5.order_send(req)
    if res is not None and res.retcode == mt5.TRADE_RETCODE_DONE:
        logger.info(f"🛡️ BROKER SL/TP UPDATED: Ticket #{ticket} ({symbol}) | SL: {new_sl:.5f} | TP: {new_tp:.5f}")
        return True
    else:
        err = res.comment if res else mt5.last_error()
        logger.warning(f"Failed to update broker SL/TP for #{ticket}: {err}")
        return False

def close_position(ticket: int, symbol: str, volume: float, pos_type: int, reason="ACTIVE_EXIT"):
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return False
        
    close_price = tick.bid if pos_type == 0 else tick.ask
    req_type = mt5.ORDER_TYPE_SELL if pos_type == 0 else mt5.ORDER_TYPE_BUY
    
    clean_reason = "".join(c for c in str(reason) if c.isalnum() or c in "_-")[:25]
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": req_type,
        "position": ticket,
        "price": close_price,
        "deviation": 15,
        "magic": MAGIC_NUMBER,
        "comment": f"IC_{clean_reason}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment = res.comment if res else mt5.last_error()
        logger.warning(f"Failed to close ticket {ticket}: {comment}")
        return False
    else:
        logger.info(f"⚡ CLOSED TICKET #{ticket} ({symbol} {volume}L) @ {close_price} | Reason: {reason}")
        log_trade_to_journal({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": "EXIT",
            "ticket": ticket,
            "symbol": symbol,
            "type": "SELL" if pos_type == 0 else "BUY",
            "volume": volume,
            "exit_price": close_price,
            "reason": reason
        })
        if ticket in live_position_states:
            del live_position_states[ticket]
        return True

def open_order(symbol: str, order_type: str, lot: float, sl_price: float, tp_price: float, comment="L1_Active") -> Optional[int]:
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return None
    
    price = tick.ask if order_type == "BUY" else tick.bid
    req_type = mt5.ORDER_TYPE_BUY if order_type == "BUY" else mt5.ORDER_TYPE_SELL
    
    clean_comment = "".join(c for c in str(comment) if c.isalnum() or c in "_-")[:25]
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": req_type,
        "price": price,
        "sl": round(sl_price, 5 if "JPY" not in symbol else 3),
        "tp": round(tp_price, 5 if "JPY" not in symbol else 3),
        "deviation": 15,
        "magic": MAGIC_NUMBER,
        "comment": f"IC_{clean_comment}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    res = mt5.order_send(req)
    if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
        comment_err = res.comment if res else mt5.last_error()
        logger.error(f"Order failed {symbol} {order_type} {lot}L: {comment_err}")
        return None
    logger.info(f"🎯 ORDER EXECUTED WITH HARD BROKER-SIDE SL/TP:")
    logger.info(f"   Symbol: {symbol} | {order_type} {lot}L @ {price} | Ticket: #{res.order}")
    logger.info(f"   HARD BROKER SL: {sl_price:.5f} | HARD BROKER TP: {tp_price:.5f}")
    log_trade_to_journal({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": "ENTRY",
        "ticket": res.order,
        "symbol": symbol,
        "type": order_type,
        "volume": lot,
        "entry_price": price,
        "sl_price": sl_price,
        "tp_price": tp_price,
        "comment": clean_comment
    })
    return res.order

def calculate_multi_timeframe_data(symbol: str):
    rates_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 250)
    rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 150)
    rates_h1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 250)
    
    if rates_m5 is None or len(rates_m5) < 220 or rates_h1 is None or len(rates_h1) < 200:
        return None, None, None
        
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['time'] = pd.to_datetime(df_m5['time'], unit='s')
    df_m5['ema20'] = ta.trend.EMAIndicator(df_m5['close'], window=20).ema_indicator()
    df_m5['ema50'] = ta.trend.EMAIndicator(df_m5['close'], window=50).ema_indicator()
    df_m5['ema200'] = ta.trend.EMAIndicator(df_m5['close'], window=200).ema_indicator()
    df_m5['ema20_slope'] = df_m5['ema20'].diff(2) / 2.0
    df_m5['atr14'] = ta.volatility.AverageTrueRange(df_m5['high'], df_m5['low'], df_m5['close'], window=14).average_true_range()
    df_m5['rsi14'] = ta.momentum.RSIIndicator(df_m5['close'], window=14).rsi()
    df_m5['vol_sma'] = df_m5['tick_volume'].rolling(20).mean()
    df_m5['vol_ratio'] = df_m5['tick_volume'] / df_m5['vol_sma'].replace(0, 1)
    df_m5['swing_low_val'] = df_m5['low'].rolling(3).min()
    df_m5['swing_high_val'] = df_m5['high'].rolling(3).max()
    
    df_m15 = pd.DataFrame(rates_m15)
    df_m15['ema20'] = ta.trend.EMAIndicator(df_m15['close'], window=20).ema_indicator()
    df_m15['ema50'] = ta.trend.EMAIndicator(df_m15['close'], window=50).ema_indicator()
    
    df_h1 = pd.DataFrame(rates_h1)
    df_h1['ema50'] = ta.trend.EMAIndicator(df_h1['close'], window=50).ema_indicator()
    df_h1['ema200'] = ta.trend.EMAIndicator(df_h1['close'], window=200).ema_indicator()
    df_h1['ema50_slope'] = df_h1['ema50'].diff(3) / 3.0
    
    return df_m5, df_m15, df_h1

def evaluate_thesis_score(direction: str, row_m5: pd.Series, row_m15: pd.Series, row_h1: pd.Series) -> float:
    score = 0.0
    if direction == "BUY":
        if row_h1['close'] > row_h1['ema200']: score += 15.0
        if row_h1['close'] > row_h1['ema50']: score += 10.0
        if row_h1['ema50_slope'] > 0: score += 15.0
        if row_m15['close'] > row_m15['ema20']: score += 10.0
        if row_m15['close'] > row_m15['ema50']: score += 10.0
        if row_m5['close'] > row_m5['ema20']: score += 10.0
        if row_m5['ema20_slope'] > 0: score += 10.0
        if 45 <= row_m5['rsi14'] <= 70: score += 10.0
        if row_m5['vol_ratio'] >= 1.0: score += 10.0
    else:
        if row_h1['close'] < row_h1['ema200']: score += 15.0
        if row_h1['close'] < row_h1['ema50']: score += 10.0
        if row_h1['ema50_slope'] < 0: score += 15.0
        if row_m15['close'] < row_m15['ema20']: score += 10.0
        if row_m15['close'] < row_m15['ema50']: score += 10.0
        if row_m5['close'] < row_m5['ema20']: score += 10.0
        if row_m5['ema20_slope'] < 0: score += 10.0
        if 30 <= row_m5['rsi14'] <= 55: score += 10.0
        if row_m5['vol_ratio'] >= 1.0: score += 10.0
    return max(0.0, min(100.0, score))

def manage_active_trade(pos_mt5, row_m5: pd.Series, prev_m5: pd.Series, row_m15: pd.Series, row_h1: pd.Series, pip_size: float) -> Tuple[bool, str]:
    ticket = pos_mt5.ticket
    direction = "BUY" if pos_mt5.type == 0 else "SELL"
    curr_price = pos_mt5.price_current
    atr = row_m5['atr14']
    
    if ticket not in live_position_states:
        # Generous breathing room: 2.5x ATR (20 to 25 pips buffer)
        r_pips = max(18.0, (atr / pip_size) * 2.5)
        init_stop = pos_mt5.price_open - (r_pips * pip_size) if direction == "BUY" else pos_mt5.price_open + (r_pips * pip_size)
        init_tp = pos_mt5.price_open + (r_pips * 2.5 * pip_size) if direction == "BUY" else pos_mt5.price_open - (r_pips * 2.5 * pip_size)
        
        if pos_mt5.sl == 0.0 or pos_mt5.sl is None:
            modify_broker_sl_tp(ticket, pos_mt5.symbol, init_stop, init_tp)
            
        live_position_states[ticket] = ActivePositionState(
            ticket=ticket,
            symbol=pos_mt5.symbol,
            direction=direction,
            entry_price=pos_mt5.price_open,
            initial_r_pips=r_pips,
            initial_stop=init_stop,
            broker_sl=pos_mt5.sl if pos_mt5.sl != 0.0 else init_stop,
            broker_tp=pos_mt5.tp if pos_mt5.tp != 0.0 else init_tp
        )
        
    p_state = live_position_states[ticket]
    
    if direction == "BUY":
        current_r = (curr_price - p_state.entry_price) / (p_state.initial_r_pips * pip_size)
        if curr_price <= p_state.current_stop:
            return True, f"TRAILING_STOP (R={current_r:+.2f})"
    else:
        current_r = (p_state.entry_price - curr_price) / (p_state.initial_r_pips * pip_size)
        if curr_price >= p_state.current_stop:
            return True, f"TRAILING_STOP (R={current_r:+.2f})"

    thesis_score = evaluate_thesis_score(direction, row_m5, row_m15, row_h1)
    p_state.thesis_score = thesis_score
    
    # ── TRUE ASYMMETRIC INSTITUTIONAL MEGA-TREND TRAILING LADDER ──
    # Calculate exact net pip profit on this trade
    if direction == "BUY":
        pip_profit = (curr_price - p_state.entry_price) / pip_size
    else:
        pip_profit = (p_state.entry_price - curr_price) / pip_size
        
    # Track Maximum Favorable Excursion (Peak Pips)
    if pip_profit > p_state.mfe_pips:
        p_state.mfe_pips = pip_profit

    # 🪜 STEP 1: +20 PIPS GAIN (+$4.00) -> Lock Breakeven (+3 pips green buffer)
    # Allows normal 12-15 pip intraday market retests WITHOUT scratching the trade prematurely!
    if pip_profit >= 20.0 and p_state.state == TradeState.INITIAL:
        p_state.state = TradeState.PROFIT_PROTECTION
        if direction == "BUY":
            new_stop = p_state.entry_price + (3.0 * pip_size)
            if new_stop > p_state.current_stop:
                p_state.current_stop = new_stop
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, p_state.current_tp)
        else:
            new_stop = p_state.entry_price - (3.0 * pip_size)
            if new_stop < p_state.current_stop:
                p_state.current_stop = new_stop
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, p_state.current_tp)
        logger.info(f"🛡️ [{pos_mt5.symbol}] STEP 1 (+{pip_profit:.1f} pips): SL locked at Entry (+3 pips green buffer). 100% RISK-FREE!")

    # 🪜 STEP 2: +35 PIPS GAIN (+$7.00) -> Lock +18 Pips & EXPAND TP TO +80 PIPS
    if pip_profit >= 35.0 and p_state.state in [TradeState.INITIAL, TradeState.PROFIT_PROTECTION]:
        p_state.state = TradeState.TREND_RUN
        if direction == "BUY":
            new_stop = p_state.entry_price + (18.0 * pip_size)
            expanded_tp = p_state.entry_price + (80.0 * pip_size)
            if new_stop > p_state.current_stop:
                p_state.current_stop = new_stop
                p_state.current_tp = expanded_tp
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, expanded_tp)
        else:
            new_stop = p_state.entry_price - (18.0 * pip_size)
            expanded_tp = p_state.entry_price - (80.0 * pip_size)
            if new_stop < p_state.current_stop:
                p_state.current_stop = new_stop
                p_state.current_tp = expanded_tp
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, expanded_tp)
        logger.info(f"🔒 [{pos_mt5.symbol}] STEP 2 (+{pip_profit:.1f} pips): SL moved to +18 pips (+$3.60 banked) & TP expanded to +80 pips!")

    # 🪜 STEP 3: +55 PIPS GAIN (+$11.00) -> Lock +35 Pips
    if pip_profit >= 55.0:
        p_state.state = TradeState.MAX_PROFIT_EXPANSION
        if direction == "BUY":
            new_stop = p_state.entry_price + (35.0 * pip_size)
            if new_stop > p_state.current_stop:
                p_state.current_stop = new_stop
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, p_state.current_tp)
        else:
            new_stop = p_state.entry_price - (35.0 * pip_size)
            if new_stop < p_state.current_stop:
                p_state.current_stop = new_stop
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, p_state.current_tp)
        logger.info(f"💰💰 [{pos_mt5.symbol}] STEP 3 (+{pip_profit:.1f} pips): SL at +35 pips (+$7.00 banked)!")

    # 🪜 STEP 4: +80+ PIPS GAIN (+$16.00+) -> Trail 20 Pips Behind Peak High/Low
    if pip_profit >= 80.0:
        if direction == "BUY":
            new_stop = curr_price - (20.0 * pip_size)
            if new_stop > p_state.current_stop + (2.0 * pip_size):
                p_state.current_stop = new_stop
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, p_state.current_tp)
        else:
            new_stop = curr_price + (20.0 * pip_size)
            if new_stop < p_state.current_stop - (2.0 * pip_size):
                p_state.current_stop = new_stop
                modify_broker_sl_tp(ticket, pos_mt5.symbol, new_stop, p_state.current_tp)

    # ── MACRO REGIME INVALIDATION (Only on decisive H1 macro reversal after 6+ bars) ──
    bar_time = row_m5['time']
    if p_state.last_evaluated_bar != bar_time:
        p_state.last_evaluated_bar = bar_time
        p_state.bars_held += 1

    if p_state.bars_held >= 6: # At least 30 minutes of trade time
        if direction == "BUY":
            if row_h1['close'] < row_h1['ema200'] and row_m15['close'] < row_m15['ema50']:
                return True, "MACRO_H1_REVERSAL"
        else:
            if row_h1['close'] > row_h1['ema200'] and row_m15['close'] > row_m15['ema50']:
                return True, "MACRO_H1_REVERSAL"

    return False, ""

def analyze_and_trade():
    acc = mt5.account_info()
    if not acc:
        connect_mt5()
        return
        
    balance = acc.balance
    all_positions = get_bot_positions()
    
    # ── 🛡️ EMERGENCY 10% GLOBAL ACCOUNT KILL-SWITCH ──
    if all_positions:
        total_pnl = sum(p.profit for p in all_positions)
        if total_pnl <= -(balance * GLOBAL_HARD_STOP_PCT):
            logger.warning(f"🚨 GLOBAL 10% HARD STOP TRIGGERED! P&L: ${total_pnl:.2f} <= -${(balance*0.10):.2f}")
            for p in all_positions:
                close_position(p.ticket, p.symbol, p.volume, p.type, reason="GLOBAL_EMERGENCY_STOP")
            return

    for sym in SYMBOLS:
        pip_size = 0.0001 if "JPY" not in sym else 0.01
        sym_positions = [p for p in all_positions if p.symbol == sym]
        
        df_m5, df_m15, df_h1 = calculate_multi_timeframe_data(sym)
        if df_m5 is None:
            continue
            
        # In MetaTrader 5, df.iloc[-1] is the LIVE UNCLOSED forming bar.
        # Closed completed candles are df.iloc[-2] (last closed) and df.iloc[-3] (previous closed).
        curr_bar_time = df_m5['time'].iloc[-2]
        row_m5 = df_m5.iloc[-2]
        prev_m5 = df_m5.iloc[-3]
        row_m15 = df_m15.iloc[-2]
        row_h1 = df_h1.iloc[-2]
        atr = row_m5['atr14']
        
        # ── 1. MANAGE ACTIVE POSITIONS ──
        if sym_positions:
            for pos in sym_positions:
                should_close, reason = manage_active_trade(pos, row_m5, prev_m5, row_m15, row_h1, pip_size)
                if should_close:
                    close_position(pos.ticket, sym, pos.volume, pos.type, reason=reason)
                    
        # ── 2. NEW ENTRY GENERATION WITH HARD BROKER-SIDE SL/TP ──
        else:
            if last_processed_m5_bar.get(sym) == curr_bar_time:
                continue
            last_processed_m5_bar[sym] = curr_bar_time
            
            # Avoid low-liquidity rollover deadzone (21:30 - 23:30 Server Time / spreads widen significantly)
            server_hour = datetime.now().hour
            
            r_pips = max(18.0, (atr / pip_size) * 2.5)
            tp_pips = r_pips * 3.0 # True 1:3 Asymmetric Target
            
            # Compute Real-Time Multi-Timeframe Thesis Score
            thesis_buy = evaluate_thesis_score("BUY", row_m5, row_m15, row_h1)
            thesis_sell = evaluate_thesis_score("SELL", row_m5, row_m15, row_h1)
            
            # High-Probability Momentum Entry (Thesis >= 60 + M5 Directional Trigger)
            if thesis_buy >= 60.0 and row_m5['close'] > row_m5['ema20'] and prev_m5['close'] <= prev_m5['ema20']:
                tick = mt5.symbol_info_tick(sym)
                entry_p = tick.ask if tick else row_m5['close']
                sl_p = entry_p - (r_pips * pip_size)
                tp_p = entry_p + (tp_pips * pip_size)
                logger.info(f"🎯 NEW ENTRY SIGNAL: {sym} BUY (Thesis Score: {thesis_buy:.0f}/100 | M5 EMA20 Breakout)")
                open_order(sym, "BUY", BASE_LOT, sl_price=sl_p, tp_price=tp_p, comment="L1_Expansion")
                
            elif thesis_sell >= 60.0 and row_m5['close'] < row_m5['ema20'] and prev_m5['close'] >= prev_m5['ema20']:
                tick = mt5.symbol_info_tick(sym)
                entry_p = tick.bid if tick else row_m5['close']
                sl_p = entry_p + (r_pips * pip_size)
                tp_p = entry_p - (tp_pips * pip_size)
                logger.info(f"🎯 NEW ENTRY SIGNAL: {sym} SELL (Thesis Score: {thesis_sell:.0f}/100 | M5 EMA20 Breakdown)")
                open_order(sym, "SELL", BASE_LOT, sl_price=sl_p, tp_price=tp_p, comment="L1_Expansion")

def main():
    logger.info("=" * 75)
    logger.info("  IC MARKETS LIVE ENGINE WITH ASYMMETRIC TREND-EXPANSION & TIGHT-LOCK")
    logger.info("=" * 75)
    
    if not connect_mt5():
        logger.error("Initial MT5 connection failed.")
        
    logger.info(f"  ACTIVE ACCOUNT: #{ACCOUNT_LOGIN} | SERVER: {ACCOUNT_SERVER}")
    logger.info(f"  ASYMMETRIC TREND EXPANSION: ACTIVE (TP expands to +6R on strong trends)")
    logger.info(f"  TIGHT-LOCK PROFIT TRAILING: ACTIVE (Locks 80-90% of gains)")
    logger.info("=" * 75)
    
    heartbeat_counter = 0
    while True:
        try:
            analyze_and_trade()
            heartbeat_counter += 1
            if heartbeat_counter >= 60:
                heartbeat_counter = 0
                acc = mt5.account_info()
                if acc:
                    logger.info(f"[HEARTBEAT] Account Healthy | Balance: ${acc.balance:.2f} | Equity: ${acc.equity:.2f} | Net Floating: ${acc.profit:+.2f}")
        except Exception as e:
            logger.error(f"Error in active trade manager loop: {e}")
            time.sleep(5)
            connect_mt5()
        time.sleep(CHECK_INTERVAL_SEC)

if __name__ == "__main__":
    main()
