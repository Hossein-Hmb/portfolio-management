# Portfolio MVP — Frontend (Next.js 14, App Router)

## Setup

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000`. The dev server proxies `/api/*` to `http://localhost:8000` (your FastAPI backend).

## Pages

- `/`              — Dashboard (KPIs, equity curve, allocations, top winners/losers)
- `/holdings`      — All positions, filterable by tag/search
- `/transactions`  — Add/list/delete transactions
- `/accounts`      — Create accounts (Taxable, TFSA, RRSP, etc.)
- `/performance`   — TWR, XIRR, volatility, drawdown, Sharpe, equity curve
- `/positions/[ticker]` — Security detail: position by account, transaction log, edit metadata (sector, tags, thesis, target/stop)

## Stack

- Next.js 14 (App Router) + TypeScript
- Tailwind CSS (dark theme baked in)
- Recharts (pie + line)
- SWR for data fetching
