/**
 * MetricCard.js
 * Reusable KPI summary card used in the Overview dashboard.
 *
 * Props:
 *   label  (string) — muted label shown above the value
 *   value  (string|number) — main display value
 *   sub    (string) — small subtitle below the value (optional)
 */

function MetricCard({ label, value, sub }) {
  return (
    <div style={{
      background:   "var(--color-bg-secondary, #F4F4F4)",
      borderRadius: 8,
      padding:      "1rem",
    }}>
      <div style={{ fontSize: 11, color: "#595959", marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 500, color: "#1a1a1a" }}>
        {value ?? "—"}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: "#888", marginTop: 3 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

export default MetricCard;
