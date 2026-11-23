#!/usr/bin/env python3
"""
Unified FastAPI server for FinPlan (Single-Port Architecture).

Serves both:
  - Static frontend UI from frontend/public/ (GET /, /styles.css, /app.js, ...)
  - REST API under /api/* (and /health, /api/docs)
"""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict

import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import db as finance_db
from pdf import _demo_data
from routes import auth_router, plans_router

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(os.environ.get("STATIC_DIR") or (REPO_ROOT / "frontend" / "public")).resolve()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    finance_db.init_db(seed_demo_payload=_demo_data())
    yield


app = FastAPI(
    title="FinPlan API",
    description="Unified single-port FastAPI + SQLite + ReportLab application.",
    version="2.2.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

cors_origins = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:8787,http://127.0.0.1:8787").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def root_health() -> Dict[str, str]:
    finance_db.init_db(seed_demo_payload=_demo_data())
    return {"status": "ok", "service": "ai-finance", "db": "ok"}


api = APIRouter(prefix="/api")
api.include_router(auth_router)
api.include_router(plans_router)
app.include_router(api)


@app.get("/robots.txt")
def robots_txt() -> Response:
    return Response(content="User-agent: *\nDisallow: /\n", media_type="text/plain")


@app.get("/{full_path:path}")
def serve_frontend(full_path: str) -> Response:
    """Serve static frontend assets and SPA fallback on the same single port."""
    if full_path.startswith("api/") or full_path == "api":
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    rel = full_path.lstrip("/") or "index.html"
    candidate = (STATIC_DIR / rel).resolve()
    try:
        candidate.relative_to(STATIC_DIR)
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

    if candidate.is_file():
        return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
    if "." in Path(rel).name:
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})
    return JSONResponse(status_code=404, content={"detail": "Frontend assets not found"})


def main() -> int:
    parser = argparse.ArgumentParser(description="Run unified single-port FastAPI server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8787, help="Port to listen on (default: 8787).")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
