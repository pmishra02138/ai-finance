"""Environment configuration and financial plan context builder for Plan Insights."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.2:latest"


class CopilotConfigError(RuntimeError):
    """Raised when an explicit AI provider configuration is invalid."""


class CopilotAPIError(RuntimeError):
    """Raised when the upstream AI API call fails."""


def _parse_dotenv(env_file: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not env_file.is_file():
        return values
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def get_env_setting(name: str, default: str = "", env_path: Optional[Path] = None) -> str:
    direct = os.environ.get(name, "").strip()
    if direct:
        return direct
    dotenv_vals = _parse_dotenv(env_path or (REPO_ROOT / ".env"))
    return dotenv_vals.get(name, default).strip()


def build_plan_context(plan: Dict[str, Any], module_runs: List[Dict[str, Any]]) -> str:
    """Summarize the active plan and saved module runs for grounded LLM context."""
    payload = plan.get("payload") or {}
    cats = payload.get("categories") or {}
    cf = payload.get("cash_flow") or {}
    debt = payload.get("debt") or {}
    inv = payload.get("investments") or {}
    ret = payload.get("retirement") or {}
    prot = payload.get("protection") or {}
    mc = ret.get("monte_carlo") or {}

    summary_obj = {
        "plan_title": plan.get("title") or payload.get("client_name") or "Personal Financial Plan",
        "health_score": plan.get("health_score", payload.get("health_score", 0)),
        "grade": plan.get("grade", payload.get("grade", "--")),
        "signal": payload.get("signal", ""),
        "pillar_scores": {
            "cash_flow": cats.get("cash_flow", 0),
            "debt": cats.get("debt", 0),
            "investments": cats.get("investments", 0),
            "retirement": cats.get("retirement", 0),
            "protection": cats.get("protection", 0),
        },
        "cash_flow": {
            "monthly_income": cf.get("monthly_income", 0),
            "gross_annual_income": cf.get("gross_annual_income", 0),
            "budget_50_30_20": cf.get("budget_50_30_20"),
        },
        "debt_accounts": debt.get("accounts") or [],
        "investments": {
            "total_value": inv.get("total_value", 0),
            "allocation": inv.get("allocation") or [],
        },
        "retirement": {
            "current_age": ret.get("current_age"),
            "retirement_age": ret.get("retirement_age"),
            "current_balance": ret.get("current_balance"),
            "target_balance": ret.get("target_balance"),
            "monthly_contribution": ret.get("monthly_contribution"),
            "employer_match_monthly": ret.get("employer_match_monthly"),
            "monte_carlo_survival_pct": mc.get("success_rate_pct"),
            "monte_carlo_median": mc.get("retire_p50"),
        },
        "protection_items": prot.get("items") or [],
        "top_action_items": (payload.get("action_items") or [])[:5],
        "saved_module_summaries": [
            {
                "module": r.get("module_name"),
                "score": r.get("score"),
                "summary": (r.get("outputs") or {}).get("summary", ""),
            }
            for r in (module_runs or [])
        ],
    }
    return json.dumps(summary_obj, indent=2)
