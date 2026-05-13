import { useState, useEffect, useCallback, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, Legend,
} from "recharts";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

const CHANNELS = ["tv","ooh","print","facebook","search"];
const COLORS   = { search:"#2E75B6", facebook:"#5DCAA5", tv:"#7F77DD", ooh:"#EF9F27", print:"#D85A30" };
const CH_LABEL = { tv:"TV", ooh:"OOH", print:"Print", facebook:"Facebook", search:"Search" };

export default function BudgetOptimizer() {
  const [totalBudget,  setTotalBudget]  = useState(100000);
  const [allocation,   setAllocation]   = useState({});
  const [predRevenue,  setPredRevenue]  = useState(null);
  const [optLoading,   setOptLoading]   = useState(false);
  const [saveLoading,  setSaveLoading]  = useState(false);
  const [scenarios,    setScenarios]    = useState([]);
  const [scenName,     setScenName]     = useState("");
  const [saveMsg,      setSaveMsg]      = useState(null);
  const [initLoading,  setInitLoading]  = useState(true);
  const [compareIds,   setCompareIds]   = useState([]);
  const [error,        setError]        = useState(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    ApiService.getScenarios()
      .then(r => setScenarios(r.scenarios || []))
      .catch(e => setError(e.message))
      .finally(() => setInitLoading(false));
  }, []);

  const runOptimizer = useCallback((budget) => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setOptLoading(true);
      try {
        const res = await ApiService.optimize(budget, null);
        setAllocation(res.allocation || {});
        setPredRevenue(res.predicted_revenue);
        if (res.note) setSaveMsg({ type:"info", text: res.note });
      } catch (e) { setError(e.message); }
      finally { setOptLoading(false); }
    }, 400);
  }, []);

  useEffect(() => {
    if (totalBudget > 0) runOptimizer(totalBudget);
  }, [totalBudget, runOptimizer]);

  const handleSave = async () => {
    if (!scenName.trim()) { setSaveMsg({ type:"warn", text:"Enter a scenario name first." }); return; }
    setSaveLoading(true);
    try {
      await ApiService.saveScenario(scenName.trim(), totalBudget, allocation, predRevenue);
      const updated = await ApiService.getScenarios();
      setScenarios(updated.scenarios || []);
      setSaveMsg({ type:"ok", text:`"${scenName.trim()}" saved!` });
      setScenName("");
      setTimeout(() => setSaveMsg(null), 3000);
    } catch (e) { setSaveMsg({ type:"err", text:`Error: ${e.message}` }); }
    finally { setSaveLoading(false); }
  };

  const handleDelete = async (id) => {
    try {
      await ApiService.deleteScenario(id);
      setScenarios(prev => prev.filter(s => s.id !== id));
      setCompareIds(prev => prev.filter(i => i !== id));
    } catch (e) { setError(e.message); }
  };

  const toggleCompare = (id) => {
    setCompareIds(prev =>
      prev.includes(id)
        ? prev.filter(i => i !== id)
        : prev.length < 3 ? [...prev, id] : prev
    );
  };

  const allocTotal = Object.values(allocation).reduce((s,v) => s+(v||0), 0);
  const chartData  = CHANNELS.map(ch => ({
    name: CH_LABEL[ch], spend: allocation[ch] ? Math.round(allocation[ch]) : 0, channel: ch,
  }));

  // Scenario comparison data
  const compareScenarios = scenarios.filter(s => compareIds.includes(s.id));

  if (initLoading) return <LoadingSpinner message="Loading optimizer..." />;

  return (
    <div>
      {error && <div style={S.errorBox}>Error: {error}</div>}

      <div style={S.grid2}>
        {/* Left: controls */}
        <div>
          <div style={S.card}>
            <div style={S.cardTitle}>Total budget</div>
            <div style={S.budgetRow}>
              <span style={S.budgetCurrency}>$</span>
              <input type="number" min={1000} max={10000000} step={1000}
                value={totalBudget}
                onChange={e => setTotalBudget(Math.max(0, Number(e.target.value)))}
                style={S.budgetInput} />
            </div>
            <input type="range" min={10000} max={500000} step={5000}
              value={Math.min(totalBudget, 500000)}
              onChange={e => setTotalBudget(Number(e.target.value))}
              style={{ width:"100%", marginTop:8 }} />
            <div style={S.rangeLabels}><span>$10k</span><span>$500k</span></div>
          </div>

          <div style={{ ...S.card, background: predRevenue ? "#E2F0D9" : "#F4F4F4" }}>
            <div style={S.cardTitle}>Predicted weekly revenue</div>
            {optLoading
              ? <div style={{ color:"#888", fontSize:13 }}>Calculating...</div>
              : <div style={S.predRevenue}>{predRevenue ? `$${predRevenue.toLocaleString()}` : "—"}</div>
            }
            {predRevenue && totalBudget > 0 && (
              <div style={S.roiHint}>
                ROI: ${(predRevenue/totalBudget).toFixed(2)} per $1 spent
              </div>
            )}
          </div>

          <div style={S.card}>
            <div style={S.cardTitle}>Save this scenario</div>
            <div style={S.saveRow}>
              <input type="text" placeholder="e.g. Q4 search-heavy"
                value={scenName} onChange={e => setScenName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSave()}
                style={S.nameInput} />
              <button onClick={handleSave} disabled={saveLoading} style={S.saveBtn}>
                {saveLoading ? "Saving..." : "Save"}
              </button>
            </div>
            {saveMsg && (
              <div style={{
                ...S.saveMsg,
                background: saveMsg.type==="ok" ? "#E2F0D9" : saveMsg.type==="err" ? "#FCE4D6" : "#FFF2CC",
                color:      saveMsg.type==="ok" ? "#1D6A38" : saveMsg.type==="err" ? "#843C1D" : "#7F6000",
              }}>{saveMsg.text}</div>
            )}
          </div>
        </div>

        {/* Right: allocation chart */}
        <div style={S.card}>
          <div style={S.cardHeader}>
            <span style={S.cardTitle}>
              Optimal allocation
              {optLoading && <span style={S.calcBadge}> Calculating...</span>}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ left:0, right:10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize:11 }} />
              <YAxis tickFormatter={v=>`$${(v/1000).toFixed(0)}k`} tick={{ fontSize:11 }} />
              <Tooltip formatter={v=>[`$${v.toLocaleString()}`,"Spend"]}
                contentStyle={{ fontSize:12, borderRadius:6 }} />
              <Bar dataKey="spend" radius={[4,4,0,0]}>
                {chartData.map(e => <Cell key={e.channel} fill={COLORS[e.channel]||"#888"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ marginTop:10 }}>
            {CHANNELS.map(ch => (
              <div key={ch} style={S.allocRow}>
                <span style={{ ...S.dot, background: COLORS[ch] }} />
                <span style={S.chLabel}>{CH_LABEL[ch]}</span>
                <span style={S.allocAmt}>
                  ${(allocation[ch]||0).toLocaleString(undefined,{maximumFractionDigits:0})}
                </span>
                <span style={S.allocPct}>
                  {allocTotal>0 ? `${((allocation[ch]||0)/allocTotal*100).toFixed(1)}%` : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Saved scenarios table */}
      {scenarios.length > 0 && (
        <div style={S.card}>
          <div style={S.cardHeader}>
            <span style={S.cardTitle}>Saved scenarios</span>
            <span style={{ fontSize:11, color:"#888" }}>
              Select up to 3 to compare side by side
            </span>
          </div>
          <div style={{ overflowX:"auto" }}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>Compare</th>
                  <th style={S.th}>Name</th>
                  <th style={S.th}>Budget</th>
                  <th style={S.th}>Predicted revenue</th>
                  {CHANNELS.map(ch => <th key={ch} style={S.th}>{CH_LABEL[ch]}</th>)}
                  <th style={S.th}></th>
                </tr>
              </thead>
              <tbody>
                {scenarios.map((s, i) => (
                  <tr key={s.id} style={{
                    background: compareIds.includes(s.id) ? "#EBF3FB" : i%2===0 ? "#fff" : "#FAFAFA"
                  }}>
                    <td style={{ ...S.td, textAlign:"center" }}>
                      <input type="checkbox"
                        checked={compareIds.includes(s.id)}
                        onChange={() => toggleCompare(s.id)}
                        disabled={!compareIds.includes(s.id) && compareIds.length >= 3}
                      />
                    </td>
                    <td style={{ ...S.td, fontWeight:500 }}>{s.scenario_name || "—"}</td>
                    <td style={S.td}>
                      ${(s.total_budget||0).toLocaleString(undefined,{maximumFractionDigits:0})}
                    </td>
                    <td style={{ ...S.td, color:"#1D6A38", fontWeight:500 }}>
                      {s.predicted_revenue
                        ? `$${s.predicted_revenue.toLocaleString(undefined,{maximumFractionDigits:0})}`
                        : "—"}
                    </td>
                    {CHANNELS.map(ch => (
                      <td key={ch} style={{ ...S.td, fontSize:11, color:"#595959" }}>
                        ${((s.allocation?.[ch]||0)/1000).toFixed(1)}k
                      </td>
                    ))}
                    <td style={S.td}>
                      <button onClick={() => handleDelete(s.id)} style={S.delBtn}>✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Side-by-side comparison */}
      {compareScenarios.length >= 2 && (
        <div style={S.card}>
          <div style={S.cardTitle}>
            Scenario comparison — {compareScenarios.map(s => s.scenario_name).join(" vs ")}
          </div>
          <div style={{ display:"grid", gridTemplateColumns:`repeat(${compareScenarios.length},1fr)`, gap:14, marginBottom:16 }}>
            {compareScenarios.map(s => (
              <div key={s.id} style={S.compareCard}>
                <div style={S.compareName}>{s.scenario_name}</div>
                <div style={S.compareBudget}>
                  ${(s.total_budget||0).toLocaleString(undefined,{maximumFractionDigits:0})} budget
                </div>
                <div style={S.compareRevenue}>
                  {s.predicted_revenue
                    ? `$${s.predicted_revenue.toLocaleString(undefined,{maximumFractionDigits:0})}`
                    : "—"}
                  <span style={S.compareRevLabel}> predicted</span>
                </div>
                {s.total_budget > 0 && s.predicted_revenue && (
                  <div style={S.compareRoi}>
                    ROI: ${(s.predicted_revenue/s.total_budget).toFixed(2)}/dollar
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Grouped bar chart comparing allocations */}
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={CHANNELS.map(ch => {
                const row = { channel: CH_LABEL[ch] };
                compareScenarios.forEach(s => {
                  row[s.scenario_name] = Math.round((s.allocation?.[ch]||0)/1000);
                });
                return row;
              })}
              margin={{ left:0, right:10 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="channel" tick={{ fontSize:11 }} />
              <YAxis tickFormatter={v=>`$${v}k`} tick={{ fontSize:11 }} />
              <Tooltip formatter={(v,n)=>[`$${v}k`, n]}
                contentStyle={{ fontSize:12, borderRadius:6 }} />
              <Legend wrapperStyle={{ fontSize:11 }} />
              {compareScenarios.map((s, i) => (
                <Bar key={s.id} dataKey={s.scenario_name}
                  fill={["#2E75B6","#EF9F27","#5DCAA5"][i]}
                  radius={[3,3,0,0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

const S = {
  grid2:          { display:"grid", gridTemplateColumns:"1fr 1.4fr", gap:14, marginBottom:14 },
  card:           { background:"#fff", border:"0.5px solid #e0e0e0", borderRadius:10, padding:16, marginBottom:14 },
  cardHeader:     { display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:12 },
  cardTitle:      { fontSize:13, fontWeight:500, color:"#1a1a1a" },
  budgetRow:      { display:"flex", alignItems:"center", gap:6 },
  budgetCurrency: { fontSize:18, color:"#595959" },
  budgetInput:    { flex:1, fontSize:22, fontWeight:500, border:"none", outline:"none", background:"transparent", color:"#1F4E79" },
  rangeLabels:    { display:"flex", justifyContent:"space-between", fontSize:10, color:"#aaa", marginTop:2 },
  predRevenue:    { fontSize:28, fontWeight:500, color:"#1D6A38" },
  roiHint:        { fontSize:11, color:"#595959", marginTop:4 },
  saveRow:        { display:"flex", gap:8 },
  nameInput:      { flex:1, padding:"7px 10px", borderRadius:6, border:"1px solid #ddd", fontSize:12 },
  saveBtn:        { padding:"7px 18px", borderRadius:6, background:"#2E75B6", color:"#fff", border:"none", cursor:"pointer", fontSize:12, fontWeight:500 },
  saveMsg:        { marginTop:8, padding:"5px 10px", borderRadius:5, fontSize:12 },
  calcBadge:      { fontSize:10, color:"#888", fontWeight:400 },
  allocRow:       { display:"flex", alignItems:"center", gap:8, padding:"5px 0", borderBottom:"0.5px solid #f0f0f0" },
  dot:            { width:10, height:10, borderRadius:"50%", flexShrink:0 },
  chLabel:        { flex:1, fontSize:12, color:"#444" },
  allocAmt:       { fontSize:12, fontWeight:500, minWidth:70, textAlign:"right" },
  allocPct:       { fontSize:11, color:"#888", minWidth:40, textAlign:"right" },
  table:          { width:"100%", borderCollapse:"collapse", fontSize:12 },
  th:             { textAlign:"left", padding:"7px 10px", borderBottom:"1px solid #e0e0e0", fontSize:11, color:"#888", fontWeight:500, whiteSpace:"nowrap" },
  td:             { padding:"8px 10px", borderBottom:"0.5px solid #f0f0f0", verticalAlign:"middle" },
  delBtn:         { background:"none", border:"none", cursor:"pointer", color:"#aaa", fontSize:13, padding:0 },
  errorBox:       { background:"#FCE4D6", color:"#843C1D", padding:12, borderRadius:8, fontSize:13, marginBottom:12 },
  compareCard:    { background:"#F8F9FA", borderRadius:8, padding:"14px 16px", textAlign:"center" },
  compareName:    { fontSize:13, fontWeight:500, color:"#1a1a1a", marginBottom:6 },
  compareBudget:  { fontSize:11, color:"#888", marginBottom:6 },
  compareRevenue: { fontSize:22, fontWeight:500, color:"#1D6A38" },
  compareRevLabel:{ fontSize:11, fontWeight:400, color:"#888" },
  compareRoi:     { fontSize:11, color:"#595959", marginTop:4 },
};
