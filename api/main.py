from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import os, json
from decimal import Decimal, ROUND_HALF_UP

app = FastAPI()

# Enable CORS
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

# Load telemetry data
file_path = os.path.join(os.path.dirname(__file__), "q-vercel-latency.json")
with open(file_path, "r") as f:
    telemetry_data = json.load(f)

# Request model
class Query(BaseModel):
    regions: list[str]
    threshold_ms: int

# Helper: Round precisely to 2 decimal places (e.g., 165.05)
def precise_round(value):
    return float(Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# Endpoint
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

        avg_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)
        avg_uptime = np.mean(uptimes)
        breaches = sum(1 for l in latencies if l > threshold)

        response[region] = {
            "avg_latency_ms": precise_round(avg_latency),
            "p95_latency_ms": precise_round(p95_latency),
            "average_uptime_pct": precise_round(avg_uptime),
            "breaches": breaches,
        }

    return JSONResponse(content={"regions": response},
                        headers={"Access-Control-Allow-Origin": "*"})

# Local test
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
