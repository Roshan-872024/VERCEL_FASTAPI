from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json, math
from decimal import Decimal, ROUND_HALF_UP

app = FastAPI()

# ✅ Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.options("/{full_path:path}")
async def preflight_handler(request: Request, full_path: str):
    """Handles CORS preflight (OPTIONS) requests."""
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

class Query(BaseModel):
    regions: list[str]
    threshold_ms: int

# ✅ Linear interpolation percentile (Excel-style)
def percentile_linear(data, percentile):
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
    return data_sorted[lower] + (data_sorted[upper] - data_sorted[lower]) * (rank - lower)

@app.post("/api/latency")
async def latency(query: Query):
    response = {}

    for region in query.regions:
        entries = [e for e in telemetry_data if e["region"].lower() == region.lower()]
        if not entries:
            continue

        latencies = [float(e["latency_ms"]) for e in entries]
        uptimes = [float(e["uptime_pct"]) for e in entries]

        # ✅ avg_latency: normal mean rounded to 2 decimals
        avg_latency = round(sum(latencies) / len(latencies), 2)

        # ✅ p95_latency: linear interpolation + Decimal rounding
        p95_raw = percentile_linear(latencies, 95)
        p95_latency = float(Decimal(str(p95_raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        avg_uptime = round(sum(uptimes) / len(uptimes), 2)
        breaches = sum(1 for l in latencies if l > query.threshold_ms)

        response[region] = {
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "average_uptime_pct": avg_uptime,
            "breaches": breaches,
        }

    return JSONResponse(
        content={"regions": response},
        headers={"Access-Control-Allow-Origin": "*"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
