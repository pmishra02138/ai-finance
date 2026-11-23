"""Stage 2 calculators: Foundation & Defense (Budget, Emergency Fund, Debt Payoff)."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from .common import _clamp, _f, _money, _pct, score_grade


def _simulate_debt_payoff(
    accounts: List[Dict[str, Any]],
    extra_monthly: float,
    strategy: str = "avalanche",
    max_months: int = 600,
) -> Tuple[int, float, List[Dict[str, Any]]]:
    """Month-by-month debt amortization for avalanche (highest APR) or snowball (smallest balance)."""
    items = []
    for idx, acc in enumerate(accounts):
        bal = max(0.0, _f(acc.get("balance")))
        if bal <= 0:
            continue
        items.append(
            {
                "name": str(acc.get("name") or f"Debt {idx + 1}"),
                "balance": bal,
                "apr": max(0.0, _f(acc.get("apr"))),
                "min_payment": max(0.0, _f(acc.get("min_payment"))),
                "paid_off_month": None,
                "interest_paid": 0.0,
            }
        )
    if not items:
        return 0, 0.0, []

    if strategy == "snowball":
        items.sort(key=lambda d: (d["balance"], -d["apr"]))
    else:
        items.sort(key=lambda d: (-d["apr"], d["balance"]))

    total_interest = 0.0
    months = 0
    extra = max(0.0, extra_monthly)

    while any(d["balance"] > 0.01 for d in items) and months < max_months:
        months += 1
        freed = extra
        # 1. Accrue monthly interest and pay minimums
        for d in items:
            if d["balance"] <= 0.01:
                freed += d["min_payment"]
                continue
            interest = d["balance"] * (d["apr"] / 100.0 / 12.0)
            d["balance"] += interest
            d["interest_paid"] += interest
            total_interest += interest

            min_pmt = d["min_payment"] if d["min_payment"] > 0 else max(25.0, d["balance"] * 0.02)
            pay = min(d["balance"], min_pmt)
            d["balance"] -= pay
            if d["balance"] <= 0.01:
                d["balance"] = 0.0
                d["paid_off_month"] = months

        # 2. Apply extra + snowball/avalanche rollover to priority target(s)
        for d in items:
            if freed <= 0.01:
                break
            if d["balance"] <= 0.01:
                continue
            pay = min(d["balance"], freed)
            d["balance"] -= pay
            freed -= pay
            if d["balance"] <= 0.01:
                d["balance"] = 0.0
                d["paid_off_month"] = months

    order_rows = [
        {
            "order": i + 1,
            "name": d["name"],
            "apr": d["apr"],
            "paid_off_month": d["paid_off_month"] or max_months,
            "interest_paid": round(d["interest_paid"], 2),
        }
        for i, d in enumerate(items)
    ]
    return months, round(total_interest, 2), order_rows


def calc_budget(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cf = plan.get("cash_flow") or {}
    income = _f(inputs.get("monthly_income"), _f(cf.get("monthly_income"), 9200))
    needs = _f(inputs.get("monthly_needs"), 4500)
    wants = _f(inputs.get("monthly_wants"), 1500)

    total_out = needs + wants
    surplus = income - total_out
    needs_pct = (needs / income * 100.0) if income > 0 else 0.0
    wants_pct = (wants / income * 100.0) if income > 0 else 0.0
    save_pct = (surplus / income * 100.0) if income > 0 else 0.0

    score = _clamp(
        (40.0 if save_pct >= 20 else max(0.0, save_pct * 2.0))
        + (35.0 if needs_pct <= 50 else max(0.0, 35.0 - (needs_pct - 50.0) * 1.2))
        + (25.0 if wants_pct <= 30 else max(0.0, 25.0 - (wants_pct - 30.0) * 1.2))
    )
    recs = []
    if needs_pct > 50:
        recs.append(f"Needs are {_pct(needs_pct)} (target <=50%). Look to trim {_money(needs - income * 0.50)}/mo in fixed bills.")
    if wants_pct > 30:
        recs.append(f"Wants are {_pct(wants_pct)} (target <=30%). Trimming {_money(wants - income * 0.30)}/mo boosts savings immediately.")
    if save_pct < 20:
        recs.append(f"Savings rate is {_pct(save_pct)}. Automate {_money(max(0.0, income * 0.20 - surplus))}/mo extra into savings/investments.")
    if not recs:
        recs.append("Budget meets or exceeds the 50/30/20 benchmark.")

    existing_expenses = cf.get("expenses") or []
    return {
        "module": "finance-budget",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"50/30/20 Split: Needs {_pct(needs_pct)} / Wants {_pct(wants_pct)} / Savings {_pct(save_pct)} ({_money(surplus)}/mo surplus).",
        "metrics": [
            {"label": "Monthly Income", "value": _money(income), "tone": "neutral"},
            {"label": "Needs (Target <=50%)", "value": f"{_money(needs)} ({_pct(needs_pct)})", "tone": "good" if needs_pct <= 50 else "warn"},
            {"label": "Wants (Target <=30%)", "value": f"{_money(wants)} ({_pct(wants_pct)})", "tone": "good" if wants_pct <= 30 else "warn"},
            {"label": "Savings (Target >=20%)", "value": f"{_money(surplus)} ({_pct(save_pct)})", "tone": "good" if save_pct >= 20 else "bad"},
        ],
        "tables": [
            {
                "title": "50/30/20 Comparison",
                "columns": ["Bucket", "Actual ($)", "Actual (%)", "Target ($)", "Variance"],
                "rows": [
                    ["Needs", _money(needs), _pct(needs_pct), _money(income * 0.5), _money(needs - income * 0.5)],
                    ["Wants", _money(wants), _pct(wants_pct), _money(income * 0.3), _money(wants - income * 0.3)],
                    ["Savings & Extra Debt", _money(surplus), _pct(save_pct), _money(income * 0.2), _money(surplus - income * 0.2)],
                ],
            }
        ],
        "chart": {
            "type": "donut",
            "title": "Monthly Cash Flow Allocation",
            "items": [
                {"label": "Needs", "value": round(max(0.0, needs), 2)},
                {"label": "Wants", "value": round(max(0.0, wants), 2)},
                {"label": "Savings", "value": round(max(0.0, surplus), 2)},
            ],
        },
        "recommendations": recs,
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "cash_flow": round(score, 1)},
            "cash_flow": {
                **cf,
                "monthly_income": income,
                "expenses": existing_expenses if existing_expenses else [("Essential Needs", needs), ("Discretionary Wants", wants)],
                "budget_50_30_20": {"needs": needs, "wants": wants, "savings": surplus},
                "commentary": recs[0],
            },
        },
    }


def calc_emergency(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    monthly_essential = _f(inputs.get("monthly_essential_expenses"), 4000)
    current_ef = _f(inputs.get("current_emergency_fund"), 11000)
    monthly_contrib = _f(inputs.get("monthly_contribution"), 500)
    stability = str(inputs.get("job_stability") or "stable").lower()
    dependents = int(_f(inputs.get("dependents"), 0))
    self_employed = bool(inputs.get("self_employed", False))

    target_months = 3
    if stability == "variable":
        target_months = 6
    elif stability == "high_risk":
        target_months = 9
    if dependents > 0:
        target_months += 2
    if self_employed:
        target_months += 3
    target_months = min(12, max(3, target_months))

    target_amount = monthly_essential * target_months
    months_covered = (current_ef / monthly_essential) if monthly_essential > 0 else 0.0
    gap = max(0.0, target_amount - current_ef)
    months_to_goal = math.ceil(gap / monthly_contrib) if gap > 0 and monthly_contrib > 0 else (0 if gap == 0 else 999)
    pct_funded = (current_ef / target_amount * 100.0) if target_amount > 0 else 100.0
    score = _clamp(pct_funded)

    return {
        "module": "finance-emergency",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"Emergency fund covers {months_covered:.1f} of {target_months} recommended months ({_money(current_ef)} / {_money(target_amount)}).",
        "metrics": [
            {"label": "Current Fund", "value": _money(current_ef), "tone": "neutral"},
            {"label": "Target Fund", "value": f"{_money(target_amount)} ({target_months} mos)", "tone": "neutral"},
            {"label": "Coverage", "value": f"{months_covered:.1f} mos", "tone": "good" if months_covered >= target_months else ("warn" if months_covered >= 3 else "bad")},
            {"label": "Remaining Gap", "value": _money(gap), "tone": "good" if gap == 0 else "warn"},
            {"label": "Time to Target", "value": "Funded" if gap == 0 else (f"{months_to_goal} mos" if months_to_goal < 999 else "Set contribution"), "tone": "neutral"},
        ],
        "tables": [
            {
                "title": "Recommended Parking Vehicles",
                "columns": ["Tier", "Suggested Vehicle", "Role"],
                "rows": [
                    ["Tier 1 (1 mo)", "Checking / High-Yield Savings (HYSA)", "Instant same-day liquidity"],
                    ["Tier 2 (2-5 mos)", "HYSA or Treasury Money Market Fund", "4-5% yield, FDIC/Treasury backed"],
                    ["Tier 3 (6+ mos)", "3-Month T-Bill Ladder", "State-tax exempt yield"],
                ],
            }
        ],
        "chart": {
            "type": "bars",
            "title": "Emergency Fund Progress (%)",
            "items": [{"label": "Funded", "value": round(_clamp(pct_funded), 1)}],
        },
        "recommendations": [
            f"Target {target_months} months of essential expenses ({_money(target_amount)}).",
            "Keep funds in an FDIC-insured HYSA or Treasury Money Market — never in equities.",
        ],
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "protection": round(max(40.0, score * 0.8 + 15.0), 1)},
        },
    }


def calc_debt(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    debt_section = plan.get("debt") or {}
    accounts = inputs.get("accounts")
    if not isinstance(accounts, list):
        accounts = debt_section.get("accounts") or []
    extra = _f(inputs.get("extra_monthly_payment"), 400)

    total_bal = sum(_f(a.get("balance")) for a in accounts)
    total_min = sum(_f(a.get("min_payment")) for a in accounts)
    weighted_apr = (
        sum(_f(a.get("balance")) * _f(a.get("apr")) for a in accounts) / total_bal if total_bal > 0 else 0.0
    )

    av_months, av_int, av_order = _simulate_debt_payoff(accounts, extra, "avalanche")
    sn_months, sn_int, _ = _simulate_debt_payoff(accounts, extra, "snowball")
    int_saved = max(0.0, round(sn_int - av_int, 2))

    if total_bal <= 0:
        score = 100.0
    else:
        score = _clamp(95.0 - weighted_apr * 2.2 - min(35.0, av_months * 0.45))

    return {
        "module": "finance-debt",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": (
            "Debt-free! No active balances."
            if total_bal <= 0
            else f"Avalanche pays off {_money(total_bal)} in {av_months} mos ({_money(av_int)} interest), saving {_money(int_saved)} vs. Snowball."
        ),
        "metrics": [
            {"label": "Total Debt", "value": _money(total_bal), "tone": "good" if total_bal == 0 else "warn"},
            {"label": "Weighted Avg APR", "value": _pct(weighted_apr), "tone": "good" if weighted_apr < 7 else ("warn" if weighted_apr < 15 else "bad")},
            {"label": "Avalanche Payoff", "value": f"{av_months} mos", "tone": "neutral"},
            {"label": "Avalanche Interest", "value": _money(av_int), "tone": "neutral"},
            {"label": "Interest Saved vs Snowball", "value": _money(int_saved), "tone": "good"},
        ],
        "tables": [
            {
                "title": "Avalanche vs Snowball Comparison",
                "columns": ["Strategy", "Months to Debt-Free", "Total Interest", "Extra / Mo"],
                "rows": [
                    ["Avalanche (Highest APR)", str(av_months), _money(av_int), _money(extra)],
                    ["Snowball (Smallest Bal)", str(sn_months), _money(sn_int), _money(extra)],
                ],
            },
            {
                "title": "Avalanche Payoff Order",
                "columns": ["Order", "Account", "APR", "Paid Off (Mo)", "Interest"],
                "rows": [
                    [f"#{r['order']}", r["name"], _pct(r["apr"]), str(r["paid_off_month"]), _money(r["interest_paid"])]
                    for r in av_order
                ],
            },
        ],
        "chart": {
            "type": "bars",
            "title": "Total Interest Cost ($)",
            "items": [
                {"label": "Avalanche", "value": av_int},
                {"label": "Snowball", "value": sn_int},
            ],
        },
        "recommendations": (
            ["Maintain zero high-interest consumer debt and redirect surplus into investments."]
            if total_bal <= 0
            else [
                f"Direct {_money(extra)}/mo extra to '{av_order[0]['name']}' ({_pct(av_order[0]['apr'])} APR) first.",
                f"Minimum payments total {_money(total_min)}/mo; automate all minimums to avoid late fees.",
            ]
        ),
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "debt": round(score, 1)},
            "debt": {
                "strategy": "Avalanche (highest APR first)",
                "payoff_months": av_months,
                "total_interest": av_int,
                "accounts": accounts,
            },
        },
    }
