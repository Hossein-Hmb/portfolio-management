"use client";
import useSWR from "swr";
import { useState } from "react";
import Link from "next/link";
import { api, fetcher, fmtMoney } from "@/lib/api";

type RuleResult = {
  rule_id: string;
  title: string;
  status: "pass" | "warn" | "fail" | "info" | "skip";
  message: string;
  math: Record<string, any>;
};

type AnalysisResult = {
  proposal: any;
  context: any;
  rules: RuleResult[];
  score: number;
  recommendation: "ok" | "review" | "do_not_enter";
  saved_proposal_id?: number;
};

const STATUS_STYLE: Record<RuleResult["status"], string> = {
  pass: "border-green-700/60 bg-green-900/15",
  warn: "border-amber-700/60 bg-amber-900/15",
  fail: "border-red-700/60 bg-red-900/15",
  info: "border-line bg-panel",
  skip: "border-line/50 bg-panel/40 opacity-70",
};

const STATUS_DOT: Record<RuleResult["status"], string> = {
  pass: "bg-green-400",
  warn: "bg-amber-400",
  fail: "bg-red-400",
  info: "bg-sky-400",
  skip: "bg-zinc-500",
};

const REC_STYLE: Record<AnalysisResult["recommendation"], { label: string; cls: string }> = {
  ok: { label: "OK to consider", cls: "bg-green-900/30 border-green-700/60 text-green-200" },
  review: { label: "Review carefully", cls: "bg-amber-900/30 border-amber-700/60 text-amber-200" },
  do_not_enter: { label: "Do not enter", cls: "bg-red-900/30 border-red-700/60 text-red-200" },
};

const blankForm = {
  ticker: "",
  action: "buy",
  instrument: "stock",
  quantity: "",
  total_capital: "",
  strike: "",
  expiry: "",
  premium: "",
  edge_thesis: "",
  profit_target: "",
  stop_loss: "",
  win_probability: "",
  expected_profit: "",
  expected_loss: "",
};

function toFloat(v: string): number | null {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export default function AnalyzePage() {
  const [form, setForm] = useState(blankForm);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: proposals, mutate: refetchProposals } = useSWR<any[]>("/api/proposals", fetcher);

  const isOption = form.instrument === "call" || form.instrument === "put";

  function update<K extends keyof typeof form>(k: K, v: string) {
    setForm({ ...form, [k]: v });
  }

  async function submit(e: React.FormEvent, save: boolean) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const body: any = {
        ticker: form.ticker.toUpperCase(),
        action: form.action,
        instrument: form.instrument,
        quantity: toFloat(form.quantity) ?? 0,
        total_capital: toFloat(form.total_capital) ?? 0,
        edge_thesis: form.edge_thesis,
        profit_target: toFloat(form.profit_target),
        stop_loss: toFloat(form.stop_loss),
        win_probability: toFloat(form.win_probability),
        expected_profit: toFloat(form.expected_profit),
        expected_loss: toFloat(form.expected_loss),
      };
      if (isOption) {
        body.strike = toFloat(form.strike);
        body.expiry = form.expiry || null;
        body.premium = toFloat(form.premium);
      }
      const res = await api<AnalysisResult>(
        `/api/analyze-trade${save ? "?save=true" : ""}`,
        { method: "POST", body: JSON.stringify(body) },
      );
      setResult(res);
      if (save) refetchProposals();
    } catch (err: any) {
      setError(String(err.message || err));
    } finally {
      setLoading(false);
    }
  }

  async function updateProposal(id: number, patch: any) {
    await api(`/api/proposals/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
    refetchProposals();
  }

  async function deleteProposal(id: number) {
    if (!confirm("Delete this proposal?")) return;
    await api(`/api/proposals/${id}`, { method: "DELETE" });
    refetchProposals();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Trade analysis</h1>
        <p className="text-sm text-muted mt-1">
          Quant-style pre-trade checklist: EV, half-Kelly sizing, IV vs realized vol,
          theta budget, earnings risk, and pre-committed exits.
        </p>
      </div>

      <form onSubmit={(e) => submit(e, false)} className="card grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label>Ticker</label>
          <input value={form.ticker} onChange={(e) => update("ticker", e.target.value.toUpperCase())} placeholder="AAPL" required />
        </div>
        <div>
          <label>Action</label>
          <select value={form.action} onChange={(e) => update("action", e.target.value)}>
            <option value="buy">buy</option>
            <option value="sell">sell</option>
          </select>
        </div>
        <div>
          <label>Instrument</label>
          <select value={form.instrument} onChange={(e) => update("instrument", e.target.value)}>
            <option value="stock">stock</option>
            <option value="call">call</option>
            <option value="put">put</option>
          </select>
        </div>
        <div>
          <label>Quantity (shares or contracts)</label>
          <input type="number" step="any" value={form.quantity} onChange={(e) => update("quantity", e.target.value)} required />
        </div>

        <div>
          <label>Total capital ($)</label>
          <input type="number" step="any" value={form.total_capital} onChange={(e) => update("total_capital", e.target.value)} required />
        </div>

        {isOption && (
          <>
            <div>
              <label>Strike</label>
              <input type="number" step="any" value={form.strike} onChange={(e) => update("strike", e.target.value)} />
            </div>
            <div>
              <label>Expiry</label>
              <input type="date" value={form.expiry} onChange={(e) => update("expiry", e.target.value)} />
            </div>
            <div>
              <label>Premium (per share)</label>
              <input type="number" step="any" value={form.premium} onChange={(e) => update("premium", e.target.value)} />
            </div>
          </>
        )}

        <div>
          <label>P(win) — 0..1</label>
          <input type="number" step="any" min="0" max="1" value={form.win_probability} onChange={(e) => update("win_probability", e.target.value)} />
        </div>
        <div>
          <label>Expected profit ($)</label>
          <input type="number" step="any" value={form.expected_profit} onChange={(e) => update("expected_profit", e.target.value)} />
        </div>
        <div>
          <label>Expected loss ($, positive)</label>
          <input type="number" step="any" value={form.expected_loss} onChange={(e) => update("expected_loss", e.target.value)} />
        </div>

        <div>
          <label>Profit target</label>
          <input type="number" step="any" value={form.profit_target} onChange={(e) => update("profit_target", e.target.value)} />
        </div>
        <div>
          <label>Stop loss</label>
          <input type="number" step="any" value={form.stop_loss} onChange={(e) => update("stop_loss", e.target.value)} />
        </div>

        <div className="col-span-2 md:col-span-4">
          <label>Edge thesis — why do you know something the market doesn't?</label>
          <textarea
            value={form.edge_thesis}
            onChange={(e) => update("edge_thesis", e.target.value)}
            rows={3}
            placeholder="Be specific. 'It feels cheap' is not edge."
          />
        </div>

        <div className="col-span-2 md:col-span-4 flex gap-2">
          <button className="btn btn-primary" type="submit" disabled={loading}>
            {loading ? "Analyzing…" : "Analyze"}
          </button>
          <button
            className="btn"
            type="button"
            disabled={loading || !form.ticker}
            onClick={(e) => submit(e as any, true)}
          >
            Analyze &amp; save
          </button>
          <button className="btn" type="button" onClick={() => { setForm(blankForm); setResult(null); }}>
            Reset
          </button>
        </div>

        {error && <div className="col-span-2 md:col-span-4 text-red-400 text-sm">{error}</div>}
      </form>

      {result && (
        <div className="space-y-4">
          <div className={`card border ${REC_STYLE[result.recommendation].cls}`}>
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <div className="text-xs uppercase tracking-wider text-muted">Recommendation</div>
                <div className="text-2xl font-semibold">{REC_STYLE[result.recommendation].label}</div>
              </div>
              <div className="text-right">
                <div className="text-xs uppercase tracking-wider text-muted">Score</div>
                <div className="text-2xl font-mono">{(result.score * 100).toFixed(0)}%</div>
              </div>
              {result.saved_proposal_id && (
                <div className="text-xs text-muted">Saved as #{result.saved_proposal_id}</div>
              )}
            </div>
            <ContextSummary ctx={result.context} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {result.rules.map((r) => (
              <div key={r.rule_id} className={`card border ${STATUS_STYLE[r.status]}`}>
                <div className="flex items-center gap-2">
                  <span className={`inline-block w-2 h-2 rounded-full ${STATUS_DOT[r.status]}`} />
                  <div className="font-medium">{r.title}</div>
                  <span className="text-xs uppercase tracking-wider text-muted ml-auto">{r.status}</span>
                </div>
                <div className="text-sm mt-2">{r.message}</div>
                {r.math && Object.keys(r.math).length > 0 && (
                  <details className="mt-2">
                    <summary className="text-xs text-muted cursor-pointer">math</summary>
                    <pre className="text-xs font-mono bg-bg/60 rounded p-2 mt-1 overflow-x-auto">
                      {JSON.stringify(r.math, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">Saved proposals</h2>
          <span className="text-xs text-muted">Process audit — did you only take ok/review trades?</span>
        </div>
        <div className="overflow-x-auto">
          <table className="tbl">
            <thead><tr>
              <th>Date</th><th>Ticker</th><th>Type</th><th>Verdict</th>
              <th className="text-right">Score</th>
              <th>Decision</th><th>Outcome</th>
              <th className="text-right">Realized P/L</th><th></th>
            </tr></thead>
            <tbody>
              {proposals?.map((p) => (
                <tr key={p.id}>
                  <td className="text-xs">{new Date(p.created_at).toLocaleDateString()}</td>
                  <td className="font-mono">{p.ticker}</td>
                  <td>
                    <span className="text-xs px-1.5 py-0.5 bg-line rounded">
                      {p.action} {p.instrument}
                      {p.instrument !== "stock" && p.strike ? ` ${p.strike}` : ""}
                    </span>
                  </td>
                  <td>
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${REC_STYLE[p.recommendation as keyof typeof REC_STYLE]?.cls || ""}`}>
                      {p.recommendation}
                    </span>
                  </td>
                  <td className="text-right font-mono">{(p.score * 100).toFixed(0)}%</td>
                  <td>
                    <select value={p.decision} onChange={(e) => updateProposal(p.id, { decision: e.target.value })}>
                      <option value="pending">pending</option>
                      <option value="entered">entered</option>
                      <option value="skipped">skipped</option>
                    </select>
                  </td>
                  <td>
                    <select value={p.outcome || ""} onChange={(e) => updateProposal(p.id, { outcome: e.target.value })}>
                      <option value="">—</option>
                      <option value="open">open</option>
                      <option value="win">win</option>
                      <option value="loss">loss</option>
                      <option value="breakeven">breakeven</option>
                    </select>
                  </td>
                  <td className="text-right font-mono">
                    {p.realized_pl != null ? fmtMoney(p.realized_pl) : "—"}
                  </td>
                  <td className="flex gap-1">
                    <Link href={`/analyze/${p.id}`} className="btn">view</Link>
                    <button className="btn" onClick={() => deleteProposal(p.id)}>✕</button>
                  </td>
                </tr>
              ))}
              {!proposals?.length && (
                <tr><td colSpan={9} className="text-center text-muted py-6">No proposals yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function ContextSummary({ ctx }: { ctx: any }) {
  if (!ctx) return null;
  const items: [string, string][] = [];
  if (ctx.spot) items.push(["Spot", `$${ctx.spot.toFixed(2)}`]);
  if (ctx.hv30 != null) items.push(["HV30", `${(ctx.hv30 * 100).toFixed(1)}%`]);
  if (ctx.days_to_expiry != null) items.push(["DTE", `${ctx.days_to_expiry}d`]);
  if (ctx.option) {
    items.push(["IV", `${(ctx.option.iv * 100).toFixed(1)}%`]);
    items.push(["Mid", `$${ctx.option.mid?.toFixed(2)}`]);
    items.push(["OI", String(ctx.option.open_interest)]);
  }
  if (ctx.earnings_date) items.push(["Earnings", ctx.earnings_date]);
  if (!items.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm">
      {items.map(([k, v]) => (
        <div key={k}>
          <span className="text-muted text-xs uppercase tracking-wider mr-2">{k}</span>
          <span className="font-mono">{v}</span>
        </div>
      ))}
    </div>
  );
}
