from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json
from decimal import Decimal, ROUND_HALF_UP
import math

# -------------------------------------------------------------
# Initialize FastAPI app
# -------------------------------------------------------------
app = FastAPI()

# ✅ Enable CORS (for dashboards/browsers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ✅ Handle preflight OPTIONS requests
@app.options("/{full_path:path}")
async def preflight_handler(request: Request, full_path: str):
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )

# -------------------------------------------------------------
# Load telemetry data
# -------------------------------------------------------------
file_path = os.path.join(os.path.dirname(__file__), "q-vercel-latency.json")

with open(file_path, "r") as f:
    telemetry_data = json.load(f)

# -------------------------------------------------------------
# Define request body schema
# -------------------------------------------------------------
class Query(BaseModel):
    regions: list[str]
    threshold_ms: int

# -------------------------------------------------------------
# Manual linear interpolation percentile
# -------------------------------------------------------------
def percentile_linear(data, percentile):
    """Manual linear interpolation percentile implementation."""
    if not data:
        return None
    data_sorted = sorted(data)
    N = len(data_sorted)
    if N == 1:
        return data_sorted[0]
    rank = (percentile / 100) * (N - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return data_sorted[int(rank)]
    d0 = data_sorted[lower] * (upper - rank)
    d1 = data_sorted[upper] * (rank - lower)
    return d0 + d1

# -------------------------------------------------------------
# POST endpoint
# -------------------------------------------------------------
@app.post("/api/latency")
async def latency(query: Query):
    response = {}

    for region in query.regions:
        entries = [e for e in telemetry_data if e["region"].lower() == region.lower()]
        if not entries:
            continue

        latencies = [float(e["latency_ms"]) for e in entries]
        uptimes = [float(e["uptime_pct"]) for e in entries]

        # Average latency (mean)
        avg_latency = round(sum(latencies) / len(latencies), 2)

        # ✅ Linear interpolation percentile
        p95_latency = percentile_linear(latencies, 95)
        p95_latency = float(Decimal(str(p95_latency)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        avg_uptime = round(sum(uptimes) / len(uptimes), 2)
        breaches = sum(1 for l in latencies if l > query.threshold_ms)

        response[region] = {
            "avg_latency_ms": float(avg_latency),
            "p95_latency_ms": float(p95_latency),
            "average_uptime_pct": float(avg_uptime),
            "breaches": int(breaches),
        }

    return JSONResponse(
        content={"regions": response},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# -------------------------------------------------------------
# Local testing (won’t run on Vercel)
# -------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
