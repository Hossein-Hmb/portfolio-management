"""Seed the database with example accounts, instruments, and trades.

Run:  python seed.py
"""
from datetime import date
from app.db import SessionLocal, engine, Base
from app import models

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Wipe (MVP-friendly)
db.query(models.Transaction).delete()
db.query(models.Instrument).delete()
db.query(models.Account).delete()
db.commit()

# Accounts
tax = models.Account(name="Taxable", account_type="taxable", currency="CAD")
tfsa = models.Account(name="TFSA", account_type="tfsa", currency="CAD")
rrsp = models.Account(name="RRSP", account_type="rrsp", currency="CAD")
evolve = models.Account(name="Evolve Simple - main", account_type="other", currency="CAD")
db.add_all([tax, tfsa, rrsp, evolve]); db.commit()

# Instruments
instruments = [
    dict(ticker="AAPL", name="Apple Inc.",       asset_type="stock", currency="USD", sector="Technology",        country="US", tags="long-term"),
    dict(ticker="MSFT", name="Microsoft Corp.",  asset_type="stock", currency="USD", sector="Technology",        country="US", tags="long-term"),
    dict(ticker="VTI",  name="Vanguard Total US",asset_type="etf",   currency="USD", sector="Diversified",       country="US", tags="core"),
    dict(ticker="VFV.TO", name="Vanguard S&P 500 CAD", asset_type="etf", currency="CAD", sector="Diversified",  country="CA", tags="core"),
    dict(ticker="SHOP.TO", name="Shopify Inc.",  asset_type="stock", currency="CAD", sector="Technology",        country="CA", tags="swing"),
    dict(ticker="ENB.TO", name="Enbridge Inc.",  asset_type="stock", currency="CAD", sector="Energy",            country="CA", tags="dividend"),
    dict(ticker="NVDA", name="NVIDIA Corp.",     asset_type="stock", currency="USD", sector="Semiconductors",    country="US", tags="swing"),
    dict(ticker="BTC-USD", name="Bitcoin",        asset_type="crypto", currency="USD", sector="Crypto",          country="-",  tags="alt"),
]
inst_map = {}
for spec in instruments:
    i = models.Instrument(**spec)
    db.add(i); db.commit(); db.refresh(i)
    inst_map[i.ticker] = i

# Helper
def tx(account, ticker, typ, date_, qty=0.0, price=0.0, fees=0.0, fx=1.0, currency="CAD", notes=""):
    inst = inst_map.get(ticker) if ticker else None
    db.add(models.Transaction(
        account_id=account.id,
        instrument_id=inst.id if inst else None,
        date=date_, type=typ, quantity=qty, price=price, fees=fees,
        fx_rate=fx, currency=currency, notes=notes,
    ))

# Deposits (price field holds total amount for cash flows)
tx(tax,    None, "deposit", date(2024, 1, 5),  price=15000)
tx(tfsa,   None, "deposit", date(2024, 1, 5),  price=20000)
tx(rrsp,   None, "deposit", date(2024, 2, 1),  price=10000)
tx(evolve, None, "deposit", date(2024, 3, 1),  price=5000)

# Trades
tx(tax,  "AAPL",   "buy",  date(2024, 2, 10), qty=20, price=185.50, fees=4.99, fx=1.35, currency="USD")
tx(tax,  "MSFT",   "buy",  date(2024, 3, 14), qty=10, price=415.00, fees=4.99, fx=1.36, currency="USD")
tx(tax,  "NVDA",   "buy",  date(2024, 4, 22), qty=8,  price=820.00, fees=4.99, fx=1.37, currency="USD")
tx(tax,  "NVDA",   "sell", date(2025, 2, 18), qty=4,  price=1180.00, fees=4.99, fx=1.42, currency="USD")
tx(tfsa, "VTI",    "buy",  date(2024, 1, 22), qty=40, price=235.00, fees=4.99, fx=1.34, currency="USD")
tx(tfsa, "VFV.TO", "buy",  date(2024, 1, 22), qty=30, price=110.00, fees=4.99, currency="CAD")
tx(tfsa, "SHOP.TO","buy",  date(2024, 6, 3),  qty=25, price=95.00,  fees=4.99, currency="CAD")
tx(rrsp, "ENB.TO", "buy",  date(2024, 2, 8),  qty=80, price=46.20,  fees=4.99, currency="CAD")
tx(rrsp, "ENB.TO", "dividend", date(2024, 6, 1), price=73.60, notes="quarterly")
tx(rrsp, "ENB.TO", "dividend", date(2024, 9, 1), price=73.60, notes="quarterly")
tx(rrsp, "ENB.TO", "dividend", date(2024, 12,1), price=73.60, notes="quarterly")
tx(evolve, "BTC-USD", "buy", date(2024, 3, 15), qty=0.05, price=68000, fees=10, fx=1.35, currency="USD")

db.commit()
print("Seed complete:",
      db.query(models.Account).count(), "accounts,",
      db.query(models.Instrument).count(), "instruments,",
      db.query(models.Transaction).count(), "transactions.")
db.close()
