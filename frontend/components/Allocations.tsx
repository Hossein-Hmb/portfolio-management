"use client";

const COLORS = [
  "#4ade80",
  "#60a5fa",
  "#f59e0b",
  "#f472b6",
  "#a78bfa",
  "#22d3ee",
  "#f87171",
  "#facc15",
  "#94a3b8",
];

type AllocationSlice = { label: string; value: number; pct: number };

function money(value: number) {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function conicGradient(data: AllocationSlice[]) {
  let cursor = 0;
  const stops = data.map((slice, index) => {
    const start = cursor;
    cursor += slice.pct;
    const color = COLORS[index % COLORS.length];
    return `${color} ${start}% ${cursor}%`;
  });
  return `conic-gradient(${stops.join(", ")})`;
}

export function AllocationPie({
  title,
  data,
}: {
  title: string;
  data: AllocationSlice[];
}) {
  const rows = data.filter((slice) => slice.value > 0 && slice.pct > 0);
  const total = rows.reduce((sum, slice) => sum + slice.value, 0);

  return (
    <div className="card overflow-hidden">
      <div className="text-sm text-muted mb-2">{title}</div>
      {rows.length === 0 ? (
        <div className="flex h-52 items-center justify-center text-sm text-muted">
          No allocation data yet.
        </div>
      ) : (
        <div className="grid min-h-52 gap-4 sm:grid-cols-[120px_1fr] sm:items-center">
          <div
            className="mx-auto size-28 rounded-full border border-line shadow-inner"
            style={{ background: conicGradient(rows) }}
            aria-label={`${title}: ${rows.map((row) => `${row.label} ${row.pct}%`).join(", ")}`}>
            <div className="m-7 flex size-14 items-center justify-center rounded-full border border-line bg-panel text-xs font-semibold text-muted">
              {money(total)}
            </div>
          </div>
          <div className="min-w-0 space-y-2">
            {rows.map((slice, index) => (
              <div key={slice.label}>
                <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                  <div className="flex min-w-0 items-center gap-2">
                    <span
                      className="size-2 rounded-full"
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    />
                    <span className="truncate">{slice.label}</span>
                  </div>
                  <span className="font-mono text-muted">
                    {slice.pct.toFixed(2)}%
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-bg">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.max(slice.pct, 1)}%`,
                      backgroundColor: COLORS[index % COLORS.length],
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
