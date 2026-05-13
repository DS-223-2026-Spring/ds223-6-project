import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, ReferenceLine,
  Area, AreaChart, Legend,
} from "recharts";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

const COLORS   = { search:"#2E75B6", facebook:"#5DCAA5", tv:"#7F77DD", ooh:"#EF9F27", print:"#D85A30" };
const ADSTOCK_DECAY = { tv:0.68, ooh:0.40, print:0.35, facebook:0.25, search:0.12 };

export default function ChannelDeepDive() {
  const [results,     setResults]     = useState(null);
  const [weeklyData,  setWeeklyData]  = useState(null);
  const [selected,    setSelected]    = useState("search");
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);

  useEffect(() => {
    Promise.all([
      ApiService.getResults(),
      ApiService.getChannelWeekly(),
    ])
      .then(([r, w]) => {
        setResults(r);
        setWeeklyData(w);
        if (r?.channels?.length) setSelected(r.channels[0].channel);
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <LoadingSpinner message="Loading channel data..." />;
  if (error)   return <div style={S.errorBox}>Error: {error}</div>;

  const channels = results?.channels ?? [];
  if (channels.length === 0)
    return <div style={S.emptyBox}>No model results yet. Train the model first.</div>;

  const ch       = channels.find(c => c.channel === selected) || channels[0];
  const color    = COLORS[ch.channel] || "#888";
  const decay    = ADSTOCK_DECAY[ch.channel] || 0.3;

  // ── Real weekly data from API ──────────────────────────────────────────────
  const chWeekly = weeklyData?.channels?.[ch.channel] || {};
  const weeks    = weeklyData?.weeks || [];

  // Subsample for chart readability (~40 points)
  const step       = Math.max(1, Math.floor(weeks.length / 40));
  const sampledWks = weeks.filter((_, i) => i % step === 0);

  const spendTimeline = sampledWks.map(w => ({
    week:    w.slice(0, 7),
    spend:   Math.round((chWeekly[w]?.spend || 0) / 1000),
    contrib: Math.round((chWeekly[w]?.contribution || 0) / 1000),
  }));

  // Real saturation curve from actual data points
  const satCurveData = sampledWks
    .map(w => ({
      adstock:   Math.round(chWeekly[w]?.adstock || 0),
      saturated: +(chWeekly[w]?.saturated || 0).toFixed(4),
      contrib:   Math.round(chWeekly[w]?.contribution || 0),
    }))
    .filter(d => d.adstock > 0)
    .sort((a, b) => a.adstock - b.adstock);

  // Adstock decay reference chart (8 weeks)
  const decayData = Array.from({ length: 9 }, (_, i) => ({
    week:   `Wk ${i}`,
    effect: Math.round(Math.pow(decay, i) * 100),
  }));

  // CI data if Bayesian model available
  const hasCI = ch.roi_lower_90 != null && ch.roi_upper_90 != null;

  return (
    <div>
      {/* Channel selector */}
      <div style={S.selectorRow}>
        {channels.map(c => (
          <button key={c.channel} onClick={() => setSelected(c.channel)}
            style={{
              ...S.selBtn,
              background:  selected === c.channel ? COLORS[c.channel] : "#F4F4F4",
              color:       selected === c.channel ? "#fff" : "#444",
              borderColor: COLORS[c.channel],
            }}>
            {c.channel.charAt(0).toUpperCase() + c.channel.slice(1)}
          </button>
        ))}
      </div>

      {/* Stat cards */}
      <div style={S.statGrid}>
        <div style={S.statCard}>
          <div style={S.statLabel}>ROI</div>
          <div style={{ ...S.statValue, color }}>
            {ch.roi_estimate ? `$${ch.roi_estimate.toFixed(2)}` : "—"}
          </div>
          {hasCI && (
            <div style={S.statSub}>
              90% CI: ${ch.roi_lower_90.toFixed(2)} – ${ch.roi_upper_90.toFixed(2)}
            </div>
          )}
        </div>
        <div style={S.statCard}>
          <div style={S.statLabel}>Revenue share</div>
          <div style={S.statValue}>
            {ch.contribution_pct ? `${ch.contribution_pct.toFixed(1)}%` : "—"}
          </div>
          {ch.predicted_revenue_contribution && (
            <div style={S.statSub}>
              ~${(ch.predicted_revenue_contribution / 1e6).toFixed(1)}M total
            </div>
          )}
        </div>
        <div style={S.statCard}>
          <div style={S.statLabel}>Recommendation</div>
          <div style={{
            ...S.statValue, fontSize:14, marginTop:4,
            color: ch.recommendation === "under-invested" ? "#1D6A38"
                 : ch.recommendation === "over-invested"  ? "#843C1D" : "#0C447C",
          }}>
            {ch.recommendation ?? "—"}
          </div>
        </div>
        <div style={S.statCard}>
          <div style={S.statLabel}>Adstock decay λ</div>
          <div style={S.statValue}>{decay.toFixed(2)}</div>
          <div style={S.statSub}>
            {decay >= 0.5 ? "Long carryover" : decay >= 0.3 ? "Medium" : "Short"}
          </div>
        </div>
      </div>

      {/* Saturation curve — real data */}
      <div style={S.card}>
        <div style={S.cardTitle}>
          Response (saturation) curve — real data from model
        </div>
        <div style={S.cardSub}>
          Each point is a week of real data. The curve shows how revenue contribution
          grows as adstock-transformed spend increases — the flattening shows
          where diminishing returns begin.
          {!satCurveData.length && " (Run baseline.py to populate)"}
        </div>
        {satCurveData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={satCurveData} margin={{ left:10, right:20 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="adstock"
                tickFormatter={v => `$${(v/1000).toFixed(0)}k`}
                tick={{ fontSize:10 }} label={{ value:"Adstock spend", position:"insideBottomRight", offset:-5, fontSize:10 }} />
              <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} tick={{ fontSize:11 }} />
              <Tooltip
                formatter={(v, n) => [`$${v.toLocaleString()}`, n === "contrib" ? "Revenue contribution" : n]}
                labelFormatter={l => `Adstock: $${Number(l).toLocaleString()}`}
                contentStyle={{ fontSize:12, borderRadius:6 }} />
              <Area type="monotone" dataKey="contrib" name="Revenue contribution"
                stroke={color} fill={color + "33"} strokeWidth={2} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={S.noData}>No feature data yet — train the model first.</div>
        )}
      </div>

      <div style={S.grid2}>
        {/* Adstock decay */}
        <div style={S.card}>
          <div style={S.cardTitle}>Adstock decay — λ = {decay}</div>
          <div style={S.cardSub}>
            How much of this week's ad effect carries over to future weeks.
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={decayData} margin={{ left:10, right:10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="week" tick={{ fontSize:11 }} />
              <YAxis tickFormatter={v => `${v}%`} tick={{ fontSize:11 }} domain={[0,110]} />
              <Tooltip formatter={v => [`${v}%`, "Remaining effect"]}
                contentStyle={{ fontSize:12, borderRadius:6 }} />
              <Bar dataKey="effect" radius={[4,4,0,0]}>
                {decayData.map((_, i) => (
                  <Cell key={i} fill={color} opacity={1 - (i / decayData.length) * 0.75} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Weekly spend vs contribution */}
        <div style={S.card}>
          <div style={S.cardTitle}>Weekly spend vs revenue contribution</div>
          <div style={S.cardSub}>
            Bars = actual spend. Line = estimated revenue contribution from this channel.
          </div>
          {spendTimeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={spendTimeline} margin={{ left:0, right:10 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="week" tick={{ fontSize:9 }}
                  interval={Math.floor(spendTimeline.length / 5)} />
                <YAxis tickFormatter={v => `$${v}k`} tick={{ fontSize:11 }} />
                <Tooltip formatter={(v, n) => [`$${v}k`, n === "spend" ? "Spend" : "Revenue contrib"]}
                  contentStyle={{ fontSize:12, borderRadius:6 }} />
                <Legend wrapperStyle={{ fontSize:11 }} />
                <Bar dataKey="spend" name="Spend" fill={color + "88"} radius={[2,2,0,0]} />
                <Line type="monotone" dataKey="contrib" name="Revenue contrib"
                  stroke={color} strokeWidth={2} dot={false} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={S.noData}>No weekly data yet.</div>
          )}
        </div>
      </div>

      {/* Bayesian CI card — shown only when Bayesian model available */}
      {hasCI && (
        <div style={{ ...S.card, background:"#EBF3FB" }}>
          <div style={S.cardTitle}>Bayesian credible interval (90% CI)</div>
          <div style={S.cardSub}>
            The Bayesian model (PyMC) sampled the posterior distribution of this
            channel's ROI. Instead of a single point estimate, we get a range of
            plausible values.
          </div>
          <div style={S.ciRow}>
            <div style={S.ciBox}>
              <div style={S.ciLabel}>Lower bound (5th percentile)</div>
              <div style={{ ...S.ciValue, color:"#843C1D" }}>
                ${ch.roi_lower_90.toFixed(2)} / $1
              </div>
            </div>
            <div style={S.ciBox}>
              <div style={S.ciLabel}>Point estimate (posterior mean)</div>
              <div style={{ ...S.ciValue, color }}>
                ${ch.roi_estimate.toFixed(2)} / $1
              </div>
            </div>
            <div style={S.ciBox}>
              <div style={S.ciLabel}>Upper bound (95th percentile)</div>
              <div style={{ ...S.ciValue, color:"#1D6A38" }}>
                ${ch.roi_upper_90.toFixed(2)} / $1
              </div>
            </div>
          </div>
          <div style={{ fontSize:11, color:"#595959", marginTop:8 }}>
            The true ROI is likely between ${ch.roi_lower_90.toFixed(2)} and
            ${ch.roi_upper_90.toFixed(2)} with 90% probability.
            A narrower interval = higher model confidence in this channel's ROI.
          </div>
        </div>
      )}
    </div>
  );
}

const S = {
  selectorRow: { display:"flex", gap:8, marginBottom:16, flexWrap:"wrap" },
  selBtn:      { padding:"6px 16px", borderRadius:20, border:"1.5px solid", cursor:"pointer", fontSize:12, fontWeight:500, transition:"all .15s" },
  statGrid:    { display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10, marginBottom:14 },
  statCard:    { background:"#fff", border:"0.5px solid #e0e0e0", borderRadius:10, padding:"12px 14px" },
  statLabel:   { fontSize:11, color:"#888", marginBottom:4 },
  statValue:   { fontSize:20, fontWeight:500, color:"#1a1a1a" },
  statSub:     { fontSize:11, color:"#aaa", marginTop:2 },
  card:        { background:"#fff", border:"0.5px solid #e0e0e0", borderRadius:10, padding:16, marginBottom:14 },
  cardTitle:   { fontSize:13, fontWeight:500, color:"#1a1a1a", marginBottom:4 },
  cardSub:     { fontSize:11, color:"#888", marginBottom:12, lineHeight:1.5 },
  grid2:       { display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 },
  ciRow:       { display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:10, marginTop:8 },
  ciBox:       { textAlign:"center", padding:"10px", background:"#fff", borderRadius:8 },
  ciLabel:     { fontSize:11, color:"#595959", marginBottom:4 },
  ciValue:     { fontSize:18, fontWeight:500 },
  errorBox:    { background:"#FCE4D6", color:"#843C1D", padding:14, borderRadius:8, fontSize:13 },
  emptyBox:    { background:"#F4F4F4", color:"#888", padding:"2rem", borderRadius:8, textAlign:"center", fontSize:13 },
  noData:      { color:"#888", fontSize:12, textAlign:"center", padding:"1rem" },
};
