import { useState, useEffect } from "react";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

export default function ModelSettings() {
  const [runs,      setRuns]      = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [retraining,setRetraining]= useState(false);
  const [retainMsg, setRetainMsg] = useState(null);
  const [error,     setError]     = useState(null);

  const loadRuns = () => {
    setLoading(true);
    ApiService.getModelRuns()
      .then(r => setRuns(r.runs || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadRuns(); }, []);

  const handleRetrain = async () => {
    setRetraining(true);
    setRetainMsg(null);
    try {
      const res = await ApiService.triggerRetrain();
      setRetainMsg({ type: "ok", text: res.message || "Retrain started. Refresh in ~30 seconds." });
      setTimeout(() => loadRuns(), 35000);
    } catch (e) {
      setRetainMsg({ type: "err", text: `Error: ${e.message}` });
    } finally {
      setRetraining(false);
    }
  };

  const statusColor = { complete: "#1D6A38", failed: "#843C1D", running: "#7F6000", pending: "#888", reference: "#888" };
  const statusBg    = { complete: "#E2F0D9", failed: "#FCE4D6", running: "#FFF2CC", pending: "#F4F4F4", reference: "#F4F4F4" };

  if (loading) return <LoadingSpinner message="Loading model history..." />;

  const realRuns = runs.filter(r => !["holiday_ref","curve_ref"].includes(r.model_version));

  return (
    <div>
      {error && <div style={styles.errorBox}>Error: {error}</div>}

      {/* Retrain panel */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Model training</div>
        <p style={styles.body}>
          Runs the full MMM pipeline: adstock transforms → saturation → OLS regression →
          writes results to the database. The dashboard updates automatically after training completes.
        </p>
        <div style={styles.actionRow}>
          <button onClick={handleRetrain} disabled={retraining} style={styles.retainBtn}>
            {retraining ? "Starting..." : "Retrain model"}
          </button>
          <button onClick={loadRuns} style={styles.refreshBtn}>Refresh history</button>
        </div>
        {retainMsg && (
          <div style={{
            ...styles.retainMsg,
            background: retainMsg.type === "ok" ? "#E2F0D9" : "#FCE4D6",
            color:      retainMsg.type === "ok" ? "#1D6A38" : "#843C1D",
          }}>
            {retainMsg.text}
          </div>
        )}
      </div>

      {/* Model run history */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Model run history</div>
        {realRuns.length === 0 ? (
          <div style={styles.emptyText}>No model runs yet. Click "Retrain model" to start.</div>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                {["ID","Version","R² test","Status","Run at","Notes"].map(h => (
                  <th key={h} style={styles.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {realRuns.map((run, i) => (
                <tr key={run.id} style={{ background: i % 2 === 0 ? "#fff" : "#FAFAFA" }}>
                  <td style={styles.td}>{run.id}</td>
                  <td style={{ ...styles.td, fontFamily: "monospace", fontSize: 11 }}>{run.model_version}</td>
                  <td style={{ ...styles.td, fontWeight: 500, color: run.r_squared >= 0.85 ? "#1D6A38" : "#7F6000" }}>
                    {run.r_squared ? run.r_squared.toFixed(4) : "—"}
                  </td>
                  <td style={styles.td}>
                    <span style={{
                      fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 20,
                      background: statusBg[run.status] || "#F4F4F4",
                      color:      statusColor[run.status] || "#444",
                    }}>{run.status}</span>
                  </td>
                  <td style={{ ...styles.td, color: "#888", fontSize: 11 }}>
                    {run.run_at ? new Date(run.run_at).toLocaleString() : "—"}
                  </td>
                  <td style={{ ...styles.td, maxWidth: 280, fontSize: 11, color: "#595959", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {run.notes || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pipeline info */}
      <div style={styles.card}>
        <div style={styles.cardTitle}>Pipeline details</div>
        <div style={styles.pipelineGrid}>
          {[
            { step:"1", title:"Adstock transform", desc:"Applies geometric decay per channel to model carryover effects. TV λ=0.68, Search λ=0.12." },
            { step:"2", title:"Hill saturation",   desc:"Applies Hill function to model diminishing returns. Output scaled 0→1 per channel." },
            { step:"3", title:"Feature matrix",    desc:"Combines saturated spend with organic controls: competitor sales, newsletter, events, seasonality." },
            { step:"4", title:"OLS regression",    desc:"Trains LinearRegression on 80% of weeks, evaluates on held-out 20%. Writes R², MAE, coefficients." },
          ].map(p => (
            <div key={p.step} style={styles.pipelineStep}>
              <div style={styles.stepNum}>{p.step}</div>
              <div>
                <div style={styles.stepTitle}>{p.title}</div>
                <div style={styles.stepDesc}>{p.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const styles = {
  card:         { background:"#fff", border:"0.5px solid #e0e0e0", borderRadius:10, padding:16, marginBottom:14 },
  cardTitle:    { fontSize:13, fontWeight:500, color:"#1a1a1a", marginBottom:10 },
  body:         { fontSize:12, color:"#595959", lineHeight:1.6, marginBottom:12 },
  actionRow:    { display:"flex", gap:10, alignItems:"center", flexWrap:"wrap" },
  retainBtn:    { padding:"8px 20px", borderRadius:7, background:"#2E75B6", color:"#fff", border:"none", cursor:"pointer", fontSize:13, fontWeight:500 },
  refreshBtn:   { padding:"8px 16px", borderRadius:7, background:"transparent", color:"#2E75B6", border:"1px solid #2E75B6", cursor:"pointer", fontSize:13 },
  retainMsg:    { marginTop:10, padding:"8px 12px", borderRadius:6, fontSize:12 },
  emptyText:    { color:"#888", fontSize:13 },
  errorBox:     { background:"#FCE4D6", color:"#843C1D", padding:12, borderRadius:8, fontSize:13, marginBottom:12 },
  table:        { width:"100%", borderCollapse:"collapse", fontSize:12 },
  th:           { textAlign:"left", padding:"7px 10px", borderBottom:"1px solid #e0e0e0", fontSize:11, color:"#888", fontWeight:500 },
  td:           { padding:"8px 10px", borderBottom:"0.5px solid #f0f0f0", verticalAlign:"top" },
  pipelineGrid: { display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 },
  pipelineStep: { display:"flex", gap:10, alignItems:"flex-start", padding:"10px 12px", background:"#F8F9FA", borderRadius:7 },
  stepNum:      { width:22, height:22, borderRadius:"50%", background:"#2E75B6", color:"#fff", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, flexShrink:0 },
  stepTitle:    { fontSize:12, fontWeight:500, color:"#1a1a1a", marginBottom:3 },
  stepDesc:     { fontSize:11, color:"#595959", lineHeight:1.5 },
};
