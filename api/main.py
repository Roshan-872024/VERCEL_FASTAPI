from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json, math

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
# Helper: manual 95th percentile (nearest-rank)
# -------------------------------------------------------------
def percentile_nearest_rank(data, percentile):
    if not data:
        return None
    data_sorted = sorted(data)
    k = math.ceil((percentile / 100) * len(data_sorted))
    return data_sorted[min(k - 1, len(data_sorted) - 1)]

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

        # Compute metrics
        avg_latency = round(sum(latencies) / len(latencies), 2)
        p95_latency = round(percentile_nearest_rank(latencies, 95), 2)
        avg_uptime = round(sum(uptimes) / len(uptimes), 2)
        breaches = sum(1 for l in latencies if l > query.threshold_ms)

        response[region] = {
            "avg_latency_ms": float(avg_latency),
            "avg_latency": float(avg_latency),
            "p95_latency_ms": float(p95_latency),
            "p95_latency": float(p95_latency),
            "average_uptime_pct": float(avg_uptime),
            "breaches": int(breaches),
        }

    return JSONResponse(
        content={"regions": response},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# -------------------------------------------------------------
# Local testing
# -------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
