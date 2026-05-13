-- ─────────────────────────────────────────────────────────────────────────────
--  Migration 03 — model_predictions table
--  Stores weekly actual vs predicted revenue per model run.
--  Enables the time-series chart and model evaluation view in the dashboard.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS model_predictions (
    id               SERIAL PRIMARY KEY,
    model_run_id     INTEGER REFERENCES model_runs(id) ON DELETE CASCADE,
    week_start       DATE          NOT NULL,
    actual_revenue   NUMERIC(14,2) NOT NULL,
    predicted_revenue NUMERIC(14,2) NOT NULL,
    residual         NUMERIC(14,2) GENERATED ALWAYS AS (actual_revenue - predicted_revenue) STORED,
    created_at       TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_run   ON model_predictions(model_run_id);
CREATE INDEX IF NOT EXISTS idx_predictions_week  ON model_predictions(week_start);
