"use client";
import useSWR from "swr";
import { useState } from "react";
import { api, fetcher } from "@/lib/api";

export default function Accounts() {
  const { data, mutate } = useSWR<any[]>("/api/accounts", fetcher);
  const [form, setForm] = useState({ name: "", account_type: "taxable", currency: "CAD", notes: "" });

  async function submit(e: any) {
    e.preventDefault();
    await api("/api/accounts", { method: "POST", body: JSON.stringify(form) });
    setForm({ name: "", account_type: "taxable", currency: "CAD", notes: "" });
    mutate();
  }

  async function del(id: number) {
    if (!confirm("Delete account and all its transactions?")) return;
    await api(`/api/accounts/${id}`, { method: "DELETE" });
    mutate();
  }

  return (
    <div className="space-y-6">
      <form onSubmit={submit} className="card grid grid-cols-2 md:grid-cols-5 gap-3">
        <div><label>Name</label><input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
        <div>
          <label>Type</label>
          <select value={form.account_type} onChange={(e) => setForm({ ...form, account_type: e.target.value })}>
            {["taxable", "tfsa", "rrsp", "resp", "other"].map((t) => <option key={t}>{t}</option>)}
          </select>
        </div>
        <div><label>Currency</label><input value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} /></div>
        <div className="md:col-span-2"><label>Notes</label><input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
        <div className="flex items-end col-span-2 md:col-span-5">
          <button className="btn btn-primary" type="submit">Add account</button>
        </div>
      </form>

      <div className="card">
        <table className="tbl">
          <thead><tr><th>Name</th><th>Type</th><th>Currency</th><th>Notes</th><th></th></tr></thead>
          <tbody>
            {data?.map((a: any) => (
              <tr key={a.id}>
                <td>{a.name}</td><td>{a.account_type}</td><td>{a.currency}</td>
                <td className="text-muted text-xs">{a.notes}</td>
                <td><button className="btn" onClick={() => del(a.id)}>Delete</button></td>
              </tr>
            ))}
            {!data?.length && <tr><td colSpan={5} className="text-center text-muted py-6">No accounts yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
