"""Populate the PriceHistory table for every instrument.

Run from `backend/`:
    python fetch_history.py

Takes a while (throttled to respect Yahoo/CoinGecko rate limits). Re-run when
you add new tickers or want fresher bars. The performance page reads from this
table — no live network calls during request handling.
"""
from app.db import SessionLocal, engine, Base
from app import models, quotes

Base.metadata.create_all(bind=engine)
db = SessionLocal()

first_tx = db.query(models.Transaction).order_by(models.Transaction.date).first()
if not first_tx:
    print("No transactions in DB — nothing to fetch.")
    raise SystemExit(0)

start = first_tx.date
n_tickers = db.query(models.Instrument).count()
print(f"Fetching history from {start} for {n_tickers} tickers (~{n_tickers}s minimum)...")
stats = quotes.populate_history(db, start)
print(f"Done. ok={stats['ok']}  empty={stats['empty']}  rows={stats['rows']}")
db.close()
