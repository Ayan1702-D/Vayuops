"use client";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
} from "recharts";
export function SeriesChart({
  data,
  series,
  boundaries = [],
}: {
  data: object[];
  series: { key: string; name: string; color: string; dashed?: boolean }[];
  boundaries?: string[];
}) {
  if (!data.length)
    return (
      <p className="empty">No observations are available for this selection.</p>
    );
  return (
    <div
      className="chart"
      role="img"
      aria-label={series.map((x) => x.name).join(" and ") + " over time"}
    >
      <ResponsiveContainer width="100%" height={300}>
        <LineChart
          data={data}
          margin={{ top: 24, right: 25, left: 0, bottom: 12 }}
          accessibilityLayer
        >
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            minTickGap={45}
          />
          <YAxis tick={{ fill: "var(--muted)", fontSize: 11 }} width={45} />
          <Tooltip
            contentStyle={{
              background: "var(--panel)",
              border: "1px solid var(--border)",
              borderRadius: 12,
              color: "var(--text)",
            }}
          />
          <Legend />
          {boundaries.map((x) => (
            <ReferenceLine
              key={x}
              x={x}
              stroke="var(--muted)"
              strokeDasharray="3 3"
            />
          ))}
          {series.map((x) => (
            <Line
              key={x.key}
              dataKey={x.key}
              name={x.name}
              stroke={x.color}
              strokeWidth={2.5}
              dot={x.dashed || data.length < 4}
              activeDot={{ r: 5 }}
              strokeDasharray={x.dashed ? "5 4" : undefined}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
