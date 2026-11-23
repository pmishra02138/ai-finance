"""Health and authentication routes (`/api/health`, `/api/auth/*`)."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import db as finance_db
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pdf import _demo_data

from .deps import LoginRequest, check_auth_rate_limit, extract_bearer, get_current_user

router = APIRouter()


@router.get("/health")
def health() -> Dict[str, str]:
    finance_db.init_db(seed_demo_payload=_demo_data())
    return {"status": "ok", "service": "ai-finance", "db": "ok"}


@router.post("/auth/login")
def login(body: LoginRequest, request: Request) -> Dict[str, Any]:
    check_auth_rate_limit(request)
    finance_db.init_db(seed_demo_payload=_demo_data())
    result = finance_db.authenticate_user(body.username, body.password)
    if result is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return result


@router.post("/auth/register", status_code=201)
def register(body: LoginRequest, request: Request) -> Dict[str, Any]:
    if os.environ.get("FINPLAN_ALLOW_REGISTRATION", "1") == "0":
        raise HTTPException(status_code=403, detail="Account registration is disabled on this instance.")
    check_auth_rate_limit(request)
    finance_db.init_db(seed_demo_payload=_demo_data())
    try:
        return finance_db.register_user(body.username, body.password, seed_demo_payload=_demo_data())
    except finance_db.DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auth/logout")
def logout(authorization: Optional[str] = Header(default=None)) -> Dict[str, str]:
    token = extract_bearer(authorization)
    finance_db.revoke_token(token)
    return {"status": "logged_out"}


@router.get("/auth/me")
def me(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    return user
