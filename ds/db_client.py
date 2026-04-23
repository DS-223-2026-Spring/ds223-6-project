"""
db_client.py
Reusable PostgreSQL helper for the DS service.
Uses environment variables set by docker-compose.
"""

import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def get_engine():
    """Create and return a SQLAlchemy engine from env vars."""
    host     = os.getenv("POSTGRES_HOST", "db")
    port     = os.getenv("POSTGRES_PORT", "5432")
    db       = os.getenv("POSTGRES_DB",   "mmm_db")
    user     = os.getenv("POSTGRES_USER", "mmm_user")
    password = os.getenv("POSTGRES_PASSWORD", "mmm_pass")
    url      = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def read_table(table_name: str) -> pd.DataFrame:
    """Read an entire table into a DataFrame."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(f"SELECT * FROM {table_name}", conn)


def write_dataframe(df: pd.DataFrame, table_name: str, if_exists: str = "append"):
    """Write a DataFrame to a table. if_exists: 'append' or 'replace'."""
    engine = get_engine()
    df.to_sql(table_name, engine, if_exists=if_exists, index=False)
    print(f"  Wrote {len(df)} rows to {table_name}")


def execute_query(sql: str):
    """Run a raw SQL statement (e.g. DELETE, UPDATE)."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(sql))


if __name__ == "__main__":
    # Quick connection test – run with: docker exec mmm_ds python db_client.py
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database()"))
            db_name = result.fetchone()[0]
        print(f"  Connected to database: {db_name}")
    except Exception as e:
        print(f"  Connection failed: {e}")
