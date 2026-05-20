"""Trade analysis rules engine.

A pure-function evaluator that takes a `TradeProposal` and returns a list of
`RuleResult`s. Each rule is one of the quant-trading principles the user
wants enforced before entering a position (positive EV, Kelly sizing, IV
sanity, theta budget, etc.). Rules degrade to ``status="skip"`` when they
need market data that isn't available — they never raise.

To add a rule:
1. Write a function `rule_xxx(p, ctx) -> RuleResult`.
2. Append it to `_RULES` below.

The endpoint in `main.py` wires this to `POST /api/analyze-trade`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Dict, List, Optional

from . import market_data as md


# ---------- Inputs / outputs ----------

@dataclass
class TradeProposal:
    ticker: str
    action: str                       # "buy" | "sell"
    instrument: str                   # "stock" | "call" | "put"
    quantity: float                   # shares, or contracts (1 contract = 100 shares)
    total_capital: float              # for sizing rules
    # Options-only:
    strike: Optional[float] = None
    expiry: Optional[date] = None
    premium: Optional[float] = None   # per-share premium the user expects to pay/receive
    # User-supplied thesis & exits:
    edge_thesis: str = ""
    profit_target: Optional[float] = None    # underlying or option price
    stop_loss: Optional[float] = None
    win_probability: Optional[float] = None  # user's subjective P(win), 0..1
    expected_profit: Optional[float] = None  # $ if win
    expected_loss: Optional[float] = None    # $ if lose (positive number)


@dataclass
class RuleResult:
    rule_id: str
    title: str
    status: str                       # "pass" | "warn" | "fail" | "info" | "skip"
    message: str
    math: Dict[str, Any] = field(default_factory=dict)


# ---------- Context loader ----------

@dataclass
class Context:
    spot: float
    closes: List[float]
    hv30: Optional[float]
    option: Optional[md.OptionQuote]
    greeks: Optional[md.Greeks]
    days_to_expiry: Optional[int]
    earnings_date: Optional[date]


def _load_context(p: TradeProposal) -> Context:
    closes = md.get_closes(p.ticker, period="1y")
    spot = closes[-1] if closes else 0.0
    hv30 = md.realized_vol(closes, window=30)

    option: Optional[md.OptionQuote] = None
    greeks: Optional[md.Greeks] = None
    dte: Optional[int] = None
    if p.instrument in ("call", "put") and p.strike and p.expiry:
        option = md.get_option_quote(p.ticker, p.expiry, p.strike, p.instrument)
        dte = max((p.expiry - date.today()).days, 0)
        iv_for_greeks = option.iv if option and option.iv > 0 else (hv30 or 0.0)
        if spot and iv_for_greeks > 0 and dte > 0:
            greeks = md.black_scholes_greeks(
                spot=spot, strike=p.strike, days_to_expiry=dte,
                iv=iv_for_greeks, right=p.instrument,
            )

    earn = md.next_earnings(p.ticker)
    return Context(
        spot=spot, closes=closes, hv30=hv30,
        option=option, greeks=greeks,
        days_to_expiry=dte, earnings_date=earn,
    )


# ---------- Individual rules ----------

def rule_implied_move(p: TradeProposal, ctx: Context) -> RuleResult:
    if not ctx.option or ctx.option.iv <= 0 or not ctx.days_to_expiry or not ctx.spot:
        return RuleResult("implied_move", "Implied move", "skip",
                          "Not an option trade or no IV available.")
    move = ctx.option.iv * ctx.spot * math.sqrt(ctx.days_to_expiry / 365.0)
    pct = move / ctx.spot * 100
    return RuleResult(
        "implied_move", "Implied move", "info",
        f"Market expects ±${move:.2f} ({pct:.1f}%) by expiry. "
        f"You profit only if the move exceeds this.",
        {"implied_move": round(move, 4), "pct": round(pct, 2),
         "iv": round(ctx.option.iv, 4), "dte": ctx.days_to_expiry, "spot": ctx.spot},
    )


def rule_iv_vs_hv(p: TradeProposal, ctx: Context) -> RuleResult:
    if not ctx.option or ctx.option.iv <= 0 or ctx.hv30 is None:
        return RuleResult("iv_vs_hv", "IV vs realized vol", "skip",
                          "Need an option IV and 30d realized vol.")
    ratio = md.iv_vs_hv_ratio(ctx.option.iv, ctx.hv30)
    buying = p.action == "buy"
    status = "pass"
    msg = f"IV/HV30 = {ratio:.2f}."
    if ratio is None:
        return RuleResult("iv_vs_hv", "IV vs realized vol", "skip", "Ratio unavailable.")
    if ratio > 1.5 and buying:
        status = "fail"
        msg += " You are buying options when IV is heavily inflated vs realized vol — negative EV on average."
    elif ratio > 1.3 and buying:
        status = "warn"
        msg += " IV is meaningfully above realized vol; buyers are paying a premium."
    elif ratio < 0.9 and not buying:
        status = "warn"
        msg += " IV is below realized vol; selling premium here has weaker edge."
    elif ratio > 1.3 and not buying:
        status = "pass"
        msg += " Selling into elevated IV — favorable on average."
    return RuleResult("iv_vs_hv", "IV vs realized vol", status, msg,
                      {"iv": round(ctx.option.iv, 4), "hv30": round(ctx.hv30, 4),
                       "ratio": round(ratio, 3)})


def rule_expected_value(p: TradeProposal, ctx: Context) -> RuleResult:
    pw, profit, loss = p.win_probability, p.expected_profit, p.expected_loss
    if pw is None or profit is None or loss is None:
        return RuleResult("ev", "Expected value", "skip",
                          "Provide win_probability, expected_profit, expected_loss.")
    if not (0.0 <= pw <= 1.0):
        return RuleResult("ev", "Expected value", "fail",
                          "win_probability must be between 0 and 1.")
    ev = pw * profit - (1 - pw) * loss
    status = "pass" if ev > 0 else "fail"
    msg = f"EV = ({pw:.2f} × ${profit:.2f}) − ({1-pw:.2f} × ${loss:.2f}) = ${ev:.2f}."
    if ev <= 0:
        msg += " Negative expected value — do not enter without a specific reason to override your probability estimate."
    return RuleResult("ev", "Expected value", status, msg,
                      {"p_win": pw, "profit": profit, "loss": loss, "ev": round(ev, 2)})


def rule_kelly_sizing(p: TradeProposal, ctx: Context) -> RuleResult:
    pw, profit, loss = p.win_probability, p.expected_profit, p.expected_loss
    if pw is None or profit is None or loss is None or loss <= 0:
        return RuleResult("kelly", "Kelly sizing", "skip",
                          "Need win_probability, expected_profit, expected_loss.")
    b = profit / loss                   # payoff ratio
    q = 1 - pw
    f_full = (b * pw - q) / b if b > 0 else -1.0
    f_half = max(f_full / 2.0, 0.0)
    rec_dollars = f_half * p.total_capital
    proposed_risk = loss
    status = "pass"
    msg = (f"Half-Kelly = {f_half*100:.2f}% → recommend risking up to "
           f"${rec_dollars:.2f} (of ${p.total_capital:.0f}). "
           f"Your proposed risk: ${proposed_risk:.2f}.")
    if f_full <= 0:
        status = "fail"
        msg = ("Full Kelly is non-positive — the math says don't take this trade at any size. "
               f"f* = {f_full*100:.2f}%.")
    elif proposed_risk > rec_dollars * 1.05:
        status = "warn"
        msg += " You are over-sized relative to half-Kelly."
    return RuleResult("kelly", "Kelly sizing", status, msg,
                      {"f_full": round(f_full, 4), "f_half": round(f_half, 4),
                       "recommended_dollars": round(rec_dollars, 2),
                       "proposed_risk": round(proposed_risk, 2)})


def rule_position_size(p: TradeProposal, ctx: Context) -> RuleResult:
    if p.total_capital <= 0:
        return RuleResult("position_size", "Position size", "skip", "Need total_capital.")
    if p.instrument == "stock":
        risk = abs(p.quantity) * (ctx.spot or 0.0)
    else:
        prem = p.premium if p.premium is not None else (ctx.option.mid if ctx.option else 0.0)
        risk = abs(p.quantity) * 100 * (prem or 0.0)
    if risk <= 0:
        return RuleResult("position_size", "Position size", "skip",
                          "Couldn't compute risk (missing price/premium).")
    pct = risk / p.total_capital * 100
    if pct > 10:
        status, msg = "fail", f"Position is {pct:.1f}% of capital — far above the 1–5% guideline."
    elif pct > 5:
        status, msg = "warn", f"Position is {pct:.1f}% of capital — above the 5% ceiling."
    elif pct > 2:
        status, msg = "warn", f"Position is {pct:.1f}% of capital — within 2–5%, size deliberately."
    else:
        status, msg = "pass", f"Position is {pct:.1f}% of capital."
    return RuleResult("position_size", "Position size", status, msg,
                      {"risk_dollars": round(risk, 2), "pct_of_capital": round(pct, 2)})


def rule_theta_budget(p: TradeProposal, ctx: Context) -> RuleResult:
    if p.instrument == "stock" or not ctx.greeks or not ctx.option or not ctx.days_to_expiry:
        return RuleResult("theta", "Theta budget", "skip", "Not applicable to this trade.")
    per_day = ctx.greeks.theta * 100 * abs(p.quantity)
    total = per_day * ctx.days_to_expiry
    premium = (p.premium if p.premium is not None else ctx.option.mid) * 100 * abs(p.quantity)
    if premium <= 0:
        return RuleResult("theta", "Theta budget", "skip", "Need a premium to compare.")
    pct = abs(total) / premium * 100
    if p.action == "buy":
        if pct > 75:
            status, msg = "fail", f"Theta will eat {pct:.0f}% of premium by expiry — buying is essentially renting time decay."
        elif pct > 50:
            status, msg = "warn", f"Theta will eat ~{pct:.0f}% of premium by expiry."
        else:
            status, msg = "pass", f"Theta cost ~{pct:.0f}% of premium over {ctx.days_to_expiry} days."
    else:
        status = "pass"
        msg = f"Selling premium: theta works for you (~${abs(total):.2f} over {ctx.days_to_expiry} days)."
    return RuleResult("theta", "Theta budget", status, msg,
                      {"theta_per_day": round(per_day, 4), "theta_total": round(total, 2),
                       "premium_total": round(premium, 2), "pct_of_premium": round(pct, 2)})


def rule_earnings_proximity(p: TradeProposal, ctx: Context) -> RuleResult:
    if not ctx.earnings_date:
        return RuleResult("earnings", "Earnings proximity", "skip", "No earnings date found.")
    days = (ctx.earnings_date - date.today()).days
    if p.instrument in ("call", "put") and p.expiry:
        inside = date.today() <= ctx.earnings_date <= p.expiry
        if inside:
            return RuleResult("earnings", "Earnings proximity", "warn",
                              f"Earnings on {ctx.earnings_date} falls inside your trade window — expect IV crush after the report.",
                              {"earnings_date": ctx.earnings_date.isoformat(), "days_away": days})
    if 0 <= days <= 7:
        return RuleResult("earnings", "Earnings proximity", "warn",
                          f"Earnings in {days} day(s) — vol and direction can dislocate.",
                          {"earnings_date": ctx.earnings_date.isoformat(), "days_away": days})
    return RuleResult("earnings", "Earnings proximity", "info",
                      f"Earnings on {ctx.earnings_date} ({days} days away).",
                      {"earnings_date": ctx.earnings_date.isoformat(), "days_away": days})


def rule_pre_commit_exits(p: TradeProposal, ctx: Context) -> RuleResult:
    missing = []
    if p.profit_target is None:
        missing.append("profit_target")
    if p.stop_loss is None:
        missing.append("stop_loss")
    if missing:
        return RuleResult("exits", "Pre-committed exits", "fail",
                          f"Set these before entering: {', '.join(missing)}. "
                          "Pre-committing counteracts prospect-theory bias.")
    return RuleResult("exits", "Pre-committed exits", "pass",
                      f"Profit target ${p.profit_target}, stop ${p.stop_loss}.")


def rule_edge_thesis(p: TradeProposal, ctx: Context) -> RuleResult:
    text = (p.edge_thesis or "").strip()
    if len(text) < 30:
        return RuleResult("edge", "Edge thesis", "fail",
                          "Articulate (≥30 chars) why you know something the market doesn't. "
                          "If you can't, your edge probably isn't real.")
    return RuleResult("edge", "Edge thesis", "pass", "Edge thesis recorded.",
                      {"length": len(text)})


def rule_greeks_breakdown(p: TradeProposal, ctx: Context) -> RuleResult:
    if not ctx.greeks:
        return RuleResult("greeks", "Greeks breakdown", "skip", "Not an option or missing inputs.")
    g = ctx.greeks
    return RuleResult("greeks", "Greeks breakdown", "info",
                      f"Δ {g.delta:+.2f}  Γ {g.gamma:.4f}  Θ ${g.theta*100:+.2f}/day  "
                      f"ν ${g.vega*100*0.01:+.2f}/1%-IV   (per contract)",
                      {"delta": round(g.delta, 4), "gamma": round(g.gamma, 6),
                       "theta_per_day_per_contract": round(g.theta * 100, 4),
                       "vega_per_1pct_per_contract": round(g.vega * 100 * 0.01, 4),
                       "bs_price": round(g.price, 4)})


_RULES = [
    rule_edge_thesis,
    rule_pre_commit_exits,
    rule_position_size,
    rule_expected_value,
    rule_kelly_sizing,
    rule_implied_move,
    rule_iv_vs_hv,
    rule_theta_budget,
    rule_greeks_breakdown,
    rule_earnings_proximity,
]


# ---------- Orchestration ----------

_STATUS_WEIGHT = {"pass": 1.0, "info": 1.0, "skip": 1.0,
                  "warn": 0.5, "fail": 0.0}


def analyze(proposal: TradeProposal) -> Dict[str, Any]:
    ctx = _load_context(proposal)
    results: List[RuleResult] = []
    for fn in _RULES:
        try:
            results.append(fn(proposal, ctx))
        except Exception as e:
            results.append(RuleResult(fn.__name__, fn.__name__, "skip",
                                      f"Rule errored: {e}"))

    scored = [r for r in results if r.status in ("pass", "warn", "fail")]
    score = (sum(_STATUS_WEIGHT[r.status] for r in scored) / len(scored)) if scored else 1.0
    has_fail = any(r.status == "fail" for r in results)
    has_warn = any(r.status == "warn" for r in results)
    recommendation = "do_not_enter" if has_fail else ("review" if has_warn else "ok")

    return {
        "proposal": asdict(proposal) | {
            "expiry": proposal.expiry.isoformat() if proposal.expiry else None,
        },
        "context": {
            "spot": ctx.spot,
            "hv30": ctx.hv30,
            "days_to_expiry": ctx.days_to_expiry,
            "earnings_date": ctx.earnings_date.isoformat() if ctx.earnings_date else None,
            "option": (
                {"bid": ctx.option.bid, "ask": ctx.option.ask, "mid": ctx.option.mid,
                 "iv": ctx.option.iv, "open_interest": ctx.option.open_interest,
                 "volume": ctx.option.volume}
                if ctx.option else None
            ),
        },
        "rules": [asdict(r) for r in results],
        "score": round(score, 3),
        "recommendation": recommendation,
    }
