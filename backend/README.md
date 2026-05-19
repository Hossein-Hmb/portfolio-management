# Portfolio MVP — Backend (FastAPI)

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                     # optional: load sample data
uvicorn app.main:app --reload --port 8000
```

API will be at `http://localhost:8000` and OpenAPI docs at `http://localhost:8000/docs`.

## Endpoints (quick reference)

- `GET  /api/health`
- `GET/POST /api/accounts`, `DELETE /api/accounts/{id}`
- `GET/POST /api/instruments`, `PATCH /api/instruments/{id}`
- `GET/POST /api/transactions?account_id=&ticker=`, `DELETE /api/transactions/{id}`
- `GET  /api/holdings`
- `GET  /api/summary`               — dashboard payload (allocations, P/L, winners/losers)
- `GET  /api/performance`           — TWR (1M/3M/YTD/1Y/ALL), XIRR, vol, max DD, Sharpe + equity curve
- `GET  /api/positions/{ticker}`    — security detail view
- `GET  /api/quotes/{ticker}?force=true`
- `POST /api/quotes/refresh`

## Cash flow convention

For cash-only events (`deposit`, `withdrawal`, `dividend`, `interest`, `fee`, `transfer_in`, `transfer_out`) store the **total amount in the `price` field**. For `buy`/`sell`, use `quantity` and `price` per unit normally.

## Notes

- Average-cost basis. Realized P/L is computed on sells.
- Quote cache is 15 minutes; `force=true` bypasses it.
- For the equity curve, MVP applies today's last price across historical days. Swap in true historical bars later.
