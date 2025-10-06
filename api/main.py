from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from decimal import Decimal, ROUND_HALF_UP
import os, json, math

app = FastAPI()

# Enable full CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.options("/{full_path:path}")
async def preflight_handler(request: Request, full_path: str):
    """Handles preflight OPTIONS requests for CORS."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )

# Load telemetry JSON file
file_path = os.path.join(os.path.dirname(__file__), "q-vercel-latency.json")
with open(file_path, "r") as f:
    telemetry_data = json.load(f)

class Query(BaseModel):
    regions: list[str]
    threshold_ms: int

# Linear interpolation (Excel-style percentile)
def percentile_linear(data, percentile):
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

        latencies = [Decimal(str(e["latency_ms"])) for e in entries]
        uptimes = [Decimal(str(e["uptime_pct"])) for e in entries]

        # ✅ Use Decimal for exact rounding of mean and percentile
        avg_latency_val = sum(latencies) / Decimal(len(latencies))
        avg_latency = avg_latency_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        p95_raw = percentile_linear([float(l) for l in latencies], 95)
        p95_latency = Decimal(str(p95_raw)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        avg_uptime_val = sum(uptimes) / Decimal(len(uptimes))
        avg_uptime = avg_uptime_val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        breaches = sum(1 for l in latencies if l > Decimal(query.threshold_ms))

        response[region] = {
            "avg_latency": float(avg_latency),
            "p95_latency": float(p95_latency),
            "average_uptime": float(avg_uptime),
            "breaches": int(breaches),
        }

    return JSONResponse(
        content={"regions": response},
        headers={"Access-Control-Allow-Origin": "*"},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
