"""
db_helpers.py
Reusable PostgreSQL helper functions for the MMM platform.
Owned by the DB Engineer — all other services import from here.

Usage:
    from db_helpers import get_connection, insert_rows, select_rows

Connection uses environment variables set by docker-compose.
"""

import os
import json
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection():
    """
    Opens and returns a raw psycopg2 connection using env vars.
    Caller is responsible for closing: conn.close()

    Environment variables used:
        POSTGRES_HOST     (default: db)
        POSTGRES_PORT     (default: 5432)
        POSTGRES_DB       (default: mmm_db)
        POSTGRES_USER     (default: mmm_user)
        POSTGRES_PASSWORD (default: mmm_pass)
    """
    return psycopg2.connect(
        host     = os.getenv("POSTGRES_HOST",     "db"),
        port     = int(os.getenv("POSTGRES_PORT", "5432")),
        dbname   = os.getenv("POSTGRES_DB",       "mmm_db"),
        user     = os.getenv("POSTGRES_USER",     "mmm_user"),
        password = os.getenv("POSTGRES_PASSWORD", "mmm_pass"),
    )


def verify_connection() -> bool:
    """
    Checks that the database is reachable and returns True/False.
    Prints the connected database name on success.
    """
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT current_database(), version()")
        db_name, version = cursor.fetchone()
        print(f"  Connected to: {db_name}")
        print(f"  PostgreSQL:   {version.split(',')[0]}")
        conn.close()
        return True
    except Exception as e:
        print(f"  Connection failed: {e}")
        return False


# ── SELECT ────────────────────────────────────────────────────────────────────

def select_rows(table: str, filters: dict = None) -> list[dict]:
    """
    Fetches rows from a table. Returns a list of dicts (column → value).

    Args:
        table:   Table name, e.g. "raw_spend_data"
        filters: Optional WHERE conditions, e.g. {"channel": "tv"}

    Example:
        rows = select_rows("raw_spend_data", {"channel": "search"})
    """
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if filters:
        where  = " AND ".join(f"{k} = %s" for k in filters)
        values = list(filters.values())
        cursor.execute(f"SELECT * FROM {table} WHERE {where}", values)
    else:
        cursor.execute(f"SELECT * FROM {table}")

    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def select_query(sql: str, params: tuple = None) -> list[dict]:
    """
    Runs a custom SELECT query and returns results as list of dicts.

    Example:
        rows = select_query(
            "SELECT channel, SUM(spend_usd) FROM raw_spend_data GROUP BY channel"
        )
    """
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(sql, params)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


# ── INSERT ────────────────────────────────────────────────────────────────────

def insert_row(table: str, data: dict) -> int:
    """
    Inserts one row and returns the generated ID.

    Args:
        table: Target table name
        data:  Dict of column → value pairs

    Example:
        new_id = insert_row("revenue_data", {"week_start": "2023-01-02", "total_revenue": 142000})
    """
    columns      = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    values       = list(data.values())

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING id",
        values
    )
    new_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return new_id


def insert_rows(table: str, rows: list[dict]) -> int:
    """
    Bulk-inserts multiple rows efficiently. Returns number of rows inserted.

    Example:
        count = insert_rows("raw_spend_data", [
            {"week_start": "2023-01-02", "channel": "tv",     "spend_usd": 12000},
            {"week_start": "2023-01-02", "channel": "search", "spend_usd": 8500},
        ])
    """
    if not rows:
        return 0

    columns      = ", ".join(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(rows[0]))
    values       = [list(row.values()) for row in rows]

    conn   = get_connection()
    cursor = conn.cursor()
    psycopg2.extras.execute_batch(
        cursor,
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        values,
        page_size=500
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


# ── UPDATE ────────────────────────────────────────────────────────────────────

def update_row(table: str, row_id: int, data: dict) -> bool:
    """
    Updates a single row by its primary key ID.

    Args:
        table:  Table name
        row_id: Value of the id column
        data:   Dict of column → new value pairs

    Example:
        update_row("model_runs", 3, {"status": "complete", "r_squared": 0.91})
    """
    set_clause = ", ".join(f"{k} = %s" for k in data)
    values     = list(data.values()) + [row_id]

    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE {table} SET {set_clause} WHERE id = %s", values)
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated


# ── DELETE ────────────────────────────────────────────────────────────────────

def delete_row(table: str, row_id: int) -> bool:
    """
    Deletes a single row by its primary key ID. Returns True if a row was deleted.

    Example:
        delete_row("budget_scenarios", 5)
    """
    conn   = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table} WHERE id = %s", (row_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ── Table utilities ───────────────────────────────────────────────────────────

def count_rows(table: str) -> int:
    """Returns the total number of rows in a table."""
    result = select_query(f"SELECT COUNT(*) AS n FROM {table}")
    return result[0]["n"]


def validate_table(table: str, expected_columns: list[str]) -> dict:
    """
    Checks that a table exists and has the expected columns.
    Returns a dict with 'ok' (bool) and 'missing_columns' (list).

    Example:
        result = validate_table("raw_spend_data", ["week_start", "channel", "spend_usd"])
    """
    rows = select_query(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table,)
    )
    actual   = {row["column_name"] for row in rows}
    missing  = [c for c in expected_columns if c not in actual]
    return {"ok": len(missing) == 0, "missing_columns": missing}


# ── Run standalone to verify connection ──────────────────────────────────────
if __name__ == "__main__":
    print("Verifying database connection...")
    ok = verify_connection()
    if ok:
        print("\nRow counts:")
        for table in ["raw_spend_data", "revenue_data", "processed_features",
                      "model_runs", "channel_coefficients", "budget_scenarios"]:
            print(f"  {table}: {count_rows(table)} rows")
