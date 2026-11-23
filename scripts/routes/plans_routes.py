"""Financial plans, module calculators, Plan Insights chat, and PDF export routes."""

from __future__ import annotations

from typing import Any, Dict, List

import db as finance_db
from ai_copilot import CopilotAPIError, CopilotConfigError, ask_copilot
from calculators import run_module
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from module_registry import VALID_MODULE_NAMES, get_modules_catalog
from pdf import _demo_data

from .deps import (
    ModuleRunRequest,
    PlanChatRequest,
    PlanResetRequest,
    PlanUpsertRequest,
    get_current_user,
    normalize_plan_meta,
    render_pdf_bytes,
)

router = APIRouter()


@router.get("/modules")
def list_modules() -> Dict[str, Any]:
    return get_modules_catalog()


@router.get("/plans")
def list_user_plans(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, List[Dict[str, Any]]]:
    return {"plans": finance_db.list_plans(user["id"])}


@router.post("/plans", status_code=201)
def create_user_plan(
    body: PlanUpsertRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    title, score, grade, normalized = normalize_plan_meta(body.title, body.payload)
    return finance_db.create_plan(user["id"], title, score, grade, normalized)


@router.get("/plans/{plan_id}")
def get_user_plan(plan_id: int, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.put("/plans/{plan_id}")
def update_user_plan(
    plan_id: int,
    body: PlanUpsertRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    title, score, grade, normalized = normalize_plan_meta(body.title, body.payload)
    updated = finance_db.update_plan(user["id"], plan_id, title, score, grade, normalized)
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated


@router.post("/plans/{plan_id}/reset")
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

    _, score, grade, normalized = normalize_plan_meta(plan_title, raw_payload)
    updated = finance_db.reset_plan(user["id"], plan_id, score, grade, normalized)
    if updated is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return updated


@router.delete("/plans/{plan_id}")
def delete_user_plan(plan_id: int, user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, str]:
    deleted = finance_db.delete_plan(user["id"], plan_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "deleted"}


@router.get("/plans/{plan_id}/pdf")
def get_user_plan_pdf(
    plan_id: int,
    inline: bool = Query(False),
    user: Dict[str, Any] = Depends(get_current_user),
) -> Response:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    try:
        pdf_bytes = render_pdf_bytes(plan["payload"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="FINANCE-PLAN-{plan_id}.pdf"'},
    )


@router.get("/plans/{plan_id}/modules")
def get_plan_module_runs(
    plan_id: int,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    runs = finance_db.list_module_runs(user["id"], plan_id)
    return {"plan_id": plan_id, "runs": runs, "completed_modules": [r["module_name"] for r in runs]}


@router.post("/plans/{plan_id}/modules/{module_name}/run")
def run_plan_module(
    plan_id: int,
    module_name: str,
    body: ModuleRunRequest,
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    if module_name not in VALID_MODULE_NAMES:
        raise HTTPException(status_code=404, detail=f"Unknown module: {module_name}")
    plan = finance_db.get_plan(user["id"], plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    result = run_module(module_name, body.inputs, plan["payload"])
    result_with_sync = {**result, "_synced": bool(body.sync_to_plan)}
    saved_run = finance_db.upsert_module_run(
        user["id"],
        plan_id,
        module_name,
        body.inputs,
        result_with_sync,
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
        title, score, grade, normalized = normalize_plan_meta(plan["title"], merged)
        updated_plan = finance_db.update_plan(user["id"], plan_id, title, score, grade, normalized)

    return {"run": saved_run, "result": result, "updated_plan": updated_plan}


@router.post("/plans/{plan_id}/chat")
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


@router.get("/demo-data")
def demo_data() -> Dict[str, Any]:
    return _demo_data()


@router.get("/demo")
def demo_pdf(inline: bool = Query(False)) -> Response:
    try:
        pdf_bytes = render_pdf_bytes(_demo_data())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    disposition = "inline" if inline else "attachment"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="FINANCE-PLAN-sample.pdf"'},
    )


@router.post("/generate")
def generate_pdf(payload: Dict[str, Any]) -> Response:
    try:
        pdf_bytes = render_pdf_bytes(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="FINANCE-PLAN.pdf"'},
    )
