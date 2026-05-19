"""SQLAlchemy ORM models. Everything flows from the transaction ledger."""
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base


class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)        # "Taxable", "TFSA", "RRSP", "Evolve Simple - main"
    account_type = Column(String, nullable=False)             # taxable | tfsa | rrsp | resp | other
    currency = Column(String, nullable=False, default="CAD")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")


class Instrument(Base):
    __tablename__ = "instruments"
    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, unique=True)
    name = Column(String, default="")
    asset_type = Column(String, default="stock")              # stock | etf | bond | crypto | cash | other
    currency = Column(String, default="USD")
    sector = Column(String, default="")
    country = Column(String, default="")
    tags = Column(String, default="")                         # comma-separated
    thesis = Column(Text, default="")
    target_price = Column(Float, nullable=True)
    stop_price = Column(Float, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    instrument_id = Column(Integer, ForeignKey("instruments.id"), nullable=True)  # null for pure cash flows
    date = Column(Date, nullable=False)
    # buy | sell | dividend | interest | deposit | withdrawal | fee | transfer_in | transfer_out
    type = Column(String, nullable=False)
    quantity = Column(Float, default=0.0)
    price = Column(Float, default=0.0)
    fees = Column(Float, default=0.0)
    currency = Column(String, default="CAD")
    fx_rate = Column(Float, default=1.0)                      # rate to account currency
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    account = relationship("Account", back_populates="transactions")
    instrument = relationship("Instrument")


class PriceCache(Base):
    """Cached quote snapshots so we don't hammer yfinance."""
    __tablename__ = "price_cache"
    ticker = Column(String, primary_key=True)
    last_price = Column(Float, default=0.0)
    previous_close = Column(Float, default=0.0)
    week52_high = Column(Float, default=0.0)
    week52_low = Column(Float, default=0.0)
    dividend_yield = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    fetched_at = Column(DateTime, default=datetime.utcnow)


class PortfolioValuePoint(Base):
    """Historical portfolio value snapshots for charts."""
    __tablename__ = "portfolio_value"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False, index=True)
    total_value = Column(Float, default=0.0)
    cash_value = Column(Float, default=0.0)
