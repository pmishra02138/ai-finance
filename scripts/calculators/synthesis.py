"""Stage 5 calculator: Synthesis & Export (Full 5-Pillar Health Analysis & Dynamic Action Items)."""

from __future__ import annotations

from typing import Any, Dict, List

from .common import _clamp, _f, _money, score_grade, score_signal


def build_dynamic_action_items(plan: Dict[str, Any], pillars: List[tuple[str, float]]) -> List[Dict[str, str]]:
    """Derive live prioritized action items from the current synced plan state."""
    actions: List[Dict[str, str]] = []

    # 1. Protection & Estate gaps
    prot = plan.get("protection") or {}
    for it in prot.get("items") or []:
        st = str(it.get("status") or "").lower()
        name = str(it.get("name") or "Protection")
        rec = str(it.get("recommendation") or "")
        if "miss" in st or "critical" in st:
            actions.append({"action": f"{name}: {rec}", "category": "Protection", "priority": "High", "impact": "Critical"})
        elif "partial" in st or "review" in st:
            actions.append({"action": f"{name}: {rec}", "category": "Protection", "priority": "Med", "impact": "Med"})

    # 2. High-APR debt (>7%)
    debt = plan.get("debt") or {}
    high_debts = [a for a in (debt.get("accounts") or []) if _f(a.get("balance")) > 0 and _f(a.get("apr")) > 7.0]
    high_debts.sort(key=lambda a: -_f(a.get("apr")))
    for a in high_debts[:2]:
        actions.append({
            "action": f"Pay down {a.get('name', 'High-APR Debt')} ({_money(_f(a.get('balance')))} at {_f(a.get('apr')):.1f}% APR) via Avalanche.",
            "category": "Debt",
            "priority": "High",
            "impact": "High",
        })

    # 3. Retirement gap / Monte Carlo survival
    ret = plan.get("retirement") or {}
    mc = ret.get("monte_carlo") or {}
    mc_surv = _f(mc.get("success_rate_pct"), 100.0) if mc else 100.0
    if mc and mc_surv < 80.0:
        actions.append({
            "action": f"Raise retirement savings rate or adjust target age (Monte Carlo survival is {mc_surv:.1f}%, target >=80%).",
            "category": "Retirement",
            "priority": "High",
            "impact": "High",
        })

    # 4. Investment drift (>5pp)
    inv = plan.get("investments") or {}
    drifted = [
        a for a in (inv.get("allocation") or [])
        if abs(_f(a.get("pct")) - _f(a.get("target_pct", a.get("pct")))) > 5.0
    ]
    if drifted:
        top_d = max(drifted, key=lambda a: abs(_f(a.get("pct")) - _f(a.get("target_pct", a.get("pct")))))
        diff = _f(top_d.get("pct")) - _f(top_d.get("target_pct", top_d.get("pct")))
        direction = "overweight" if diff > 0 else "underweight"
        actions.append({
            "action": f"Rebalance portfolio: {top_d.get('name', 'Asset')} is {direction} by {abs(diff):.1f}pp.",
            "category": "Investments",
            "priority": "Med",
            "impact": "Med",
        })

    # 5. Pillar fallback if any pillar is below 75 and wasn't already covered
    covered_cats = {a["category"] for a in actions}
    for name, sc in sorted(pillars, key=lambda x: x[1]):
        if name not in covered_cats and sc < 75.0:
            actions.append({
                "action": f"Strengthen {name} pillar (currently {round(sc)}/100) in its Stage module.",
                "category": name,
                "priority": "High" if sc < 55.0 else "Med",
                "impact": "High" if sc < 55.0 else "Med",
            })

    if not actions:
        actions.append({
            "action": "Maintain automated savings, annual rebalancing, and yearly beneficiary/estate review.",
            "category": "Maintenance",
            "priority": "Low",
            "impact": "Low",
        })

    prio_rank = {"critical": 0, "high": 0, "med": 1, "medium": 1, "low": 2}
    return sorted(actions, key=lambda a: prio_rank.get(a["priority"].lower(), 1))[:10]


def calc_analyze(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cats = plan.get("categories") or {}
    c_cf = _clamp(_f(inputs.get("cash_flow_score"), _f(cats.get("cash_flow"), 75)))
    c_debt = _clamp(_f(inputs.get("debt_score"), _f(cats.get("debt"), 60)))
    c_inv = _clamp(_f(inputs.get("investments_score"), _f(cats.get("investments"), 72)))
    c_ret = _clamp(_f(inputs.get("retirement_score"), _f(cats.get("retirement"), 65)))
    c_prot = _clamp(_f(inputs.get("protection_score"), _f(cats.get("protection"), 60)))

    composite = round((c_cf + c_debt + c_inv + c_ret + c_prot) / 5.0, 1)
    grade = score_grade(composite)
    signal = score_signal(composite)

    pillars = [
        ("Cash Flow", c_cf),
        ("Debt", c_debt),
        ("Investments", c_inv),
        ("Retirement", c_ret),
        ("Protection", c_prot),
    ]
    weakest = min(pillars, key=lambda x: x[1])
    strongest = max(pillars, key=lambda x: x[1])
    sorted_actions = build_dynamic_action_items(plan, pillars)

    return {
        "module": "finance-analyze",
        "score": composite,
        "grade": grade,
        "summary": f"Composite Financial Health Score: {composite}/100 (Grade {grade}) — {signal}. Strongest: {strongest[0]}; Top focus: {weakest[0]}.",
        "metrics": [
            {"label": "Composite Score", "value": f"{composite}/100", "tone": "good" if composite >= 70 else ("warn" if composite >= 40 else "bad")},
            {"label": "Grade", "value": grade, "tone": "good" if composite >= 70 else "warn"},
            {"label": "Strongest Pillar", "value": f"{strongest[0]} ({round(strongest[1])})", "tone": "good"},
            {"label": "Priority Gap", "value": f"{weakest[0]} ({round(weakest[1])})", "tone": "bad" if weakest[1] < 50 else "warn"},
        ],
        "tables": [
            {
                "title": "5-Pillar Financial Health Breakdown",
                "columns": ["Category", "Weight", "Score", "Grade"],
                "rows": [[name, "20%", f"{round(sc)}/100", score_grade(sc)] for name, sc in pillars],
            }
        ],
        "chart": {
            "type": "bars",
            "title": "5-Pillar Score Dashboard",
            "items": [{"label": name, "value": round(sc, 1)} for name, sc in pillars],
        },
        "action_items": sorted_actions,
        "recommendations": [
            f"Prioritize {weakest[0]} (currently {round(weakest[1])}/100) for the fastest composite score lift.",
            "Click 'Preview PDF' or 'Download PDF' above to export your 9-page FINANCE-PLAN.pdf report.",
        ],
        "plan_patch": {
            "health_score": composite,
            "grade": grade,
            "signal": signal,
            "action_items": sorted_actions,
            "categories": {
                "cash_flow": round(c_cf, 1),
                "debt": round(c_debt, 1),
                "investments": round(c_inv, 1),
                "retirement": round(c_ret, 1),
                "protection": round(c_prot, 1),
            },
        },
    }
