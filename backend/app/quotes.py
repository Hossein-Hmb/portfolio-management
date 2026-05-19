"""Quote fetching via yfinance with a 15-minute SQLite cache."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from . import models

CACHE_TTL = timedelta(minutes=15)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _refresh_via_yfinance(ticker: str):
    """Best-effort yfinance fetch. Tries history first (most reliable),
    then enriches with fast_info/info when available."""
    try:
        import yfinance as yf
    except Exception as e:
        print(f"[quotes] yfinance not installed: {e}")
        return None

    last = prev = hi = lo = 0.0
    currency = "USD"
    dy = 0.0

    t = yf.Ticker(ticker)

    # Primary path: 1y history (works even when fast_info/info endpoints fail)
    hist = _safe(lambda: t.history(period="1y", auto_adjust=False))
    if hist is not None and not hist.empty:
        closes = hist["Close"].dropna()
        if len(closes):
            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) > 1 else last
            hi = float(closes.max())
            lo = float(closes.min())

    # Optional enrichment
    fast = _safe(lambda: dict(t.fast_info)) or {}
    currency = fast.get("currency") or currency
    if not last:
        last = float(fast.get("last_price") or fast.get("lastPrice") or 0.0)
        prev = float(fast.get("previous_close") or fast.get("previousClose") or 0.0)
    info = _safe(lambda: t.info, {}) or {}
    dy = float(info.get("dividendYield") or 0.0)

    if not last:
        print(f"[quotes] no price available for {ticker}")
        return None

    return {
        "last_price": last,
        "previous_close": prev or last,
        "week52_high": hi or last,
        "week52_low": lo or last,
        "dividend_yield": dy,
        "currency": currency,
    }


def get_quote(db: Session, ticker: str, force: bool = False) -> dict:
    row = db.query(models.PriceCache).filter_by(ticker=ticker).first()
    now = datetime.utcnow()
    if row and not force and (now - row.fetched_at) < CACHE_TTL:
        return _row_to_dict(row)

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
    for t in tickers:
        out[t] = get_quote(db, t, force=True)
    return out
