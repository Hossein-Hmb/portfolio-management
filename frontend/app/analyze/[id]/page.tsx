"use client";
import useSWR from "swr";
import Link from "next/link";
import { useParams } from "next/navigation";
import { fetcher } from "@/lib/api";

const STATUS_STYLE: Record<string, string> = {
  pass: "border-green-700/60 bg-green-900/15",
  warn: "border-amber-700/60 bg-amber-900/15",
  fail: "border-red-700/60 bg-red-900/15",
  info: "border-line bg-panel",
  skip: "border-line/50 bg-panel/40 opacity-70",
};

const STATUS_DOT: Record<string, string> = {
  pass: "bg-green-400",
  warn: "bg-amber-400",
  fail: "bg-red-400",
  info: "bg-sky-400",
  skip: "bg-zinc-500",
};

export default function ProposalDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, error } = useSWR<any>(`/api/proposals/${params.id}`, fetcher);

  if (error) return <div className="text-red-400">{String(error.message || error)}</div>;
  if (!data) return <div className="text-muted">Loading…</div>;

  const a = data.analysis;
  return (
    <div className="space-y-6">
      <Link href="/analyze" className="btn">← Back</Link>

      <div className="card">
        <div className="text-xs uppercase tracking-wider text-muted">Proposal #{data.id}</div>
        <div className="text-2xl font-semibold">
          {data.ticker} — {data.action} {data.instrument}
          {data.instrument !== "stock" && data.strike ? ` ${data.strike} ${data.expiry || ""}` : ""}
        </div>
        <div className="text-sm text-muted mt-1">Created {new Date(data.created_at).toLocaleString()}</div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <KV k="Quantity" v={data.quantity} />
          <KV k="Total capital" v={`$${data.total_capital}`} />
          <KV k="Premium" v={data.premium != null ? `$${data.premium}` : "—"} />
          <KV k="Recommendation" v={data.recommendation} />
          <KV k="Score" v={`${(data.score * 100).toFixed(0)}%`} />
          <KV k="P(win)" v={data.win_probability ?? "—"} />
          <KV k="Exp. profit" v={data.expected_profit ?? "—"} />
          <KV k="Exp. loss" v={data.expected_loss ?? "—"} />
          <KV k="Profit target" v={data.profit_target ?? "—"} />
          <KV k="Stop loss" v={data.stop_loss ?? "—"} />
          <KV k="Decision" v={data.decision} />
          <KV k="Outcome" v={data.outcome || "—"} />
        </div>

        {data.edge_thesis && (
          <div className="mt-4">
            <div className="text-xs uppercase tracking-wider text-muted">Edge thesis</div>
            <div className="text-sm mt-1 whitespace-pre-wrap">{data.edge_thesis}</div>
          </div>
        )}
      </div>

      {a && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {a.rules.map((r: any) => (
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
      )}
    </div>
  );
}

function KV({ k, v }: { k: string; v: any }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted">{k}</div>
      <div className="font-mono">{String(v)}</div>
    </div>
  );
}
