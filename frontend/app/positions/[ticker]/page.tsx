"use client";
import useSWR from "swr";
import { useParams } from "next/navigation";
import { fetcher, fmtMoney, fmtPct, cls, api } from "@/lib/api";
import { useState, useEffect } from "react";

export default function PositionDetail() {
  const { ticker } = useParams<{ ticker: string }>();
  const t = decodeURIComponent(ticker);
  const { data, mutate, isLoading } = useSWR<any>(`/api/positions/${t}`, fetcher);
  const [inst, setInst] = useState<any>(null);

  useEffect(() => { if (data?.instrument) setInst(data.instrument); }, [data]);

  async function saveMeta() {
    await api(`/api/instruments/${inst.id}`, { method: "PATCH", body: JSON.stringify(inst) });
    mutate();
  }

  if (isLoading || !data) return <div className="text-muted">Loading…</div>;
  const totalUnits = data.holdings.reduce((s: number, h: any) => s + h.units, 0);
  const totalMV = data.holdings.reduce((s: number, h: any) => s + h.market_value, 0);
  const totalPL = data.holdings.reduce((s: number, h: any) => s + h.unrealized_pl, 0);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <div className="text-3xl font-semibold">{data.instrument.ticker}</div>
          <div className="text-muted">{data.instrument.name}</div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="card"><div className="kpi-label">Last</div><div className="kpi-value">{fmtMoney(data.quote.last_price, data.instrument.currency)}</div></div>
          <div className="card"><div className="kpi-label">Prev close</div><div className="kpi-value">{fmtMoney(data.quote.previous_close, data.instrument.currency)}</div></div>
          <div className="card"><div className="kpi-label">52w High</div><div className="kpi-value">{fmtMoney(data.quote.week52_high, data.instrument.currency)}</div></div>
          <div className="card"><div className="kpi-label">52w Low</div><div className="kpi-value">{fmtMoney(data.quote.week52_low, data.instrument.currency)}</div></div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="card"><div className="kpi-label">Total units</div><div className="kpi-value font-mono">{totalUnits}</div></div>
        <div className="card"><div className="kpi-label">Market value</div><div className="kpi-value">{fmtMoney(totalMV, data.instrument.currency)}</div></div>
        <div className="card"><div className="kpi-label">Unrealized P/L</div><div className={`kpi-value ${cls(totalPL)}`}>{fmtMoney(totalPL, data.instrument.currency)}</div></div>
        <div className="card"><div className="kpi-label">Dividend yield</div><div className="kpi-value">{fmtPct((data.quote.dividend_yield || 0) * 100)}</div></div>
      </div>

      <div className="card overflow-x-auto">
        <div className="text-sm text-muted mb-2">Position by account</div>
        <table className="tbl">
          <thead><tr><th>Account</th><th className="text-right">Units</th><th className="text-right">Avg cost</th><th className="text-right">MV</th><th className="text-right">P/L</th></tr></thead>
          <tbody>
            {data.holdings.map((h: any) => (
              <tr key={h.account_id}>
                <td>{h.account_name}</td>
                <td className="text-right font-mono">{h.units}</td>
                <td className="text-right font-mono">{fmtMoney(h.avg_cost, h.currency)}</td>
                <td className="text-right font-mono">{fmtMoney(h.market_value, h.currency)}</td>
                <td className={`text-right font-mono ${cls(h.unrealized_pl)}`}>{fmtMoney(h.unrealized_pl, h.currency)} <span className="text-xs">({fmtPct(h.unrealized_pl_pct)})</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {inst && (
        <div className="card grid grid-cols-2 md:grid-cols-4 gap-3">
          <div><label>Sector</label><input value={inst.sector || ""} onChange={(e) => setInst({ ...inst, sector: e.target.value })} /></div>
          <div><label>Country</label><input value={inst.country || ""} onChange={(e) => setInst({ ...inst, country: e.target.value })} /></div>
          <div><label>Asset type</label>
            <select value={inst.asset_type} onChange={(e) => setInst({ ...inst, asset_type: e.target.value })}>
              {["stock","etf","bond","crypto","cash","other"].map((x) => <option key={x}>{x}</option>)}
            </select>
          </div>
          <div><label>Tags (comma)</label><input value={inst.tags || ""} onChange={(e) => setInst({ ...inst, tags: e.target.value })} /></div>
          <div><label>Target price</label><input type="number" step="any" value={inst.target_price ?? ""} onChange={(e) => setInst({ ...inst, target_price: e.target.value ? Number(e.target.value) : null })} /></div>
          <div><label>Stop price</label><input type="number" step="any" value={inst.stop_price ?? ""} onChange={(e) => setInst({ ...inst, stop_price: e.target.value ? Number(e.target.value) : null })} /></div>
          <div className="md:col-span-4"><label>Thesis</label><textarea rows={3} value={inst.thesis || ""} onChange={(e) => setInst({ ...inst, thesis: e.target.value })} /></div>
          <div className="md:col-span-4"><button className="btn btn-primary" onClick={saveMeta}>Save</button></div>
        </div>
      )}

      <div className="card overflow-x-auto">
        <div className="text-sm text-muted mb-2">Transactions</div>
        <table className="tbl">
          <thead><tr><th>Date</th><th>Type</th><th className="text-right">Qty</th><th className="text-right">Price</th><th className="text-right">Fees</th><th>Notes</th></tr></thead>
          <tbody>
            {data.transactions.map((t: any) => (
              <tr key={t.id}>
                <td>{t.date}</td>
                <td><span className="text-xs px-1.5 py-0.5 bg-line rounded">{t.type}</span></td>
                <td className="text-right font-mono">{t.quantity}</td>
                <td className="text-right font-mono">{fmtMoney(t.price, t.currency)}</td>
                <td className="text-right font-mono">{fmtMoney(t.fees, t.currency)}</td>
                <td className="text-xs text-muted">{t.notes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
