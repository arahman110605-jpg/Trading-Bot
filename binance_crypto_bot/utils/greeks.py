"""
greeks.py — Black-Scholes Option Pricing & Greeks Calculator for Crypto Options.
"""

import math
from typing import Dict, Any

def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

def calculate_black_scholes(
    option_type: str,
    spot_price: float,
    strike_price: float,
    time_to_expiry_years: float,
    volatility: float = 0.50,
    risk_free_rate: float = 0.03
) -> Dict[str, float]:
    """
    Calculate theoretical option price and Greeks (Delta, Gamma, Theta, Vega).
    
    :param option_type: "CALL" or "PUT"
    :param spot_price: Current underlying spot price (e.g. $60,000)
    :param strike_price: Option strike price (e.g. $60,000)
    :param time_to_expiry_years: Time to expiry in years (e.g. 7 days / 365 = 0.0191)
    :param volatility: Implied Volatility (IV) e.g. 0.50 = 50%
    :param risk_free_rate: Risk-free rate (default 3% or 0.03)
    """
    S = max(spot_price, 0.01)
    K = max(strike_price, 0.01)
    T = max(time_to_expiry_years, 0.0001)  # Prevent division by zero
    v = max(volatility, 0.01)
    r = risk_free_rate

    d1 = (math.log(S / K) + (r + 0.5 * v * v) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)

    opt_type = option_type.upper()

    if opt_type in ["CALL", "C"]:
        price = (S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)) * 0.001
        delta = norm_cdf(d1)
        theta = ((- (S * norm_pdf(d1) * v) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365.0) * 0.001
    else:  # PUT
        price = (K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)) * 0.001
        delta = norm_cdf(d1) - 1.0
        theta = ((- (S * norm_pdf(d1) * v) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365.0) * 0.001

    gamma = norm_pdf(d1) / (S * v * math.sqrt(T))
    vega = (S * norm_pdf(d1) * math.sqrt(T)) / 100.0  # Per 1% IV change

    return {
        "theoretical_price": round(max(price, 0.0), 2),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4)
    }
