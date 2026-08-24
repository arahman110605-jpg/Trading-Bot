"""
MetaTrader 5 Broker Interface & Client Wrapper
Handles API initialization, market data fetching, and order executions.
"""
import logging
import MetaTrader5 as mt5
import pandas as pd
from typing import Dict, List, Optional, Any

logger = logging.getLogger("MT5Client")

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

class MT5Client:
    def __init__(self, account: str = "", password: str = "", server: str = "", path: str = ""):
        self.account = int(account) if account and account.isdigit() else None
        self.password = password
        self.server = server
        self.path = path
        self.is_connected = False

    def connect(self) -> bool:
        """Initializes connection to MetaTrader 5 Terminal"""
        init_kwargs = {}
        if self.path:
            init_kwargs["path"] = self.path
        if self.account and self.password and self.server:
            init_kwargs["login"] = self.account
            init_kwargs["password"] = self.password
            init_kwargs["server"] = self.server

        if not mt5.initialize(**init_kwargs):
            err = mt5.last_error()
            logger.error(f"MT5 initialization failed: {err}")
            self.is_connected = False
            return False

        account_info = mt5.account_info()
        if account_info is None:
            logger.error(f"Failed to get account info: {mt5.last_error()}")
            self.is_connected = False
            return False

        self.is_connected = True
        logger.info(
            f"Connected to MT5 - Account: {account_info.login} ({account_info.name}) | "
            f"Server: {account_info.server} | Balance: {account_info.balance} {account_info.currency} | "
            f"Leverage: 1:{account_info.leverage}"
        )
        return True

    def disconnect(self):
        """Shutdown MT5 connection"""
        mt5.shutdown()
        self.is_connected = False
        logger.info("Disconnected from MetaTrader 5")

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Returns account balance, equity, margin, free margin"""
        if not self.is_connected and not self.connect():
            return None
        info = mt5.account_info()
        if info is None:
            return None
        return info._asdict()

    def get_symbol_info(self, symbol: str):
        """Retrieves and enables symbol in MarketWatch, handling broker suffixes like '#'"""
        if not self.is_connected and not self.connect():
            return None
        
        info = mt5.symbol_info(symbol)
        # If symbol not found, try adding '#' (for XM Ultra Low accounts) or standard alternatives
        if info is None:
            for alt in [f"{symbol}#", f"{symbol}.i#", symbol.replace("#", "")]:
                info = mt5.symbol_info(alt)
                if info is not None:
                    symbol = alt
                    break

        if info is None:
            logger.warning(f"Symbol '{symbol}' not found on broker")
            return None
            
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.error(f"Failed to select symbol {symbol} in MarketWatch")
                return None
            info = mt5.symbol_info(symbol)
        return info

    def get_market_data(self, symbol: str, timeframe_str: str = "M15", count: int = 300) -> Optional[pd.DataFrame]:
        """Fetches OHLCV candlestick data and converts to DataFrame"""
        if not self.is_connected and not self.connect():
            return None

        sym_info = self.get_symbol_info(symbol)
        real_symbol = sym_info.name if sym_info else symbol

        tf = TIMEFRAME_MAP.get(timeframe_str.upper(), mt5.TIMEFRAME_M15)
        rates = mt5.copy_rates_from_pos(real_symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to fetch rates for {real_symbol}: {mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        return df

    def get_filling_type(self, symbol_info) -> int:
        """Determines best supported order filling type for the broker symbol"""
        filling_mode = symbol_info.filling_mode
        # bit 0 (1): FOK, bit 1 (2): IOC
        if filling_mode & 1:
            return mt5.ORDER_FILLING_FOK
        elif filling_mode & 2:
            return mt5.ORDER_FILLING_IOC
        else:
            return mt5.ORDER_FILLING_RETURN

    def open_order(
        self,
        symbol: str,
        order_type: str,
        lot_size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        magic: int = 888001,
        comment: str = "MT5 Bot"
    ) -> Optional[int]:
        """
        Sends a market Buy or Sell order with Stop Loss and Take Profit
        """
        sym_info = self.get_symbol_info(symbol)
        if sym_info is None:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.error(f"Could not get tick for {symbol}")
            return None

        digits = sym_info.digits
        price = tick.ask if order_type.upper() == "BUY" else tick.bid
        action_type = mt5.ORDER_TYPE_BUY if order_type.upper() == "BUY" else mt5.ORDER_TYPE_SELL
        filling = self.get_filling_type(sym_info)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": action_type,
            "price": round(price, digits),
            "deviation": 20,
            "magic": magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        if stop_loss is not None and stop_loss > 0:
            request["sl"] = round(stop_loss, digits)
        if take_profit is not None and take_profit > 0:
            request["tp"] = round(take_profit, digits)

        result = mt5.order_send(request)
        if result is None:
            logger.error(f"Order send failed for {symbol}: {mt5.last_error()}")
            return None

        if result.retcode not in (0, mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED):
            logger.error(f"Order failed for {symbol} | Retcode: {result.retcode} ({result.comment})")
            return None

        order_id = result.order if result.order > 0 else result.request_id
        logger.info(
            f"[ORDER SUCCESS] {order_type.upper()} {symbol} {lot_size} lots @ {price} | "
            f"SL: {request.get('sl')} | TP: {request.get('tp')} | Ticket/ID: {order_id}"
        )
        return order_id

    def get_open_positions(self, symbol: Optional[str] = None, magic: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieves list of active open positions"""
        if not self.is_connected and not self.connect():
            return []

        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()

        if positions is None:
            return []

        pos_list = []
        for pos in positions:
            p_dict = pos._asdict()
            if magic is not None and p_dict.get("magic") != magic:
                continue
            pos_list.append(p_dict)
        return pos_list

    def modify_position_sl_tp(self, ticket: int, symbol: str, sl: float, tp: float) -> bool:
        """Modifies Stop Loss and/or Take Profit of an existing position"""
        sym_info = self.get_symbol_info(symbol)
        if sym_info is None:
            return False

        digits = sym_info.digits
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": round(sl, digits),
            "tp": round(tp, digits),
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Position {ticket} ({symbol}) modified | New SL: {round(sl, digits)}, TP: {round(tp, digits)}")
            return True
        else:
            err = result.comment if result else mt5.last_error()
            logger.warning(f"Failed to modify position {ticket}: {err}")
            return False

    def close_position(self, ticket: int) -> bool:
        """Closes an open position by ticket number"""
        pos = mt5.positions_get(ticket=ticket)
        if not pos or len(pos) == 0:
            logger.warning(f"Position {ticket} not found to close")
            return False

        p = pos[0]
        sym_info = self.get_symbol_info(p.symbol)
        if sym_info is None:
            return False

        order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(p.symbol)
        price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
        filling = self.get_filling_type(sym_info)

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": ticket,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": order_type,
            "price": round(price, sym_info.digits),
            "deviation": 20,
            "magic": p.magic,
            "comment": "Close order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(f"Position {ticket} ({p.symbol}) closed successfully at {result.price}")
            return True
        else:
            err = result.comment if result else mt5.last_error()
            logger.error(f"Failed to close position {ticket}: {err}")
            return False
