"""FastAPI app exposing the portfolio MVP API."""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from . import models, schemas, analytics, quotes, rules
from .db import engine, get_db, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Portfolio MVP API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- Accounts ----------
@app.get("/api/accounts", response_model=List[schemas.AccountOut])
def list_accounts(db: Session = Depends(get_db)):
    return db.query(models.Account).order_by(models.Account.id).all()


@app.post("/api/accounts", response_model=schemas.AccountOut)
def create_account(body: schemas.AccountIn, db: Session = Depends(get_db)):
    if db.query(models.Account).filter_by(name=body.name).first():
        raise HTTPException(400, "Account name already exists")
    a = models.Account(**body.model_dump())
    db.add(a); db.commit(); db.refresh(a)
    return a


@app.delete("/api/accounts/{aid}")
def delete_account(aid: int, db: Session = Depends(get_db)):
    a = db.get(models.Account, aid)
    if not a:
        raise HTTPException(404, "Not found")
    db.delete(a); db.commit()
    return {"ok": True}


# ---------- Instruments ----------
@app.get("/api/instruments", response_model=List[schemas.InstrumentOut])
def list_instruments(db: Session = Depends(get_db)):
    return db.query(models.Instrument).order_by(models.Instrument.ticker).all()


@app.post("/api/instruments", response_model=schemas.InstrumentOut)
def create_instrument(body: schemas.InstrumentIn, db: Session = Depends(get_db)):
    body.ticker = body.ticker.upper()
    existing = db.query(models.Instrument).filter_by(ticker=body.ticker).first()
    if existing:
        for k, v in body.model_dump().items():
            setattr(existing, k, v)
        db.commit(); db.refresh(existing)
        return existing
    inst = models.Instrument(**body.model_dump())
    db.add(inst); db.commit(); db.refresh(inst)
    return inst


@app.patch("/api/instruments/{iid}", response_model=schemas.InstrumentOut)
def update_instrument(iid: int, body: schemas.InstrumentIn, db: Session = Depends(get_db)):
    inst = db.get(models.Instrument, iid)
    if not inst:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump().items():
        setattr(inst, k, v)
    db.commit(); db.refresh(inst)
    return inst


# ---------- Transactions ----------
def _resolve_instrument(db: Session, ticker: Optional[str]) -> Optional[models.Instrument]:
    if not ticker:
        return None
    ticker = ticker.upper().strip()
    inst = db.query(models.Instrument).filter_by(ticker=ticker).first()
    if not inst:
        inst = models.Instrument(ticker=ticker, name=ticker)
        db.add(inst); db.commit(); db.refresh(inst)
    return inst


def _tx_to_out(t: models.Transaction) -> dict:
    return {
        "id": t.id,
        "account_id": t.account_id,
        "instrument_id": t.instrument_id,
        "ticker": t.instrument.ticker if t.instrument else None,
        "date": t.date,
        "type": t.type,
        "quantity": t.quantity,
        "price": t.price,
        "fees": t.fees,
        "currency": t.currency,
        "fx_rate": t.fx_rate,
        "notes": t.notes,
    }


@app.get("/api/transactions", response_model=List[schemas.TransactionOut])
def list_transactions(account_id: Optional[int] = None, ticker: Optional[str] = None,
                       db: Session = Depends(get_db)):
    q = db.query(models.Transaction)
    if account_id:
        q = q.filter(models.Transaction.account_id == account_id)
    if ticker:
        inst = db.query(models.Instrument).filter_by(ticker=ticker.upper()).first()
        if inst:
            q = q.filter(models.Transaction.instrument_id == inst.id)
    q = q.order_by(models.Transaction.date.desc(), models.Transaction.id.desc())
    return [_tx_to_out(t) for t in q.all()]


@app.post("/api/transactions", response_model=schemas.TransactionOut)
def create_transaction(body: schemas.TransactionIn, db: Session = Depends(get_db)):
    if not db.get(models.Account, body.account_id):
        raise HTTPException(400, "Account not found")
    inst = _resolve_instrument(db, body.ticker) if body.type in ("buy", "sell", "dividend", "split") else None
    t = models.Transaction(
        account_id=body.account_id,
        instrument_id=inst.id if inst else None,
        date=body.date,
        type=body.type,
        quantity=body.quantity,
        price=body.price,
        fees=body.fees,
        currency=body.currency,
        fx_rate=body.fx_rate,
        notes=body.notes,
    )
    db.add(t); db.commit(); db.refresh(t)
    return _tx_to_out(t)


@app.delete("/api/transactions/{tid}")
def delete_transaction(tid: int, db: Session = Depends(get_db)):
    t = db.get(models.Transaction, tid)
    if not t:
        raise HTTPException(404, "Not found")
    db.delete(t); db.commit()
    return {"ok": True}


# ---------- Quotes ----------
@app.get("/api/quotes/{ticker}")
def get_quote(ticker: str, force: bool = False, db: Session = Depends(get_db)):
    return quotes.get_quote(db, ticker.upper(), force=force)


@app.post("/api/quotes/refresh")
def refresh_quotes(db: Session = Depends(get_db)):
    return quotes.refresh_all(db)


@app.post("/api/history/refresh")
def refresh_history(db: Session = Depends(get_db)):
    """Repopulate the PriceHistory table from yfinance/CoinGecko.
    Slow (~60s for ~50 tickers) — run when you've imported new transactions or
    want fresher historical bars. The performance page reads this table directly."""
    txs = db.query(models.Transaction).order_by(models.Transaction.date).first()
    start = txs.date if txs else date.today()
    return quotes.populate_history(db, start)


# ---------- Portfolio analytics ----------
@app.get("/api/holdings", response_model=List[schemas.HoldingOut])
def holdings(db: Session = Depends(get_db)):
    return analytics.compute_holdings(db)


@app.get("/api/summary", response_model=schemas.PortfolioSummary)
def summary(db: Session = Depends(get_db)):
    return analytics.portfolio_summary(db)


@app.get("/api/performance", response_model=schemas.PerformanceOut)
def performance(db: Session = Depends(get_db)):
    return analytics.performance(db)


@app.post("/api/analyze-trade")
def analyze_trade(body: schemas.TradeProposalIn, save: bool = False,
                  db: Session = Depends(get_db)):
    proposal = rules.TradeProposal(
        ticker=body.ticker.upper(),
        action=body.action,
        instrument=body.instrument,
        quantity=body.quantity,
        total_capital=body.total_capital,
        strike=body.strike,
        expiry=body.expiry,
        premium=body.premium,
        edge_thesis=body.edge_thesis,
        profit_target=body.profit_target,
        stop_loss=body.stop_loss,
        win_probability=body.win_probability,
        expected_profit=body.expected_profit,
        expected_loss=body.expected_loss,
    )
    result = rules.analyze(proposal)

    if save:
        import json as _json
        row = models.TradeProposal(
            ticker=proposal.ticker, action=proposal.action, instrument=proposal.instrument,
            quantity=proposal.quantity, total_capital=proposal.total_capital,
            strike=proposal.strike, expiry=proposal.expiry, premium=proposal.premium,
            edge_thesis=proposal.edge_thesis,
            profit_target=proposal.profit_target, stop_loss=proposal.stop_loss,
            win_probability=proposal.win_probability,
            expected_profit=proposal.expected_profit, expected_loss=proposal.expected_loss,
            analysis_json=_json.dumps(result),
            recommendation=result["recommendation"], score=result["score"],
        )
        db.add(row); db.commit(); db.refresh(row)
        result["saved_proposal_id"] = row.id
    return result


@app.get("/api/proposals", response_model=List[schemas.ProposalOut])
def list_proposals(db: Session = Depends(get_db)):
    return (db.query(models.TradeProposal)
              .order_by(models.TradeProposal.created_at.desc()).all())


@app.get("/api/proposals/{pid}")
def get_proposal(pid: int, db: Session = Depends(get_db)):
    row = db.get(models.TradeProposal, pid)
    if not row:
        raise HTTPException(404, "Not found")
    import json as _json
    out = schemas.ProposalOut.model_validate(row).model_dump()
    out["analysis"] = _json.loads(row.analysis_json) if row.analysis_json else None
    return out


@app.patch("/api/proposals/{pid}", response_model=schemas.ProposalOut)
def update_proposal(pid: int, body: schemas.ProposalDecisionIn,
                    db: Session = Depends(get_db)):
    row = db.get(models.TradeProposal, pid)
    if not row:
        raise HTTPException(404, "Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit(); db.refresh(row)
    return row


@app.delete("/api/proposals/{pid}")
def delete_proposal(pid: int, db: Session = Depends(get_db)):
    row = db.get(models.TradeProposal, pid)
    if not row:
        raise HTTPException(404, "Not found")
    db.delete(row); db.commit()
    return {"ok": True}


@app.get("/api/positions/{ticker}")
def position_detail(ticker: str, db: Session = Depends(get_db)):
    inst = db.query(models.Instrument).filter_by(ticker=ticker.upper()).first()
    if not inst:
        raise HTTPException(404, "Instrument not found")
    holds = [h for h in analytics.compute_holdings(db) if h["ticker"] == inst.ticker]
    txs = (db.query(models.Transaction)
             .filter(models.Transaction.instrument_id == inst.id)
             .order_by(models.Transaction.date.desc()).all())
    q = quotes.get_quote(db, inst.ticker)
    return {
        "instrument": {
            "id": inst.id, "ticker": inst.ticker, "name": inst.name,
            "asset_type": inst.asset_type, "currency": inst.currency,
            "sector": inst.sector, "country": inst.country, "tags": inst.tags,
            "thesis": inst.thesis, "target_price": inst.target_price, "stop_price": inst.stop_price,
        },
        "quote": q,
        "holdings": holds,
        "transactions": [_tx_to_out(t) for t in txs],
    }
