"use client";
import useSWR from "swr";
import Link from "next/link";
import { fetcher, fmtMoney, fmtPct, cls } from "@/lib/api";
import { MoneyKpi } from "@/components/Kpi";
import { AllocationPie } from "@/components/Allocations";
import { EquityCurve } from "@/components/EquityCurve";

export default function Dashboard() {
  const { data: s, error, isLoading } = useSWR<any>("/api/summary", fetcher);
  const { data: perf } = useSWR<any>("/api/performance", fetcher);

  if (error) return <div className="card neg">Failed to load: {String(error)}</div>;
  if (isLoading || !s) return <div className="text-muted">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <MoneyKpi label="Total Value" amount={s.total_value} />
        <MoneyKpi label="Invested" amount={s.invested_value} />
        <MoneyKpi label="Cash" amount={s.cash_value} />
        <MoneyKpi label="Unrealized P/L" amount={s.unrealized_pl} pct={s.unrealized_pl_pct} />
        <MoneyKpi label="Day Change" amount={s.day_change} pct={s.day_change_pct} />
      </div>

      {perf?.series?.length > 0 && <EquityCurve data={perf.series} />}

      {perf && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          {Object.entries(perf.twr).map(([k, v]: any) => (
            <div key={k} className="card">
              <div className="kpi-label">TWR {k}</div>
              <div className={`kpi-value ${cls(v)}`}>{fmtPct(v)}</div>
            </div>
          ))}
          <div className="card">
            <div className="kpi-label">XIRR</div>
            <div className={`kpi-value ${cls(perf.xirr)}`}>{fmtPct(perf.xirr)}</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <AllocationPie title="By Asset Type" data={s.by_asset_type} />
        <AllocationPie title="By Sector" data={s.by_sector} />
        <AllocationPie title="By Account" data={s.by_account} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <PositionsTable title="Top Positions" rows={s.top_positions} />
        <PositionsTable title="Top Winners" rows={s.top_winners} />
        <PositionsTable title="Top Losers" rows={s.top_losers} />
      </div>
    </div>
  );
}

function PositionsTable({ title, rows }: { title: string; rows: any[] }) {
  return (
    <div className="card">
      <div className="text-sm text-muted mb-2">{title}</div>
      <table className="tbl">
        <thead><tr><th>Ticker</th><th className="text-right">MV</th><th className="text-right">P/L</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.ticker}-${r.account_id}`}>
              <td>
                <Link href={`/positions/${encodeURIComponent(r.ticker)}`} className="hover:underline">
                  {r.ticker}
                </Link>
                <div className="text-xs text-muted">{r.account_name}</div>
              </td>
              <td className="text-right">{fmtMoney(r.market_value)}</td>
              <td className={`text-right ${cls(r.unrealized_pl)}`}>
                {fmtMoney(r.unrealized_pl)}
                <div className="text-xs">{fmtPct(r.unrealized_pl_pct)}</div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
