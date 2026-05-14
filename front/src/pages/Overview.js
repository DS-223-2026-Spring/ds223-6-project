import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
  LineChart, Line, Legend, ErrorBar,
} from "recharts";
import MetricCard from "../components/MetricCard";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

const COLORS = {
  search: "#2E75B6", facebook: "#5DCAA5", tv: "#7F77DD",
  ooh: "#EF9F27", print: "#D85A30",
};
const REC_COLOR = { "under-invested":"#1D6A38","over-invested":"#843C1D","optimal":"#0C447C","no-signal":"#888" };
const REC_BG    = { "under-invested":"#E2F0D9","over-invested":"#FCE4D6","optimal":"#EBF3FB","no-signal":"#F4F4F4" };

function exportCSV(channels, modelVersion) {
  const header = "channel,roi_estimate,contribution_pct,recommendation";
  const rows   = channels.map(c =>
    `${c.channel},${c.roi_estimate ?? ""},${c.contribution_pct ?? ""},${c.recommendation ?? ""}`
  );
  const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = `mmm_results_${modelVersion}.csv`; a.click();
  URL.revokeObjectURL(url);
}

export default function Overview() {
  const [results,     setResults]     = useState(null);
  const [summary,     setSummary]     = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    Promise.all([
      ApiService.getResults(),
      ApiService.getDataSummary(),
      ApiService.getPredictions(),
    ])
      .then(([r, s, p]) => {
        setResults(r);
        setSummary(s);
        setPredictions(p.points || []);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner message="Loading model results..." />;
  if (error)   return <div style={S.errorBox}>Error: {error}</div>;

  const channels   = results?.channels ?? [];
  const bestCh     = channels[0];

  const roiData = channels.map(c => {
    const roi = c.roi_estimate ? +c.roi_estimate.toFixed(2) : 0;
    // ErrorBar expects [lowerDelta, upperDelta] relative to the bar value
    const ciLower = c.roi_lower_90 != null ? +(roi - c.roi_lower_90).toFixed(2) : null;
    const ciUpper = c.roi_upper_90 != null ? +(c.roi_upper_90 - roi).toFixed(2) : null;
    return {
      name:    c.channel.charAt(0).toUpperCase() + c.channel.slice(1),
      roi,
      pct:     c.contribution_pct ? +c.contribution_pct.toFixed(1) : 0,
      rec:     c.recommendation,
      channel: c.channel,
      // ciError is [downwardDelta, upwardDelta] — only set when both bounds exist
      ciError: ciLower != null && ciUpper != null ? [ciLower, ciUpper] : null,
    };
  });
  const hasBayesianCI = roiData.some(d => d.ciError != null);

  // Sample predictions to ~40 points for chart readability
  const predStep   = Math.max(1, Math.floor(predictions.length / 40));
  const predSample = predictions.filter((_, i) => i % predStep === 0);
  const predChartData = predSample.map(p => ({
    week:      p.week_start.slice(0, 7), // YYYY-MM
    actual:    Math.round(p.actual_revenue / 1000),
    predicted: Math.round(p.predicted_revenue / 1000),
  }));

  const r2 = results?.r_squared;
  const r2Color = r2 >= 0.9 ? "#1D6A38" : r2 >= 0.8 ? "#7F6000" : "#843C1D";

  return (
    <div>
      {/* KPI cards */}
      <div style={S.kpiGrid}>
        <MetricCard label="Model version"   value={results?.model_version ?? "—"} />
        <MetricCard label="R² test set"
          value={r2 ? <span style={{ color: r2Color }}>{r2.toFixed(3)}</span> : "—"}
          sub="closer to 1.0 = better fit" />
        <MetricCard label="Best ROI channel" value={bestCh?.channel ?? "—"}
          sub={bestCh ? `$${bestCh.roi_estimate?.toFixed(2)} per $1` : null} />
        <MetricCard label="Data loaded"
          value={summary?.total_weeks ? `${summary.total_weeks} weeks` : "—"}
          sub={summary ? `${summary.first_week} → ${summary.last_week}` : null} />
      </div>

      {channels.length === 0 ? (
        <div style={S.emptyBox}>
          No model results yet. Run{" "}
          <code style={S.code}>docker exec mmm_ds python models/baseline.py</code>
        </div>
      ) : (
        <>
          {/* ROI bar chart + export */}
          <div style={S.card}>
            <div style={S.cardHeader}>
              <span style={S.cardTitle}>
                Channel ROI — revenue per $1 spent
                {hasBayesianCI && (
                  <span style={{ fontSize:11, fontWeight:400, color:"#7F77DD", marginLeft:8 }}>
                    ◈ with 90% credible intervals
                  </span>
                )}
              </span>
              <button style={S.exportBtn}
                onClick={() => exportCSV(channels, results?.model_version || "export")}>
                ↓ Export CSV
              </button>
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={roiData} layout="vertical" margin={{ left:10, right:40 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tickFormatter={v => `$${v}`} tick={{ fontSize:11 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize:12 }} width={72} />
                <Tooltip
                  formatter={(v, name, props) => {
                    if (name !== "roi") return null;
                    const d = props.payload;
                    if (d.ciError) {
                      const lo = (v - d.ciError[0]).toFixed(2);
                      const hi = (v + d.ciError[1]).toFixed(2);
                      return [`$${v} (90% CI: $${lo}–$${hi})`, "ROI"];
                    }
                    return [`$${v}`, "ROI"];
                  }}
                  contentStyle={{ fontSize:12, borderRadius:6 }} />
                <ReferenceLine x={1} stroke="#888" strokeDasharray="4 2"
                  label={{ value: "Break-even", position: "top", fontSize: 10, fill: "#888"}} />
                <Bar dataKey="roi" radius={[0,4,4,0]}>
                  {roiData.map(e => <Cell key={e.channel} fill={COLORS[e.channel]||"#888"} />)}
                  {hasBayesianCI && (
                    <ErrorBar dataKey="ciError" width={4} strokeWidth={2} stroke="#555" direction="x" />
                  )}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div style={S.grid2}>
            {/* Contribution % */}
            <div style={S.card}>
              <div style={S.cardTitle}>Revenue contribution %</div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={roiData} margin={{ left:-10, right:10 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize:11 }} />
                  <YAxis tickFormatter={v=>`${v}%`} tick={{ fontSize:11 }} />
                  <Tooltip formatter={v=>[`${v}%`,"Contribution"]}
                    contentStyle={{ fontSize:12, borderRadius:6 }} />
                  <Bar dataKey="pct" radius={[4,4,0,0]}>
                    {roiData.map(e => <Cell key={e.channel} fill={COLORS[e.channel]||"#888"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Recommendations */}
            <div style={S.card}>
              <div style={S.cardTitle}>Investment recommendations</div>
              {roiData.map(c => (
                <div key={c.channel} style={S.recRow}>
                  <span style={{ ...S.dot, background: COLORS[c.channel] }} />
                  <span style={{ flex:1, fontSize:13 }}>
                    {c.name}
                    <span style={{ color:"#888", fontSize:11, marginLeft:4 }}>({c.pct}%)</span>
                  </span>
                  {c.rec && (
                    <span style={{
                      ...S.recPill,
                      background: REC_BG[c.rec]  || "#F4F4F4",
                      color:      REC_COLOR[c.rec]|| "#444",
                    }}>{c.rec}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Actual vs Predicted chart */}
          {predChartData.length > 0 && (
            <div style={S.card}>
              <div style={S.cardTitle}>
                Actual vs predicted revenue — weekly (USD thousands)
              </div>
              <div style={{ fontSize:11, color:"#888", marginBottom:10 }}>
                R² = {r2?.toFixed(4)} — how closely the model tracks actual revenue.
                Gaps between lines show where the model over- or under-predicts.
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={predChartData} margin={{ left:10, right:20 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="week" tick={{ fontSize:10 }}
                    interval={Math.floor(predChartData.length / 8)} />
                  <YAxis tickFormatter={v=>`$${v}k`} tick={{ fontSize:11 }} />
                  <Tooltip formatter={(v,n)=>[`$${v.toLocaleString()}k`, n]}
                    contentStyle={{ fontSize:12, borderRadius:6 }} />
                  <Legend wrapperStyle={{ fontSize:12 }} />
                  <Line type="monotone" dataKey="actual"    name="Actual"
                    stroke="#1F4E79" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="predicted" name="Predicted"
                    stroke="#EF9F27" strokeWidth={2} dot={false} strokeDasharray="5 3" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  );
}

const S = {
  kpiGrid:    { display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10, marginBottom:16 },
  card:       { background:"#fff", border:"0.5px solid #e0e0e0", borderRadius:10, padding:16, marginBottom:14 },
  cardHeader: { display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:12 },
  cardTitle:  { fontSize:13, fontWeight:500, color:"#1a1a1a" },
  grid2:      { display:"grid", gridTemplateColumns:"1.2fr 1fr", gap:14 },
  recRow:     { display:"flex", alignItems:"center", gap:8, padding:"7px 0", borderBottom:"0.5px solid #f0f0f0" },
  dot:        { width:10, height:10, borderRadius:"50%", flexShrink:0 },
  recPill:    { fontSize:11, fontWeight:500, padding:"2px 9px", borderRadius:20 },
  exportBtn:  { fontSize:11, padding:"4px 12px", borderRadius:6, border:"1px solid #2E75B6", color:"#2E75B6", background:"transparent", cursor:"pointer" },
  errorBox:   { background:"#FCE4D6", color:"#843C1D", padding:14, borderRadius:8, fontSize:13 },
  emptyBox:   { background:"#F4F4F4", color:"#888", padding:"2rem", borderRadius:8, textAlign:"center", fontSize:13 },
  code:       { background:"#e8e8e8", padding:"1px 6px", borderRadius:4, fontFamily:"monospace", fontSize:12 },
};
