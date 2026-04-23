# ─────────────────────────────────────────────────────────────
#  DB Service – PostgreSQL 15 + Python helpers
#  SQL scripts in ./init/ run automatically on first startup.
#  Python scripts (db_helpers.py, load_data.py) run on demand.
# ─────────────────────────────────────────────────────────────

FROM postgres:15-alpine

# Install Python 3 + pip so db_helpers.py and load_data.py can run
RUN apk add --no-cache python3 py3-pip gcc musl-dev postgresql-dev python3-dev

# Install Python dependencies
RUN pip3 install --no-cache-dir --break-system-packages \
    psycopg2-binary==2.9.9 \
    pandas==2.2.2 \
    python-dotenv==1.0.1

# Copy SQL init scripts (run automatically on first start)
COPY init/ /docker-entrypoint-initdb.d/

# Copy Python helper scripts
RUN mkdir -p /app
COPY db_helpers.py /app/db_helpers.py
COPY load_data.py  /app/load_data.py

WORKDIR /app

EXPOSE 5432
