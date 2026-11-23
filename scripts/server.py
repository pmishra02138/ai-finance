#!/usr/bin/env python3
"""
Unified FastAPI server for AI Personal Finance Advisor (Single-Port Architecture).

Serves both:
  - Static frontend UI from frontend/public/ (GET /, /styles.css, /app.js, ...)
  - REST API under /api/* (and /health, /docs)

Endpoints:
  GET    /                       -> Frontend SPA (index.html)
  GET    /health | /api/health   -> {"status": "ok", "service": "ai-finance", "db": "ok"}
  POST   /api/auth/login         -> Authenticate (default: user / password)
  POST   /api/auth/register      -> Create new user account
  POST   /api/auth/logout        -> Revoke bearer session token
  GET    /api/auth/me            -> Return authenticated user info
  GET    /api/modules            -> List 5-stage 14-module catalog
  GET    /api/plans              -> List user's saved financial plans
  POST   /api/plans              -> Create a new financial plan
  GET    /api/plans/{id}         -> Fetch a single plan
  PUT    /api/plans/{id}         -> Update a plan
  DELETE /api/plans/{id}         -> Delete a plan
  GET    /api/plans/{id}/pdf     -> Generate PDF for a saved plan
  GET    /api/plans/{id}/modules -> List saved module runs for a plan
  POST   /api/plans/{id}/modules/{name}/run -> Run calculator & optionally sync to plan
  GET    /api/demo-data          -> Return sample plan JSON
  GET    /api/demo               -> Generate sample PDF
  POST   /api/generate           -> Generate PDF from posted JSON
  GET    /api/docs               -> Interactive Swagger UI
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import db as finance_db
from ai_copilot import CopilotAPIError, CopilotConfigError, ask_copilot
from calculators import run_module
from module_registry import VALID_MODULE_NAMES, get_modules_catalog
from pdf import _demo_data, build_pdf
from scoring import score_grade, score_signal

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(os.environ.get("STATIC_DIR") or (REPO_ROOT / "frontend" / "public")).resolve()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    finance_db.init_db(seed_demo_payload=_demo_data())
    yield


app = FastAPI(
    title="AI Personal Finance Advisor API",
    description="Unified single-port FastAPI + SQLite + ReportLab application.",
    version="2.1.0",
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

_AUTH_RATE_LOCK = threading.Lock()
_AUTH_ATTEMPTS: Dict[str, Deque[float]] = defaultdict(deque)
AUTH_RATE_LIMIT = 30
AUTH_RATE_WINDOW_SEC = 60.0


def _check_auth_rate_limit(request: Request) -> None:
    ip = (request.client.host if request.client else None) or "unknown"
    now = time.monotonic()
    with _AUTH_RATE_LOCK:
        dq = _AUTH_ATTEMPTS[ip]
        while dq and now - dq[0] > AUTH_RATE_WINDOW_SEC:
            dq.popleft()
        if len(dq) >= AUTH_RATE_LIMIT:
            raise HTTPException(status_code=429, detail="Too many authentication attempts. Please wait and retry.")
        dq.append(now)


class LoginRequest(BaseModel):
    username: str
    password: str


class PlanUpsertRequest(BaseModel):
    title: Optional[str] = None
    payload: Dict[str, Any]


class ModuleRunRequest(BaseModel):
    inputs: Dict[str, Any] = {}
    sync_to_plan: bool = False


def _extract_bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = _extract_bearer(authorization)
    user = finance_db.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return user


def _render_pdf_bytes(data: Dict[str, Any]) -> bytes:
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        build_pdf(data, tmp_path)
        with open(tmp_path, "rb") as fh:
            return fh.read()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def _normalize_plan_meta(title: Optional[str], payload: Dict[str, Any]) -> tuple[str, float, str, Dict[str, Any]]:
    data = dict(payload)
    cats = data.get("categories") or {}
    if "health_score" in data and data["health_score"] is not None:
        score = float(data["health_score"])
    elif cats:
        vals = [float(cats.get(k, 0)) for k in ("cash_flow", "debt", "investments", "retirement", "protection")]
        score = round(sum(vals) / len(vals), 1)
        data["health_score"] = score
    else:
        score = 0.0
        data["health_score"] = score

    grade = str(data.get("grade") or score_grade(score))
    data["grade"] = grade
    if not data.get("signal"):
        data["signal"] = score_signal(score)

    resolved_title = (title or data.get("client_name") or "Personal Financial Plan").strip()
    return resolved_title, score, grade, data


api = APIRouter(prefix="/api")


@app.get("/health")
@api.get("/health")
def health() -> Dict[str, str]:
    finance_db.init_db(seed_demo_payload=_demo_data())
    return {"status": "ok", "service": "ai-finance", "db": "ok"}


@api.post("/auth/login")
def login(body: LoginRequest, request: Request) -> Dict[str, Any]:
    _check_auth_rate_limit(request)
    finance_db.init_db(seed_demo_payload=_demo_data())
    result = finance_db.authenticate_user(body.username, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return result


@api.post("/auth/register", status_code=201)
def register(body: LoginRequest, request: Request) -> Dict[str, Any]:
    if os.environ.get("FINPLAN_ALLOW_REGISTRATION", "1") == "0":
        raise HTTPException(status_code=403, detail="Account registration is disabled on this instance.")
    _check_auth_rate_limit(request)
    finance_db.init_db(seed_demo_payload=_demo_data())
    try:
        return finance_db.register_user(body.username, body.password, seed_demo_payload=_demo_data())
    except finance_db.DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@api.post("/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    token = _extract_bearer(authorization)
    finance_db.revoke_token(token)
    return {"status": "logged_out"}


@api.get("/auth/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return user


@api.get("/modules")
def list_modules() -> Dict[str, Any]:
    return get_modules_catalog()


@api.get("/plans")
def list_user_plans(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, List[Dict[str, Any]]]:
    return {"plans": finance_db.list_plans(user["id"])}


@api.post("/plans", status_code=201)
def create_user_plan(
    body: PlanUpsertRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    title, score, grade, normalized = _normalize_plan_meta(body.title, body.payload)
    return finance_db.create_plan(user["id"], title, score, grade, normalized)


@api.get("/plans/{plan_id}")
def get_user_plan(plan_id: int, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@api.put("/plans/{plan_id}")
def update_user_plan(
    plan_id: int,
    body: PlanUpsertRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    title, score, grade, normalized = _normalize_plan_meta(body.title, body.payload)
    updated = finance_db.update_plan(user["id"], plan_id, title, score, grade, normalized)
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated


class PlanResetRequest(BaseModel):
    template: str = "blank"


@api.post("/plans/{plan_id}/reset")
def reset_user_plan(
    plan_id: int,
    body: PlanResetRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    existing = finance_db.get_plan(user["id"], plan_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan_title = existing["title"]
    if body.template == "sample":
        raw_payload = {**_demo_data(), "client_name": plan_title}
    else:
        raw_payload = {
            "client_name": plan_title,
            "health_score": 0,
            "grade": "--",
            "signal": "New Plan — Run Modules to Score",
            "categories": {"cash_flow": 0, "debt": 0, "investments": 0, "retirement": 0, "protection": 0},
            "cash_flow": {"monthly_income": 0, "gross_annual_income": 0, "expenses": []},
            "debt": {"accounts": []},
            "investments": {"total_value": 0, "allocation": []},
            "retirement": {"current_age": 35, "retirement_age": 65, "current_balance": 0, "target_balance": 0, "monthly_contribution": 0},
            "protection": {"items": []},
            "action_items": [],
        }

    _, score, grade, normalized = _normalize_plan_meta(plan_title, raw_payload)
    updated = finance_db.reset_plan(user["id"], plan_id, score, grade, normalized)
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated


@api.delete("/plans/{plan_id}")
def delete_user_plan(plan_id: int, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, str]:
    deleted = finance_db.delete_plan(user["id"], plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "deleted"}


@api.get("/plans/{plan_id}/pdf")
def get_user_plan_pdf(
    plan_id: int,
    inline: bool = Query(False),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    try:
        pdf_bytes = _render_pdf_bytes(plan["payload"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="FINANCE-PLAN-{plan_id}.pdf"'},
    )


@api.get("/plans/{plan_id}/modules")
def get_plan_module_runs(
    plan_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    runs = finance_db.list_module_runs(user["id"], plan_id)
    return {"plan_id": plan_id, "runs": runs, "completed_modules": [r["module_name"] for r in runs]}


@api.post("/plans/{plan_id}/modules/{module_name}/run")
def run_plan_module(
    plan_id: int,
    module_name: str,
    body: ModuleRunRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if module_name not in VALID_MODULE_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown module '{module_name}'")
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    result = run_module(module_name, body.inputs, plan["payload"])
    saved_run = finance_db.upsert_module_run(
        user["id"],
        plan_id,
        module_name,
        body.inputs,
        result,
        score=result.get("score"),
    )

    updated_plan = None
    if body.sync_to_plan and result.get("plan_patch"):
        patch = result["plan_patch"]
        merged = dict(plan["payload"])
        for k, v in patch.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        if "categories" in patch and "health_score" not in patch:
            merged.pop("health_score", None)
            merged.pop("grade", None)
            merged.pop("signal", None)
        title, score, grade, normalized = _normalize_plan_meta(plan["title"], merged)
        updated_plan = finance_db.update_plan(user["id"], plan_id, title, score, grade, normalized)

    return {"run": saved_run, "result": result, "updated_plan": updated_plan}


class PlanChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []


@api.post("/plans/{plan_id}/chat")
def chat_with_copilot(
    plan_id: int,
    body: PlanChatRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, str]:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    runs = finance_db.list_module_runs(user["id"], plan_id)
    try:
        return ask_copilot(body.message, body.history, plan, runs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CopilotConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CopilotAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@api.get("/demo-data")
def demo_data() -> Dict[str, Any]:
    return _demo_data()


@api.get("/demo")
def demo_pdf(inline: bool = Query(False)) -> Response:
    try:
        pdf_bytes = _render_pdf_bytes(_demo_data())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="FINANCE-PLAN-sample.pdf"'},
    )


@api.post("/generate")
def generate_pdf(payload: Dict[str, Any]) -> Response:
    try:
        pdf_bytes = _render_pdf_bytes(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="FINANCE-PLAN.pdf"'},
    )


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
