"""Holdings, P/L, and performance math derived from the transaction ledger."""
from collections import defaultdict
from datetime import date, timedelta
from typing import List, Dict
from sqlalchemy.orm import Session
from . import models, quotes


CASH_TYPES = {"deposit", "withdrawal", "interest", "dividend", "fee", "transfer_in", "transfer_out"}
SNAPSHOT_NOTE_PREFIXES = ("snapshot", "holdings-report import")
NET_DEPOSIT_NOTE_PREFIX = "net deposit snapshot"


def _is_snapshot_position(t: models.Transaction) -> bool:
    return bool(t.notes) and t.notes.startswith(SNAPSHOT_NOTE_PREFIXES)


def _is_net_deposit_snapshot(t: models.Transaction) -> bool:
    return bool(t.notes) and t.notes.startswith(NET_DEPOSIT_NOTE_PREFIX)


def _signed_cash(t: models.Transaction) -> float:
    """Return cash flow into the account in account currency."""
    amt = 0.0
    if _is_snapshot_position(t) or _is_net_deposit_snapshot(t):
        return amt
    if t.type == "buy":
        amt = -(t.quantity * t.price + t.fees) * t.fx_rate
    elif t.type == "sell":
        amt = (t.quantity * t.price - t.fees) * t.fx_rate
    elif t.type in ("deposit", "transfer_in"):
        amt = t.price * t.fx_rate if t.price else t.quantity * t.fx_rate
    elif t.type in ("withdrawal", "transfer_out", "fee"):
        amt = -(t.price or t.quantity) * t.fx_rate
    elif t.type in ("dividend", "interest"):
        amt = (t.price or t.quantity * t.price) * t.fx_rate if t.quantity else t.price * t.fx_rate
        # simpler: dividend stored as total amount in `price`
        amt = t.price * t.fx_rate
    return amt


def compute_holdings(db: Session) -> List[dict]:
    """Aggregate transactions into per-(account, instrument) positions using average cost."""
    rows: Dict[tuple, dict] = {}
    realized: Dict[tuple, float] = defaultdict(float)

    txs = (db.query(models.Transaction)
             .order_by(models.Transaction.date.asc(), models.Transaction.id.asc())
             .all())

    for t in txs:
        if t.instrument_id is None or t.type not in ("buy", "sell", "split"):
            continue
        key = (t.account_id, t.instrument_id)
        pos = rows.setdefault(key, {"units": 0.0, "cost_basis": 0.0})
        if t.type == "buy":
            pos["units"] += t.quantity
            pos["cost_basis"] += t.quantity * t.price + t.fees
        elif t.type == "split":
            pos["units"] += t.quantity
            if pos["units"] <= 1e-9:
                pos["units"] = 0.0
                pos["cost_basis"] = 0.0
        else:  # sell
            avg = (pos["cost_basis"] / pos["units"]) if pos["units"] else 0.0
            proceeds = t.quantity * t.price - t.fees
            realized[key] += proceeds - avg * t.quantity
            pos["units"] -= t.quantity
            pos["cost_basis"] -= avg * t.quantity
            if pos["units"] <= 1e-9:
                pos["units"] = 0.0
                pos["cost_basis"] = 0.0

    holdings = []
    total_mv = 0.0
    accounts = {a.id: a for a in db.query(models.Account).all()}
    instruments = {i.id: i for i in db.query(models.Instrument).all()}

    for (aid, iid), pos in rows.items():
        if pos["units"] <= 0:
            continue
        inst = instruments.get(iid)
        acct = accounts.get(aid)
        if not inst or not acct:
            continue
        q = quotes.get_quote(db, inst.ticker)
        last = q["last_price"] or 0.0
        mv = last * pos["units"]
        total_mv += mv
        avg = pos["cost_basis"] / pos["units"] if pos["units"] else 0.0
        upl = mv - pos["cost_basis"]
        upl_pct = (upl / pos["cost_basis"] * 100.0) if pos["cost_basis"] else 0.0
        holdings.append({
            "ticker": inst.ticker,
            "name": inst.name,
            "asset_type": inst.asset_type,
            "sector": inst.sector or "Unknown",
            "country": inst.country or "Unknown",
            "currency": inst.currency,
            "account_id": acct.id,
            "account_name": acct.name,
            "units": round(pos["units"], 6),
            "avg_cost": round(avg, 4),
            "cost_basis_raw": pos["cost_basis"],
            "cost_basis": round(pos["cost_basis"], 2),
            "last_price": round(last, 4),
            "market_value_raw": mv,
            "market_value": round(mv, 2),
            "unrealized_pl_raw": upl,
            "unrealized_pl": round(upl, 2),
            "unrealized_pl_pct": round(upl_pct, 2),
            "weight": 0.0,
            "tags": inst.tags or "",
            "realized_pl": round(realized.get((aid, iid), 0.0), 2),
        })

    for h in holdings:
        h["weight"] = round((h["market_value"] / total_mv * 100.0), 2) if total_mv else 0.0

    holdings.sort(key=lambda h: h["market_value"], reverse=True)
    return holdings


def compute_cash_balances(db: Session) -> Dict[int, float]:
    """Return cash by account_id derived from transactions."""
    bal: Dict[int, float] = defaultdict(float)
    for t in db.query(models.Transaction).all():
        bal[t.account_id] += _signed_cash(t)
    return bal


def compute_net_deposits(db: Session) -> float:
    """Return net external deposits in account currency."""
    total = 0.0
    for t in db.query(models.Transaction).all():
        if t.type in ("deposit", "transfer_in"):
            total += (t.price or t.quantity) * t.fx_rate
        elif t.type in ("withdrawal", "transfer_out"):
            total -= (t.price or t.quantity) * t.fx_rate
    return round(total, 2)


def compute_realized_pl(db: Session) -> float:
    total = 0.0
    rows: Dict[tuple, dict] = {}
    txs = (db.query(models.Transaction)
             .order_by(models.Transaction.date.asc(), models.Transaction.id.asc()).all())
    for t in txs:
        if t.instrument_id is None or t.type not in ("buy", "sell"):
            continue
        key = (t.account_id, t.instrument_id)
        pos = rows.setdefault(key, {"units": 0.0, "cost_basis": 0.0})
        if t.type == "buy":
            pos["units"] += t.quantity
            pos["cost_basis"] += t.quantity * t.price + t.fees
        else:
            avg = (pos["cost_basis"] / pos["units"]) if pos["units"] else 0.0
            total += (t.quantity * t.price - t.fees) - avg * t.quantity
            pos["units"] -= t.quantity
            pos["cost_basis"] -= avg * t.quantity
    return round(total, 2)


def allocation_breakdown(holdings, key) -> list:
    buckets = defaultdict(float)
    total = 0.0
    for h in holdings:
        value = h.get("market_value_raw", h["market_value"])
        buckets[h.get(key) or "Unknown"] += value
        total += value
    out = [{"label": k, "value": round(v, 2),
            "pct": round((v / total * 100.0) if total else 0.0, 2)}
           for k, v in buckets.items()]
    out.sort(key=lambda x: x["value"], reverse=True)
    return out


def portfolio_summary(db: Session) -> dict:
    holdings = compute_holdings(db)
    cash_by_acct = compute_cash_balances(db)
    cash_total = sum(cash_by_acct.values())
    invested = sum(h.get("market_value_raw", h["market_value"]) for h in holdings)
    total = invested + cash_total
    cost = sum(h.get("cost_basis_raw", h["cost_basis"]) for h in holdings)
    upl = invested - cost
    upl_pct = (upl / cost * 100.0) if cost else 0.0
    realized = compute_realized_pl(db)
    net_deposits = compute_net_deposits(db)
    total_return = total - net_deposits
    total_return_pct = (total_return / net_deposits * 100.0) if net_deposits else 0.0

    # Day change: sum of units * (last - prev_close)
    day_change = 0.0
    for h in holdings:
        q = quotes.get_quote(db, h["ticker"])
        day_change += (q["last_price"] - q["previous_close"]) * h["units"]
    prev_invested = invested - day_change
    day_pct = (day_change / prev_invested * 100.0) if prev_invested else 0.0

    by_acct = defaultdict(float)
    accounts = {a.id: a for a in db.query(models.Account).all()}
    for h in holdings:
        by_acct[h["account_name"]] += h.get("market_value_raw", h["market_value"])
    for aid, c in cash_by_acct.items():
        name = accounts[aid].name if aid in accounts else f"Account {aid}"
        by_acct[name] += c
    by_account = sorted(
        [{"label": k, "value": round(v, 2),
          "pct": round((v / total * 100.0) if total else 0.0, 2)} for k, v in by_acct.items()],
        key=lambda x: x["value"], reverse=True,
    )

    winners = sorted(holdings, key=lambda h: h["unrealized_pl"], reverse=True)[:5]
    losers = sorted(holdings, key=lambda h: h["unrealized_pl"])[:5]

    return {
        "total_value": round(total, 2),
        "cash_value": round(cash_total, 2),
        "invested_value": round(invested, 2),
        "total_cost_basis": round(cost, 2),
        "unrealized_pl": round(upl, 2),
        "unrealized_pl_pct": round(upl_pct, 2),
        "realized_pl": realized,
        "net_deposits": net_deposits,
        "total_return": round(total_return, 2),
        "total_return_pct": round(total_return_pct, 2),
        "day_change": round(day_change, 2),
        "day_change_pct": round(day_pct, 2),
        "by_asset_type": allocation_breakdown(holdings, "asset_type"),
        "by_sector": allocation_breakdown(holdings, "sector"),
        "by_currency": allocation_breakdown(holdings, "currency"),
        "by_account": by_account,
        "top_positions": holdings[:5],
        "top_winners": winners,
        "top_losers": losers,
    }


# ---------- Performance (TWR, XIRR, drawdown, vol, sharpe) ----------

def _portfolio_value_series(db: Session) -> List[tuple]:
    """Replay the ledger and compute portfolio value (cash + holdings @ historical
    close) per day. Falls back to the last live quote for tickers without history."""
    txs = (db.query(models.Transaction)
             .order_by(models.Transaction.date.asc(), models.Transaction.id.asc()).all())
    if not txs:
        return []
    instruments = {i.id: i for i in db.query(models.Instrument).all()}
    start = txs[0].date
    end = date.today()

    # Pre-fetch per-ticker historical bars and forward-fill so every calendar day
    # has a price.
    price_by_day: Dict[str, Dict[date, float]] = {}
    fallback: Dict[str, float] = {}
    cached_prices = {p.ticker: p.last_price for p in db.query(models.PriceCache).all()}
    for inst in instruments.values():
        hist = quotes.get_history(db, inst.ticker)
        if hist:
            filled: Dict[date, float] = {}
            last_p = 0.0
            d = start
            while d <= end:
                if d in hist:
                    last_p = hist[d]
                if last_p:
                    filled[d] = last_p
                d += timedelta(days=1)
            price_by_day[inst.ticker] = filled
        else:
            fallback[inst.ticker] = cached_prices.get(inst.ticker) or 0.0

    def price(ticker: str, d: date) -> float:
        if ticker in price_by_day:
            return price_by_day[ticker].get(d, 0.0)
        return fallback.get(ticker, 0.0)

    series = []
    cash = 0.0
    units: Dict[int, float] = defaultdict(float)
    idx = 0
    d = start
    while d <= end:
        while idx < len(txs) and txs[idx].date <= d:
            t = txs[idx]
            cash += _signed_cash(t)
            if t.instrument_id is not None and t.type in ("buy", "sell", "split"):
                if t.type == "buy" or t.type == "split":
                    units[t.instrument_id] += t.quantity
                else:
                    units[t.instrument_id] -= t.quantity
            idx += 1
        mv = cash
        for iid, u in units.items():
            if u <= 0:
                continue
            inst = instruments.get(iid)
            if not inst:
                continue
            mv += u * price(inst.ticker, d)
        series.append((d, round(mv, 2)))
        d += timedelta(days=1)
    return series


def _twr(series, cashflows_by_date) -> float:
    """Simple time-weighted return: chain daily sub-period returns, adjusting for external flows."""
    if len(series) < 2:
        return 0.0
    chain = 1.0
    prev_d, prev_v = series[0]
    for d, v in series[1:]:
        flow = cashflows_by_date.get(d, 0.0)
        denom = prev_v + flow
        if denom > 0:
            chain *= (v / denom)
        prev_d, prev_v = d, v
    return chain - 1.0


def _xirr(flows):
    """flows: list of (date, amount). Newton's method."""
    if not flows:
        return 0.0
    from scipy.optimize import brentq
    d0 = flows[0][0]

    def npv(r):
        return sum(amt / ((1 + r) ** ((d - d0).days / 365.0)) for d, amt in flows)
    try:
        return brentq(npv, -0.999, 10.0)
    except Exception:
        return 0.0


def performance(db: Session) -> dict:
    series = _portfolio_value_series(db)
    if not series:
        return {"twr": {}, "xirr": 0.0, "volatility": 0.0, "max_drawdown": 0.0,
                "sharpe": 0.0, "series": []}

    # External cash flows per date (deposit/withdrawal/transfer)
    external = defaultdict(float)
    for t in db.query(models.Transaction).all():
        if _is_net_deposit_snapshot(t):
            continue
        if t.type in ("deposit", "transfer_in"):
            external[t.date] += (t.price or t.quantity) * t.fx_rate
        elif t.type in ("withdrawal", "transfer_out"):
            external[t.date] -= (t.price or t.quantity) * t.fx_rate

    # TWR over standard windows
    end_d = series[-1][0]

    def twr_from(start_d):
        sub = [(d, v) for d, v in series if d >= start_d]
        return _twr(sub, external)

    twr = {
        "1M": round(twr_from(end_d - timedelta(days=30)) * 100, 2),
        "3M": round(twr_from(end_d - timedelta(days=90)) * 100, 2),
        "YTD": round(twr_from(date(end_d.year, 1, 1)) * 100, 2),
        "1Y": round(twr_from(end_d - timedelta(days=365)) * 100, 2),
        "ALL": round(_twr(series, external) * 100, 2),
    }

    # XIRR: external flows + terminal value as inflow
    flows = []
    for d, amt in sorted(external.items()):
        if amt:
            flows.append((d, -amt))           # money in = negative
    flows.append((end_d, series[-1][1]))      # final value = positive
    xirr_v = round(_xirr(flows) * 100, 2)

    # Volatility (annualized stdev of daily returns)
    rets = []
    for i in range(1, len(series)):
        prev = series[i - 1][1]
        if prev > 0:
            rets.append((series[i][1] - prev) / prev)
    import math
    if rets:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / max(len(rets) - 1, 1)
        vol = math.sqrt(var) * math.sqrt(252)
    else:
        vol = 0.0

    # Max drawdown
    peak = -1e18
    mdd = 0.0
    for _, v in series:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, (v - peak) / peak)

    # Sharpe (rf=0 for MVP)
    sharpe = round(((sum(rets) / len(rets) * 252) / vol), 2) if vol and rets else 0.0

    return {
        "twr": twr,
        "xirr": xirr_v,
        "volatility": round(vol * 100, 2),
        "max_drawdown": round(mdd * 100, 2),
        "sharpe": sharpe,
        "series": [{"date": d, "value": v} for d, v in series],
    }
