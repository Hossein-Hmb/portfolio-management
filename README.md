# Portfolio Management — MVP

A personal portfolio dashboard built around a proper **transaction ledger**: every holding, P/L, allocation, and performance metric is derived from the trades you log. Designed to be hacked on.

## Stack

- **Backend:** FastAPI · SQLAlchemy · SQLite · yfinance (15-min cached quotes) · scipy (XIRR)
- **Frontend:** Next.js 14 (App Router) · TypeScript · Tailwind · Recharts · SWR

## What's in the MVP

| Area | Status |
| --- | --- |
| Multiple accounts (Taxable, TFSA, RRSP, Evolve Simple, …) | ✅ |
| Instrument-agnostic holdings (stock / ETF / bond / crypto / cash) | ✅ |
| Transaction ledger (buy, sell, dividend, interest, deposit, withdrawal, fee, transfers) | ✅ |
| Average-cost basis, unrealized + realized P/L | ✅ |
| Live quotes via yfinance (15-min cache, manual refresh button) | ✅ |
| Dashboard: net worth, day change, allocation pies (asset / sector / account) | ✅ |
| Top positions / winners / losers | ✅ |
| Position detail: per-account split, edit sector/country/tags/thesis/target/stop, full tx history | ✅ |
| Performance: TWR (1M/3M/YTD/1Y/ALL), XIRR, volatility, max drawdown, Sharpe | ✅ |
| Tags as first-class filter on holdings | ✅ |
| Sample seed data so you can click around immediately | ✅ |

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                       # optional: load sample data
uvicorn app.main:app --reload --port 8000
```

OpenAPI docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App at `http://localhost:3000`. The dev server proxies `/api/*` to the backend.

## Project layout

```
portfolio-management/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI routes
│   │   ├── models.py          # SQLAlchemy ORM
│   │   ├── schemas.py         # Pydantic I/O
│   │   ├── db.py              # engine + session
│   │   ├── quotes.py          # yfinance + cache
│   │   └── analytics.py       # holdings, P/L, TWR, XIRR, drawdown, Sharpe
│   ├── seed.py
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── app/
│   │   ├── page.tsx                       # Dashboard
│   │   ├── holdings/page.tsx
│   │   ├── transactions/page.tsx
│   │   ├── accounts/page.tsx
│   │   ├── performance/page.tsx
│   │   └── positions/[ticker]/page.tsx    # Security detail
│   ├── components/                        # Kpi, Allocations, EquityCurve
│   ├── lib/api.ts
│   ├── tailwind.config.ts
│   └── next.config.mjs                    # /api/* → :8000
└── README.md
```

## Data model

Everything flows from `transactions`:

- `accounts` — name, type (taxable/tfsa/rrsp/…), currency
- `instruments` — ticker, name, asset_type, currency, sector, country, tags, thesis, target/stop
- `transactions` — `account_id`, optional `instrument_id`, `date`, `type`, `quantity`, `price`, `fees`, `currency`, `fx_rate`, `notes`
- `price_cache` — yfinance snapshot (15-min TTL)

For cash-only events (deposit/withdrawal/dividend/interest/fee/transfer), store the **total amount in the `price` column**; leave `quantity` at 0.

## Roadmap ideas (next obvious bumps)

- Historical bars (yfinance `history`) for a true equity curve and time-weighted attribution
- CSV import for Evolve Simple / Wealthsimple / IBKR
- Benchmark comparison (VT, S&P 500, TSX)
- Custom dashboards & saved filter screens
- Forward dividend income projection
- Mobile read-only view
- Auth + encrypted storage for any future API keys

## License

MIT — see `LICENSE`.
