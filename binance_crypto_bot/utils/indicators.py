"""
indicators.py — Technical Indicators and Quantitative calculations for Crypto Trading.
"""

import pandas as pd
import numpy as np
from typing import Tuple, List

def calculate_ema(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """Calculate Exponential Moving Average."""
    return df[column].ewm(span=period, adjust=False).mean()

def calculate_sma(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """Calculate Simple Moving Average."""
    return df[column].rolling(window=period).mean()

def calculate_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.Series:
    """Calculate Relative Strength Index."""
    delta = df[column].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9, column: str = "close") -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD line, Signal line, and MACD Histogram."""
    ema_fast = calculate_ema(df, fast, column)
    ema_slow = calculate_ema(df, slow, column)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range (ATR)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean().fillna(0)

def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, column: str = "close") -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Upper, Middle, and Lower Bollinger Bands."""
    middle = calculate_sma(df, period, column)
    rolling_std = df[column].rolling(window=period).std()
    upper = middle + (rolling_std * std_dev)
    lower = middle - (rolling_std * std_dev)
    return upper, middle, lower

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average Directional Index (ADX) to measure trend strength."""
    df = df.copy()
    high, low, close = df["high"], df["low"], df["close"]
    
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * (pd.Series(plus_dm).rolling(window=period).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (pd.Series(minus_dm).rolling(window=period).mean() / atr.replace(0, np.nan))
    
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.rolling(window=period).mean().fillna(15.0)
    return adx

def calculate_grid_levels(current_price: float, lower_bound: float, upper_bound: float, num_grids: int = 10) -> List[float]:
    """Calculate Grid price levels for Quantitative Grid Trading."""
    if num_grids < 2 or lower_bound >= upper_bound:
        return [current_price]
    step = (upper_bound - lower_bound) / (num_grids - 1)
    levels = [round(lower_bound + (i * step), 4) for i in range(num_grids)]
    return levels
