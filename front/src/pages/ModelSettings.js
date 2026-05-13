import { useState, useEffect, useRef } from "react";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

export default function ModelSettings() {
  const [runs,        setRuns]        = useState([]);
  const [modelTypes,  setModelTypes]  = useState(null);
  const [pipelineRuns,setPipelineRuns] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [retraining,  setRetraining]  = useState(false);
  const [retainMsg,   setRetainMsg]   = useState(null);
  const [error,       setError]       = useState(null);
  const pollRef = useRef(null);

  const loadAll = () => {
    return Promise.all([
      ApiService.getModelRuns(),
      ApiService.getPipelineRuns(),
      ApiService.getModelTypes(),
    ]).then(([m, p, t]) => {
      setRuns(m.runs || []);
      setPipelineRuns(p.runs || []);
      setModelTypes(t);
    });
  };

  useEffect(() => {
    loadAll().catch(e => setError(e.message)).finally(() => setLoading(false));
    return () => clearInterval(pollRef.current);
  }, []);

  const startPolling = (expectedCount) => {
    pollRef.current = setInterval(async () => {
      try {
        const m = await ApiService.getModelRuns();
        const realRuns = (m.runs || []).filter(
          r => !["holiday_ref","curve_ref"].includes(r.model_version)
        );
        if (realRuns.length > expectedCount) {
          clearInterval(pollRef.current);
          setRuns(m.runs || []);
          setRetraining(false);
          setRetainMsg({ type:"ok", text:"Retrain complete — new model run added." });
          loadAll();
        }
      } catch (e) { clearInterval(pollRef.current); }
    }, 5000);
  };

  const [bayesLoading,  setBayesLoading]  = useState(false);
  const [bayesMsg,      setBayesMsg]      = useState(null);
  const [bayesRuns,     setBayesRuns]     = useState(500);

  const handleRetrainBayesian = async () => {
    setBayesLoading(true);
    setBayesMsg(null);
    const currentRealCount = runs.filter(
      r => !["holiday_ref","curve_ref"].includes(r.model_version)
    ).length;
    try {
      const res = await ApiService.retrainBayesian(Number(bayesRuns));
      setBayesMsg({ type:"ok", text: res.message || "Bayesian retrain started (~3 min). Polling..." });
      startPolling(currentRealCount);
    } catch (e) {
      setBayesMsg({ type:"err", text:`Error: ${e.message}` });
      setBayesLoading(false);
    }
  };

  const handleRetrain = async () => {
    setRetraining(true);
    setRetainMsg(null);
    const currentRealCount = runs.filter(
      r => !["holiday_ref","curve_ref"].includes(r.model_version)
    ).length;
    try {
      const res = await ApiService.triggerRetrain();
      setRetainMsg({ type:"ok", text: res.message || "Retrain started. Polling for completion..." });
      startPolling(currentRealCount);
    } catch (e) {
      setRetainMsg({ type:"err", text:`Error: ${e.message}` });
      setRetraining(false);
    }
  };

  const statusColor = { complete:"#1D6A38", failed:"#843C1D", running:"#7F6000", pending:"#888", reference:"#888", success:"#1D6A38" };
  const statusBg    = { complete:"#E2F0D9", failed:"#FCE4D6", running:"#FFF2CC", pending:"#F4F4F4", reference:"#F4F4F4", success:"#E2F0D9" };

  const realRuns = runs.filter(r => !["holiday_ref","curve_ref"].includes(r.model_version));

  if (loading) return <LoadingSpinner message="Loading model history..." />;

  return (
    <div>
      {error && <div style={S.errorBox}>Error: {error}</div>}

      {/* Retrain panel */}
      <div style={S.card}>
        <div style={S.cardTitle}>Model training</div>
        <p style={S.body}>
          Runs the full MMM pipeline: adstock transforms → saturation → OLS regression
          with organic controls → writes results to the database. After retraining, the
          dashboard updates with new ROI scores and recommendations.
        </p>
        <div style={S.actionRow}>
          <button onClick={handleRetrain} disabled={retraining} style={S.retainBtn}>
            {retraining ? "⟳ Training..." : "Retrain model"}
          </button>
          <button onClick={() => loadAll()} style={S.refreshBtn}>↻ Refresh</button>
        </div>
        {retainMsg && (
          <div style={{
            ...S.msg,
            background: retainMsg.type === "ok" ? "#E2F0D9" : "#FCE4D6",
            color:      retainMsg.type === "ok" ? "#1D6A38" : "#843C1D",
          }}>
            {retainMsg.text}
            {retraining && <span style={{ marginLeft:8, fontSize:11, color:"#595959" }}>
              Checking every 5 seconds...
            </span>}
          </div>
        )}
      </div>

      {/* Model run history */}
      <div style={S.card}>
        <div style={S.cardTitle}>Model run history</div>
        {realRuns.length === 0 ? (
          <div style={S.emptyText}>No model runs yet. Click "Retrain model" to start.</div>
        ) : (
          <div style={{ overflowX:"auto" }}>
            <table style={S.table}>
              <thead>
                <tr>{["ID","Version","R² test","Status","Run at","Notes"].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {realRuns.map((run, i) => (
                  <tr key={run.id} style={{ background: i%2===0?"#fff":"#FAFAFA" }}>
                    <td style={S.td}>{run.id}</td>
                    <td style={{ ...S.td, fontFamily:"monospace", fontSize:11 }}>{run.model_version}</td>
                    <td style={{ ...S.td, fontWeight:500,
                      color: run.r_squared >= 0.9 ? "#1D6A38" : run.r_squared >= 0.8 ? "#7F6000" : "#843C1D" }}>
                      {run.r_squared ? run.r_squared.toFixed(4) : "—"}
                    </td>
                    <td style={S.td}>
                      <span style={{
                        fontSize:11, fontWeight:500, padding:"2px 8px", borderRadius:20,
                        background: statusBg[run.status]  || "#F4F4F4",
                        color:      statusColor[run.status]|| "#444",
                      }}>{run.status}</span>
                    </td>
                    <td style={{ ...S.td, color:"#888", fontSize:11 }}>
                      {run.run_at ? new Date(run.run_at).toLocaleString() : "—"}
                    </td>
                    <td style={{ ...S.td, maxWidth:260, fontSize:11, color:"#595959",
                      overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                      {run.notes || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pipeline run log */}
      <div style={S.card}>
        <div style={S.cardTitle}>Pipeline run log (Prefect + manual)</div>
        {pipelineRuns.length === 0 ? (
          <div style={S.emptyText}>
            No pipeline runs logged yet. Run{" "}
            <code style={S.code}>docker exec mmm_orch python pipeline_flow.py</code>
          </div>
        ) : (
          <div style={{ overflowX:"auto" }}>
            <table style={S.table}>
              <thead>
                <tr>{["Flow","Status","Started","Duration","Spend rows","Model run","Error"].map(h => (
                  <th key={h} style={S.th}>{h}</th>
                ))}</tr>
              </thead>
              <tbody>
                {pipelineRuns.map((run, i) => {
                  const started  = run.started_at  ? new Date(run.started_at)  : null;
                  const finished = run.finished_at ? new Date(run.finished_at) : null;
                  const durationS = started && finished
                    ? Math.round((finished - started) / 1000)
                    : null;
                  return (
                    <tr key={run.id} style={{ background: i%2===0?"#fff":"#FAFAFA" }}>
                      <td style={{ ...S.td, fontFamily:"monospace", fontSize:11 }}>{run.flow_name}</td>
                      <td style={S.td}>
                        <span style={{
                          fontSize:11, fontWeight:500, padding:"2px 8px", borderRadius:20,
                          background: statusBg[run.status]  || "#F4F4F4",
                          color:      statusColor[run.status]|| "#444",
                        }}>{run.status}</span>
                      </td>
                      <td style={{ ...S.td, fontSize:11, color:"#888" }}>
                        {started ? started.toLocaleString() : "—"}
                      </td>
                      <td style={{ ...S.td, fontSize:11 }}>
                        {durationS !== null ? `${durationS}s` : "—"}
                      </td>
                      <td style={{ ...S.td, fontSize:11 }}>{run.spend_rows ?? "—"}</td>
                      <td style={{ ...S.td, fontSize:11 }}>
                        {run.model_run_id ? `#${run.model_run_id}` : "—"}
                      </td>
                      <td style={{ ...S.td, fontSize:11, color:"#843C1D", maxWidth:200,
                        overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {run.error_msg || "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Model type selector */}
      <div style={S.card}>
        <div style={S.cardTitle}>Model type</div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14 }}>
          {/* OLS */}
          <div style={{
            ...S.modelCard,
            borderColor: modelTypes?.current === "ols" ? "#2E75B6" : "#e0e0e0",
            background:  modelTypes?.current === "ols" ? "#EBF3FB" : "#fff",
          }}>
            <div style={S.modelName}>OLS Regression</div>
            <div style={S.modelDesc}>
              Fast (~30 seconds). Point estimate only. Good for rapid iteration
              and initial exploration. Currently {modelTypes?.current === "ols" ? "active" : "inactive"}.
            </div>
            <div style={S.actionRow}>
              <button onClick={handleRetrain} disabled={retraining} style={S.retainBtn}>
                {retraining ? "⟳ Training..." : "Retrain OLS"}
              </button>
            </div>
            {retainMsg && (
              <div style={{
                ...S.msg, marginTop:8,
                background: retainMsg.type==="ok" ? "#E2F0D9" : "#FCE4D6",
                color:      retainMsg.type==="ok" ? "#1D6A38" : "#843C1D",
              }}>
                {retainMsg.text}
                {retraining && <span style={{ marginLeft:6, fontSize:11, color:"#595959" }}>Checking every 5s...</span>}
              </div>
            )}
          </div>
          {/* Bayesian */}
          <div style={{
            ...S.modelCard,
            borderColor: modelTypes?.current === "bayesian" ? "#7F77DD" : "#e0e0e0",
            background:  modelTypes?.current === "bayesian" ? "#F0EFFE" : "#fff",
          }}>
            <div style={{ ...S.modelName, color:"#3C3489" }}>Bayesian (PyMC)</div>
            <div style={S.modelDesc}>
              Slower (~3 minutes). Produces 90% credible intervals per channel — shows
              uncertainty in ROI estimates. Currently {modelTypes?.current === "bayesian" ? "active" : "inactive"}.
            </div>
            <div style={{ marginBottom: 14 }}>
              <label
                style={{
                  display: "block",
                  fontSize: 12,
                  fontWeight: 600,
                  color: "#444",
                  marginBottom: 6,
                }}
              >
                Bayesian sampling draws
              </label>

              <input
                type="number"
                min="100"
                step="100"
                value={bayesRuns}
                onChange={(e) => setBayesRuns(e.target.value)}
                style={{
                  width: 110,
                  padding: "8px 10px",
                  borderRadius: 6,
                  border: "1px solid #D0D0D0",
                  fontSize: 13,
                  background: "#fff",
                }}
              />

              <div style={{ fontSize: 11, color: "#777", marginTop: 4 }}>
                Higher values improve posterior stability but increase runtime.
              </div>
            </div>
            <div style={S.actionRow}>
              <button
                onClick={handleRetrainBayesian}
                disabled={bayesLoading}
                style={S.retainBtn}
              >
                {bayesLoading ? "⟳ Bayesian training..." : "Retrain Bayesian"}
              </button>
            </div>
            {bayesMsg && (
              <div style={{
                ...S.msg, marginTop:8,
                background: bayesMsg.type==="ok" ? "#E2F0D9" : "#FCE4D6",
                color:      bayesMsg.type==="ok" ? "#1D6A38" : "#843C1D",
              }}>
                {bayesMsg.text}
              </div>
            )}
          </div>
        </div>
        {modelTypes?.note && (
          <div style={{ fontSize:11, color:"#888", marginTop:10 }}>{modelTypes.note}</div>
        )}
      </div>

      {/* Pipeline step explainer */}
      <div style={S.card}>
        <div style={S.cardTitle}>Pipeline steps</div>
        <div style={S.pipelineGrid}>
          {[
            { n:"1", title:"Adstock",   desc:"Geometric decay per channel (TV λ=0.68, Search λ=0.12). Models carryover effect." },
            { n:"2", title:"Saturation",desc:"Hill function per channel. Models diminishing returns. Output scaled 0→1." },
            { n:"3", title:"Features",  desc:"Joins organic controls (competitor sales, newsletter, events) + seasonality (Q4, month)." },
            { n:"4", title:"OLS Model", desc:"80/20 time-series split. Writes R², coefficients, ROI, recommendations, and weekly predictions to DB." },
          ].map(p => (
            <div key={p.n} style={S.stepCard}>
              <div style={S.stepNum}>{p.n}</div>
              <div>
                <div style={S.stepTitle}>{p.title}</div>
                <div style={S.stepDesc}>{p.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const S = {
  card:        { background:"#fff", border:"0.5px solid #e0e0e0", borderRadius:10, padding:16, marginBottom:14 },
  cardTitle:   { fontSize:13, fontWeight:500, color:"#1a1a1a", marginBottom:10 },
  body:        { fontSize:12, color:"#595959", lineHeight:1.6, marginBottom:12 },
  actionRow:   { display:"flex", gap:10, flexWrap:"wrap", alignItems:"center" },
  retainBtn:   { padding:"8px 20px", borderRadius:7, background:"#2E75B6", color:"#fff", border:"none", cursor:"pointer", fontSize:13, fontWeight:500 },
  refreshBtn:  { padding:"8px 16px", borderRadius:7, background:"transparent", color:"#2E75B6", border:"1px solid #2E75B6", cursor:"pointer", fontSize:13 },
  msg:         { marginTop:10, padding:"8px 12px", borderRadius:6, fontSize:12 },
  emptyText:   { color:"#888", fontSize:13 },
  errorBox:    { background:"#FCE4D6", color:"#843C1D", padding:12, borderRadius:8, fontSize:13, marginBottom:12 },
  table:       { width:"100%", borderCollapse:"collapse", fontSize:12 },
  th:          { textAlign:"left", padding:"7px 10px", borderBottom:"1px solid #e0e0e0", fontSize:11, color:"#888", fontWeight:500, whiteSpace:"nowrap" },
  td:          { padding:"8px 10px", borderBottom:"0.5px solid #f0f0f0", verticalAlign:"top" },
  pipelineGrid:{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 },
  stepCard:    { display:"flex", gap:10, alignItems:"flex-start", padding:"10px 12px", background:"#F8F9FA", borderRadius:7 },
  stepNum:     { width:22, height:22, borderRadius:"50%", background:"#2E75B6", color:"#fff", display:"flex", alignItems:"center", justifyContent:"center", fontSize:11, fontWeight:700, flexShrink:0 },
  stepTitle:   { fontSize:12, fontWeight:500, color:"#1a1a1a", marginBottom:3 },
  stepDesc:    { fontSize:11, color:"#595959", lineHeight:1.5 },
  code:        { background:"#e8e8e8", padding:"1px 6px", borderRadius:4, fontFamily:"monospace", fontSize:11 },
  modelCard:   { border:"1.5px solid", borderRadius:10, padding:14, transition:"all .2s" },
  modelName:   { fontSize:13, fontWeight:600, color:"#1a1a1a", marginBottom:6 },
  modelDesc:   { fontSize:12, color:"#595959", lineHeight:1.55, marginBottom:12 },
};
