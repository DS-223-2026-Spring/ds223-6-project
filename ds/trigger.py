"""
trigger.py — lightweight HTTP trigger for the DS pipeline.
Runs as a separate process inside the ds container.
The back container calls POST /run to trigger baseline.py.

Start: uvicorn trigger:app --host 0.0.0.0 --port 5000
"""

import subprocess
import sys
import os
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="DS Trigger API")

@app.get("/health")
def health():
    return {"status": "ok", "service": "mmm-ds-trigger"}

@app.post("/run")
def run_pipeline():
    """Triggers baseline.py and returns stdout/stderr."""
    script = os.path.join(os.path.dirname(__file__), "models", "baseline.py")
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=300,
            cwd="/app",
        )
        if result.returncode != 0:
            return {
                "status": "failed",
                "error": result.stderr[-1000:],
                "stdout": result.stdout[-500:],
            }
        return {
            "status": "success",
            "stdout": result.stdout[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "error": "Pipeline exceeded 5 minutes"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
