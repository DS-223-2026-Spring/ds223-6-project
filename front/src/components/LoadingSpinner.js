/**
 * LoadingSpinner.js
 * Simple loading indicator shown while API calls are in flight.
 *
 * Props:
 *   message (string) — optional text shown below the spinner
 */

function LoadingSpinner({ message = "Loading..." }) {
  return (
    <div style={{ textAlign: "center", padding: "2rem", color: "#888" }}>
      <div style={{
        width:  28,
        height: 28,
        border: "3px solid #e0e0e0",
        borderTop: "3px solid #2E75B6",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
        margin: "0 auto 12px",
      }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <span style={{ fontSize: 13 }}>{message}</span>
    </div>
  );
}

export default LoadingSpinner;
