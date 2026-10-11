"""
main.py: FastAPI entrypoint for Bankism Gateway.
Exposes:
- POST /api/screen
- POST /api/execute
- GET /api/account
- POST /api/reset
- GET /api/audit
- GET /api/results
- GET /healthz
Mounts static files for the console UI.
Enforces per-IP rate limiting and fail-closed security.
"""

import os
import time
from typing import Dict, List, Any
from pathlib import Path
from collections import defaultdict
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

load_dotenv()

from .schemas import ScreenRequest, ExecuteRequest, VerdictResponse, AccountResponse
from .pipeline import execute_firewall_pipeline
from .mock_bank import bank_instance

app = FastAPI(title="Bankism Deterministic AI Firewall Gateway", version="1.0.0")

# In-memory audit log (last 50 requests)
AUDIT_LOG: List[Dict[str, Any]] = []

# Basic per-IP sliding window rate limiter (max 60 requests per minute)
IP_REQUEST_TIMESTAMPS = defaultdict(list)
RATE_LIMIT_PER_MINUTE = 60

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Only rate limit /api endpoints
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        timestamps = IP_REQUEST_TIMESTAMPS[client_ip]
        # Keep timestamps within last 60s
        IP_REQUEST_TIMESTAMPS[client_ip] = [ts for ts in timestamps if now - ts < 60]
        if len(IP_REQUEST_TIMESTAMPS[client_ip]) >= RATE_LIMIT_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"detail": "RATE_LIMIT_EXCEEDED: Maximum 60 requests per minute per IP."}
            )
        IP_REQUEST_TIMESTAMPS[client_ip].append(now)

    response = await call_next(request)
    return response

@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "service": "Bankism Firewall",
        "mode": os.getenv("LLM_MODE", "offline"),
        "version": "1.0.0"
    }

@app.post("/api/screen", response_model=VerdictResponse)
async def screen_endpoint(payload: ScreenRequest, request: Request):
    llm_mode = os.getenv("LLM_MODE", "offline")
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Check if header requested simulated compromise (test harness only if enabled)
    simulate_compromise = False
    if os.getenv("DEMO_HARNESS", "0") == "1":
        simulate_compromise = request.headers.get("x-simulate-compromised-model") == "true"

    try:
        verdict = await execute_firewall_pipeline(
            command=payload.command,
            memo=payload.memo,
            llm_mode=llm_mode,
            model_name=model_name,
            simulate_compromise=simulate_compromise
        )

        # Append to in-memory audit log (retain last 50)
        AUDIT_LOG.insert(0, {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "request_id": verdict["request_id"],
            "command": payload.command[:80] + ("..." if len(payload.command) > 80 else ""),
            "verdict": verdict["verdict"],
            "threat_category": verdict["threat_category"],
            "risk_score": verdict["risk_score"],
            "raw_verdict": verdict
        })
        if len(AUDIT_LOG) > 50:
            AUDIT_LOG.pop()

        return verdict
    except Exception as e:
        # Strict Fail Closed: Never return unvalidated status
        raise HTTPException(
            status_code=500,
            detail=f"FAIL_CLOSED_SYSTEM_ERROR: {type(e).__name__} - {str(e)}"
        )

@app.post("/api/execute")
async def execute_endpoint(payload: ExecuteRequest):
    result = bank_instance.execute_mandate(
        mandate_payload=payload.mandate.payload.model_dump(),
        signature=payload.mandate.signature
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@app.get("/api/account", response_model=AccountResponse)
async def get_account_endpoint():
    return bank_instance.get_account_summary()

@app.post("/api/reset")
async def reset_endpoint():
    bank_instance.reset()
    AUDIT_LOG.clear()
    return {"status": "success", "message": "Demo banking environment and audit log reset."}

@app.get("/api/audit")
async def get_audit_endpoint():
    return AUDIT_LOG

@app.get("/api/results")
async def get_results_endpoint():
    results_file = Path(__file__).resolve().parent.parent / "static" / "results.json"
    if results_file.exists():
        return FileResponse(results_file, media_type="application/json")
    return {
        "status": "pending",
        "message": "Run tests/run_eval.py to generate live precomputed benchmark metrics."
    }

# Mount static directory for UI
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")
