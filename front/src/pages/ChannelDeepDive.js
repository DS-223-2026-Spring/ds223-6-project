import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell
} from "recharts";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

const CHANNELS = ["tv", "ooh", "print", "facebook", "search"];
const COLORS   = { search:"#2E75B6", facebook:"#5DCAA5", tv:"#7F77DD", ooh:"#EF9F27", print:"#D85A30" };

const ADSTOCK_DECAY = { tv:0.68, ooh:0.40, print:0.35, facebook:0.25, search:0.12 };

function buildSaturationCurve(roi) {
  if (!roi || roi === 0) return [];
  const points = [];
  for (let pct = 0; pct <= 100; pct += 5) {
    const spend = pct * 1000;
    const n = 2, K = 50000 * 0.5;
    const sat = Math.pow(spend, n) / (Math.pow(spend, n) + Math.pow(K, n));
    points.push({ spend: `$${(spend/1000).toFixed(0)}k`, revenue: Math.round(sat * roi * spend) });
  }
  return points;
}

function buildAdstockDecay(decay) {
  const weeks = [];
  let val = 100;
  for (let w = 0; w <= 8; w++) {
    weeks.push({ week: `Wk ${w}`, effect: Math.round(val) });
    val *= decay;
  }
  return weeks;
}

export default function ChannelDeepDive() {
  const [data,       setData]       = useState(null);
  const [selected,   setSelected]   = useState("search");
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);

  useEffect(() => {
    ApiService.getResults()
      .then(r => { setData(r); if (r?.channels?.length) setSelected(r.channels[0].channel); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner message="Loading channel data..." />;
  if (error)   return <div style={styles.errorBox}>Error: {error}</div>;

  const channels = data?.channels ?? [];
  if (channels.length === 0)
    return <div style={styles.emptyBox}>No model results yet. Train the model first.</div>;

  const ch       = channels.find(c => c.channel === selected) || channels[0];
  const satCurve = buildSaturationCurve(ch.roi_estimate);
  const adstock  = buildAdstockDecay(ADSTOCK_DECAY[ch.channel] || 0.3);

  return (
    <div>
      {/* Channel selector */}
      <div style={styles.selectorRow}>
        {channels.map(c => (
          <button key={c.channel} onClick={() => setSelected(c.channel)}
            style={{
              ...styles.selBtn,
              background:  selected === c.channel ? COLORS[c.channel] : "#F4F4F4",
              color:       selected === c.channel ? "#fff" : "#444",
              borderColor: COLORS[c.channel],
            }}>
            {c.channel.charAt(0).toUpperCase() + c.channel.slice(1)}
          </button>
        ))}
      </div>

      {/* Channel headline stats */}
      <div style={styles.statRow}>
        {[
          { label: "ROI",            value: ch.roi_estimate ? `$${ch.roi_estimate.toFixed(2)}` : "—", sub: "per $1 spent" },
          { label: "Revenue share",  value: ch.contribution_pct ? `${ch.contribution_pct.toFixed(1)}%` : "—" },
          { label: "Recommendation", value: ch.recommendation ?? "—" },
          { label: "Adstock decay",  value: `λ = ${ADSTOCK_DECAY[ch.channel] ?? "—"}`, sub: "weeks of carryover" },
        ].map(s => (
          <div key={s.label} style={styles.statCard}>
            <div style={styles.statLabel}>{s.label}</div>
            <div style={styles.statValue}>{s.value}</div>
            {s.sub && <div style={styles.statSub}>{s.sub}</div>}
          </div>
        ))}
      </div>

      {/* Saturation curve */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>
          Response curve — how revenue grows as {ch.channel} spend increases
        </div>
        <div style={styles.cardSub}>
          The curve flattens at higher spend levels, showing diminishing returns.
          Current spend level indicates where you are on the curve.
        </div>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={satCurve} margin={{ left: 10, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="spend" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
            <Tooltip formatter={v => [`$${v.toLocaleString()}`, "Predicted revenue"]}
              contentStyle={{ fontSize: 12, borderRadius: 6 }} />
            <Line type="monotone" dataKey="revenue"
              stroke={COLORS[ch.channel]} strokeWidth={2.5} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Adstock decay */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>
          Adstock decay — how long {ch.channel}'s effect lasts after the ad runs
        </div>
        <div style={styles.cardSub}>
          Week 0 = week the ad runs (100% effect). Subsequent weeks show remaining influence.
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={adstock} margin={{ left: 10, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="week" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} domain={[0, 110]} />
            <Tooltip formatter={v => [`${v}%`, "Remaining effect"]}
              contentStyle={{ fontSize: 12, borderRadius: 6 }} />
            <Bar dataKey="effect" radius={[4, 4, 0, 0]}>
              {adstock.map((_, i) => (
                <Cell key={i} fill={COLORS[ch.channel]}
                  opacity={1 - (i / adstock.length) * 0.7} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

const styles = {
  selectorRow: { display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" },
  selBtn:      { padding: "6px 16px", borderRadius: 20, border: "1.5px solid", cursor: "pointer", fontSize: 12, fontWeight: 500, transition: "all .15s" },
  statRow:     { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 10, marginBottom: 14 },
  statCard:    { background: "#fff", border: "0.5px solid #e0e0e0", borderRadius: 10, padding: "12px 14px" },
  statLabel:   { fontSize: 11, color: "#888", marginBottom: 4 },
  statValue:   { fontSize: 20, fontWeight: 500, color: "#1a1a1a" },
  statSub:     { fontSize: 11, color: "#aaa", marginTop: 2 },
  card:        { background: "#fff", border: "0.5px solid #e0e0e0", borderRadius: 10, padding: 16, marginBottom: 14 },
  cardTitle:   { fontSize: 13, fontWeight: 500, color: "#1a1a1a", marginBottom: 4 },
  cardSub:     { fontSize: 11, color: "#888", marginBottom: 12, lineHeight: 1.5 },
  errorBox:    { background: "#FCE4D6", color: "#843C1D", padding: 14, borderRadius: 8, fontSize: 13 },
  emptyBox:    { background: "#F4F4F4", color: "#888", padding: "2rem", borderRadius: 8, textAlign: "center", fontSize: 13 },
};
