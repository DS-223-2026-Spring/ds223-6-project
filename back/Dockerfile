# ─────────────────────────────────────────────────────────────
#  Backend Service – FastAPI (Python 3.11)
#  REST API that serves model results and runs the optimizer.
#  Swagger UI available at http://localhost:8000/docs
# ─────────────────────────────────────────────────────────────

FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run FastAPI with uvicorn
# --reload enables hot-reload when code changes (dev mode)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

EXPOSE 8000
