#!/usr/bin/env python3
"""
FastAPI backend server for AI Personal Finance Advisor.

Endpoints:
  GET    /               -> Service overview & available endpoints
  GET    /health         -> {"status": "ok", "service": "ai-finance", "db": "ok"}
  POST   /auth/login     -> Authenticate with username/password (default: user/password)
  POST   /auth/logout    -> Revoke bearer session token
  GET    /auth/me        -> Return authenticated user info
  GET    /plans          -> List authenticated user's saved financial plans
  POST   /plans          -> Create a new financial plan in SQLite
  GET    /plans/{id}     -> Fetch a single saved plan
  PUT    /plans/{id}     -> Update an existing saved plan
  DELETE /plans/{id}     -> Delete a saved plan
  GET    /plans/{id}/pdf -> Generate PDF for a saved plan
  GET    /demo-data      -> Return sample financial plan JSON payload
  GET    /demo           -> Generate and return FINANCE-PLAN-sample.pdf
  POST   /generate       -> Generate PDF from posted JSON payload
  GET    /docs           -> Interactive Swagger UI
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import db as finance_db
from calculators import run_skill
from generate_finance_pdf import _demo_data, build_pdf, score_grade, score_signal
from skill_registry import VALID_SKILL_NAMES, get_skills_catalog


@asynccontextmanager
async def lifespan(_app: FastAPI):
    finance_db.init_db(seed_demo_payload=_demo_data())
    yield


app = FastAPI(
    title="AI Personal Finance Advisor API",
    description="FastAPI + SQLite + ReportLab backend for the unified AI Personal Finance Advisor app.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class PlanUpsertRequest(BaseModel):
    title: Optional[str] = None
    payload: Dict[str, Any]


class SkillRunRequest(BaseModel):
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


@app.get("/")
def root(request: Request) -> Any:
    accept = request.headers.get("accept", "")
    if "text/html" in accept.lower():
        host = request.url.hostname or "127.0.0.1"
        return RedirectResponse(url=f"http://{host}:3000", status_code=307)
    return {
        "service": "ai-finance",
        "status": "ok",
        "frontend_url": "http://localhost:3000",
        "docs_url": "/docs",
        "endpoints": [
            "/health",
            "/auth/login",
            "/auth/me",
            "/auth/logout",
            "/plans",
            "/skills",
            "/demo",
            "/demo-data",
            "/generate",
            "/docs",
        ],
    }


@app.get("/health")
def health() -> Dict[str, str]:
    finance_db.init_db(seed_demo_payload=_demo_data())
    return {"status": "ok", "service": "ai-finance", "db": "ok"}


@app.post("/auth/login")
def login(body: LoginRequest) -> Dict[str, Any]:
    finance_db.init_db(seed_demo_payload=_demo_data())
    result = finance_db.authenticate_user(body.username, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return result


@app.post("/auth/register", status_code=201)
def register(body: LoginRequest) -> Dict[str, Any]:
    finance_db.init_db(seed_demo_payload=_demo_data())
    try:
        return finance_db.register_user(body.username, body.password, seed_demo_payload=_demo_data())
    except finance_db.DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    token = _extract_bearer(authorization)
    finance_db.revoke_token(token)
    return {"status": "logged_out"}


@app.get("/auth/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return user


@app.get("/plans")
def list_user_plans(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, List[Dict[str, Any]]]:
    return {"plans": finance_db.list_plans(user["id"])}


@app.post("/plans", status_code=201)
def create_user_plan(
    body: PlanUpsertRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    title, score, grade, normalized = _normalize_plan_meta(body.title, body.payload)
    return finance_db.create_plan(user["id"], title, score, grade, normalized)


@app.get("/plans/{plan_id}")
def get_user_plan(plan_id: int, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@app.put("/plans/{plan_id}")
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


@app.delete("/plans/{plan_id}")
def delete_user_plan(plan_id: int, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, str]:
    deleted = finance_db.delete_plan(user["id"], plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "deleted"}


@app.get("/plans/{plan_id}/pdf")
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


@app.get("/skills")
def list_skills() -> Dict[str, Any]:
    return get_skills_catalog()


@app.get("/plans/{plan_id}/skills")
def get_plan_skill_runs(
    plan_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    runs = finance_db.list_skill_runs(user["id"], plan_id)
    return {"plan_id": plan_id, "runs": runs, "completed_skills": [r["skill_name"] for r in runs]}


@app.post("/plans/{plan_id}/skills/{skill_name}/run")
def run_plan_skill(
    plan_id: int,
    skill_name: str,
    body: SkillRunRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if skill_name not in VALID_SKILL_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown skill '{skill_name}'")
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    result = run_skill(skill_name, body.inputs, plan["payload"])
    saved_run = finance_db.upsert_skill_run(
        user["id"],
        plan_id,
        skill_name,
        body.inputs,
        result,
        score=result.get("score"),
    )

    updated_plan = None
    if body.sync_to_plan and result.get("plan_patch"):
        merged = dict(plan["payload"])
        for k, v in result["plan_patch"].items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        title, score, grade, normalized = _normalize_plan_meta(plan["title"], merged)
        updated_plan = finance_db.update_plan(user["id"], plan_id, title, score, grade, normalized)

    return {"run": saved_run, "result": result, "updated_plan": updated_plan}


@app.get("/demo-data")
def demo_data() -> Dict[str, Any]:
    return _demo_data()


@app.get("/demo")
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


@app.post("/generate")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run FastAPI localhost backend server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8787, help="Port to listen on (default: 8787).")
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
