"""Shared FastAPI dependencies, request models, rate limiting, and PDF/plan helpers."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional

import db as finance_db
from fastapi import Header, HTTPException, Request
from pdf import _demo_data, build_pdf
from pydantic import BaseModel
from scoring import score_grade, score_signal

_AUTH_RATE_LOCK = threading.Lock()
_AUTH_ATTEMPTS: Dict[str, Deque[float]] = defaultdict(deque)
AUTH_RATE_LIMIT = 30
AUTH_RATE_WINDOW_SEC = 60.0


def check_auth_rate_limit(request: Request) -> None:
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


class PlanResetRequest(BaseModel):
    template: str = "blank"


class ModuleRunRequest(BaseModel):
    inputs: Dict[str, Any] = {}
    sync_to_plan: bool = False


class PlanChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []


def extract_bearer(authorization: Optional[str]) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return authorization.split(" ", 1)[1].strip()


def get_current_user(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = extract_bearer(authorization)
    user = finance_db.get_user_by_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return user


def render_pdf_bytes(data: Dict[str, Any]) -> bytes:
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


def normalize_plan_meta(title: Optional[str], payload: Dict[str, Any]) -> tuple[str, float, str, Dict[str, Any]]:
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
