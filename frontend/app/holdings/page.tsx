"use client";
import useSWR from "swr";
import Link from "next/link";
import { useState, useMemo } from "react";
import { api, fetcher, fmtMoney, fmtPct, cls } from "@/lib/api";

export default function Holdings() {
  const { data, error, isLoading, mutate } = useSWR<any[]>("/api/holdings", fetcher);
  const { data: accts } = useSWR<any[]>("/api/accounts", fetcher);
  const [q, setQ] = useState("");
  const [tag, setTag] = useState("");

  const [form, setForm] = useState<any>({
    account_id: "", ticker: "", quantity: "", avg_cost: "", currency: "CAD",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function addHolding(e: any) {
    e.preventDefault();
    setErr(null);
    if (!form.account_id || !form.ticker || !form.quantity || !form.avg_cost) {
      setErr("Account, ticker, shares, and average cost are required.");
      return;
    }
    setSaving(true);
    try {
      await api("/api/transactions", {
        method: "POST",
        body: JSON.stringify({
          account_id: Number(form.account_id),
          ticker: form.ticker.toUpperCase(),
          date: new Date().toISOString().slice(0, 10),
          type: "buy",
          quantity: Number(form.quantity),
          price: Number(form.avg_cost),
          fees: 0,
          currency: form.currency,
          fx_rate: 1,
          notes: "snapshot",
        }),
      });
      setForm({ ...form, ticker: "", quantity: "", avg_cost: "" });
      mutate();
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setSaving(false);
    }
  }

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
      <form onSubmit={addHolding} className="card grid grid-cols-2 md:grid-cols-6 gap-3">
        <div className="md:col-span-6">
          <div className="font-medium">Add a holding</div>
          <div className="text-xs text-muted">Enter what you currently own — shares and your average cost. We&apos;ll record it as a buy dated today.</div>
        </div>
        <div>
          <label>Account</label>
          <select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} required>
            <option value="">—</option>
            {accts?.map((a: any) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div>
          <label>Ticker</label>
          <input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })} placeholder="AAPL" />
        </div>
        <div>
          <label>Shares</label>
          <input type="number" step="any" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} placeholder="10" />
        </div>
        <div>
          <label>Average cost / share</label>
          <input type="number" step="any" value={form.avg_cost} onChange={(e) => setForm({ ...form, avg_cost: e.target.value })} placeholder="185.50" />
        </div>
        <div>
          <label>Currency</label>
          <input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} />
        </div>
        <div className="flex items-end">
          <button className="btn btn-primary w-full" type="submit" disabled={saving}>{saving ? "Saving…" : "Add holding"}</button>
        </div>
        {err && <div className="md:col-span-6 neg text-sm">{err}</div>}
      </form>

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
