"""Stage 4 calculators: Horizons & Trade-Offs (Retirement, FIRE, Goals, Scenario Compare)."""

from __future__ import annotations

from typing import Any, Dict

from .common import _clamp, _f, _fv_monthly, _money, _pct, score_grade


def calc_retirement(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    ret = plan.get("retirement") or {}
    age = int(_f(inputs.get("current_age"), _f(ret.get("current_age"), 38)))
    retire_age = int(_f(inputs.get("retirement_age"), _f(ret.get("retirement_age"), 65)))
    balance = _f(inputs.get("current_balance"), _f(ret.get("current_balance"), 184000))
    monthly = _f(inputs.get("monthly_contribution"), _f(ret.get("monthly_contribution"), 920))
    annual_spend = _f(inputs.get("desired_annual_spending"), 58000)
    ss_annual = _f(inputs.get("social_security_annual"), 0)

    years = max(0, retire_age - age)
    net_need_annual = max(0.0, annual_spend - ss_annual)
    target = net_need_annual * 25.0

    proj_cons = _fv_monthly(balance, monthly, 0.05, years)
    proj_mod = _fv_monthly(balance, monthly, 0.06, years)
    proj_agg = _fv_monthly(balance, monthly, 0.07, years)
    gap = max(0.0, target - proj_mod)

    plus_200 = _fv_monthly(balance, monthly + 200, 0.06, years)
    plus_400 = _fv_monthly(balance, monthly + 400, 0.06, years)
    score = _clamp((proj_mod / target * 100.0) if target > 0 else 100.0)

    scenarios = [
        {"name": "Conservative (5%)", "monthly": monthly, "projected": round(proj_cons), "verdict": "On track" if proj_cons >= target else f"Short {_money(target - proj_cons)}"},
        {"name": "Moderate (6%)", "monthly": monthly, "projected": round(proj_mod), "verdict": "On track" if proj_mod >= target else f"Short {_money(target - proj_mod)}"},
        {"name": "Moderate +$200/mo", "monthly": monthly + 200, "projected": round(plus_200), "verdict": "On track" if plus_200 >= target else f"Short {_money(target - plus_200)}"},
        {"name": "Moderate +$400/mo", "monthly": monthly + 400, "projected": round(plus_400), "verdict": "On track" if plus_400 >= target else f"Short {_money(target - plus_400)}"},
        {"name": "Aggressive (7%)", "monthly": monthly, "projected": round(proj_agg), "verdict": "On track" if proj_agg >= target else f"Short {_money(target - proj_agg)}"},
    ]

    return {
        "skill": "finance-retirement",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"In {years} yrs (age {retire_age}), moderate 6% projection reaches {_money(proj_mod)} vs. {_money(target)} target (25x rule).",
        "metrics": [
            {"label": "Years to Retirement", "value": f"{years} yrs", "tone": "neutral"},
            {"label": "Target Nest Egg (25x)", "value": _money(target), "tone": "neutral"},
            {"label": "Projected (6% Real)", "value": _money(proj_mod), "tone": "good" if proj_mod >= target else "warn"},
            {"label": "Projected Gap", "value": _money(gap), "tone": "good" if gap == 0 else "bad"},
        ],
        "tables": [
            {
                "title": "Retirement Scenarios",
                "columns": ["Scenario", "Monthly Save", "Projected @ Retirement", "Result"],
                "rows": [[s["name"], _money(s["monthly"]), _money(s["projected"]), s["verdict"]] for s in scenarios],
            }
        ],
        "chart": {
            "type": "bars",
            "title": "Projected Nest Egg vs Target ($)",
            "items": [
                {"label": "5% Cons.", "value": round(proj_cons)},
                {"label": "6% Mod.", "value": round(proj_mod)},
                {"label": "7% Aggr.", "value": round(proj_agg)},
                {"label": "Target", "value": round(target)},
            ],
        },
        "recommendations": [
            "On track at 6% real return — maintain contributions and review annually."
            if gap == 0
            else f"Close the {_money(gap)} gap by raising monthly contributions or extending working horizon by 2-3 years."
        ],
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "retirement": round(score, 1)},
            "retirement": {
                "current_age": age,
                "retirement_age": retire_age,
                "current_balance": balance,
                "target_balance": target,
                "monthly_contribution": monthly,
                "scenarios": scenarios[:4],
            },
        },
    }


def calc_fire(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    ret = plan.get("retirement") or {}
    annual_expenses = _f(inputs.get("annual_expenses"), 60000)
    current_invested = _f(inputs.get("current_invested"), _f(ret.get("current_balance"), 184000))
    annual_savings = _f(inputs.get("annual_savings"), 24000)
    swr = max(2.0, min(6.0, _f(inputs.get("withdrawal_rate"), 4.0)))
    real_return = _f(inputs.get("expected_real_return"), 6.0) / 100.0
    age = int(_f(inputs.get("current_age"), _f(ret.get("current_age"), 38)))

    fi_regular = annual_expenses / (swr / 100.0)
    fi_lean = (annual_expenses * 0.75) / (swr / 100.0)
    fi_fat = (annual_expenses * 1.50) / (swr / 100.0)
    years_to_65 = max(1, 65 - age)
    coast_fi = fi_regular / ((1.0 + real_return) ** years_to_65)

    # Simulate years to regular FI
    bal = current_invested
    years_to_fi = 0
    while bal < fi_regular and years_to_fi < 60:
        bal = bal * (1.0 + real_return) + annual_savings
        years_to_fi += 1

    progress = (current_invested / fi_regular * 100.0) if fi_regular > 0 else 100.0
    return {
        "skill": "finance-fire",
        "score": round(_clamp(progress), 1),
        "grade": score_grade(_clamp(progress)),
        "summary": f"Regular FI number ({swr:.1f}% SWR): {_money(fi_regular)}. Estimated {years_to_fi} yrs to FI (age {age + years_to_fi}).",
        "metrics": [
            {"label": "Regular FI Number", "value": _money(fi_regular), "tone": "neutral"},
            {"label": "Coast FI Number", "value": _money(coast_fi), "tone": "good" if current_invested >= coast_fi else "neutral"},
            {"label": "Years to FI", "value": f"{years_to_fi} yrs (age {age + years_to_fi})", "tone": "good" if years_to_fi <= 15 else "neutral"},
            {"label": "FI Progress", "value": _pct(progress), "tone": "good" if progress >= 50 else "warn"},
        ],
        "tables": [
            {
                "title": "FIRE Variants",
                "columns": ["FIRE Type", "Annual Spend", "Target Number", "Status"],
                "rows": [
                    ["Lean FIRE (75%)", _money(annual_expenses * 0.75), _money(fi_lean), "Reached" if current_invested >= fi_lean else _money(fi_lean - current_invested) + " left"],
                    ["Regular FIRE (100%)", _money(annual_expenses), _money(fi_regular), "Reached" if current_invested >= fi_regular else _money(fi_regular - current_invested) + " left"],
                    ["Fat FIRE (150%)", _money(annual_expenses * 1.5), _money(fi_fat), "Reached" if current_invested >= fi_fat else _money(fi_fat - current_invested) + " left"],
                    ["Coast FIRE (to 65)", _money(annual_expenses), _money(coast_fi), "Reached!" if current_invested >= coast_fi else _money(coast_fi - current_invested) + " left"],
                ],
            }
        ],
        "chart": {
            "type": "bars",
            "title": "FIRE Targets vs Current ($)",
            "items": [
                {"label": "Current", "value": round(current_invested)},
                {"label": "Coast FI", "value": round(coast_fi)},
                {"label": "Lean FI", "value": round(fi_lean)},
                {"label": "Regular FI", "value": round(fi_regular)},
            ],
        },
        "recommendations": [
            "Every $100/mo cut in recurring expenses reduces your Regular FI target by $30,000 (at 4% SWR).",
            "Build a 1-2 year cash/bond tent before retiring early to mitigate sequence-of-returns risk.",
        ],
        "plan_patch": {},
    }


def calc_goals(inputs: Dict[str, Any], _plan: Dict[str, Any]) -> Dict[str, Any]:
    name = str(inputs.get("goal_name") or "House Down Payment")
    target = _f(inputs.get("target_amount"), 80000)
    current = _f(inputs.get("current_saved"), 20000)
    years = max(0.25, _f(inputs.get("years_to_goal"), 5))
    annual_return = _f(inputs.get("expected_return"), 4.5) / 100.0

    months = max(1, int(round(years * 12)))
    r = annual_return / 12.0
    fv_current = current * ((1.0 + r) ** months)
    shortfall = max(0.0, target - fv_current)
    if shortfall <= 0:
        req_monthly = 0.0
    elif abs(r) < 1e-12:
        req_monthly = shortfall / months
    else:
        req_monthly = shortfall * r / (((1.0 + r) ** months) - 1.0)

    vehicle = (
        "HYSA / T-Bills (preserve principal)"
        if years < 3
        else ("Balanced 40/60 or CD/Bond Ladder" if years <= 7 else "Diversified Index ETFs (70/30+)")
    )
    pct_done = (current / target * 100.0) if target > 0 else 100.0

    return {
        "skill": "finance-goals",
        "score": round(_clamp(pct_done), 1),
        "grade": None,
        "summary": f"Goal '{name}': need {_money(req_monthly)}/mo for {years:.1f} yrs (at {_pct(annual_return * 100)} return) to reach {_money(target)}.",
        "metrics": [
            {"label": "Target Amount", "value": _money(target), "tone": "neutral"},
            {"label": "Current Saved", "value": _money(current), "tone": "neutral"},
            {"label": "Required Monthly Save", "value": _money(req_monthly), "tone": "good" if req_monthly == 0 else "warn"},
            {"label": "Recommended Vehicle", "value": vehicle, "tone": "neutral"},
        ],
        "tables": [
            {
                "title": "Timeline Adjustment Scenarios",
                "columns": ["Timeline", "Required Monthly Contribution"],
                "rows": [
                    [f"{years:.1f} years (target)", _money(req_monthly)],
                    [f"{years + 2:.1f} years (+2 yrs)", _money(max(0.0, (target - current * ((1 + r) ** int((years + 2) * 12))) * (r / (((1 + r) ** int((years + 2) * 12)) - 1) if r > 0 else 1 / ((years + 2) * 12))))],
                ],
            }
        ],
        "chart": {
            "type": "bars",
            "title": "Goal Funding Progress (%)",
            "items": [{"label": name[:14], "value": round(_clamp(pct_done), 1)}],
        },
        "recommendations": [
            f"Automate {_money(req_monthly)}/mo into a dedicated sub-account ({vehicle}).",
        ],
        "plan_patch": {},
    }


def calc_compare(inputs: Dict[str, Any], _plan: Dict[str, Any]) -> Dict[str, Any]:
    name_a = str(inputs.get("scenario_a_name") or "Scenario A (e.g., Rent & Invest)")
    upfront_a = _f(inputs.get("scenario_a_upfront"), 0)
    monthly_a = _f(inputs.get("scenario_a_monthly_cost"), 2400)
    monthly_invest_a = _f(inputs.get("scenario_a_monthly_invest"), 800)

    name_b = str(inputs.get("scenario_b_name") or "Scenario B (e.g., Buy Home)")
    upfront_b = _f(inputs.get("scenario_b_upfront"), 60000)
    monthly_b = _f(inputs.get("scenario_b_monthly_cost"), 3200)
    monthly_invest_b = _f(inputs.get("scenario_b_monthly_invest"), 0)

    years = max(1, int(_f(inputs.get("horizon_years"), 10)))
    rate = _f(inputs.get("investment_return"), 6.5) / 100.0

    total_cost_a = upfront_a + monthly_a * 12 * years
    total_cost_b = upfront_b + monthly_b * 12 * years
    # Opportunity cost of lower upfront invested
    diff_upfront_a = max(0.0, upfront_b - upfront_a)
    diff_upfront_b = max(0.0, upfront_a - upfront_b)
    fv_a = _fv_monthly(diff_upfront_a, monthly_invest_a, rate, years)
    fv_b = _fv_monthly(diff_upfront_b, monthly_invest_b, rate, years)

    net_a = fv_a - total_cost_a
    net_b = fv_b - total_cost_b
    winner = name_a if net_a >= net_b else name_b
    advantage = abs(net_a - net_b)

    return {
        "skill": "finance-compare",
        "score": None,
        "grade": None,
        "summary": f"Over {years} years, '{winner}' leads by {_money(advantage)} in net financial position (at {_pct(rate * 100)} return).",
        "metrics": [
            {"label": f"{name_a} Invested FV", "value": _money(fv_a), "tone": "neutral"},
            {"label": f"{name_b} Invested FV", "value": _money(fv_b), "tone": "neutral"},
            {"label": "Financial Winner", "value": winner, "tone": "good"},
            {"label": "Net Advantage", "value": _money(advantage), "tone": "good"},
        ],
        "tables": [
            {
                "title": f"{years}-Year Side-by-Side Comparison",
                "columns": ["Metric", name_a, name_b],
                "rows": [
                    ["Upfront Cash Outlay", _money(upfront_a), _money(upfront_b)],
                    ["Monthly Cost", _money(monthly_a), _money(monthly_b)],
                    [f"Total {years}-Yr Cash Cost", _money(total_cost_a), _money(total_cost_b)],
                    [f"Projected Invested Value ({years} yr)", _money(fv_a), _money(fv_b)],
                    ["Net Position (Invested - Cost)", _money(net_a), _money(net_b)],
                ],
            }
        ],
        "chart": {
            "type": "bars",
            "title": f"{years}-Year Projected Invested Value ($)",
            "items": [
                {"label": "Scenario A", "value": round(fv_a)},
                {"label": "Scenario B", "value": round(fv_b)},
            ],
        },
        "recommendations": [
            f"'{winner}' wins purely on modeled cash/investment math by {_money(advantage)} over {years} years.",
            "Weigh non-financial factors (flexibility, risk tolerance, lifestyle) alongside the quantitative edge.",
        ],
        "plan_patch": {},
    }
