# api/index.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import os
import math

app = FastAPI()

# --- CORS: allow any origin to POST ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # allow all origins
    allow_credentials=False,
    allow_methods=["POST"],    # only POST is needed
    allow_headers=["*"],
)

# --- Load telemetry once at startup ---
# Assumes q-vercel-latency.json is in the project root
TELEMETRY_PATH = os.path.join(os.path.dirname(__file__), "..", "q-vercel-latency.json")

with open(TELEMETRY_PATH, "r") as f:
    telemetry_data = json.load(f)

# --- Request body schema ---
class AnalyticsRequest(BaseModel):
    regions: List[str]
    threshold_ms: float

# --- Helper functions ---

def mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)

def percentile(values: List[float], p: float) -> float:
    """
    Simple percentile: p in [0, 100].
    For example, p=95 -> 95th percentile.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    # position in sorted list
    k = (p / 100) * (len(sorted_vals) - 1)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    # linear interpolation
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

# --- POST endpoint ---

@app.post("/analytics")
def analytics(body: AnalyticsRequest) -> Dict[str, Any]:
    regions = body.regions
    threshold = body.threshold_ms

    if not regions:
        raise HTTPException(status_code=400, detail="regions list cannot be empty")

    # Prepare response as a dict keyed by region
    response: Dict[str, Dict[str, float]] = {}

    for region in regions:
        # Filter telemetry for this region
        region_records = [r for r in telemetry_data if r.get("region") == region]

        if not region_records:
            # If no data for this region, you can either skip or return zeros.
            # Here we'll return zeros.
            response[region] = {
                "avg_latency": 0.0,
                "p95_latency": 0.0,
                "avg_uptime": 0.0,
                "breaches": 0,
            }
            continue

        latencies = [float(r["latency_ms"]) for r in region_records]
        uptimes = [float(r["uptime"]) for r in region_records]

        avg_latency = mean(latencies)
        p95_latency = percentile(latencies, 95)
        avg_uptime = mean(uptimes)
        breaches = sum(1 for v in latencies if v > threshold)

        response[region] = {
            "avg_latency": avg_latency,
            "p95_latency": p95_latency,
            "avg_uptime": avg_uptime,
            "breaches": breaches,
        }

    return response

# Default GET just to test the root
@app.get("/")
def read_root():
    return {"message": "Latency analytics API is running"}
