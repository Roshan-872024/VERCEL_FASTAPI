from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import os, json
from decimal import Decimal, ROUND_HALF_UP, getcontext

# -------------------------------------------------------------
# Create FastAPI app
# -------------------------------------------------------------
app = FastAPI()

# Enable CORS for all origins and methods
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Handle preflight requests
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
# Helper: exact rounding (2 decimal places, round-half-up)
# -------------------------------------------------------------
getcontext().prec = 6  # enough precision
def precise(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# -------------------------------------------------------------
# Endpoint
# -------------------------------------------------------------
@app.post("/api/latency")
async def latency(query: Query):
    response = {}
    for region in query.regions:
        entries = [e for e in telemetry_data if e["region"] == region]
        if not entries:
            continue

        latencies = np.array([e["latency_ms"] for e in entries], dtype=float)
        uptimes = np.array([e["uptime_pct"] for e in entries], dtype=float)

        avg_latency = precise(np.mean(latencies))
        p95_latency = precise(np.percentile(latencies, 95))
        avg_uptime = precise(np.mean(uptimes))
        breaches = int(np.sum(latencies > query.threshold_ms))

        response[region] = {
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "average_uptime_pct": avg_uptime,
            "breaches": breaches,
        }

    return JSONResponse(content=response, headers={"Access-Control-Allow-Origin": "*"})

# -------------------------------------------------------------
# Local test (optional)
# -------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
