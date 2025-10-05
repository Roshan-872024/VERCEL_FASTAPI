from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import os, json

# -------------------------------------------------------------
# Create FastAPI app
# -------------------------------------------------------------
app = FastAPI()

# ✅ Enable CORS for all origins and methods
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # Allows all origins (your dashboard, browser, etc.)
    allow_methods=["*"],      # Allow all HTTP methods
    allow_headers=["*"],      # Allow all custom headers
    expose_headers=["*"],     # Expose all headers in browser response
)

# ✅ Universal handler for CORS preflight (OPTIONS requests)
@app.options("/{full_path:path}")
async def preflight_handler(request: Request, full_path: str):
    """Handles any CORS preflight request (required by browsers)."""
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

        avg_latency = np.mean(latencies)
        p95_latency = np.percentile(latencies, 95)
        avg_uptime = np.mean(uptimes)
        breaches = sum(1 for l in latencies if l > threshold)

        response[region] = {
            "avg_latency_ms": round(float(avg_latency), 2),
            "p95_latency_ms": round(float(p95_latency), 2),
            "average_uptime_pct": round(float(avg_uptime), 2),
            "breaches": breaches,
        }

    # ✅ Include CORS headers in the response
    return JSONResponse(
    content={"regions": response},
    headers={"Access-Control-Allow-Origin": "*"}
)


# -------------------------------------------------------------
# Local testing (won’t run on Vercel)
# -------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
