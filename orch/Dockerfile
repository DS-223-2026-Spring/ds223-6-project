# ─────────────────────────────────────────────────────────────
#  Orchestration Service – Prefect (Python 3.13)
#  Manages and schedules pipeline runs.
#  Prefect UI at http://localhost:4200
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Start Prefect server (Prefect 3 syntax — no --host flag needed)
CMD ["prefect", "server", "start", "--host", "0.0.0.0", "--port", "4200"]

EXPOSE 4200
