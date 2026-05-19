"use client";
import useSWR from "swr";
import { fetcher, fmtPct, cls } from "@/lib/api";
import { EquityCurve } from "@/components/EquityCurve";

export default function Performance() {
  const { data, isLoading } = useSWR<any>("/api/performance", fetcher);
  if (isLoading || !data) return <div className="text-muted">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-7 gap-3">
        {Object.entries(data.twr).map(([k, v]: any) => (
          <div key={k} className="card">
            <div className="kpi-label">TWR {k}</div>
            <div className={`kpi-value ${cls(v)}`}>{fmtPct(v)}</div>
          </div>
        ))}
        <div className="card"><div className="kpi-label">XIRR</div><div className={`kpi-value ${cls(data.xirr)}`}>{fmtPct(data.xirr)}</div></div>
        <div className="card"><div className="kpi-label">Volatility (ann.)</div><div className="kpi-value">{fmtPct(data.volatility)}</div></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="card"><div className="kpi-label">Max Drawdown</div><div className={`kpi-value neg`}>{fmtPct(data.max_drawdown)}</div></div>
        <div className="card"><div className="kpi-label">Sharpe (rf=0)</div><div className="kpi-value">{data.sharpe}</div></div>
        <div className="card"><div className="kpi-label">Days observed</div><div className="kpi-value">{data.series.length}</div></div>
      </div>
      <EquityCurve data={data.series} />
    </div>
  );
}
