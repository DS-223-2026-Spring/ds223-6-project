// App.js – MMM Platform Dashboard skeleton
// Uses ApiService for all backend calls.
// Replace placeholder sections with real components in Sprint 3.

import { useState, useEffect } from "react";
import ApiService from "./components/ApiService";
import MetricCard from "./components/MetricCard";
import LoadingSpinner from "./components/LoadingSpinner";

const PAGES = ["Overview", "Channels", "Budget Optimizer", "Model Settings"];

function App() {
  const [page, setPage]       = useState("Overview");
  const [health, setHealth]   = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [h, r] = await Promise.all([
          ApiService.getHealth(),
          ApiService.getResults(),
        ]);
        setHealth(h);
        setResults(r);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  return (
    <div style={{ fontFamily: "sans-serif", padding: "2rem", maxWidth: 960 }}>

      {/* Header */}
      <h1 style={{ color: "#1F4E79", marginBottom: 4 }}>MMM Platform</h1>
      <p style={{ color: "#595959", marginBottom: 8 }}>
        Marketing Mix Modeling Dashboard
      </p>
      {health && (
        <span style={{
          fontSize: 11, padding: "2px 10px", borderRadius: 20,
          background: health.database === "connected" ? "#E2F0D9" : "#FCE4D6",
          color:      health.database === "connected" ? "#1D6A38" : "#843C1D",
        }}>
          DB: {health.database}
        </span>
      )}

      {/* Navigation */}
      <nav style={{ display: "flex", gap: 16, margin: "20px 0 24px",
                    borderBottom: "1px solid #ddd", paddingBottom: 12 }}>
        {PAGES.map(name => (
          <button key={name} onClick={() => setPage(name)} style={{
            background: "none", border: "none", cursor: "pointer",
            color:      page === name ? "#1F4E79" : "#2E75B6",
            fontWeight: page === name ? 600 : 400,
            fontSize:   14,
            borderBottom: page === name ? "2px solid #1F4E79" : "none",
            paddingBottom: 4,
          }}>
            {name}
          </button>
        ))}
      </nav>

      {/* Content */}
      {loading && <LoadingSpinner message="Connecting to API..." />}
      {error   && <div style={{ color: "#843C1D", background: "#FCE4D6",
                                padding: "1rem", borderRadius: 8 }}>
                    Error: {error}
                  </div>}

      {!loading && !error && page === "Overview" && (
        <>
          {/* KPI cards — data comes from GET /results */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)",
                        gap: 12, marginBottom: 28 }}>
            <MetricCard label="Model version"  value={results?.model_version ?? "—"} />
            <MetricCard label="Model R²"       value={results?.r_squared
                                                        ? results.r_squared.toFixed(2)
                                                        : "—"} />
            <MetricCard label="Channels"       value={results?.channels?.length ?? "—"} />
            <MetricCard label="Best ROI"
              value={results?.channels?.length
                ? results.channels[0].channel
                : "—"}
              sub={results?.channels?.length
                ? `$${results.channels[0].roi_estimate?.toFixed(2)} per $1`
                : null}
            />
          </div>

          {/* ROI chart placeholder — Sprint 3 will use Recharts BarChart */}
          <div style={{ background: "#F4F4F4", borderRadius: 8, padding: "2rem",
                        textAlign: "center", color: "#888", marginBottom: 16 }}>
            ROI bar chart — Sprint 3 (data from GET /results → channels[])
          </div>

          {/* Optimizer placeholder */}
          <div style={{ background: "#F4F4F4", borderRadius: 8, padding: "2rem",
                        textAlign: "center", color: "#888" }}>
            Budget optimizer — Sprint 4 (POST /optimize with total_budget + constraints)
          </div>
        </>
      )}

      {!loading && !error && page === "Channels" && (
        <div style={{ background: "#F4F4F4", borderRadius: 8, padding: "2rem",
                      textAlign: "center", color: "#888" }}>
          Channel deep dive — Sprint 3
          <br /><small>Needs: GET /results → channels[] with roi_estimate and contribution_pct</small>
        </div>
      )}

      {!loading && !error && page === "Budget Optimizer" && (
        <div style={{ background: "#F4F4F4", borderRadius: 8, padding: "2rem",
                      textAlign: "center", color: "#888" }}>
          Budget optimizer sliders — Sprint 4
          <br /><small>Needs: POST /optimize &#123; total_budget, constraints &#125; → allocation, predicted_revenue</small>
        </div>
      )}

      {!loading && !error && page === "Model Settings" && (
        <div style={{ background: "#F4F4F4", borderRadius: 8, padding: "2rem",
                      textAlign: "center", color: "#888" }}>
          Model run history — Sprint 4
          <br /><small>Needs: GET /model-runs → runs[]</small>
        </div>
      )}

    </div>
  );
}

export default App;
