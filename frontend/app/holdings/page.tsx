"use client";
import useSWR from "swr";
import Link from "next/link";
import { useState, useMemo } from "react";
import { fetcher, fmtMoney, fmtPct, cls } from "@/lib/api";

export default function Holdings() {
  const { data, error, isLoading, mutate } = useSWR<any[]>("/api/holdings", fetcher);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");

  const rows = useMemo(() => {
    if (!data) return [];
    return data.filter((h) =>
      (!q || h.ticker.toLowerCase().includes(q.toLowerCase()) || (h.name || "").toLowerCase().includes(q.toLowerCase())) &&
      (!tag || (h.tags || "").toLowerCase().includes(tag.toLowerCase()))
    );
  }, [data, q, tag]);

  const refresh = async () => {
    await fetch("/api/quotes/refresh", { method: "POST" });
    mutate();
  };

  if (error) return <div className="card neg">Failed: {String(error)}</div>;
  if (isLoading) return <div className="text-muted">Loading…</div>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="w-60">
          <label>Search</label>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ticker or name" />
        </div>
        <div className="w-40">
          <label>Tag</label>
          <input value={tag} onChange={(e) => setTag(e.target.value)} placeholder="e.g. long-term" />
        </div>
        <button className="btn" onClick={refresh}>↻ Refresh quotes</button>
      </div>

      <div className="card overflow-x-auto">
        <table className="tbl">
          <thead>
            <tr>
              <th>Ticker</th><th>Account</th><th>Type</th>
              <th className="text-right">Units</th>
              <th className="text-right">Avg cost</th>
              <th className="text-right">Last</th>
              <th className="text-right">Mkt value</th>
              <th className="text-right">Unrl P/L</th>
              <th className="text-right">Realized</th>
              <th className="text-right">Weight</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((h: any) => (
              <tr key={`${h.ticker}-${h.account_id}`}>
                <td>
                  <Link href={`/positions/${encodeURIComponent(h.ticker)}`} className="hover:underline">
                    {h.ticker}
                  </Link>
                  <div className="text-xs text-muted">{h.name}</div>
                </td>
                <td>{h.account_name}</td>
                <td className="text-xs text-muted">{h.asset_type}</td>
                <td className="text-right font-mono">{h.units}</td>
                <td className="text-right font-mono">{fmtMoney(h.avg_cost, h.currency)}</td>
                <td className="text-right font-mono">{fmtMoney(h.last_price, h.currency)}</td>
                <td className="text-right font-mono">{fmtMoney(h.market_value, h.currency)}</td>
                <td className={`text-right font-mono ${cls(h.unrealized_pl)}`}>
                  {fmtMoney(h.unrealized_pl, h.currency)}
                  <div className="text-xs">{fmtPct(h.unrealized_pl_pct)}</div>
                </td>
                <td className={`text-right font-mono ${cls(h.realized_pl || 0)}`}>{fmtMoney(h.realized_pl || 0, h.currency)}</td>
                <td className="text-right">{fmtPct(h.weight)}</td>
                <td className="text-xs text-muted">{h.tags}</td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={11} className="text-center text-muted py-6">No holdings yet — add a transaction.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
