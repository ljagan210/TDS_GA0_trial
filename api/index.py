import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Load the telemetry file that sits next to this script (any .json file in this folder)
DATA_FILE = sorted(Path(__file__).parent.glob("*.json"))[0]
RECORDS = json.loads(DATA_FILE.read_text(encoding="utf-8"))


def find_key(record, word):
    """Return the column whose name contains `word`, e.g. 'latency' -> 'latency_ms'."""
    return next(k for k in record if word in k.lower())


REGION_KEY = find_key(RECORDS[0], "region")
LATENCY_KEY = find_key(RECORDS[0], "latency")
UPTIME_KEY = find_key(RECORDS[0], "uptime")


def percentile(values, pct):
    """Percentile with linear interpolation (same method as numpy's default)."""
    ordered = sorted(values)
    if not ordered:
        return 0
    position = (len(ordered) - 1) * pct / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def compute(regions, threshold_ms):
    result = {}
    for region in regions:
        rows = [r for r in RECORDS if r[REGION_KEY] == region]
        latencies = [r[LATENCY_KEY] for r in rows]
        uptimes = [r[UPTIME_KEY] for r in rows]
        result[region] = {
            "avg_latency": sum(latencies) / len(latencies) if rows else 0,
            "p95_latency": percentile(latencies, 95),
            "avg_uptime": sum(uptimes) / len(uptimes) if rows else 0,
            "breaches": sum(1 for value in latencies if value > threshold_ms),
        }
    return result


# Catch-all route, so the endpoint works at /, /api, /api/latency, and so on
@app.post("/{path:path}")
async def latency(request: Request, path: str = ""):
    body = await request.json()
    return {"regions": compute(body.get("regions", []), body.get("threshold_ms", 180))}


@app.get("/{path:path}")
def health(path: str = ""):
    return {"status": "ok", "records": len(RECORDS), "send": "POST with regions and threshold_ms"}
