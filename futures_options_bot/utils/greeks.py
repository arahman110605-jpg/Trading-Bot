"""
greeks.py — Black-Scholes Option Pricing and Greeks Calculator.

Calculates:
  - Delta: Sensitivity of option price to underlying price change
  - Gamma: Rate of change of Delta
  - Theta: Time decay per day
  - Vega: Sensitivity to Implied Volatility (IV)
  - Implied Volatility (IV): Solves for IV given current market price
"""

import math
from futures_options_bot.config import RISK_FREE_RATE


def norm_pdf(x: float) -> float:
    """Standard normal probability density function (PDF)."""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function (CDF)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def calculate_d1_d2(S: float, K: float, T: float, r: float, sigma: float):
    """
    S: Underlying Spot Price
    K: Strike Price
    T: Time to Expiry (in years)
    r: Risk-free interest rate (e.g. 0.07 for 7%)
    sigma: Volatility (annualized, e.g. 0.15 for 15%)
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0, 0.0

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def option_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str = "CE") -> float:
    """Calculates theoretical Black-Scholes option price."""
    if T <= 0:
        # Intrinsic value at expiry
        if option_type.upper() == "CE":
            return max(0.0, S - K)
        else:
            return max(0.0, K - S)

    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)

    if option_type.upper() == "CE":
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

    return max(0.05, round(price, 2))


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float = RISK_FREE_RATE,
    sigma: float = 0.15,
    option_type: str = "CE"
) -> dict:
    """
    Returns dictionary with theoretical price and option greeks:
      - price, delta, gamma, theta (per day), vega (per 1% IV change), iv
    """
    if T <= 0.0001:
        T = 0.0001  # Prevent divide-by-zero on expiry day

    option_type = option_type.upper()
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    sqrt_T = math.sqrt(T)

    price = option_price(S, K, T, r, sigma, option_type)

    if option_type == "CE":
        delta = norm_cdf(d1)
        theta = (- (S * norm_pdf(d1) * sigma) / (2 * sqrt_T) - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365.0
    else:
        delta = norm_cdf(d1) - 1.0
        theta = (- (S * norm_pdf(d1) * sigma) / (2 * sqrt_T) + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365.0

    gamma = norm_pdf(d1) / (S * sigma * sqrt_T) if (S * sigma * sqrt_T) > 0 else 0.0
    vega = (S * norm_pdf(d1) * sqrt_T) / 100.0  # Change per 1% move in IV

    return {
        "price": round(price, 2),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "iv": round(sigma * 100, 2),
    }


def calculate_implied_volatility(
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float = RISK_FREE_RATE,
    option_type: str = "CE"
) -> float:
    """Uses Newton-Raphson method to solve for Implied Volatility (IV)."""
    if market_price <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.15

    sigma = 0.20  # Initial guess 20%
    for _ in range(20):
        price = option_price(S, K, T, r, sigma, option_type)
        d1, _ = calculate_d1_d2(S, K, T, r, sigma)
        vega = S * norm_pdf(d1) * math.sqrt(T)

        diff = price - market_price
        if abs(diff) < 1e-4:
            break
        if abs(vega) < 1e-6:
            break

        sigma -= diff / vega
        if sigma <= 0.001:
            sigma = 0.001
            break
        if sigma > 5.0:
            sigma = 5.0
            break

    return round(sigma, 4)
