-- ─────────────────────────────────────────────────────────────
--  MMM Platform – Database Schema
--  Runs automatically on first docker-compose up.
--  Tables: raw_spend_data, revenue_data, processed_features,
--          model_runs, channel_coefficients, budget_scenarios
-- ─────────────────────────────────────────────────────────────

-- Raw weekly ad spend per channel
CREATE TABLE IF NOT EXISTS raw_spend_data (
    id            SERIAL PRIMARY KEY,
    week_start    DATE          NOT NULL,
    channel       VARCHAR(50)   NOT NULL,   -- tv, ooh, print, facebook, search
    spend_usd     NUMERIC(12,2) NOT NULL,
    campaign_name VARCHAR(100),
    ingested_at   TIMESTAMP DEFAULT NOW(),
    UNIQUE (week_start, channel)            -- prevents duplicate rows on re-run
);

-- Weekly revenue totals
CREATE TABLE IF NOT EXISTS revenue_data (
    id            SERIAL PRIMARY KEY,
    week_start    DATE          NOT NULL UNIQUE,
    total_revenue NUMERIC(14,2) NOT NULL,
    ingested_at   TIMESTAMP DEFAULT NOW()
);

-- Pipeline output: transformed features ready for modeling
CREATE TABLE IF NOT EXISTS processed_features (
    id                SERIAL PRIMARY KEY,
    week_start        DATE          NOT NULL,
    channel           VARCHAR(50)   NOT NULL,
    adstock_value     NUMERIC(14,4),   -- after adstock decay transform
    saturated_value   NUMERIC(14,4),   -- after Hill function saturation
    seasonality_index NUMERIC(6,4) DEFAULT 1.0,
    promo_flag        SMALLINT     DEFAULT 0,
    holiday_flag      SMALLINT     DEFAULT 0,
    processed_at      TIMESTAMP DEFAULT NOW()
);

-- One row per model training run
CREATE TABLE IF NOT EXISTS model_runs (
    id              SERIAL PRIMARY KEY,
    run_at          TIMESTAMP DEFAULT NOW(),
    model_version   VARCHAR(20) NOT NULL,
    status          VARCHAR(20) DEFAULT 'pending',  -- pending | complete | failed
    r_squared       NUMERIC(5,4),
    hyperparameters JSONB,    -- stores lambda, hill params etc as JSON
    notes           TEXT
);

-- Model output: ROI per channel per run
CREATE TABLE IF NOT EXISTS channel_coefficients (
    id                SERIAL PRIMARY KEY,
    model_run_id      INTEGER REFERENCES model_runs(id) ON DELETE CASCADE,
    channel           VARCHAR(50)  NOT NULL,
    coefficient       NUMERIC(10,6),
    roi_estimate      NUMERIC(8,4),   -- revenue per $1 spent
    contribution_pct  NUMERIC(5,2)    -- % of total attributed revenue
);

-- Saved optimizer scenarios
CREATE TABLE IF NOT EXISTS budget_scenarios (
    id               SERIAL PRIMARY KEY,
    model_run_id     INTEGER REFERENCES model_runs(id) ON DELETE SET NULL,
    scenario_name    VARCHAR(100),
    created_at       TIMESTAMP DEFAULT NOW(),
    total_budget     NUMERIC(12,2) NOT NULL,
    allocation_json  JSONB NOT NULL,  -- {"tv": 20000, "search": 32000, ...}
    predicted_revenue NUMERIC(14,2)
);

-- Helpful indexes for common queries
CREATE INDEX IF NOT EXISTS idx_raw_spend_week    ON raw_spend_data(week_start);
CREATE INDEX IF NOT EXISTS idx_raw_spend_channel ON raw_spend_data(channel);
CREATE INDEX IF NOT EXISTS idx_revenue_week      ON revenue_data(week_start);
CREATE INDEX IF NOT EXISTS idx_features_week     ON processed_features(week_start);
CREATE INDEX IF NOT EXISTS idx_coeff_run         ON channel_coefficients(model_run_id);
