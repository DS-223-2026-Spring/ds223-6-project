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
    coeff_rows = db.execute(text("""
        SELECT channel, roi_estimate, contribution_pct, coefficient,
               recommendation, predicted_revenue_contribution
        FROM   channel_coefficients
        WHERE  model_run_id = :run_id
        ORDER  BY roi_estimate DESC NULLS LAST
    """), {"run_id": run_row.id}).fetchall()

    return {
        "model_version": run_row.model_version,
        "r_squared":     float(run_row.r_squared) if run_row.r_squared else None,
        "run_at":        str(run_row.run_at),
        "channels": [
            {
                "channel":          row.channel,
                "roi_estimate":     float(row.roi_estimate)    if row.roi_estimate    else None,
                "contribution_pct": float(row.contribution_pct) if row.contribution_pct else None,
                "coefficient":      float(row.coefficient)     if row.coefficient     else None,
                "recommendation":   row.recommendation,
                "predicted_revenue_contribution": float(row.predicted_revenue_contribution) if row.predicted_revenue_contribution else None,
            }
            for row in coeff_rows
        ]
    }


# ── Model run history ─────────────────────────────────────────────────────────

def get_model_runs(db: Session) -> list:
    """
    Returns all model runs ordered by most recent first.
    Table used: model_runs
    """
    rows = db.execute(text("""
        SELECT id, model_version, status, r_squared, run_at, notes
        FROM   model_runs
        ORDER  BY run_at DESC
    """)).fetchall()

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

def get_all_scenarios(db: Session) -> list:
    """
    Returns all saved budget scenarios ordered by most recent first.
    Table used: budget_scenarios
    """
    rows = db.execute(text("""
        SELECT id, scenario_name, total_budget, allocation_json,
               predicted_revenue, created_at
        FROM   budget_scenarios
        ORDER  BY created_at DESC
    """)).fetchall()

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
