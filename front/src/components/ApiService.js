/**
 * ApiService.js
 * Centralized helper for all backend API calls.
 * All components import from here — no raw fetch/axios calls in components.
 *
 * Base URL is read from the REACT_APP_API_URL environment variable,
 * which is set in docker-compose.yml to http://localhost:8000.
 */

const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

async function request(method, path, body = null) {
  const options = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body) options.body = JSON.stringify(body);

  const res = await fetch(`${BASE_URL}${path}`, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

const ApiService = {
  // ── Health ──────────────────────────────────────────────
  getHealth: () => request("GET", "/health"),

  // ── Model results ────────────────────────────────────────
  getResults:   () => request("GET", "/results"),
  getModelRuns: () => request("GET", "/model-runs"),
  triggerRetrain: () => request("POST", "/retrain"),

  // ── Optimizer ────────────────────────────────────────────
  optimize: (totalBudget, constraints = null) =>
    request("POST", "/optimize", { total_budget: totalBudget, constraints }),

  // ── Scenarios ────────────────────────────────────────────
  getScenarios: () => request("GET", "/scenarios"),
  saveScenario: (name, totalBudget, allocation, predictedRevenue = null) =>
    request("POST", "/scenarios", {
      scenario_name:     name,
      total_budget:      totalBudget,
      allocation,
      predicted_revenue: predictedRevenue,
    }),
  updateScenario: (id, data) => request("PUT",    `/scenarios/${id}`, data),
  deleteScenario: (id)       => request("DELETE", `/scenarios/${id}`),

  // ── Data summary ─────────────────────────────────────────
  getDataSummary: () => request("GET", "/data-summary"),
};

export default ApiService;
