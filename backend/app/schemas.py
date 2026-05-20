"""Pydantic schemas for API I/O."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime


class AccountIn(BaseModel):
    name: str
    account_type: str = "taxable"
    currency: str = "CAD"
    notes: str = ""


class AccountOut(AccountIn):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True


class InstrumentIn(BaseModel):
    ticker: str
    name: str = ""
    asset_type: str = "stock"
    currency: str = "USD"
    sector: str = ""
    country: str = ""
    tags: str = ""
    thesis: str = ""
    target_price: Optional[float] = None
    stop_price: Optional[float] = None


class InstrumentOut(InstrumentIn):
    id: int
    class Config:
        from_attributes = True


class TransactionIn(BaseModel):
    account_id: int
    ticker: Optional[str] = None         # convenience: looked up / created
    date: date
    type: str                            # buy/sell/dividend/...
    quantity: float = 0.0
    price: float = 0.0
    fees: float = 0.0
    currency: str = "CAD"
    fx_rate: float = 1.0
    notes: str = ""


class TransactionOut(BaseModel):
    id: int
    account_id: int
    instrument_id: Optional[int]
    ticker: Optional[str] = None
    date: date
    type: str
    quantity: float
    price: float
    fees: float
    currency: str
    fx_rate: float
    notes: str
    class Config:
        from_attributes = True


class HoldingOut(BaseModel):
    ticker: str
    name: str
    asset_type: str
    sector: str
    country: str
    currency: str
    account_id: int
    account_name: str
    units: float
    avg_cost: float
    cost_basis: float
    last_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float
    weight: float
    tags: str


class AllocationSlice(BaseModel):
    label: str
    value: float
    pct: float


class PortfolioSummary(BaseModel):
    total_value: float
    cash_value: float
    invested_value: float
    total_cost_basis: float
    unrealized_pl: float
    unrealized_pl_pct: float
    realized_pl: float
    net_deposits: float
    total_return: float
    total_return_pct: float
    day_change: float
    day_change_pct: float
    by_asset_type: List[AllocationSlice]
    by_sector: List[AllocationSlice]
    by_currency: List[AllocationSlice]
    by_account: List[AllocationSlice]
    top_positions: List[HoldingOut]
    top_winners: List[HoldingOut]
    top_losers: List[HoldingOut]


class TimeSeriesPoint(BaseModel):
    date: date
    value: float


class PerformanceOut(BaseModel):
    twr: dict        # {"1M": 0.03, "3M": ..., "YTD": ..., "1Y": ..., "ALL": ...}
    xirr: float
    volatility: float
    max_drawdown: float
    sharpe: float
    series: List[TimeSeriesPoint]


# ---------- Trade analysis (rules engine) ----------

class TradeProposalIn(BaseModel):
    ticker: str
    action: str = Field(description="buy or sell")
    instrument: str = Field(description="stock | call | put")
    quantity: float
    total_capital: float
    strike: Optional[float] = None
    expiry: Optional[date] = None
    premium: Optional[float] = None
    edge_thesis: str = ""
    profit_target: Optional[float] = None
    stop_loss: Optional[float] = None
    win_probability: Optional[float] = None
    expected_profit: Optional[float] = None
    expected_loss: Optional[float] = None


class ProposalDecisionIn(BaseModel):
    decision: Optional[str] = None          # entered | skipped | pending
    outcome: Optional[str] = None           # win | loss | breakeven | open
    realized_pl: Optional[float] = None
    notes: Optional[str] = None


class ProposalOut(BaseModel):
    id: int
    created_at: datetime
    ticker: str
    action: str
    instrument: str
    quantity: float
    total_capital: float
    strike: Optional[float]
    expiry: Optional[date]
    premium: Optional[float]
    edge_thesis: str
    profit_target: Optional[float]
    stop_loss: Optional[float]
    win_probability: Optional[float]
    expected_profit: Optional[float]
    expected_loss: Optional[float]
    recommendation: str
    score: float
    decision: str
    outcome: str
    realized_pl: Optional[float]
    notes: str

    class Config:
        from_attributes = True
