"""Quote fetching via yfinance with a 15-minute SQLite cache.

Crypto quotes go through CoinGecko instead — Yahoo aggressively rate-limits
crypto endpoints and CoinGecko's public API is free + reliable.
"""
import logging
import time
from datetime import datetime, timedelta, date as date_cls
from typing import Dict, Optional
import urllib.request
import urllib.parse
import json
from sqlalchemy.orm import Session
from . import models

# Our internal ticker -> CoinGecko coin id
COINGECKO_IDS = {
    "BTC-USD": "bitcoin",
    "ETH-USD": "ethereum",
    "DOT-USD": "polkadot",
    "USDC-USD": "usd-coin",
}

CACHE_TTL = timedelta(minutes=15)
PINNED_QUOTE_THRESHOLD = datetime(2099, 1, 1)
THROTTLE_SECONDS = 0.35   # space out bulk requests so Yahoo doesn't 429
_HISTORY_CACHE: Dict[str, Dict[date_cls, float]] = {}

# Quiet yfinance's own logging — it spams stderr on every 429 / parse error.
for _name in ("yfinance", "yfinance.ticker", "yfinance.utils", "yfinance.data"):
    logging.getLogger(_name).setLevel(logging.CRITICAL)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _http_json(url: str, timeout: float = 8.0):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "portfolio-mgmt/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _coingecko_quote(ticker: str) -> Optional[dict]:
    coin = COINGECKO_IDS.get(ticker)
    if not coin:
        return None
    url = (
        "https://api.coingecko.com/api/v3/simple/price?"
        + urllib.parse.urlencode({
            "ids": coin,
            "vs_currencies": "cad",
            "include_24hr_change": "true",
        })
    )
    data = _http_json(url)
    if not data or coin not in data:
        time.sleep(1.5)
        data = _http_json(url)
    if not data or coin not in data:
        return None
    px = float(data[coin].get("cad") or 0.0)
    chg = float(data[coin].get("cad_24h_change") or 0.0)
    if not px:
        return None
    prev = px / (1 + chg / 100.0) if chg else px
    return {
        "last_price": px,
        "previous_close": prev,
        "week52_high": px,
        "week52_low": px,
        "dividend_yield": 0.0,
        "currency": "CAD",
    }


def _coingecko_history(ticker: str, start: date_cls) -> Dict[date_cls, float]:
    coin = COINGECKO_IDS.get(ticker)
    if not coin:
        return {}
    days = max((date_cls.today() - start).days + 1, 1)
    # `interval=daily` requires a paid CoinGecko plan; the free tier auto-picks
    # daily granularity when days > 90, which is what we always need.
    url = (
        f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?"
        + urllib.parse.urlencode({"vs_currency": "cad", "days": days})
    )
    data = _http_json(url)
    if data is None:
        time.sleep(1.5)
        data = _http_json(url)
    if not data or "prices" not in data:
        return {}
    out: Dict[date_cls, float] = {}
    for ts_ms, px in data["prices"]:
        d = datetime.utcfromtimestamp(ts_ms / 1000.0).date()
        out[d] = float(px)
    return out


def _refresh_via_yfinance(ticker: str):
    """Best-effort yfinance fetch. Uses history() only — the quoteSummary/info
    endpoints get rate-limited by Yahoo much more aggressively than history."""
    try:
        import yfinance as yf
    except Exception:
        return None

    last = prev = hi = lo = 0.0
    currency = "USD"

    t = yf.Ticker(ticker)
    hist = _safe(lambda: t.history(period="1y", auto_adjust=False))
    if hist is None or hist.empty:
        time.sleep(1.0)
        hist = _safe(lambda: t.history(period="1y", auto_adjust=False))
    if hist is None or hist.empty:
        return None

    closes = hist["Close"].dropna()
    if not len(closes):
        return None
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) > 1 else last
    hi = float(closes.max())
    lo = float(closes.min())

    # fast_info is usually OK and gives us the listing currency. If it fails,
    # default to USD (the caller doesn't depend on this for math).
    fast = _safe(lambda: dict(t.fast_info)) or {}
    currency = fast.get("currency") or currency

    return {
        "last_price": last,
        "previous_close": prev or last,
        "week52_high": hi or last,
        "week52_low": lo or last,
        "dividend_yield": 0.0,
        "currency": currency,
    }


def get_quote(db: Session, ticker: str, force: bool = False) -> dict:
    row = db.query(models.PriceCache).filter_by(ticker=ticker).first()
    now = datetime.utcnow()
    if row and row.fetched_at >= PINNED_QUOTE_THRESHOLD:
        return _row_to_dict(row)
    if row and not force and (now - row.fetched_at) < CACHE_TTL:
        return _row_to_dict(row)

    data = _coingecko_quote(ticker) if ticker in COINGECKO_IDS else None
    if data is None:
        data = _refresh_via_yfinance(ticker)
    if data is None:
        if row:
            return _row_to_dict(row)
        # zero placeholder
        return {"last_price": 0.0, "previous_close": 0.0, "week52_high": 0.0,
                "week52_low": 0.0, "dividend_yield": 0.0, "currency": "USD"}

    if row is None:
        row = models.PriceCache(ticker=ticker, **data, fetched_at=now)
        db.add(row)
    else:
        for k, v in data.items():
            setattr(row, k, v)
        row.fetched_at = now
    db.commit()
    return data


def _row_to_dict(row: models.PriceCache) -> dict:
    return {
        "last_price": row.last_price,
        "previous_close": row.previous_close,
        "week52_high": row.week52_high,
        "week52_low": row.week52_low,
        "dividend_yield": row.dividend_yield,
        "currency": row.currency,
    }


def refresh_all(db: Session):
    tickers = [i.ticker for i in db.query(models.Instrument).all()]
    out = {}
    for i, t in enumerate(tickers):
        if i:
            time.sleep(THROTTLE_SECONDS)
        out[t] = get_quote(db, t, force=True)
    return out


def get_history(db: Session, ticker: str) -> Dict[date_cls, float]:
    """Return a {date: close_price} dict for `ticker` from the DB cache.

    Never makes a network call — run `python fetch_history.py` (or hit
    `POST /api/history/refresh`) to populate. Empty dict means "no data";
    callers fall back to today's quote.
    """
    if ticker in _HISTORY_CACHE:
        return _HISTORY_CACHE[ticker]
    rows = db.query(models.PriceHistory).filter_by(ticker=ticker).all()
    out = {r.date: r.close for r in rows}
    _HISTORY_CACHE[ticker] = out
    return out


def _fetch_history_yf(ticker: str, start: date_cls) -> Dict[date_cls, float]:
    try:
        import yfinance as yf
    except Exception:
        return {}
    out: Dict[date_cls, float] = {}
    t = yf.Ticker(ticker)
    hist = _safe(lambda: t.history(start=start.isoformat(), auto_adjust=False))
    if hist is None or hist.empty:
        time.sleep(1.0)
        hist = _safe(lambda: t.history(start=start.isoformat(), auto_adjust=False))
    if hist is not None and not hist.empty:
        for ts, close in hist["Close"].dropna().items():
            out[ts.date()] = float(close)
    return out


def populate_history(db: Session, start: date_cls) -> dict:
    """Fetch daily closes for every instrument and persist to PriceHistory.
    Slow (throttled to respect Yahoo/CoinGecko rate limits) — meant to be
    run from a CLI or once-per-refresh, not on every page load."""
    stats = {"ok": 0, "empty": 0, "rows": 0}
    tickers = [i.ticker for i in db.query(models.Instrument).all()]
    for i, ticker in enumerate(tickers):
        if i:
            time.sleep(THROTTLE_SECONDS)
        if ticker in COINGECKO_IDS:
            data = _coingecko_history(ticker, start)
            if not data:
                time.sleep(2.0)
                data = _coingecko_history(ticker, start)
        else:
            data = _fetch_history_yf(ticker, start)

        if not data:
            stats["empty"] += 1
            continue

        # Replace any existing rows for this ticker
        db.query(models.PriceHistory).filter_by(ticker=ticker).delete()
        for d, px in data.items():
            db.add(models.PriceHistory(ticker=ticker, date=d, close=px))
        stats["ok"] += 1
        stats["rows"] += len(data)
        db.commit()

    _HISTORY_CACHE.clear()
    return stats
