"""
Deterministic financial calculation engine for all 14 AI Personal Finance skills.

Every calculator takes `(inputs, plan_payload)` and returns a standardized dict:
  {
    "skill": str,
    "score": float | None,
    "grade": str | None,
    "summary": str,
    "metrics": [{"label": str, "value": str, "tone": "good"|"warn"|"bad"|"neutral"}],
    "tables": [{"title": str, "columns": [str], "rows": [[Any]]}],
    "chart": {"type": "bars"|"donut", "title": str, "items": [{"label": str, "value": float, "color": str?}]} | None,
    "recommendations": [str],
    "plan_patch": dict,   # merged into financial_plans.payload_json when sync_to_plan=True
  }
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from .baseline import calc_networth, calc_quick
from .foundation import _simulate_debt_payoff, calc_budget, calc_debt, calc_emergency
from .growth import SCREEN_STRATEGIES, calc_portfolio, calc_screen, calc_taxes
from .horizons import calc_compare, calc_fire, calc_goals, calc_retirement
from .synthesis import calc_analyze, calc_report_pdf

CALCULATORS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {
    "finance-quick": calc_quick,
    "finance-networth": calc_networth,
    "finance-budget": calc_budget,
    "finance-emergency": calc_emergency,
    "finance-debt": calc_debt,
    "finance-portfolio": calc_portfolio,
    "finance-screen": calc_screen,
    "finance-taxes": calc_taxes,
    "finance-retirement": calc_retirement,
    "finance-fire": calc_fire,
    "finance-goals": calc_goals,
    "finance-compare": calc_compare,
    "finance-analyze": calc_analyze,
    "finance-report-pdf": calc_report_pdf,
}


def run_skill(skill_name: str, inputs: Dict[str, Any], plan_payload: Dict[str, Any]) -> Dict[str, Any]:
    fn = CALCULATORS.get(skill_name)
    if fn is None:
        raise KeyError(f"Unknown skill: {skill_name}")
    return fn(inputs or {}, plan_payload or {})


__all__ = [
    "CALCULATORS",
    "SCREEN_STRATEGIES",
    "run_skill",
    "_simulate_debt_payoff",
    "calc_quick",
    "calc_networth",
    "calc_budget",
    "calc_emergency",
    "calc_debt",
    "calc_portfolio",
    "calc_screen",
    "calc_taxes",
    "calc_retirement",
    "calc_fire",
    "calc_goals",
    "calc_compare",
    "calc_analyze",
    "calc_report_pdf",
]
