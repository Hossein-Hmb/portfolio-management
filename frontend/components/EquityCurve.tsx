"use client";
import { LineChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";

export function EquityCurve({ data }: { data: { date: string; value: number }[] }) {
  return (
    <div className="card">
      <div className="text-sm text-muted mb-2">Portfolio Value</div>
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="#1f242a" vertical={false} />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#8a93a0" }} minTickGap={32} />
            <YAxis tick={{ fontSize: 11, fill: "#8a93a0" }} width={70}
                   tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
            <Tooltip
              contentStyle={{ background: "#121518", border: "1px solid #1f242a", borderRadius: 8 }}
              labelStyle={{ color: "#8a93a0" }}
              formatter={(v: any) => [`$${Number(v).toLocaleString()}`, "Value"]}
            />
            <Line type="monotone" dataKey="value" stroke="#4ade80" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
