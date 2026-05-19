"use client";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

const COLORS = ["#4ade80","#60a5fa","#f59e0b","#f472b6","#a78bfa","#22d3ee","#f87171","#facc15","#94a3b8"];

export function AllocationPie({ title, data }: { title: string; data: { label: string; value: number; pct: number }[] }) {
  return (
    <div className="card">
      <div className="text-sm text-muted mb-2">{title}</div>
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="label" outerRadius={80} innerRadius={45} stroke="#0b0d10">
              {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip
              contentStyle={{ background: "#121518", border: "1px solid #1f242a", borderRadius: 8 }}
              formatter={(v: any, _n, p: any) => [`${Number(v).toLocaleString()} (${p.payload.pct}%)`, p.payload.label]}
            />
            <Legend wrapperStyle={{ fontSize: 12, color: "#8a93a0" }} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
