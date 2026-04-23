"""
config.py
Centralized configuration for all Prefect flow parameters.
Values are read from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Database ──────────────────────────────────────────────
DB_HOST     = os.getenv("POSTGRES_HOST",     "db")
DB_PORT     = os.getenv("POSTGRES_PORT",     "5432")
DB_NAME     = os.getenv("POSTGRES_DB",       "mmm_db")
DB_USER     = os.getenv("POSTGRES_USER",     "mmm_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "mmm_pass")

# ── File paths ────────────────────────────────────────────
DATA_DIR          = os.getenv("DATA_DIR", "/app/data")
WEEKLY_CSV        = os.path.join(DATA_DIR, "dt_simulated_weekly.csv")
HOLIDAYS_CSV      = os.path.join(DATA_DIR, "dt_prophet_holidays.csv")
CURVE_CSV         = os.path.join(DATA_DIR, "df_curve_reach_freq.csv")

# ── Run modes ─────────────────────────────────────────────
RUN_MODE          = os.getenv("RUN_MODE", "manual")     # manual | scheduled
RELOAD_DATA       = os.getenv("RELOAD_DATA", "false").lower() == "true"
RUN_MODEL         = os.getenv("RUN_MODEL",   "false").lower() == "true"

# ── Expected data shape (for validation) ─────────────────
EXPECTED_WEEKS    = 208
EXPECTED_CHANNELS = ["tv", "ooh", "print", "facebook", "search"]
EXPECTED_SPEND_ROWS = EXPECTED_WEEKS * len(EXPECTED_CHANNELS)  # 1040

# ── Model settings ────────────────────────────────────────
MODEL_VERSION     = os.getenv("MODEL_VERSION", "v1.0-ols")
ADSTOCK_DECAY     = {
    "tv": 0.68, "ooh": 0.40, "print": 0.35, "facebook": 0.25, "search": 0.12
}
