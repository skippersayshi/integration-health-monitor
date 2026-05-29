from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from health_monitor import Monitor, ErrorAnalyzer, AutoFixer, RalphLoop

app = FastAPI(title="Integration Health Monitor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class HealthRequest(BaseModel):
    endpoints: List[str]

@app.post("/api/health")
async def check_health(req: HealthRequest):
    try:
        monitor = Monitor(interval_seconds=30.0)
        analyzer = ErrorAnalyzer()
        fixer = AutoFixer(max_retries=3)
        loop = RalphLoop(monitor, analyzer, fixer)
        loop.run_cycle(req.endpoints)
        statuses = [{"url": s.url, "status": s.status, "latency_ms": s.latency_ms, "error": s.error}
                    for s in monitor.last_results]
        return {"statuses": statuses}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/", response_class=HTMLResponse)
async def index():
    with open("index.html") as f:
        return f.read()
