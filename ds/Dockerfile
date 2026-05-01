# ─────────────────────────────────────────────────────────────
#  DS Service – Python 3.11 (Data Science / Pipeline)
#  Runs the MMM pipeline: EDA, adstock, saturation, model
# ─────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies needed by some Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first – Docker caches this layer
# so a code change doesn't re-download all packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the service code
COPY . .

# Install uvicorn for the trigger API (fastapi already in requirements)
RUN pip install --no-cache-dir uvicorn==0.29.0 fastapi==0.111.0

# Start the trigger API so back container can call POST /run to retrain
# Port 5000 is internal only — not exposed to host
CMD ["uvicorn", "trigger:app", "--host", "0.0.0.0", "--port", "5000"]
