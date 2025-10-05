from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import os, json

# Create FastAPI app
app = FastAPI()

# ✅ Enable CORS explicitly (for browsers and dashboards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_methods=["GET", "POST", "OPTIONS"],  # Explicitly include OPTIONS
    allow_headers=["*"],
)

# ✅ Handle preflight requests (important for Vercel + browsers)
@app.options("/api/latency")
async def options_latency():
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*"
        }
    )

# ✅ Load telemetry data file
file_path = os.path.join(os.path.dirname(__file__), "q-vercel-latency.json")

with open(file_path, "r") as f:
    telemetry_data = json.load(f)

# ✅ Define request schema
class Query(BaseModel):
    regions: list[str]
