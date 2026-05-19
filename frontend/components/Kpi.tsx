import { cls, fmtMoney, fmtPct } from "@/lib/api";

export function Kpi({ label, value, sub, tone }:
  { label: string; value: string; sub?: string; tone?: "pos" | "neg" | "muted" }) {
  return (
    <div className="card">
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value ${tone === "pos" ? "pos" : tone === "neg" ? "neg" : ""}`}>{value}</div>
      {sub && <div className="text-xs text-muted mt-1">{sub}</div>}
    </div>
  );
}

export function MoneyKpi({ label, amount, pct, currency = "CAD" }:
  { label: string; amount: number; pct?: number; currency?: string }) {
  return (
    <div className="card">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{fmtMoney(amount, currency)}</div>
      {pct !== undefined && <div className={`text-sm mt-1 ${cls(pct)}`}>{fmtPct(pct)}</div>}
    </div>
  );
}
