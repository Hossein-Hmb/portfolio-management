export const API = process.env.NEXT_PUBLIC_API_BASE || "";

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export const fetcher = (url: string) => api(url);

export const fmtMoney = (n: number, cur = "CAD") =>
  new Intl.NumberFormat("en-CA", { style: "currency", currency: cur, maximumFractionDigits: 2 }).format(n || 0);

export const fmtPct = (n: number) => `${(n ?? 0).toFixed(2)}%`;

export const cls = (n: number) => (n > 0 ? "pos" : n < 0 ? "neg" : "text-muted");
