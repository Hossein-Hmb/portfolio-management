"""Import a broker holdings CSV into the local portfolio ledger.

This script turns each current position in a holdings report into a snapshot
buy transaction, creates or updates matching accounts and instruments, and pins
the report's market prices in the quote cache so the holdings page can render
immediately from `/api/holdings`.
"""
from __future__ import annotations

import argparse
import csv
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app import models
from app.db import Base, SessionLocal, engine


IMPORT_NOTE_PREFIX = "holdings-report import"
NET_DEPOSIT_NOTE_PREFIX = "net deposit snapshot"
PINNED_QUOTE_AT = datetime(2099, 1, 1)


ASSET_TYPES = {
    "CRYPTOCURRENCY": "crypto",
    "EQUITY": "stock",
    "EXCHANGE_TRADED_FUND": "etf",
    "PRECIOUS_METAL": "precious_metal",
}

ACCOUNT_TYPES = {
    "crypto": "crypto",
    "fhsa": "fhsa",
    "non-registered": "taxable",
    "tfsa": "tfsa",
}


def money(row: dict[str, str], key: str) -> Decimal:
    raw = (row.get(key) or "0").strip()
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value for {key}: {raw!r}") from exc


def text(row: dict[str, str], key: str) -> str:
    return (row.get(key) or "").strip()


def parse_report(path: Path) -> tuple[date, list[dict[str, str]]]:
    content = path.read_text(encoding="utf-8-sig")
    report_date = date.today()
    match = re.search(r"As of (\d{4}-\d{2}-\d{2})", content)
    if match:
        report_date = date.fromisoformat(match.group(1))

    rows = []
    for row in csv.DictReader(content.splitlines()):
        if text(row, "Symbol"):
            rows.append(row)
    return report_date, rows


def account_type_for(row: dict[str, str]) -> str:
    name = text(row, "Account Type").lower()
    return ACCOUNT_TYPES.get(name, name.replace(" ", "_") or "other")


def asset_type_for(row: dict[str, str]) -> str:
    raw = text(row, "Security Type").upper()
    return ASSET_TYPES.get(raw, raw.lower() or "other")


def upsert_account(db, row: dict[str, str]) -> models.Account:
    name = text(row, "Account Name")
    account = db.query(models.Account).filter_by(name=name).first()
    notes = f"Account number: {text(row, 'Account Number')}"
    if account is None:
        account = models.Account(
            name=name,
            account_type=account_type_for(row),
            currency="CAD",
            notes=notes,
        )
        db.add(account)
    else:
        account.account_type = account_type_for(row)
        account.currency = "CAD"
        account.notes = notes
    db.flush()
    return account


def upsert_instrument(db, row: dict[str, str]) -> models.Instrument:
    ticker = text(row, "Symbol").upper()
    instrument = db.query(models.Instrument).filter_by(ticker=ticker).first()
    tags = ", ".join(part for part in [text(row, "Exchange"), text(row, "MIC")] if part)
    if instrument is None:
        instrument = models.Instrument(ticker=ticker)
        db.add(instrument)

    instrument.name = text(row, "Name") or ticker
    instrument.asset_type = asset_type_for(row)
    instrument.currency = "CAD"
    instrument.tags = tags
    db.flush()
    return instrument


def book_fx_to_cad(row: dict[str, str]) -> Decimal:
    book_value_market = money(row, "Book Value (Market)")
    if not book_value_market:
        return Decimal("1")
    return money(row, "Book Value (CAD)") / book_value_market


def market_value_cad(row: dict[str, str]) -> Decimal:
    return money(row, "Market Value") * book_fx_to_cad(row)


def pin_quote(db, row: dict[str, str], last_price: Decimal) -> None:
    ticker = text(row, "Symbol").upper()
    last_price_float = float(last_price)
    quote = db.query(models.PriceCache).filter_by(ticker=ticker).first()
    if quote is None:
        quote = models.PriceCache(ticker=ticker)
        db.add(quote)

    quote.last_price = last_price_float
    quote.previous_close = last_price_float
    quote.week52_high = last_price_float
    quote.week52_low = last_price_float
    quote.dividend_yield = 0.0
    quote.currency = "CAD"
    quote.fetched_at = PINNED_QUOTE_AT


def clear_prior_import(db, replace_all: bool) -> None:
    if replace_all:
        db.query(models.Transaction).delete()
        db.query(models.PriceCache).delete()
        db.query(models.Instrument).delete()
        db.query(models.Account).delete()
        return

    db.query(models.Transaction).filter(
        models.Transaction.notes.like(f"{IMPORT_NOTE_PREFIX}%")
    ).delete(synchronize_session=False)
    db.query(models.Transaction).filter(
        models.Transaction.notes.like(f"{NET_DEPOSIT_NOTE_PREFIX}%")
    ).delete(synchronize_session=False)


def add_net_deposit_snapshot(
    db,
    report_date: date,
    amount: Decimal | None,
    deposit_date: date | None,
) -> None:
    if amount is None:
        return
    account = db.query(models.Account).filter_by(name="Portfolio").first()
    if account is None:
        account = models.Account(
            name="Portfolio",
            account_type="summary",
            currency="CAD",
            notes="Synthetic account for portfolio-level metrics.",
        )
        db.add(account)
        db.flush()

    as_of = deposit_date or report_date
    db.add(
        models.Transaction(
            account_id=account.id,
            instrument_id=None,
            date=as_of,
            type="deposit",
            quantity=0.0,
            price=float(amount),
            fees=0.0,
            currency="CAD",
            fx_rate=1.0,
            notes=f"{NET_DEPOSIT_NOTE_PREFIX} as of {as_of.isoformat()}",
        )
    )


def import_report(
    path: Path,
    replace_all: bool,
    total_value_cad: Decimal | None = None,
    net_deposit_cad: Decimal | None = None,
    net_deposit_date: date | None = None,
) -> tuple[int, int]:
    Base.metadata.create_all(bind=engine)
    report_date, rows = parse_report(path)
    derived_total_cad = sum(market_value_cad(row) for row in rows)
    market_value_scale = (
        total_value_cad / derived_total_cad
        if total_value_cad is not None and derived_total_cad
        else Decimal("1")
    )
    market_value_by_ticker: dict[str, Decimal] = {}
    quantity_by_ticker: dict[str, Decimal] = {}
    for row in rows:
        ticker = text(row, "Symbol").upper()
        market_value_by_ticker[ticker] = (
            market_value_by_ticker.get(ticker, Decimal("0"))
            + market_value_cad(row) * market_value_scale
        )
        quantity_by_ticker[ticker] = quantity_by_ticker.get(ticker, Decimal("0")) + money(row, "Quantity")
    quote_price_by_ticker = {
        ticker: market_value_by_ticker[ticker] / quantity
        for ticker, quantity in quantity_by_ticker.items()
        if quantity
    }
    db = SessionLocal()
    try:
        clear_prior_import(db, replace_all)
        note = f"{IMPORT_NOTE_PREFIX} {report_date.isoformat()}"
        for row in rows:
            quantity = money(row, "Quantity")
            if quantity <= 0:
                continue

            avg_cost = money(row, "Book Value (CAD)") / quantity
            account = upsert_account(db, row)
            instrument = upsert_instrument(db, row)
            db.add(
                models.Transaction(
                    account_id=account.id,
                    instrument_id=instrument.id,
                    date=report_date,
                    type="buy",
                    quantity=float(quantity),
                    price=float(avg_cost),
                    fees=0.0,
                    currency="CAD",
                    fx_rate=1.0,
                    notes=note,
                )
            )
            pin_quote(db, row, quote_price_by_ticker[text(row, "Symbol").upper()])

        add_net_deposit_snapshot(db, report_date, net_deposit_cad, net_deposit_date)

        db.commit()
        return len(rows), db.query(models.Transaction).filter_by(notes=note).count()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import holdings CSV into the portfolio ledger.")
    parser.add_argument("csv_path", type=Path, help="Path to the holdings CSV report.")
    parser.add_argument(
        "--replace-all",
        action="store_true",
        help="Clear existing accounts, instruments, transactions, and quote cache before importing.",
    )
    parser.add_argument(
        "--total-value-cad",
        type=Decimal,
        help="Portfolio total in CAD to reconcile the imported market values to.",
    )
    parser.add_argument(
        "--net-deposit-cad",
        type=Decimal,
        help="Portfolio net deposits in CAD for dashboard return metrics.",
    )
    parser.add_argument(
        "--net-deposit-date",
        type=date.fromisoformat,
        help="As-of date for the net deposit figure, formatted as YYYY-MM-DD.",
    )
    args = parser.parse_args()

    rows, transactions = import_report(
        args.csv_path,
        args.replace_all,
        total_value_cad=args.total_value_cad,
        net_deposit_cad=args.net_deposit_cad,
        net_deposit_date=args.net_deposit_date,
    )
    print(f"Imported {transactions} snapshot transactions from {rows} report rows.")


if __name__ == "__main__":
    main()
