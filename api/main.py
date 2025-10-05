from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import os, json

# Create FastAPI instance
app = FastAPI()

# Enable CORS for all origins (for dashboards or browsers)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to telemetry data file
file_path = os.path.join(os.path.dirname(__file__), "q-vercel-latency.json")

# Load telemetry data at startup
with open(file_path, "r") as f:
    telemetry_data = json.load(f)

# Define request schema
class Query(BaseModel):
    regions: list[str]
    threshold_ms: int

# Define POST endpoint
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

    return JSONResponse(response)


# Local test support (optional, ignored on Vercel)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
