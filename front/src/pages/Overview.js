import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine
} from "recharts";
import MetricCard from "../components/MetricCard";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

const COLORS = {
  search: "#2E75B6", facebook: "#5DCAA5", tv: "#7F77DD",
  ooh: "#EF9F27", print: "#D85A30",
};
const REC_COLOR = { "under-invested": "#1D6A38", "over-invested": "#843C1D", "optimal": "#0C447C" };
const REC_BG    = { "under-invested": "#E2F0D9", "over-invested": "#FCE4D6", "optimal": "#EBF3FB" };

export default function Overview() {
  const [data,    setData]    = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    Promise.all([ApiService.getResults(), ApiService.getDataSummary()])
      .then(([r, s]) => { setData(r); setSummary(s); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner message="Loading model results..." />;
  if (error)   return <div style={styles.errorBox}>Error: {error}</div>;

  const channels   = data?.channels ?? [];
  const bestCh     = channels[0];
  const totalPred  = channels.reduce((s, c) => s + (c.predicted_revenue_contribution || 0), 0);
  const baselinePct = totalPred > 0
    ? Math.max(0, Math.round((1 - totalPred / (data?.r_squared ? totalPred / data.r_squared : totalPred)) * 100))
    : null;

  const chartData = channels.map(c => ({
    name:  c.channel.charAt(0).toUpperCase() + c.channel.slice(1),
    roi:   c.roi_estimate ? +c.roi_estimate.toFixed(2) : 0,
    pct:   c.contribution_pct ? +c.contribution_pct.toFixed(1) : 0,
    rec:   c.recommendation,
    channel: c.channel,
  }));

  return (
    <div>
      {/* KPI cards */}
      <div style={styles.kpiGrid}>
        <MetricCard label="Model version"  value={data?.model_version ?? "—"} />
        <MetricCard label="R² (test set)"  value={data?.r_squared ? data.r_squared.toFixed(3) : "—"}
                    sub="1.0 = perfect fit" />
        <MetricCard label="Best channel"   value={bestCh ? bestCh.channel : "—"}
                    sub={bestCh ? `$${bestCh.roi_estimate?.toFixed(2)} per $1` : null} />
        <MetricCard label="Channels modelled" value={channels.length || "—"}
                    sub={summary ? `${summary.total_weeks} weeks of data` : null} />
      </div>

      {channels.length === 0 ? (
        <div style={styles.emptyBox}>
          No model results yet. Run{" "}
          <code style={styles.code}>docker exec mmm_ds python models/baseline.py</code>{" "}
          to train the model.
        </div>
      ) : (
        <>
          {/* ROI bar chart */}
          <div style={styles.card}>
            <div style={styles.cardTitle}>Channel ROI — revenue per $1 spent</div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={v => `$${v}`} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 12 }} width={70} />
                <Tooltip
                  formatter={(v, n) => [`$${v}`, "ROI"]}
                  labelStyle={{ fontWeight: 500 }}
                  contentStyle={{ fontSize: 12, borderRadius: 6 }}
                />
                <ReferenceLine x={1} stroke="#888" strokeDasharray="4 2"
                  label={{ value: "Break-even", position: "top", fontSize: 10 }} />
                <Bar dataKey="roi" radius={[0, 4, 4, 0]}>
                  {chartData.map(entry => (
                    <Cell key={entry.channel} fill={COLORS[entry.channel] || "#888"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Contribution % + recommendations */}
          <div style={styles.grid2}>
            <div style={styles.card}>
              <div style={styles.cardTitle}>Revenue contribution %</div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={chartData} margin={{ left: -10, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
                  <Tooltip formatter={v => [`${v}%`, "Contribution"]}
                    contentStyle={{ fontSize: 12, borderRadius: 6 }} />
                  <Bar dataKey="pct" radius={[4, 4, 0, 0]}>
                    {chartData.map(entry => (
                      <Cell key={entry.channel} fill={COLORS[entry.channel] || "#888"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div style={styles.card}>
              <div style={styles.cardTitle}>Investment recommendations</div>
              {chartData.map(c => (
                <div key={c.channel} style={styles.recRow}>
                  <span style={{ ...styles.dot, background: COLORS[c.channel] }} />
                  <span style={{ flex: 1, fontSize: 13 }}>
                    {c.name}
                    <span style={{ color: "#888", fontSize: 11, marginLeft: 4 }}>
                      ({c.pct}%)
                    </span>
                  </span>
                  {c.rec && (
                    <span style={{
                      ...styles.recPill,
                      background: REC_BG[c.rec] || "#F4F4F4",
                      color:      REC_COLOR[c.rec] || "#444",
                    }}>
                      {c.rec}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

const styles = {
  kpiGrid:   { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 20 },
  card:      { background: "#fff", border: "0.5px solid #e0e0e0", borderRadius: 10, padding: 16, marginBottom: 14 },
  cardTitle: { fontSize: 13, fontWeight: 500, color: "#1a1a1a", marginBottom: 12 },
  grid2:     { display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 14 },
  recRow:    { display: "flex", alignItems: "center", gap: 8, padding: "7px 0", borderBottom: "0.5px solid #f0f0f0" },
  dot:       { width: 10, height: 10, borderRadius: "50%", flexShrink: 0 },
  recPill:   { fontSize: 11, fontWeight: 500, padding: "2px 9px", borderRadius: 20 },
  errorBox:  { background: "#FCE4D6", color: "#843C1D", padding: 14, borderRadius: 8, fontSize: 13 },
  emptyBox:  { background: "#F4F4F4", color: "#888", padding: "2rem", borderRadius: 8, textAlign: "center", fontSize: 13 },
  code:      { background: "#e8e8e8", padding: "1px 6px", borderRadius: 4, fontFamily: "monospace", fontSize: 12 },
};
