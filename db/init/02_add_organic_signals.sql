-- ─────────────────────────────────────────────────────────────────────────────
--  Migration 02 — Organic signals table + missing indexes
--  Adds organic/external variables from dt_simulated_weekly.csv that were
--  not loaded in Sprint 1. These are strong model controls:
--    competitor_sales_B  r=+0.916 with revenue (confound — must control for)
--    newsletter          r=+0.406 with revenue  (organic demand driver)
--    events              rare dummy (event1/event2 appear once each)
--    facebook_I          Facebook impressions
--    search_clicks_P     Search clicks (proxy for demand)
-- ─────────────────────────────────────────────────────────────────────────────

-- Organic and external signals — one row per week
CREATE TABLE IF NOT EXISTS organic_signals (
    id                   SERIAL PRIMARY KEY,
    week_start           DATE          NOT NULL UNIQUE,
    competitor_sales     NUMERIC(14,2),   -- competitor revenue (strong confound)
    newsletter_subs      NUMERIC(12,2),   -- newsletter subscriber count
    facebook_impressions NUMERIC(14,2),   -- total Facebook impressions
    search_clicks        NUMERIC(12,2),   -- total paid search clicks
    event_flag           VARCHAR(20) DEFAULT 'na',  -- na | event1 | event2
    ingested_at          TIMESTAMP DEFAULT NOW()
);

-- Pipeline run log — one row per Prefect/manual run for traceability
CREATE TABLE IF NOT EXISTS pipeline_run_log (
    id           SERIAL PRIMARY KEY,
    flow_name    VARCHAR(100) NOT NULL,
    started_at   TIMESTAMP DEFAULT NOW(),
    finished_at  TIMESTAMP,
    status       VARCHAR(20) DEFAULT 'running',  -- running | success | failed
    spend_rows   INTEGER,
    revenue_rows INTEGER,
    model_run_id INTEGER REFERENCES model_runs(id) ON DELETE SET NULL,
    result_json  JSONB,
    error_msg    TEXT
);

-- Missing indexes identified in Sprint 3 analysis
CREATE INDEX IF NOT EXISTS idx_model_runs_status    ON model_runs(status);
CREATE INDEX IF NOT EXISTS idx_scenarios_created    ON budget_scenarios(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_organic_week         ON organic_signals(week_start);
CREATE INDEX IF NOT EXISTS idx_pipeline_log_status  ON pipeline_run_log(status);

-- UNIQUE constraint on processed_features (DO block avoids error if already exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_features_week_channel'
    ) THEN
        EXECUTE 'ALTER TABLE processed_features
            ADD CONSTRAINT uq_features_week_channel UNIQUE (week_start, channel)';
    END IF;
END $$;

-- Add recommendation and predicted_revenue columns to channel_coefficients
ALTER TABLE channel_coefficients
    ADD COLUMN IF NOT EXISTS recommendation VARCHAR(50),      -- under-invested | over-invested | optimal
    ADD COLUMN IF NOT EXISTS predicted_revenue_contribution NUMERIC(14,2);

-- Fix column precision — coefficient values like 561357.77 overflow NUMERIC(10,6)
ALTER TABLE channel_coefficients
    ALTER COLUMN coefficient  TYPE NUMERIC(18,4),
    ALTER COLUMN roi_estimate TYPE NUMERIC(12,4);
