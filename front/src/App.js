import { useState, useEffect } from "react";
import ApiService from "./components/ApiService";
import Overview       from "./pages/Overview";
import ChannelDeepDive from "./pages/ChannelDeepDive";
import BudgetOptimizer from "./pages/BudgetOptimizer";
import ModelSettings   from "./pages/ModelSettings";

const PAGES = [
  { id: "overview",   label: "Overview" },
  { id: "channels",   label: "Channels" },
  { id: "optimizer",  label: "Budget Optimizer" },
  { id: "model",      label: "Model Settings" },
];

// Responsive CSS injected at runtime
const RESPONSIVE_CSS = `
  @media (max-width: 900px) {
    .mmm-sidebar { display: none !important; }
    .mmm-main { padding: 12px !important; }
    .mmm-topbar { padding: 12px 12px 0 !important; }
    .mmm-kpi-grid { grid-template-columns: repeat(2, 1fr) !important; }
    .mmm-grid2 { grid-template-columns: 1fr !important; }
    .mmm-stat-grid { grid-template-columns: repeat(2, 1fr) !important; }
  }
  @media (max-width: 600px) {
    .mmm-kpi-grid { grid-template-columns: 1fr 1fr !important; }
    .mmm-stat-grid { grid-template-columns: 1fr 1fr !important; }
    .mmm-grid2 { grid-template-columns: 1fr !important; }
  }
`;

export default function App() {
  const [page,   setPage]   = useState("overview");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    ApiService.getHealth()
      .then(setHealth)
      .catch(() => setHealth({ status: "degraded", database: "unreachable" }));
  }, []);

  const dbOk = health?.database === "connected";

  const content = {
    overview:  <Overview />,
    channels:  <ChannelDeepDive />,
    optimizer: <BudgetOptimizer />,
    model:     <ModelSettings />,
  };

  return (
    <>
      <style>{RESPONSIVE_CSS}</style>
      <div style={styles.shell}>
      {/* Sidebar */}
      <aside style={styles.sidebar} className="mmm-sidebar">
        <div style={styles.logo}>
          <span style={styles.logoMark}>MMM</span>
          <span style={styles.logoSub}>Platform</span>
        </div>

        {PAGES.map(p => (
          <button key={p.id} onClick={() => setPage(p.id)}
            style={{ ...styles.navItem, ...(page === p.id ? styles.navActive : {}) }}>
            {p.label}
          </button>
        ))}

        <div style={styles.sidebarBottom}>
          <div style={{
            ...styles.dbPill,
            background: dbOk ? "#E2F0D9" : "#FCE4D6",
            color:      dbOk ? "#1D6A38" : "#843C1D",
          }}>
            DB: {health ? health.database : "checking..."}
          </div>
          <div style={styles.version}>v3.0 · Sprint 3</div>
        </div>
      </aside>

      {/* Main content */}
      <main style={styles.main} className="mmm-main">
        <div style={styles.topBar} className="mmm-topbar">
          <h1 style={styles.pageTitle}>
            {PAGES.find(p => p.id === page)?.label}
          </h1>
        </div>
        <div style={styles.content} className="mmm-content">
          {content[page]}
        </div>
      </main>
    </div>
    </>
  );
}

const styles = {
  shell:       { display:"flex", minHeight:"100vh", fontFamily:"'Segoe UI', system-ui, sans-serif", background:"#F5F6FA", color:"#1a1a1a" },
  sidebar:     { width:180, flexShrink:0, background:"#fff", borderRight:"0.5px solid #e0e0e0", display:"flex", flexDirection:"column", padding:"0 0 16px 0" },
  logo:        { padding:"20px 18px 16px", borderBottom:"0.5px solid #e0e0e0", marginBottom:8 },
  logoMark:    { fontSize:16, fontWeight:700, color:"#1F4E79", display:"block" },
  logoSub:     { fontSize:11, color:"#888" },
  navItem:     { width:"100%", textAlign:"left", padding:"9px 18px", border:"none", background:"transparent", cursor:"pointer", fontSize:13, color:"#595959", borderLeft:"3px solid transparent", transition:"all .1s" },
  navActive:   { background:"#EBF3FB", color:"#1F4E79", fontWeight:500, borderLeftColor:"#2E75B6" },
  sidebarBottom:{ marginTop:"auto", padding:"0 14px" },
  dbPill:      { fontSize:11, fontWeight:500, padding:"4px 10px", borderRadius:20, textAlign:"center", marginBottom:6 },
  version:     { fontSize:10, color:"#bbb", textAlign:"center" },
  main:        { flex:1, display:"flex", flexDirection:"column", minWidth:0 },
  topBar:      { padding:"18px 24px 0", borderBottom:"0.5px solid #e0e0e0", background:"#fff" },
  pageTitle:   { fontSize:18, fontWeight:500, color:"#1F4E79", margin:"0 0 14px 0" },
  content:     { padding:20, flex:1, overflowY:"auto" },
};
