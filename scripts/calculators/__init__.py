"""
Hybrid financial calculation engine for all 10 FinPlan modules across 5 stages.

Every calculator takes `(inputs, plan_payload)` and returns a standardized dict:
  {
    "module": str,
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

from .baseline import calc_budget, calc_networth
from .foundation import _simulate_debt_payoff, calc_debt, calc_emergency, calc_protection
from .growth import SCREEN_STRATEGIES, calc_portfolio, calc_taxes
from .horizons import calc_goals, calc_retirement
from .synthesis import calc_analyze

CALCULATORS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {
    "finance-budget": calc_budget,
    "finance-networth": calc_networth,
    "finance-emergency": calc_emergency,
    "finance-debt": calc_debt,
    "finance-protection": calc_protection,
    "finance-portfolio": calc_portfolio,
    "finance-taxes": calc_taxes,
    "finance-retirement": calc_retirement,
    "finance-goals": calc_goals,
    "finance-analyze": calc_analyze,
}


def run_module(module_name: str, inputs: Dict[str, Any], plan_payload: Dict[str, Any]) -> Dict[str, Any]:
    fn = CALCULATORS.get(module_name)
    if fn is None:
        raise KeyError(f"Unknown module: {module_name}")
    return fn(inputs or {}, plan_payload or {})


__all__ = [
    "CALCULATORS",
    "SCREEN_STRATEGIES",
    "run_module",
    "_simulate_debt_payoff",
    "calc_budget",
    "calc_networth",
    "calc_emergency",
    "calc_debt",
    "calc_protection",
    "calc_portfolio",
    "calc_taxes",
    "calc_retirement",
    "calc_goals",
    "calc_analyze",
]
