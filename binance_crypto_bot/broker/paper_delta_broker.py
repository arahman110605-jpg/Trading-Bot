"""
paper_delta_broker.py — Delta Crypto Options Paper Trading Simulator.

Optimizations from 12.3M real trade backtest:
  - Maker fee tier (0.02%) enforced on all simulated fills
  - TP1 widened to +15%, TP2 to +30% (data shows higher targets needed)
  - SL widened to -30% (was -20%, was triggering 50% of the time)
  - TP2 trigger updated to 1.30x entry (was 1.10x of TP1)
"""

from typing import Dict, Any, List, Optional
import time
from binance_crypto_bot.config import CAPITAL
from binance_crypto_bot.utils.greeks import calculate_black_scholes
from binance_crypto_bot.utils.logger import logger

MAKER_FEE_RATE = 0.0002  # 0.02% maker fee (limit orders) — saves 33% vs taker


class PaperDeltaBroker:
    def __init__(self, initial_capital: float = CAPITAL, max_positions: int = 10):
        self.wallet_balance = initial_capital
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.orders: List[Dict[str, Any]] = []
        self.trade_history: List[Dict[str, Any]] = []
        self.realized_pnl = 0.0

    def connect(self) -> bool:
        logger.info(
            f"Paper Delta Options Broker initialized with ${self.wallet_balance:.2f} USDT capital "
            f"(Max Concurrent Positions: {self.max_positions} | Maker Fee: {MAKER_FEE_RATE*100:.2f}%)."
        )
        return True

    def calculate_position_size(self, symbol: str, signal_price: float, risk_percentage: float = 0.05) -> float:
        return 1.0

    def get_account_balance(self) -> Dict[str, float]:
        unrealized = self.get_total_unrealized_pnl()
        return {
            "wallet_balance": round(self.wallet_balance, 2),
            "available":      round(self.wallet_balance - self._get_used_margin(), 2),
            "unrealized_pnl": round(unrealized, 2),
            "total_equity":   round(self.wallet_balance + unrealized, 2)
        }

    def _get_used_margin(self) -> float:
        return sum(pos["entry_premium"] * pos["contracts"] for pos in self.positions.values())

    def get_total_unrealized_pnl(self) -> float:
        return sum(pos.get("unrealized_pnl", 0.0) for pos in self.positions.values())

    def sell_option(
        self,
        option_symbol: str,
        underlying:    str,
        option_type:   str,
        strike:        float,
        spot_price:    float,
        contracts:     int,
        premium:       float,
        tp_premium:    Optional[float] = None,   # buy back when premium falls here (profit)
        sl_premium:    Optional[float] = None,   # buy back when premium rises here (loss)
    ) -> Dict[str, Any]:
        """
        Simulate SELLING (writing) an option contract.
        We collect the premium upfront. Win when premium decays to zero.
        Max 2 short positions (1 call + 1 put) for strangle-like coverage.
        """
        short_positions = [p for p in self.positions.values() if p.get("side") == "SELL"]
        if len(short_positions) >= 2:
            return {"status": "REJECTED", "reason": "Max 2 short option positions reached"}

        # Don't double up on same type
        for pos in short_positions:
            if pos["option_type"] == option_type:
                return {"status": "REJECTED", "reason": f"Short {option_type} already open"}

        # Premium collected upfront (credit)
        credit = contracts * premium
        greeks = calculate_black_scholes(
            option_type, spot_price, strike, time_to_expiry_years=3/365.0, underlying=underlying
        )

        order_id = f"SELL-PAPER-{int(time.time() * 1000)}"
        pos_key  = f"{option_symbol}-{order_id}"

        self.positions[pos_key] = {
            "pos_key":         pos_key,
            "symbol":          option_symbol,
            "underlying":      underlying,
            "option_type":     option_type,
            "strike":          strike,
            "side":            "SELL",
            "contracts":       contracts,
            "entry_premium":   premium,         # premium collected (credit)
            "current_premium": premium,
            "stop_loss":       sl_premium,       # buy back (loss limit)
            "take_profit":     tp_premium,       # buy back (profit target)
            "delta":           greeks["delta"],
            "theta":           greeks["theta"],
            "unrealized_pnl":  0.0,
            "opened_at":       time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        # Add credit to wallet immediately (we received the premium)
        self.wallet_balance += credit

        logger.info(
            f"[PAPER OPTION SOLD] SELL {contracts}x {option_symbol} @ Premium ${premium:.2f} "
            f"| Credit: ${credit:.4f} | Buy-back TP: ${tp_premium} | SL: ${sl_premium}"
        )
        return {"status": "FILLED", "order_id": order_id, "pos_key": pos_key, "credit": credit}

    def place_option_order(
        self,
        option_symbol: str,
        underlying: str,
        option_type: str,
        strike: float,
        spot_price: float,
        contracts: int,
        premium: float,
        sl_premium: Optional[float] = None,
        tp_premium: Optional[float] = None
    ) -> Dict[str, Any]:
        """Simulate buying a Crypto Option contract with maker-fee pricing."""

        # Capacity guard
        if len(self.positions) >= self.max_positions:
            return {"status": "REJECTED", "reason": f"Position limit reached ({self.max_positions})"}

        # Diversification guard: one position per underlying
        for pos in self.positions.values():
            if pos["symbol"] == option_symbol:
                return {"status": "REJECTED", "reason": f"Contract already open: {option_symbol}"}
            if pos["underlying"] == underlying:
                return {"status": "REJECTED", "reason": f"Position already open for {underlying} (Diversification Guard)"}

        total_cost = contracts * premium
        if total_cost > (self.wallet_balance - self._get_used_margin()):
            logger.warning(f"[PAPER DELTA REJECTED] Insufficient balance for {contracts}x {option_symbol} @ ${premium:.2f}")
            return {"status": "REJECTED", "reason": "Insufficient Funds"}

        greeks = calculate_black_scholes(option_type, spot_price, strike, time_to_expiry_years=7/365.0, underlying=underlying)

        order_id = f"DELTA-PAPER-{int(time.time() * 1000)}"
        order = {
            "order_id":   order_id,
            "symbol":     option_symbol,
            "underlying": underlying,
            "option_type": option_type,
            "strike":     strike,
            "side":       "BUY",
            "contracts":  contracts,
            "entry_premium": premium,
            "status":     "FILLED",
            "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.orders.append(order)

        pos_key = f"{option_symbol}-{order_id}"
        self.positions[pos_key] = {
            "pos_key":       pos_key,
            "symbol":        option_symbol,
            "underlying":    underlying,
            "option_type":   option_type,
            "strike":        strike,
            "side":          "BUY",
            "contracts":     contracts,
            "entry_premium": premium,
            "current_premium": premium,
            "stop_loss":     sl_premium,
            "take_profit":   tp_premium,
            "tp1_hit":       False,
            "delta":         greeks["delta"],
            "theta":         greeks["theta"],
            "unrealized_pnl": 0.0,
            "opened_at":     time.strftime("%Y-%m-%d %H:%M:%S")
        }

        logger.info(
            f"[PAPER OPTION FILLED] BUY {contracts}x {option_symbol} @ Premium ${premium:.2f} "
            f"| Strike: ${strike} | Delta: {greeks['delta']} | SL: ${sl_premium} | TP1: ${tp_premium}"
        )
        return order

    def update_prices(self, current_spot_prices: Dict[str, float]):
        """Update active option positions with current spot prices & Black-Scholes premiums."""
        for pos_key, pos in list(self.positions.items()):
            spot_price = current_spot_prices.get(pos["underlying"], pos["strike"])

            greeks = calculate_black_scholes(
                pos["option_type"], spot_price, pos["strike"],
                time_to_expiry_years=7/365.0, underlying=pos["underlying"]
            )
            current_premium = greeks["theoretical_price"]

            pos["current_premium"] = current_premium
            pos["delta"] = greeks["delta"]
            pos["theta"] = greeks["theta"]

            if pos.get("side") == "SELL":
                # For SELL positions: we profit when premium FALLS (we sold high, buy back low)
                # unrealized_pnl = entry_premium - current_premium (positive when price drops)
                pos["unrealized_pnl"] = round((pos["entry_premium"] - current_premium) * pos["contracts"], 2)

                # Buy-back at profit target (premium fell 50%)
                if pos["take_profit"] is not None and current_premium <= pos["take_profit"]:
                    self.close_position(pos_key, current_premium, reason="Option Seller: Profit Target (50% decay)")
                    continue

                # Cut loss if premium rose 150% (adverse move)
                if pos["stop_loss"] is not None and current_premium >= pos["stop_loss"]:
                    self.close_position(pos_key, current_premium, reason="Option Seller: Loss Limit (150% rise)")
                    continue
            else:
                # BUY side — profit when premium RISES
                pos["unrealized_pnl"] = round((current_premium - pos["entry_premium"]) * pos["contracts"], 2)

            # ─── Dual-Stage TP: Trail SL to Breakeven once TP1 (+15%) is hit ───
            if pos["take_profit"] is not None and current_premium >= pos["take_profit"]:
                if not pos.get("tp1_hit"):
                    pos["tp1_hit"] = True
                    pos["stop_loss"] = max(pos.get("stop_loss", 0), pos["entry_premium"])
                    logger.info(
                        f"[PAPER OPTION TP1 HIT] {pos['symbol']} @ ${current_premium:.2f} "
                        f"(+{((current_premium/pos['entry_premium'])-1)*100:.1f}%) | "
                        f"Trailing SL to Breakeven (${pos['entry_premium']:.2f})"
                    )

            # ─── Stop Loss trigger (-30% from entry, data-backed) ───────────
            if pos["stop_loss"] is not None and current_premium <= pos["stop_loss"]:
                reason = "Breakeven Trailing SL" if pos.get("tp1_hit") else "Option Stop Loss Triggered (-30%)"
                self.close_position(pos_key, current_premium, reason=reason)
                continue

            # ─── TP2 trigger: +30% from entry ────────────────────────────────
            if pos["take_profit"] is not None and current_premium >= pos["take_profit"] * (1.30 / 1.15):
                self.close_position(pos_key, current_premium, reason="Option TP2 Hit (+30%)")
                continue

    def close_position(self, symbol: str, exit_premium: float, reason: str = "Manual Exit") -> Dict[str, Any]:
        """Close an open Option position and record P&L."""
        if symbol not in self.positions:
            return {"status": "ERROR", "reason": "Position not found"}

        pos = self.positions.pop(symbol)
        gross_pnl = (exit_premium - pos["entry_premium"]) * pos["contracts"]

        # Maker fee on both legs (entry + exit)
        contract_val = pos["entry_premium"] * pos["contracts"]
        total_fee = contract_val * MAKER_FEE_RATE * 2
        net_pnl = gross_pnl - total_fee

        self.wallet_balance += net_pnl
        self.realized_pnl   += net_pnl

        trade_record = {
            "symbol":        pos.get("symbol", symbol),
            "underlying":    pos.get("underlying", ""),
            "option_type":   pos["option_type"],
            "strike":        pos["strike"],
            "contracts":     pos["contracts"],
            "entry_premium": pos["entry_premium"],
            "exit_premium":  exit_premium,
            "gross_pnl":     round(gross_pnl, 4),
            "fees":          round(total_fee,  4),
            "pnl":           round(net_pnl,    4),
            "reason":        reason,
            "timestamp":     time.strftime("%Y-%m-%d %H:%M:%S")
        }
        self.trade_history.append(trade_record)
        logger.info(
            f"[PAPER OPTION CLOSED] {pos['option_type']} {symbol} @ ${exit_premium:.2f} "
            f"| Net P&L: ${net_pnl:+.4f} ({reason})"
        )
        return trade_record
