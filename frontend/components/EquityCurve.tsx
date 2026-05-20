"use client";

type ValuePoint = { date: string; value: number };

function money(value: number) {
  return new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0,
  }).format(value || 0);
}

function chartPath(points: ValuePoint[], width: number, height: number) {
  if (points.length === 0) return "";
  const values = points.map((point) => point.value);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 1);
  const span = max - min || 1;
  return points
    .map((point, index) => {
      const x =
        points.length === 1 ? width : (index / (points.length - 1)) * width;
      const y = height - ((point.value - min) / span) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function EquityCurve({ data }: { data: ValuePoint[] }) {
  const rows = data.filter((point) => Number.isFinite(point.value));
  const width = 900;
  const height = 240;
  const path = chartPath(rows, width, height);
  const latest = rows.at(-1);
  const first = rows[0];

  return (
    <div className="card overflow-hidden">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm text-muted">Portfolio Value</div>
          <div className="text-xs text-muted">
            {first?.date}{" "}
            {latest && first?.date !== latest.date ? `to ${latest.date}` : ""}
          </div>
        </div>
        {latest && (
          <div className="font-mono text-sm text-muted">
            {money(latest.value)}
          </div>
        )}
      </div>
      {rows.length === 0 ? (
        <div className="flex h-60 items-center justify-center text-sm text-muted">
          No portfolio value data yet.
        </div>
      ) : (
        <div className="relative h-60 overflow-hidden rounded-lg border border-line bg-bg/40">
          <svg
            className="h-full w-full"
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="none"
            role="img"
            aria-label="Portfolio value over time">
            <defs>
              <linearGradient id="equity-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#4ade80" stopOpacity="0.28" />
                <stop offset="100%" stopColor="#4ade80" stopOpacity="0.02" />
              </linearGradient>
            </defs>
            {[0.25, 0.5, 0.75].map((tick) => (
              <line
                key={tick}
                x1="0"
                x2={width}
                y1={height * tick}
                y2={height * tick}
                stroke="#1f242a"
                strokeWidth="1"
              />
            ))}
            <path
              d={`${path} L ${width} ${height} L 0 ${height} Z`}
              fill="url(#equity-fill)"
            />
            <path
              d={path}
              fill="none"
              stroke="#4ade80"
              strokeLinecap="round"
              strokeWidth="3"
            />
          </svg>
          <div className="absolute bottom-3 left-3 text-xs text-muted">
            {money(0)}
          </div>
          {latest && (
            <div className="absolute right-3 top-3 text-xs text-muted">
              {money(latest.value)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
