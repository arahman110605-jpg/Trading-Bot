"""
Trend Pullback & Momentum Strategy (EMA + MACD + RSI + ATR)
Optimized for MetaTrader 5 (Gold XAUUSD, Forex Majors, Indices, Crypto CFDs).
"""
import pandas as pd
import numpy as np
import ta
from typing import Dict, Any, Optional

class TrendMomentumStrategy:
    def __init__(
        self,
        ema_fast: int = 9,
        ema_slow: int = 21,
        ema_trend: int = 200,
        rsi_period: int = 14,
        rsi_buy_min: float = 40.0,
        rsi_buy_max: float = 70.0,
        rsi_sell_min: float = 30.0,
        rsi_sell_max: float = 60.0,
        atr_period: int = 14,
        atr_sl_mult: float = 1.0,
        atr_tp_mult: float = 2.5,
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.ema_trend = ema_trend
        self.rsi_period = rsi_period
        self.rsi_buy_min = rsi_buy_min
        self.rsi_buy_max = rsi_buy_max
        self.rsi_sell_min = rsi_sell_min
        self.rsi_sell_max = rsi_sell_max
        self.atr_period = atr_period
        self.atr_sl_mult = atr_sl_mult
        self.atr_tp_mult = atr_tp_mult

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Computes Technical Indicators on historical candlestick dataframe"""
        if len(df) < self.ema_trend + 10:
            return df

        df = df.copy()
        
        # Exponential Moving Averages
        df['ema_fast'] = ta.trend.EMAIndicator(close=df['close'], window=self.ema_fast).ema_indicator()
        df['ema_slow'] = ta.trend.EMAIndicator(close=df['close'], window=self.ema_slow).ema_indicator()
        df['ema_trend'] = ta.trend.EMAIndicator(close=df['close'], window=self.ema_trend).ema_indicator()

        # Relative Strength Index (RSI)
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=self.rsi_period).rsi()

        # Moving Average Convergence Divergence (MACD)
        macd = ta.trend.MACD(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
        df['macd_line'] = macd.macd()
        df['macd_signal'] = macd.macd_signal()
        df['macd_diff'] = macd.macd_diff()

        # Average True Range (ATR)
        df['atr'] = ta.volatility.AverageTrueRange(
            high=df['high'], low=df['low'], close=df['close'], window=self.atr_period
        ).average_true_range()

        return df

    def check_signal_from_row(self, row: pd.Series, prev: pd.Series, next_open: float = None) -> Optional[Dict[str, Any]]:
        """Evaluates signal using precalculated indicators"""
        close = row['close']
        open_price = row['open']
        ema_f = row['ema_fast']
        ema_s = row['ema_slow']
        ema_t = row['ema_trend']
        rsi = row['rsi']
        atr = row['atr']
        macd_diff = row['macd_diff']

        prev_ema_f = prev['ema_fast']
        prev_ema_s = prev['ema_slow']
        prev_rsi = prev['rsi']

        if pd.isna(ema_t) or pd.isna(rsi) or pd.isna(atr) or atr <= 0:
            return None

        entry_price = next_open if next_open is not None else close

        # -------------------------------------------------------------
        # 1. BULLISH SCENARIO (BUY)
        # -------------------------------------------------------------
        # Macro Uptrend: Close > 200 EMA
        # Momentum: EMA 9 crosses above EMA 21 OR RSI pulled back & bounced above 45
        # Confirmation: MACD Histogram > 0 and RSI not overbought
        bull_cross = (ema_f > ema_s) and (prev_ema_f <= prev_ema_s)
        rsi_bounce_buy = (prev_rsi < 45 and rsi >= 45 and close > open_price)
        
        if (close > ema_t) and (bull_cross or rsi_bounce_buy) and (macd_diff > 0) and (rsi <= self.rsi_buy_max):
            sl = entry_price - (atr * self.atr_sl_mult)
            tp = entry_price + (atr * self.atr_tp_mult)
            reason = "EMA Cross Uptrend" if bull_cross else "RSI Pullback Bounce Uptrend"
            return {
                "signal": "BUY",
                "price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "atr": atr,
                "rsi": rsi,
                "reason": f"{reason} (Close > EMA200, MACD+)"
            }

        # -------------------------------------------------------------
        # 2. BEARISH SCENARIO (SELL)
        # -------------------------------------------------------------
        # Macro Downtrend: Close < 200 EMA
        # Momentum: EMA 9 crosses below EMA 21 OR RSI pulled back & rejected below 55
        # Confirmation: MACD Histogram < 0 and RSI not oversold
        bear_cross = (ema_f < ema_s) and (prev_ema_f >= prev_ema_s)
        rsi_bounce_sell = (prev_rsi > 55 and rsi <= 55 and close < open_price)

        if (close < ema_t) and (bear_cross or rsi_bounce_sell) and (macd_diff < 0) and (rsi >= self.rsi_sell_min):
            sl = entry_price + (atr * self.atr_sl_mult)
            tp = entry_price - (atr * self.atr_tp_mult)
            reason = "EMA Cross Downtrend" if bear_cross else "RSI Pullback Rejection Downtrend"
            return {
                "signal": "SELL",
                "price": entry_price,
                "stop_loss": sl,
                "take_profit": tp,
                "atr": atr,
                "rsi": rsi,
                "reason": f"{reason} (Close < EMA200, MACD-)"
            }

        return None

    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Analyzes historical candlestick dataframe and returns trade signal if present"""
        if len(df) < self.ema_trend + 10:
            return None

        df_ind = self.calculate_indicators(df)
        prev = df_ind.iloc[-3]
        curr = df_ind.iloc[-2]
        latest_price = df_ind.iloc[-1]['close']
        return self.check_signal_from_row(curr, prev, next_open=latest_price)
