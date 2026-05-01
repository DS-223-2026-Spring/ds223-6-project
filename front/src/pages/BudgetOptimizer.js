import { useState, useEffect, useCallback, useRef } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import LoadingSpinner from "../components/LoadingSpinner";
import ApiService from "../components/ApiService";

const CHANNELS = ["tv", "ooh", "print", "facebook", "search"];
const COLORS   = { search:"#2E75B6", facebook:"#5DCAA5", tv:"#7F77DD", ooh:"#EF9F27", print:"#D85A30" };
const CHANNEL_LABELS = { tv:"TV", ooh:"OOH", print:"Print", facebook:"Facebook", search:"Search" };

export default function BudgetOptimizer() {
  const [totalBudget,   setTotalBudget]   = useState(100000);
  const [allocation,    setAllocation]    = useState({});
  const [predRevenue,   setPredRevenue]   = useState(null);
  const [optLoading,    setOptLoading]    = useState(false);
  const [saveLoading,   setSaveLoading]   = useState(false);
  const [scenarios,     setScenarios]     = useState([]);
  const [scenName,      setScenName]      = useState("");
  const [saveMsg,       setSaveMsg]       = useState(null);
  const [initLoading,   setInitLoading]   = useState(true);
  const [error,         setError]         = useState(null);
  const debounceRef = useRef(null);

  // Load existing scenarios on mount
  useEffect(() => {
    ApiService.getScenarios()
      .then(r => setScenarios(r.scenarios || []))
      .catch(e => setError(e.message))
      .finally(() => setInitLoading(false));
  }, []);

  // Debounced optimizer call — fires 400ms after last slider change
  const runOptimizer = useCallback((budget, constraints) => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setOptLoading(true);
      try {
        const res = await ApiService.optimize(budget, constraints || null);
        setAllocation(res.allocation || {});
        setPredRevenue(res.predicted_revenue);
      } catch (e) {
        setError(e.message);
      } finally {
        setOptLoading(false);
      }
    }, 400);
  }, []);

  // Run optimizer whenever total budget changes
  useEffect(() => {
    if (totalBudget > 0) runOptimizer(totalBudget, null);
  }, [totalBudget, runOptimizer]);

  const handleSave = async () => {
    if (!scenName.trim()) { setSaveMsg("Enter a scenario name first."); return; }
    setSaveLoading(true);
    try {
      await ApiService.saveScenario(scenName.trim(), totalBudget, allocation, predRevenue);
      const updated = await ApiService.getScenarios();
      setScenarios(updated.scenarios || []);
      setSaveMsg(`"${scenName.trim()}" saved!`);
      setScenName("");
      setTimeout(() => setSaveMsg(null), 3000);
    } catch (e) {
      setSaveMsg(`Error: ${e.message}`);
    } finally {
      setSaveLoading(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await ApiService.deleteScenario(id);
      setScenarios(prev => prev.filter(s => s.id !== id));
    } catch (e) { setError(e.message); }
  };

  const chartData = CHANNELS.map(ch => ({
    name:  CHANNEL_LABELS[ch],
    spend: allocation[ch] ? Math.round(allocation[ch]) : 0,
    channel: ch,
  }));

  const allocTotal = Object.values(allocation).reduce((s, v) => s + (v || 0), 0);

  if (initLoading) return <LoadingSpinner message="Loading optimizer..." />;

  return (
    <div>
      {error && <div style={styles.errorBox}>Error: {error}</div>}

      <div style={styles.grid2}>
        {/* Left: controls */}
        <div>
          {/* Total budget */}
          <div style={styles.card}>
            <div style={styles.cardTitle}>Total budget</div>
            <div style={styles.budgetRow}>
              <span style={styles.budgetLabel}>$</span>
              <input
                type="number" min={1000} max={10000000} step={1000}
                value={totalBudget}
                onChange={e => setTotalBudget(Math.max(0, Number(e.target.value)))}
                style={styles.budgetInput}
              />
            </div>
            <input type="range" min={10000} max={500000} step={5000}
              value={totalBudget}
              onChange={e => setTotalBudget(Number(e.target.value))}
              style={{ width: "100%", marginTop: 8 }}
            />
            <div style={styles.rangeLabels}>
              <span>$10k</span><span>$500k</span>
            </div>
          </div>

          {/* Predicted revenue */}
          <div style={{ ...styles.card, background: predRevenue ? "#E2F0D9" : "#F4F4F4" }}>
            <div style={styles.cardTitle}>Predicted weekly revenue</div>
            {optLoading
              ? <div style={{ color: "#888", fontSize: 13 }}>Calculating...</div>
              : <div style={styles.predRevenue}>
                  {predRevenue ? `$${predRevenue.toLocaleString()}` : "—"}
                </div>
            }
            {predRevenue && totalBudget > 0 && (
              <div style={styles.roiHint}>
                Overall ROI: ${(predRevenue / totalBudget).toFixed(2)} per $1 spent
              </div>
            )}
          </div>

          {/* Save scenario */}
          <div style={styles.card}>
            <div style={styles.cardTitle}>Save this scenario</div>
            <div style={styles.saveRow}>
              <input
                type="text" placeholder="e.g. Q4 search-heavy"
                value={scenName}
                onChange={e => setScenName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleSave()}
                style={styles.nameInput}
              />
              <button onClick={handleSave} disabled={saveLoading} style={styles.saveBtn}>
                {saveLoading ? "Saving..." : "Save"}
              </button>
            </div>
            {saveMsg && (
              <div style={{ ...styles.saveMsg, background: saveMsg.startsWith("Error") ? "#FCE4D6" : "#E2F0D9", color: saveMsg.startsWith("Error") ? "#843C1D" : "#1D6A38" }}>
                {saveMsg}
              </div>
            )}
          </div>
        </div>

        {/* Right: allocation chart */}
        <div style={styles.card}>
          <div style={styles.cardTitle}>
            Optimal allocation
            {optLoading && <span style={styles.calcBadge}>Calculating...</span>}
          </div>

          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} margin={{ left: 0, right: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={v => `$${(v/1000).toFixed(0)}k`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={v => [`$${v.toLocaleString()}`, "Spend"]}
                contentStyle={{ fontSize: 12, borderRadius: 6 }} />
              <Bar dataKey="spend" radius={[4, 4, 0, 0]}>
                {chartData.map(entry => (
                  <Cell key={entry.channel} fill={COLORS[entry.channel] || "#888"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>

          <div style={{ marginTop: 10 }}>
            {CHANNELS.map(ch => (
              <div key={ch} style={styles.allocRow}>
                <span style={{ ...styles.dot, background: COLORS[ch] }} />
                <span style={styles.chLabel}>{CHANNEL_LABELS[ch]}</span>
                <span style={styles.allocAmt}>
                  ${(allocation[ch] || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </span>
                <span style={styles.allocPct}>
                  {allocTotal > 0 ? `${((allocation[ch] || 0) / allocTotal * 100).toFixed(1)}%` : "—"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Saved scenarios */}
      {scenarios.length > 0 && (
        <div style={styles.card}>
          <div style={styles.cardTitle}>Saved scenarios</div>
          <div style={styles.scenTable}>
            <div style={styles.scenHeader}>
              <span>Name</span><span>Budget</span><span>Predicted revenue</span>
              {CHANNELS.map(ch => <span key={ch}>{CHANNEL_LABELS[ch]}</span>)}
              <span></span>
            </div>
            {scenarios.map(s => (
              <div key={s.id} style={styles.scenRow}>
                <span style={{ fontWeight: 500 }}>{s.scenario_name || "—"}</span>
                <span>${(s.total_budget || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                <span style={{ color: "#1D6A38", fontWeight: 500 }}>
                  {s.predicted_revenue ? `$${s.predicted_revenue.toLocaleString(undefined, { maximumFractionDigits: 0 })}` : "—"}
                </span>
                {CHANNELS.map(ch => (
                  <span key={ch} style={{ fontSize: 11, color: "#595959" }}>
                    ${((s.allocation?.[ch] || 0) / 1000).toFixed(1)}k
                  </span>
                ))}
                <button onClick={() => handleDelete(s.id)} style={styles.delBtn}>✕</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

const styles = {
  grid2:       { display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 14, marginBottom: 14 },
  card:        { background: "#fff", border: "0.5px solid #e0e0e0", borderRadius: 10, padding: 16, marginBottom: 14 },
  cardTitle:   { fontSize: 13, fontWeight: 500, color: "#1a1a1a", marginBottom: 12 },
  budgetRow:   { display: "flex", alignItems: "center", gap: 6 },
  budgetLabel: { fontSize: 18, color: "#595959" },
  budgetInput: { flex: 1, fontSize: 22, fontWeight: 500, border: "none", outline: "none", background: "transparent", color: "#1F4E79" },
  rangeLabels: { display: "flex", justifyContent: "space-between", fontSize: 10, color: "#aaa", marginTop: 2 },
  predRevenue: { fontSize: 28, fontWeight: 500, color: "#1D6A38" },
  roiHint:     { fontSize: 11, color: "#595959", marginTop: 4 },
  saveRow:     { display: "flex", gap: 8 },
  nameInput:   { flex: 1, padding: "7px 10px", borderRadius: 6, border: "1px solid #ddd", fontSize: 12 },
  saveBtn:     { padding: "7px 18px", borderRadius: 6, background: "#2E75B6", color: "#fff", border: "none", cursor: "pointer", fontSize: 12, fontWeight: 500 },
  saveMsg:     { marginTop: 8, padding: "5px 10px", borderRadius: 5, fontSize: 12 },
  calcBadge:   { fontSize: 10, color: "#888", fontWeight: 400, marginLeft: 8 },
  allocRow:    { display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: "0.5px solid #f0f0f0" },
  dot:         { width: 10, height: 10, borderRadius: "50%", flexShrink: 0 },
  chLabel:     { flex: 1, fontSize: 12, color: "#444" },
  allocAmt:    { fontSize: 12, fontWeight: 500, color: "#1a1a1a", minWidth: 70, textAlign: "right" },
  allocPct:    { fontSize: 11, color: "#888", minWidth: 40, textAlign: "right" },
  scenTable:   { fontSize: 12 },
  scenHeader:  { display: "grid", gridTemplateColumns: "1.5fr 1fr 1.2fr repeat(5, 0.8fr) 30px", gap: 8, padding: "6px 0", borderBottom: "1px solid #e0e0e0", fontWeight: 500, color: "#888", fontSize: 11 },
  scenRow:     { display: "grid", gridTemplateColumns: "1.5fr 1fr 1.2fr repeat(5, 0.8fr) 30px", gap: 8, padding: "8px 0", borderBottom: "0.5px solid #f0f0f0", alignItems: "center" },
  delBtn:      { background: "none", border: "none", cursor: "pointer", color: "#aaa", fontSize: 13, padding: 0 },
  errorBox:    { background: "#FCE4D6", color: "#843C1D", padding: 12, borderRadius: 8, fontSize: 13, marginBottom: 12 },
};
