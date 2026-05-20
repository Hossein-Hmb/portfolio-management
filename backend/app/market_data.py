"""Market-data helpers for the trade analysis rules engine.

Wraps yfinance for options chains, historical bars, and realized volatility,
and provides a Black-Scholes greeks calculator so the rules engine can reason
about delta / theta / vega regardless of whether yfinance returned them.

Network calls are best-effort: every public function degrades to `None` /
empty rather than raising, so the rules engine can mark a rule as
``status="skip"`` instead of crashing the whole analysis.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

# Quiet yfinance like quotes.py does.
for _name in ("yfinance", "yfinance.ticker", "yfinance.utils", "yfinance.data"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)


# ---------- Black-Scholes greeks ----------

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float       # per calendar day
    vega: float        # per 1.0 change in vol (i.e. +100 IV pts); divide by 100 for per-1%-pt
    price: float


def black_scholes_greeks(
    spot: float,
    strike: float,
    days_to_expiry: float,
    iv: float,
    right: str,                # "call" | "put"
    risk_free: float = 0.045,
    dividend_yield: float = 0.0,
) -> Optional[Greeks]:
    """Standard BS with continuous dividend yield. Returns None on degenerate inputs."""
    if spot <= 0 or strike <= 0 or iv <= 0 or days_to_expiry <= 0:
        return None
    T = days_to_expiry / 365.0
    r, q, sig = risk_free, dividend_yield, iv
    sqrtT = math.sqrt(T)
    d1 = (math.log(spot / strike) + (r - q + 0.5 * sig * sig) * T) / (sig * sqrtT)
    d2 = d1 - sig * sqrtT
    disc_r = math.exp(-r * T)
    disc_q = math.exp(-q * T)
    pdf_d1 = _norm_pdf(d1)

    if right == "call":
        price = spot * disc_q * _norm_cdf(d1) - strike * disc_r * _norm_cdf(d2)
        delta = disc_q * _norm_cdf(d1)
        theta_year = (
            -(spot * disc_q * pdf_d1 * sig) / (2 * sqrtT)
            - r * strike * disc_r * _norm_cdf(d2)
            + q * spot * disc_q * _norm_cdf(d1)
        )
    else:
        price = strike * disc_r * _norm_cdf(-d2) - spot * disc_q * _norm_cdf(-d1)
        delta = -disc_q * _norm_cdf(-d1)
        theta_year = (
            -(spot * disc_q * pdf_d1 * sig) / (2 * sqrtT)
            + r * strike * disc_r * _norm_cdf(-d2)
            - q * spot * disc_q * _norm_cdf(-d1)
        )

    gamma = disc_q * pdf_d1 / (spot * sig * sqrtT)
    vega = spot * disc_q * pdf_d1 * sqrtT      # per 1.00 change in sigma
    theta = theta_year / 365.0
    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, price=price)


# ---------- Historical bars / realized vol ----------

def _yf():
    try:
        import yfinance as yf
        return yf
    except Exception:
        return None


def get_closes(ticker: str, period: str = "1y") -> List[float]:
    """Daily closes, most-recent last. Empty list on failure."""
    yf = _yf()
    if yf is None:
        return []
    try:
        hist = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    except Exception:
        return []
    if hist is None or hist.empty or "Close" not in hist:
        return []
    return [float(x) for x in hist["Close"].dropna().tolist()]


def realized_vol(closes: List[float], window: int = 30) -> Optional[float]:
    """Annualized close-to-close realized volatility over the last `window` days."""
    if len(closes) < window + 1:
        return None
    rets = []
    for i in range(len(closes) - window, len(closes)):
        prev = closes[i - 1]
        if prev <= 0:
            continue
        rets.append(math.log(closes[i] / prev))
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(252.0)


# ---------- Options chain ----------

@dataclass
class OptionQuote:
    ticker: str
    expiry: date
    strike: float
    right: str                 # "call" | "put"
    bid: float
    ask: float
    last: float
    iv: float
    open_interest: int
    volume: int

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return self.last or self.ask or self.bid


def get_option_quote(ticker: str, expiry: date, strike: float, right: str) -> Optional[OptionQuote]:
    yf = _yf()
    if yf is None:
        return None
    try:
        t = yf.Ticker(ticker)
        chain = t.option_chain(expiry.isoformat())
    except Exception:
        time.sleep(0.5)
        try:
            chain = yf.Ticker(ticker).option_chain(expiry.isoformat())
        except Exception:
            return None
    df = chain.calls if right == "call" else chain.puts
    if df is None or df.empty:
        return None
    # Find closest strike
    row = df.iloc[(df["strike"] - strike).abs().argsort().iloc[0]]
    return OptionQuote(
        ticker=ticker,
        expiry=expiry,
        strike=float(row["strike"]),
        right=right,
        bid=float(row.get("bid") or 0.0),
        ask=float(row.get("ask") or 0.0),
        last=float(row.get("lastPrice") or 0.0),
        iv=float(row.get("impliedVolatility") or 0.0),
        open_interest=int(row.get("openInterest") or 0),
        volume=int(row.get("volume") or 0),
    )


# ---------- Earnings ----------

def next_earnings(ticker: str) -> Optional[date]:
    yf = _yf()
    if yf is None:
        return None
    try:
        cal = yf.Ticker(ticker).calendar
    except Exception:
        return None
    if cal is None:
        return None
    val = None
    # yfinance returns either a dict or a DataFrame depending on version
    if hasattr(cal, "get"):
        val = cal.get("Earnings Date")
    elif hasattr(cal, "loc"):
        try:
            val = cal.loc["Earnings Date"].iloc[0]
        except Exception:
            val = None
    if val is None:
        return None
    if isinstance(val, list) and val:
        val = val[0]
    try:
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        return datetime.fromisoformat(str(val)[:10]).date()
    except Exception:
        return None


# ---------- IV percentile (best-effort) ----------

def iv_vs_hv_ratio(current_iv: float, hv30: Optional[float]) -> Optional[float]:
    """IV/HV ratio — proxy for "is the market charging a premium over realized vol".
    True 1y IV percentile would require historical option chains, which yfinance
    doesn't expose for free. This ratio is a cheap stand-in.
    """
    if hv30 is None or hv30 <= 0 or current_iv <= 0:
        return None
    return current_iv / hv30
