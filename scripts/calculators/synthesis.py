"""Stage 5 calculators: Synthesis & Export (Full Health Analysis, PDF Report Readiness)."""

from __future__ import annotations

from typing import Any, Dict

from .common import _clamp, _f, score_grade, score_signal


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
        "recommendations": [
            f"Prioritize {weakest[0]} (currently {round(weakest[1])}/100) for the fastest composite score lift.",
            "Sync this analysis to your plan, then proceed to Stage 5 PDF Report Export to generate FINANCE-PLAN.pdf.",
        ],
        "plan_patch": {
            "health_score": composite,
            "grade": grade,
            "signal": signal,
            "categories": {
                "cash_flow": round(c_cf, 1),
                "debt": round(c_debt, 1),
                "investments": round(c_inv, 1),
                "retirement": round(c_ret, 1),
                "protection": round(c_prot, 1),
            },
        },
    }


def calc_report_pdf(_inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    score = _f(plan.get("health_score"), 0)
    grade = str(plan.get("grade") or score_grade(score))
    client = str(plan.get("client_name") or "Personal Financial Plan")
    actions = plan.get("action_items") or []
    return {
        "module": "finance-report-pdf",
        "score": round(score, 1),
        "grade": grade,
        "summary": f"Ready to export 9-page PDF report for '{client}' (Score {round(score)}/100, Grade {grade}).",
        "metrics": [
            {"label": "Client / Plan", "value": client, "tone": "neutral"},
            {"label": "Health Score", "value": f"{round(score)}/100 ({grade})", "tone": "good" if score >= 70 else "warn"},
            {"label": "Report Length", "value": "9 Pages", "tone": "neutral"},
            {"label": "Action Items Included", "value": str(len(actions)), "tone": "neutral"},
        ],
        "tables": [],
        "chart": None,
        "recommendations": [
            "Click 'Download PDF' or 'Preview PDF' to render the latest synced plan with ReportLab.",
            "Share the generated PDF with a licensed CFP or CPA for personalized execution advice.",
        ],
        "plan_patch": {},
    }
