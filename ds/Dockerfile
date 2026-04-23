# ─────────────────────────────────────────────────────────────
#  DS Service – Python 3.13 (Data Science / Pipeline)
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

# Keep container alive so you can exec into it and run scripts
# In Sprint 2 this becomes: CMD ["python", "pipeline/run_pipeline.py"]
CMD ["tail", "-f", "/dev/null"]
