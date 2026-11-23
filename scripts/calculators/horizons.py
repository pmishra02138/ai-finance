"""Stage 4 calculators: Horizons & Trade-Offs (Hybrid Deterministic Baseline + Log-Normal Monte Carlo)."""

from __future__ import annotations

from typing import Any, Dict

try:
    from module_registry import get_module_constants
except ImportError:  # pragma: no cover - when imported as scripts.calculators.*
    from ..module_registry import get_module_constants

from .common import _clamp, _f, _fv_monthly, _money, _pct, _portfolio_return_vol, score_grade
from .monte_carlo import (
    simulate_compare_mc,
    simulate_goal_mc,
    simulate_retirement_mc,
)


def calc_retirement(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    """Unified Retirement & Financial Independence (FIRE) calculator with log-normal Monte Carlo."""
    ret = plan.get("retirement") or {}
    consts = get_module_constants("finance-retirement")
    age = int(_f(inputs.get("current_age"), _f(ret.get("current_age"), 38)))
    retire_age = int(_f(inputs.get("retirement_age"), _f(ret.get("retirement_age"), 65)))
    balance = _f(inputs.get("current_balance"), _f(ret.get("current_balance"), 184000))
    monthly = _f(inputs.get("monthly_contribution"), _f(ret.get("monthly_contribution"), 920))
    employer_match = max(0.0, _f(inputs.get("employer_match_monthly"), 300))
    annual_spend_net = _f(inputs.get("desired_annual_spending"), 58000)
    swr = max(2.0, min(6.0, _f(inputs.get("withdrawal_rate"), 4.0)))
    tax_rate = _clamp(_f(inputs.get("retirement_tax_rate"), 15.0), 0.0, 45.0) / 100.0
    ss_annual = max(0.0, _f(inputs.get("social_security_annual"), 0))
    ss_start_age = int(_f(inputs.get("social_security_start_age"), 67))

    total_monthly = monthly + employer_match
    years = max(0, retire_age - age)
    # Gross annual withdrawal needed to fund after-tax spending
    gross_annual_spend = annual_spend_net / max(0.55, 1.0 - tax_rate)
    # Bridge cost if retiring before Social Security starts
    ss_delay_years = max(0, ss_start_age - retire_age) if ss_annual > 0 else 0
    steady_net_need = max(0.0, gross_annual_spend - ss_annual)
    target = steady_net_need * (100.0 / swr) + ss_annual * ss_delay_years

    # Link Monte Carlo expected return & volatility to synced portfolio allocation
    port_ret, port_vol, equity_pct = _portfolio_return_vol(
        plan,
        default_return=float(consts.get("mc_accum_return", 0.06)),
        default_vol=float(consts.get("mc_accum_vol", 0.14)),
    )
    retire_ret = max(0.02, port_ret - 0.015)
    retire_vol = max(0.06, port_vol * 0.75)

    cons_ret = max(0.02, port_ret - 0.01)
    agg_ret = port_ret + 0.01
    proj_cons = _fv_monthly(balance, total_monthly, cons_ret, years)
    proj_mod = _fv_monthly(balance, total_monthly, port_ret, years)
    proj_agg = _fv_monthly(balance, total_monthly, agg_ret, years)
    gap = max(0.0, target - proj_mod)

    plus_200 = _fv_monthly(balance, total_monthly + 200, port_ret, years)
    plus_400 = _fv_monthly(balance, total_monthly + 400, port_ret, years)
    det_score = _clamp((proj_mod / target * 100.0) if target > 0 else 100.0)

    # FIRE milestones (Lean, Regular, Fat, Coast FI) derived from the same portfolio & spending
    fi_regular = gross_annual_spend / (swr / 100.0)
    fi_lean = (gross_annual_spend * 0.75) / (swr / 100.0)
    fi_fat = (gross_annual_spend * 1.50) / (swr / 100.0)
    years_to_65 = max(1, 65 - age)
    coast_fi = fi_regular / ((1.0 + port_ret) ** years_to_65)

    fi_bal = balance
    years_to_fi = 0
    annual_save = total_monthly * 12.0
    while fi_bal < fi_regular and years_to_fi < 60:
        fi_bal = fi_bal * (1.0 + port_ret) + annual_save
        years_to_fi += 1

    # Dynamic drawdown horizon to age 95 (min 25 yrs) so early retirees face full longevity risk
    drawdown_years = max(25, 95 - retire_age)
    mc = simulate_retirement_mc(
        current_balance=balance,
        monthly_contribution=total_monthly,
        years_to_retire=years,
        retirement_age=retire_age,
        annual_gross_spending=gross_annual_spend,
        social_security_annual=ss_annual,
        social_security_start_age=ss_start_age,
        drawdown_years=drawdown_years,
        accum_return=port_ret,
        accum_vol=port_vol,
        retire_return=retire_ret,
        retire_vol=retire_vol,
        trials=int(consts.get("mc_trials", 1000)),
        seed=int(consts.get("mc_seed", 42)),
    )

    # Blend deterministic baseline (45%) and Monte Carlo survival (55%), capping <80% survival below A-
    mc_score = _clamp(mc["success_rate_pct"] * 1.1)
    blended = 0.45 * det_score + 0.55 * mc_score
    if mc["success_rate_pct"] < 80.0:
        blended = min(blended, 79.0)
    score = round(_clamp(blended), 1)

    mc_summary = {
        "trials": mc["trials"],
        "volatility_pct": mc["volatility_pct"],
        "baseline_label": f"Deterministic {_pct(port_ret * 100.0, 1)} Real Baseline ({_money(total_monthly)}/mo incl. match)",
        "baseline_value": _money(proj_mod),
        "success_label": f"{mc['drawdown_years']}-Yr Retirement Survival",
        "success_rate_pct": mc["success_rate_pct"],
        "percentiles": [
            {"label": "10th Pct (Downside)", "value": _money(mc["retire_p10"]), "raw": mc["retire_p10"]},
            {"label": "50th Pct (Median)", "value": _money(mc["retire_p50"]), "raw": mc["retire_p50"]},
            {"label": "90th Pct (Upside)", "value": _money(mc["retire_p90"]), "raw": mc["retire_p90"]},
        ],
        "note": (
            f"Log-normal Monte Carlo ({mc['trials']:,} paths, {mc['volatility_pct']}% vol from {equity_pct:.0f}% equity mix), "
            f"gross withdrawal {_money(gross_annual_spend)}/yr (at {tax_rate * 100:.1f}% tax, {swr:.1f}% SWR), SS starting age {ss_start_age}."
        ),
    }

    scenarios = [
        {"name": f"Conservative ({_pct(cons_ret * 100.0, 1)} real)", "monthly": total_monthly, "projected": round(proj_cons), "verdict": "On track" if proj_cons >= target else f"Short {_money(target - proj_cons)}"},
        {"name": f"Portfolio Baseline ({_pct(port_ret * 100.0, 1)} real)", "monthly": total_monthly, "projected": round(proj_mod), "verdict": "On track" if proj_mod >= target else f"Short {_money(target - proj_mod)}"},
        {"name": "Baseline +$200/mo", "monthly": total_monthly + 200, "projected": round(plus_200), "verdict": "On track" if plus_200 >= target else f"Short {_money(target - plus_200)}"},
        {"name": "Baseline +$400/mo", "monthly": total_monthly + 400, "projected": round(plus_400), "verdict": "On track" if plus_400 >= target else f"Short {_money(target - plus_400)}"},
        {"name": f"Aggressive ({_pct(agg_ret * 100.0, 1)} real)", "monthly": total_monthly, "projected": round(proj_agg), "verdict": "On track" if proj_agg >= target else f"Short {_money(target - proj_agg)}"},
    ]

    recs = [
        "On track at 6% real return (including employer match & withdrawal taxes) — maintain contributions and review annually."
        if gap == 0
        else f"Close the {_money(gap)} deterministic gap by raising monthly contributions or extending working horizon by 2-3 years."
    ]
    if mc["success_rate_pct"] < 80.0:
        recs.append(
            f"Monte Carlo {mc['drawdown_years']}-year survival is {mc['success_rate_pct']:.1f}% (below 80% comfort threshold) — "
            "consider boosting savings, lowering Safe Withdrawal Rate toward 3.5%, or building Roth tax diversification."
        )
    else:
        recs.append(
            f"Log-normal Monte Carlo stress test shows {mc['success_rate_pct']:.1f}% probability of sustaining {mc['drawdown_years']} years of after-tax withdrawals."
        )
    recs.append(
        f"Regular FI target at {swr:.1f}% Safe Withdrawal Rate is {_money(fi_regular)} (~{years_to_fi} yrs, age {age + years_to_fi}); Coast FI to age 65 is {_money(coast_fi)}."
    )

    return {
        "module": "finance-retirement",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": (
            f"In {years} yrs (age {retire_age}), deterministic 6% baseline reaches {_money(proj_mod)} vs. {_money(target)} tax-adjusted target; "
            f"Monte Carlo ({mc['trials']:,} trials) estimates {mc['success_rate_pct']:.1f}% {mc['drawdown_years']}-yr survival "
            f"(median {_money(mc['retire_p50'])}, Regular FI {_money(fi_regular)})."
        ),
        "metrics": [
            {"label": "Tax-Adjusted Target", "value": _money(target), "tone": "neutral"},
            {"label": "Total Save (You+Match)", "value": f"{_money(total_monthly)}/mo", "tone": "neutral"},
            {"label": "Baseline (6% Steady)", "value": _money(proj_mod), "tone": "good" if proj_mod >= target else "warn"},
            {"label": f"MC {mc['drawdown_years']}-Yr Survival", "value": _pct(mc["success_rate_pct"]), "tone": "good" if mc["success_rate_pct"] >= 80 else ("warn" if mc["success_rate_pct"] >= 65 else "bad")},
            {"label": "Regular FI (SWR)", "value": f"{_money(fi_regular)} ({years_to_fi}y)", "tone": "neutral"},
            {"label": "Coast FI (to 65)", "value": _money(coast_fi), "tone": "good" if balance >= coast_fi else "neutral"},
        ],
        "monte_carlo": mc_summary,
        "tables": [
            {
                "title": "Deterministic Retirement Scenarios (Incl. Employer Match)",
                "columns": ["Scenario", "Total Monthly Save", "Projected @ Retirement", "Result"],
                "rows": [[s["name"], _money(s["monthly"]), _money(s["projected"]), s["verdict"]] for s in scenarios],
            },
            {
                "title": f"Financial Independence (FIRE) Milestones @ {swr:.1f}% SWR",
                "columns": ["FI Variant", "Gross Annual Pull", "Target Number", "Status"],
                "rows": [
                    ["Lean FI (75%)", _money(gross_annual_spend * 0.75), _money(fi_lean), "Reached" if balance >= fi_lean else _money(fi_lean - balance) + " left"],
                    ["Regular FI (100%)", _money(gross_annual_spend), _money(fi_regular), "Reached" if balance >= fi_regular else _money(fi_regular - balance) + " left"],
                    ["Fat FI (150%)", _money(gross_annual_spend * 1.5), _money(fi_fat), "Reached" if balance >= fi_fat else _money(fi_fat - balance) + " left"],
                    ["Coast FI (to 65)", _money(gross_annual_spend), _money(coast_fi), "Reached!" if balance >= coast_fi else _money(coast_fi - balance) + " left"],
                ],
            },
        ],
        "chart": {
            "type": "bars",
            "title": "Deterministic vs Monte Carlo @ Retirement ($)",
            "items": [
                {"label": "MC 10th Pct", "value": mc["retire_p10"]},
                {"label": "6% Baseline", "value": round(proj_mod)},
                {"label": "MC Median", "value": mc["retire_p50"]},
                {"label": "MC 90th Pct", "value": mc["retire_p90"]},
                {"label": "Target", "value": round(target)},
            ],
        },
        "recommendations": recs,
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "retirement": round(score, 1)},
            "retirement": {
                "current_age": age,
                "retirement_age": retire_age,
                "current_balance": balance,
                "target_balance": round(target),
                "monthly_contribution": monthly,
                "employer_match_monthly": employer_match,
                "scenarios": scenarios[:4],
                "monte_carlo": mc,
            },
        },
    }


def calc_goals(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    """Unified Goal Milestone Planner + Optional Side-by-Side Scenario Trade-Off Comparison."""
    consts = get_module_constants("finance-goals")
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

    if years < 3:
        vehicle = "HYSA / T-Bills (preserve principal)"
        vol = 0.015
    elif years <= 7:
        vehicle = "Balanced 40/60 or CD/Bond Ladder"
        vol = 0.075
    else:
        vehicle = "Diversified Index ETFs (70/30+)"
        vol = 0.13

    mc_trials = int(consts.get("mc_trials", 1000))
    mc_seed = int(consts.get("mc_seed", 42))
    mc = simulate_goal_mc(
        current_saved=current,
        monthly_contribution=req_monthly,
        years=years,
        target_amount=target,
        expected_return=annual_return,
        volatility=vol,
        trials=mc_trials,
        seed=mc_seed,
    )

    # Binary search for an 80% Monte Carlo confidence monthly contribution when deterministic odds < 80%
    conf_monthly = req_monthly
    if mc["success_rate_pct"] < 80.0 and target > 0:
        lo, hi = req_monthly, max(req_monthly * 2.5, (target - current) / months * 2.0 + 100.0)
        for _ in range(14):
            mid = (lo + hi) / 2.0
            probe = simulate_goal_mc(
                current_saved=current,
                monthly_contribution=mid,
                years=years,
                target_amount=target,
                expected_return=annual_return,
                volatility=vol,
                trials=250,
                seed=mc_seed,
            )
            if probe["success_rate_pct"] >= 80.0:
                hi = mid
            else:
                lo = mid
        conf_monthly = hi

    mc_summary = {
        "trials": mc["trials"],
        "volatility_pct": mc["volatility_pct"],
        "baseline_label": f"Deterministic Required Save ({years:.1f} yrs)",
        "baseline_value": f"{_money(req_monthly)}/mo -> {_money(target)}",
        "success_label": f"On-Time Odds @ Baseline (80% target: {_money(conf_monthly)}/mo)",
        "success_rate_pct": mc["success_rate_pct"],
        "percentiles": [
            {"label": "10th Pct (Downside)", "value": _money(mc["p10"]), "raw": mc["p10"]},
            {"label": "50th Pct (Median)", "value": _money(mc["p50"]), "raw": mc["p50"]},
            {"label": "90th Pct (Upside)", "value": _money(mc["p90"]), "raw": mc["p90"]},
        ],
        "note": (
            f"Log-normal Monte Carlo ({mc['trials']:,} paths, {mc['volatility_pct']}% volatility) for {vehicle}."
        ),
    }

    metrics = [
        {"label": "Target Amount", "value": _money(target), "tone": "neutral"},
        {"label": "Baseline Monthly Save", "value": _money(req_monthly), "tone": "good" if req_monthly == 0 else "neutral"},
        {"label": "80% Confidence Save", "value": f"{_money(conf_monthly)}/mo", "tone": "good"},
        {"label": "MC On-Time Odds (Base)", "value": _pct(mc["success_rate_pct"]), "tone": "good" if mc["success_rate_pct"] >= 75 else "warn"},
        {"label": "Recommended Vehicle", "value": vehicle, "tone": "neutral"},
    ]

    tables = [
        {
            "title": "Timeline Adjustment Scenarios",
            "columns": ["Timeline", "Required Monthly Contribution"],
            "rows": [
                [f"{years:.1f} years (deterministic)", _money(req_monthly)],
                [f"{years:.1f} years (80% MC confidence)", _money(conf_monthly)],
                [f"{years + 2:.1f} years (+2 yrs)", _money(max(0.0, (target - current * ((1 + r) ** int((years + 2) * 12))) * (r / (((1 + r) ** int((years + 2) * 12)) - 1) if r > 0 else 1 / ((years + 2) * 12))))],
            ],
        }
    ]
    recs = [
        f"Automate {_money(conf_monthly)}/mo into a dedicated sub-account ({vehicle}) for >=80% on-time certainty (baseline deterministic minimum is {_money(req_monthly)}/mo).",
    ]
    summary = (
        f"Goal '{name}': deterministic baseline needs {_money(req_monthly)}/mo ({mc['success_rate_pct']:.1f}% MC odds); "
        f"save {_money(conf_monthly)}/mo for >=80% Monte Carlo confidence."
    )

    compare_enabled = bool(inputs.get("compare_enabled", True))
    if compare_enabled:
        name_a = str(inputs.get("scenario_a_name") or "Rent & Invest Difference")
        upfront_a = _f(inputs.get("scenario_a_upfront"), 0)
        monthly_a = _f(inputs.get("scenario_a_monthly_cost"), 2400)
        monthly_invest_a = _f(inputs.get("scenario_a_monthly_invest"), 800)
        ending_asset_a = max(0.0, _f(inputs.get("scenario_a_ending_asset"), 0))

        name_b = str(inputs.get("scenario_b_name") or "Buy Home")
        upfront_b = _f(inputs.get("scenario_b_upfront"), 60000)
        monthly_b = _f(inputs.get("scenario_b_monthly_cost"), 3200)
        monthly_invest_b = _f(inputs.get("scenario_b_monthly_invest"), 0)
        ending_asset_b = max(0.0, _f(inputs.get("scenario_b_ending_asset"), 220000))

        cmp_years = max(1, int(_f(inputs.get("horizon_years"), 10)))
        cmp_rate = _f(inputs.get("investment_return"), 6.5) / 100.0

        total_cost_a = upfront_a + monthly_a * 12 * cmp_years
        total_cost_b = upfront_b + monthly_b * 12 * cmp_years
        diff_upfront_a = max(0.0, upfront_b - upfront_a)
        diff_upfront_b = max(0.0, upfront_a - upfront_b)
        fv_a = _fv_monthly(diff_upfront_a, monthly_invest_a, cmp_rate, cmp_years)
        fv_b = _fv_monthly(diff_upfront_b, monthly_invest_b, cmp_rate, cmp_years)

        net_a = fv_a + ending_asset_a
        net_b = fv_b + ending_asset_b
        winner = name_a if net_a >= net_b else name_b
        advantage = abs(net_a - net_b)

        _, port_vol, _ = _portfolio_return_vol(plan, default_return=cmp_rate, default_vol=float(consts.get("mc_volatility", 0.14)))
        cmp_mc = simulate_compare_mc(
            diff_upfront_a=diff_upfront_a,
            monthly_invest_a=monthly_invest_a,
            total_cost_a=total_cost_a,
            ending_asset_a=ending_asset_a,
            diff_upfront_b=diff_upfront_b,
            monthly_invest_b=monthly_invest_b,
            total_cost_b=total_cost_b,
            ending_asset_b=ending_asset_b,
            years=cmp_years,
            expected_return=cmp_rate,
            volatility=port_vol,
            trials=mc_trials,
            seed=mc_seed,
        )
        winner_win_pct = cmp_mc["a_win_rate_pct"] if net_a >= net_b else cmp_mc["b_win_rate_pct"]

        metrics.append({"label": f"{cmp_years}-Yr Trade-Off Winner", "value": f"{winner} ({_pct(winner_win_pct)})", "tone": "good" if winner_win_pct >= 65 else "warn"})
        tables.append(
            {
                "title": f"{cmp_years}-Year Side-by-Side Scenario Trade-Off",
                "columns": ["Metric", name_a, name_b],
                "rows": [
                    ["Upfront Cash Outlay", _money(upfront_a), _money(upfront_b)],
                    ["Monthly Cost", _money(monthly_a), _money(monthly_b)],
                    [f"Total {cmp_years}-Yr Cash Cost", _money(total_cost_a), _money(total_cost_b)],
                    [f"Deterministic Invested FV ({cmp_years} yr)", _money(fv_a), _money(fv_b)],
                    ["Ending Asset Equity (e.g. Home)", _money(ending_asset_a), _money(ending_asset_b)],
                    ["Monte Carlo Win Rate", _pct(cmp_mc["a_win_rate_pct"]), _pct(cmp_mc["b_win_rate_pct"])],
                    ["Ending Net Wealth (Invested + Equity)", _money(net_a), _money(net_b)],
                ],
            }
        )
        recs.append(
            f"Trade-off ({cmp_years} yrs): '{winner}' leads deterministically by {_money(advantage)} and wins {winner_win_pct:.1f}% of shared-path Monte Carlo trials."
        )
        summary += f" Trade-off winner: '{winner}' ({winner_win_pct:.1f}% MC win rate)."

    pct_done = (current / target * 100.0) if target > 0 else 100.0
    return {
        "module": "finance-goals",
        "score": round(_clamp(pct_done), 1),
        "grade": None,
        "summary": summary,
        "metrics": metrics,
        "monte_carlo": mc_summary,
        "tables": tables,
        "chart": {
            "type": "bars",
            "title": "Projected Goal Value Range ($)",
            "items": [
                {"label": "MC 10th Pct", "value": mc["p10"]},
                {"label": "MC Median", "value": mc["p50"]},
                {"label": "MC 90th Pct", "value": mc["p90"]},
                {"label": "Goal Target", "value": round(target)},
            ],
        },
        "recommendations": recs,
        "plan_patch": {},
    }
