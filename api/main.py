from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal, ROUND_HALF_UP, getcontext
import os, json

# -------------------------------------------------------------
# Create FastAPI app
# -------------------------------------------------------------
app = FastAPI()

# ✅ Enable full CORS support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins
    allow_methods=["*"],       # Allow GET, POST, OPTIONS
    allow_headers=["*"],       # Allow all custom headers
    expose_headers=["*"],      # Expose all headers
)

# ✅ Handle CORS preflight requests
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
# Request schema
# -------------------------------------------------------------
class Query(BaseModel):
    regions: list[str]
    threshold_ms: int

# -------------------------------------------------------------
# Decimal math utilities
# -------------------------------------------------------------
getcontext().prec = 8  # ensure sufficient precision

def precise_mean(values):
    """Compute average using Decimal math to avoid float errors."""
    if not values:
        return Decimal("0.00")
    total = sum(Decimal(str(v)) for v in values)
    avg = total / Decimal(len(values))
    return avg.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def precise_percentile_95(values):
    """Manually compute 95th percentile using Decimal arithmetic."""
    if not values:
        return Decimal("0.00")
    sorted_vals = sorted(Decimal(str(v)) for v in values)
    k = (len(sorted_vals) - 1) * 0.95
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    d0 = sorted_vals[f] * (Decimal(c) - Decimal(k))
    d1 = sorted_vals[c] * (Decimal(k) - Decimal(f))
    val = d0 + d1
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# -------------------------------------------------------------
# Define POST endpoint
# -------------------------------------------------------------
@app.post("/api/latency")
async def latency(query: Query):
    regions = query.regions
    threshold = query.threshold_ms
    response = {}

    for region in regions:
        entries = [e for e in telemetry_data if e["region"] == region]
        if not entries:
            continue

        latencies = [e["latency_ms"] for e in entries]
        uptimes = [e["uptime_pct"] for e in entries]

        avg_latency = precise_mean(latencies)
        p95_latency = precise_percentile_95(latencies)
        avg_uptime = precise_mean(uptimes)
        breaches = sum(1 for l in latencies if l > threshold)

        response[region] = {
            "avg_latency_ms": float(avg_latency),
            "p95_latency_ms": float(p95_latency),
            "average_uptime_pct": float(avg_uptime),
            "breaches": breaches,
        }

    # ✅ Keep your preferred wrapper: {"regions": {...}}
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
