"""
crud.py
All database read/write functions for the MMM backend.
Endpoints call these functions — they never write raw SQL themselves.

Each function receives a SQLAlchemy Session from the FastAPI dependency
injector and returns plain Python dicts/lists that FastAPI serializes to JSON.
"""

from sqlalchemy.orm import Session
from sqlalchemy import text


# ── Results / Model outputs ───────────────────────────────────────────────────

def get_latest_results(db: Session) -> dict:
    """
    Fetches the most recent completed model run and its channel coefficients.
    Returns model metadata + one row per channel with ROI and contribution %.

    Tables used: model_runs, channel_coefficients
    """

    # Step 1: get the latest completed model run
    run_row = db.execute(text("""
        SELECT id, model_version, r_squared, run_at
        FROM   model_runs
        WHERE  status = 'complete'
        ORDER  BY run_at DESC
        LIMIT  1
    """)).fetchone()

    # No model has been trained yet — return empty state
    if run_row is None:
        return {
            "model_version": None,
            "r_squared":     None,
            "run_at":        None,
            "channels":      []
        }

    # Step 2: get the coefficients for that run
    # Check which optional columns exist (added in later migrations)
    col_check = db.execute(text("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'channel_coefficients'
    """)).fetchall()
    existing = {r[0] for r in col_check}

    select_cols = """channel, roi_estimate, contribution_pct, coefficient, recommendation,
                     predicted_revenue_contribution"""
    if "roi_lower_90" in existing:
        select_cols += ", roi_lower_90, roi_upper_90"

    coeff_rows = db.execute(text(f"""
        SELECT {select_cols}
        FROM   channel_coefficients
        WHERE  model_run_id = :run_id
        ORDER  BY roi_estimate DESC NULLS LAST
    """), {"run_id": run_row.id}).fetchall()

    def safe_float(val):
        return float(val) if val is not None else None

    channels_out = []
    for row in coeff_rows:
        row_dict = dict(row._mapping)
        channels_out.append({
            "channel":          row_dict.get("channel"),
            "roi_estimate":     safe_float(row_dict.get("roi_estimate")),
            "contribution_pct": safe_float(row_dict.get("contribution_pct")),
            "coefficient":      safe_float(row_dict.get("coefficient")),
            "recommendation":   row_dict.get("recommendation"),
            "predicted_revenue_contribution": safe_float(row_dict.get("predicted_revenue_contribution")),
            "roi_lower_90":     safe_float(row_dict.get("roi_lower_90")),
            "roi_upper_90":     safe_float(row_dict.get("roi_upper_90")),
        })

    return {
        "model_version": run_row.model_version,
        "r_squared":     safe_float(run_row.r_squared),
        "run_at":        str(run_row.run_at),
        "channels":      channels_out,
    }


# ── Model run history ─────────────────────────────────────────────────────────

def get_model_runs(db: Session, limit: int = 50, offset: int = 0) -> list:
    """
    Returns model runs ordered by most recent first.
    Table used: model_runs
    """
    rows = db.execute(text("""
        SELECT id, model_version, status, r_squared, run_at, notes
        FROM   model_runs
        ORDER  BY run_at DESC
        LIMIT  :limit OFFSET :offset
    """), {"limit": limit, "offset": offset}).fetchall()

    return [
        {
            "id":            row.id,
            "model_version": row.model_version,
            "status":        row.status,
            "r_squared":     float(row.r_squared) if row.r_squared else None,
            "run_at":        str(row.run_at),
            "notes":         row.notes,
        }
        for row in rows
    ]


# ── Budget scenarios ──────────────────────────────────────────────────────────

def get_all_scenarios(db: Session, limit: int = 50, offset: int = 0) -> list:
    """
    Returns all saved budget scenarios ordered by most recent first.
    Table used: budget_scenarios
    """
    rows = db.execute(text("""
        SELECT id, scenario_name, total_budget, allocation_json,
               predicted_revenue, created_at
        FROM   budget_scenarios
        ORDER  BY created_at DESC
        LIMIT  :limit OFFSET :offset
    """), {"limit": limit, "offset": offset}).fetchall()

    return [
        {
            "id":                row.id,
            "scenario_name":     row.scenario_name,
            "total_budget":      float(row.total_budget),
            "allocation":        row.allocation_json,       # already a dict from JSONB
            "predicted_revenue": float(row.predicted_revenue) if row.predicted_revenue else None,
            "created_at":        str(row.created_at),
        }
        for row in rows
    ]


def save_scenario(
    db: Session,
    scenario_name: str,
    total_budget: float,
    allocation: dict,
    predicted_revenue: float | None,
    model_run_id: int | None,
) -> dict:
    """
    Inserts a new budget scenario and returns it with its generated ID.
    Table used: budget_scenarios
    """
    import json

    result = db.execute(text("""
        INSERT INTO budget_scenarios
            (scenario_name, total_budget, allocation_json, predicted_revenue, model_run_id)
        VALUES
            (:name, :budget, :allocation, :revenue, :run_id)
        RETURNING id, created_at
    """), {
        "name":       scenario_name,
        "budget":     total_budget,
        "allocation": json.dumps(allocation),   # convert dict → JSON string for Postgres
        "revenue":    predicted_revenue,
        "run_id":     model_run_id,
    })

    db.commit()
    row = result.fetchone()

    return {
        "id":                row.id,
        "scenario_name":     scenario_name,
        "total_budget":      total_budget,
        "allocation":        allocation,
        "predicted_revenue": predicted_revenue,
        "created_at":        str(row.created_at),
    }


# ── Raw data helpers (used by DS service via API, optional) ───────────────────

def get_spend_summary(db: Session) -> dict:
    """
    Returns the date range and total spend per channel from raw_spend_data.
    Useful for the dashboard header stats.
    """
    meta = db.execute(text("""
        SELECT MIN(week_start) AS first_week,
               MAX(week_start) AS last_week,
               COUNT(DISTINCT week_start) AS total_weeks
        FROM raw_spend_data
    """)).fetchone()

    channels = db.execute(text("""
        SELECT channel, SUM(spend_usd) AS total_spend
        FROM   raw_spend_data
        GROUP  BY channel
        ORDER  BY total_spend DESC
    """)).fetchall()

    return {
        "first_week":   str(meta.first_week)  if meta.first_week  else None,
        "last_week":    str(meta.last_week)   if meta.last_week   else None,
        "total_weeks":  meta.total_weeks,
        "spend_by_channel": [
            {"channel": row.channel, "total_spend": float(row.total_spend)}
            for row in channels
        ]
    }


# ── PUT / DELETE (added to satisfy full CRUD requirement) ─────────────────────

def update_scenario(db: Session, scenario_id: int, data: dict) -> dict | None:
    """
    Updates a saved scenario by ID. Returns updated record or None if not found.
    Table used: budget_scenarios
    """
    import json
    fields = []
    values = []
    if "scenario_name" in data:
        fields.append("scenario_name = :name")
        values.append(("name", data["scenario_name"]))
    if "total_budget" in data:
        fields.append("total_budget = :budget")
        values.append(("budget", data["total_budget"]))
    if "allocation" in data:
        fields.append("allocation_json = CAST(:allocation AS jsonb)")
        values.append(("allocation", json.dumps(data["allocation"])))
    if "predicted_revenue" in data:
        fields.append("predicted_revenue = :revenue")
        values.append(("revenue", data["predicted_revenue"]))

    if not fields:
        return None

    params = dict(values)
    params["id"] = scenario_id

    result = db.execute(text(f"""
        UPDATE budget_scenarios
        SET {', '.join(fields)}
        WHERE id = :id
        RETURNING id, scenario_name, total_budget, allocation_json,
                  predicted_revenue, created_at
    """), params)
    db.commit()
    row = result.fetchone()
    if not row:
        return None
    return {
        "id":                row.id,
        "scenario_name":     row.scenario_name,
        "total_budget":      float(row.total_budget),
        "allocation":        row.allocation_json,
        "predicted_revenue": float(row.predicted_revenue) if row.predicted_revenue else None,
        "created_at":        str(row.created_at),
    }


def delete_scenario(db: Session, scenario_id: int) -> bool:
    """
    Deletes a scenario by ID. Returns True if deleted, False if not found.
    Table used: budget_scenarios
    """
    result = db.execute(
        text("DELETE FROM budget_scenarios WHERE id = :id RETURNING id"),
        {"id": scenario_id}
    )
    db.commit()
    return result.fetchone() is not None


# ── Predictions (actual vs predicted per week) ────────────────────────────────

def get_predictions(db: Session, model_run_id: int = None) -> list:
    """
    Returns weekly actual vs predicted revenue.
    If model_run_id is None, uses the latest completed run.
    Table used: model_predictions, model_runs
    """
    if model_run_id is None:
        run_row = db.execute(text("""
            SELECT id FROM model_runs
            WHERE status = 'complete'
            ORDER BY run_at DESC LIMIT 1
        """)).fetchone()
        if run_row is None:
            return []
        model_run_id = run_row.id

    rows = db.execute(text("""
        SELECT week_start, actual_revenue, predicted_revenue, residual
        FROM   model_predictions
        WHERE  model_run_id = :run_id
        ORDER  BY week_start
    """), {"run_id": model_run_id}).fetchall()

    return [
        {
            "week_start":         str(row.week_start),
            "actual_revenue":     float(row.actual_revenue),
            "predicted_revenue":  float(row.predicted_revenue),
            "residual":           float(row.residual) if row.residual is not None else None,
        }
        for row in rows
    ]


# ── Organic signals ────────────────────────────────────────────────────────────

def get_organic_signals(db: Session) -> list:
    """
    Returns weekly organic signal data (competitor sales, newsletter, events).
    Table used: organic_signals
    """
    rows = db.execute(text("""
        SELECT week_start, competitor_sales, newsletter_subs,
               facebook_impressions, search_clicks, event_flag
        FROM   organic_signals
        ORDER  BY week_start
    """)).fetchall()

    return [
        {
            "week_start":           str(row.week_start),
            "competitor_sales":     float(row.competitor_sales)     if row.competitor_sales     is not None else None,
            "newsletter_subs":      float(row.newsletter_subs)      if row.newsletter_subs      is not None else None,
            "facebook_impressions": float(row.facebook_impressions) if row.facebook_impressions is not None else None,
            "search_clicks":        float(row.search_clicks)        if row.search_clicks        is not None else None,
            "event_flag":           row.event_flag,
        }
        for row in rows
    ]


# ── Pipeline run log ───────────────────────────────────────────────────────────

def get_pipeline_runs(db: Session) -> list:
    """
    Returns all pipeline run log entries ordered by most recent first.
    Table used: pipeline_run_log
    """
    rows = db.execute(text("""
        SELECT id, flow_name, started_at, finished_at, status,
               spend_rows, revenue_rows, model_run_id, error_msg
        FROM   pipeline_run_log
        ORDER  BY started_at DESC
        LIMIT  50
    """)).fetchall()

    return [
        {
            "id":           row.id,
            "flow_name":    row.flow_name,
            "started_at":   str(row.started_at),
            "finished_at":  str(row.finished_at) if row.finished_at else None,
            "status":       row.status,
            "spend_rows":   row.spend_rows,
            "revenue_rows": row.revenue_rows,
            "model_run_id": row.model_run_id,
            "error_msg":    row.error_msg,
        }
        for row in rows
    ]


# ── Weekly channel contribution (for ChannelDeepDive real data) ───────────────

def get_weekly_channel_data(db: Session) -> dict:
    """
    Returns weekly spend and predicted contribution per channel.
    Used by the Channel Deep Dive page for real time-series charts.
    Reads from: raw_spend_data, processed_features, channel_coefficients, model_runs
    """
    # Get latest model run coefficients
    run_row = db.execute(text("""
        SELECT id FROM model_runs WHERE status = 'complete'
        ORDER BY run_at DESC LIMIT 1
    """)).fetchone()

    if run_row is None:
        return {"channels": {}, "weeks": []}

    # Get coefficients
    coeff_rows = db.execute(text("""
        SELECT channel, coefficient, roi_estimate
        FROM   channel_coefficients
        WHERE  model_run_id = :run_id
    """), {"run_id": run_row.id}).fetchall()

    coeffs = {row.channel: float(row.coefficient or 0) for row in coeff_rows}

    # Get processed features (saturated values) per week per channel
    feature_rows = db.execute(text("""
        SELECT pf.week_start, pf.channel, pf.adstock_value,
               pf.saturated_value, rs.spend_usd
        FROM   processed_features pf
        JOIN   raw_spend_data rs
               ON pf.week_start = rs.week_start AND pf.channel = rs.channel
        ORDER  BY pf.week_start, pf.channel
    """)).fetchall()

    if not feature_rows:
        return {"channels": {}, "weeks": []}

    # Build per-channel weekly series
    channel_data = {}
    weeks_set    = set()

    for row in feature_rows:
        ch    = row.channel
        week  = str(row.week_start)
        coef  = coeffs.get(ch, 0)
        contrib = float(row.saturated_value or 0) * coef

        if ch not in channel_data:
            channel_data[ch] = {}
        channel_data[ch][week] = {
            "spend":        float(row.spend_usd or 0),
            "adstock":      float(row.adstock_value or 0),
            "saturated":    float(row.saturated_value or 0),
            "contribution": round(contrib, 2),
        }
        weeks_set.add(week)

    weeks = sorted(weeks_set)
    return {"channels": channel_data, "weeks": weeks}
