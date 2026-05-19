"use client";
import useSWR from "swr";
import { useState } from "react";
import { api, fetcher, fmtMoney } from "@/lib/api";

const TX_TYPES = ["buy", "sell", "dividend", "interest", "deposit", "withdrawal", "fee", "transfer_in", "transfer_out"];

export default function Transactions() {
  const { data: txs, mutate } = useSWR<any[]>("/api/transactions", fetcher);
  const { data: accts } = useSWR<any[]>("/api/accounts", fetcher);

  const [form, setForm] = useState<any>({
    account_id: "", ticker: "", date: new Date().toISOString().slice(0, 10),
    type: "buy", quantity: 0, price: 0, fees: 0, currency: "CAD", fx_rate: 1, notes: "",
  });

  async function submit(e: any) {
    e.preventDefault();
    const body = { ...form, account_id: Number(form.account_id), quantity: Number(form.quantity),
                   price: Number(form.price), fees: Number(form.fees), fx_rate: Number(form.fx_rate) };
    await api("/api/transactions", { method: "POST", body: JSON.stringify(body) });
    setForm({ ...form, quantity: 0, price: 0, fees: 0, notes: "" });
    mutate();
  }

  async function del(id: number) {
    if (!confirm("Delete transaction?")) return;
    await api(`/api/transactions/${id}`, { method: "DELETE" });
    mutate();
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="card grid grid-cols-2 md:grid-cols-6 gap-3">
        <div>
          <label>Account</label>
          <select value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })} required>
            <option value="">—</option>
            {accts?.map((a: any) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </div>
        <div>
          <label>Type</label>
          <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {TX_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label>Date</label>
          <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
        </div>
        <div>
          <label>Ticker (for buy/sell/div)</label>
          <input value={form.ticker} onChange={(e) => setForm({ ...form, ticker: e.target.value.toUpperCase() })} placeholder="AAPL" />
        </div>
        <div>
          <label>Quantity</label>
          <input type="number" step="any" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
        </div>
        <div>
          <label>Price (per unit, or total for cash flows)</label>
          <input type="number" step="any" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })} />
        </div>
        <div>
          <label>Fees</label>
          <input type="number" step="any" value={form.fees} onChange={(e) => setForm({ ...form, fees: e.target.value })} />
        </div>
        <div>
          <label>Currency</label>
          <input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} />
        </div>
        <div>
          <label>FX → account ccy</label>
          <input type="number" step="any" value={form.fx_rate} onChange={(e) => setForm({ ...form, fx_rate: e.target.value })} />
        </div>
        <div className="md:col-span-2">
          <label>Notes</label>
          <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="flex items-end">
          <button className="btn btn-primary w-full" type="submit">Add transaction</button>
        </div>
      </form>

      <div className="card overflow-x-auto">
        <table className="tbl">
          <thead><tr>
            <th>Date</th><th>Type</th><th>Account</th><th>Ticker</th>
            <th className="text-right">Qty</th><th className="text-right">Price</th>
            <th className="text-right">Fees</th><th>Ccy</th><th>FX</th><th>Notes</th><th></th>
          </tr></thead>
          <tbody>
            {txs?.map((t: any) => (
              <tr key={t.id}>
                <td>{t.date}</td>
                <td><span className="text-xs px-1.5 py-0.5 bg-line rounded">{t.type}</span></td>
                <td>{accts?.find((a: any) => a.id === t.account_id)?.name || t.account_id}</td>
                <td>{t.ticker || "—"}</td>
                <td className="text-right font-mono">{t.quantity}</td>
                <td className="text-right font-mono">{fmtMoney(t.price, t.currency)}</td>
                <td className="text-right font-mono">{fmtMoney(t.fees, t.currency)}</td>
                <td>{t.currency}</td>
                <td className="font-mono">{t.fx_rate}</td>
                <td className="text-xs text-muted">{t.notes}</td>
                <td><button className="btn" onClick={() => del(t.id)}>✕</button></td>
              </tr>
            ))}
            {!txs?.length && <tr><td colSpan={11} className="text-center text-muted py-6">No transactions yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
