#!/usr/bin/env python3
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

import math
from typing import Any, Dict, List, Optional, Tuple

from generate_finance_pdf import score_grade, score_signal


def _f(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or val == "":
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


def _money(val: float) -> str:
    sign = "-" if val < 0 else ""
    return f"{sign}${abs(val):,.0f}"


def _pct(val: float, dec: int = 1) -> str:
    return f"{val:.{dec}f}%"


def _fv_monthly(pv: float, pmt: float, annual_rate: float, years: float) -> float:
    months = max(0, int(round(years * 12)))
    if months == 0:
        return pv
    r = annual_rate / 12.0
    if abs(r) < 1e-12:
        return pv + pmt * months
    factor = (1.0 + r) ** months
    return pv * factor + pmt * ((factor - 1.0) / r)


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


# ---------------------------------------------------------------------------
# Stage 1: Baseline & Triage
# ---------------------------------------------------------------------------
def calc_quick(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cf = plan.get("cash_flow") or {}
    ret = plan.get("retirement") or {}
    debt = plan.get("debt") or {}
    default_exp = sum(_f(x[1] if isinstance(x, (list, tuple)) else x.get("amount", 0)) for x in (cf.get("expenses") or []))
    default_debt = sum(_f(a.get("balance")) for a in (debt.get("accounts") or []))

    income = _f(inputs.get("monthly_income"), _f(cf.get("monthly_income"), 8000))
    expenses = _f(inputs.get("monthly_expenses"), default_exp or 5500)
    savings = _f(inputs.get("total_savings"), _f(ret.get("current_balance"), 50000))
    total_debt = _f(inputs.get("total_debt"), default_debt)
    age = int(_f(inputs.get("age"), _f(ret.get("current_age"), 35)))
    retire_age = int(_f(inputs.get("retirement_age"), _f(ret.get("retirement_age"), 65)))

    surplus = income - expenses
    savings_rate = (surplus / income * 100.0) if income > 0 else 0.0
    dti_annual = (total_debt / (income * 12.0) * 100.0) if income > 0 else 0.0
    ef_months = (savings / expenses) if expenses > 0 else 0.0
    years_left = max(0, retire_age - age)
    projected = _fv_monthly(savings, max(0.0, surplus * 0.5), 0.06, years_left)
    target = expenses * 12.0 * 25.0
    on_track_pct = (projected / target * 100.0) if target > 0 else 100.0

    score = _clamp(
        min(35.0, max(0.0, savings_rate * 1.4))
        + min(25.0, ef_months * 4.2)
        + max(0.0, 20.0 - dti_annual * 0.25)
        + min(20.0, on_track_pct * 0.2)
    )
    recs = []
    if savings_rate < 15:
        recs.append(f"Raise savings rate from {_pct(savings_rate)} toward 20% (+{_money(max(0, income * 0.20 - surplus))}/mo).")
    if ef_months < 6:
        recs.append(f"Build liquid reserves from {ef_months:.1f} months to 6 months ({_money(expenses * 6)}).")
    if total_debt > 0:
        recs.append(f"Attack {_money(total_debt)} total debt with Avalanche strategy to minimize interest.")
    if on_track_pct < 100:
        recs.append(f"Projected retirement balance ({_money(projected)}) is {_pct(on_track_pct, 0)} of 25x target ({_money(target)}).")
    if not recs:
        recs.append("Strong baseline across savings, liquidity, debt, and retirement trajectory.")

    return {
        "skill": "finance-quick",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"60-Second Snapshot: Score {round(score)}/100 ({score_grade(score)}) — {score_signal(score)}.",
        "metrics": [
            {"label": "Monthly Surplus", "value": _money(surplus), "tone": "good" if surplus >= 0 else "bad"},
            {"label": "Savings Rate", "value": _pct(savings_rate), "tone": "good" if savings_rate >= 20 else ("warn" if savings_rate >= 10 else "bad")},
            {"label": "Debt-to-Annual-Income", "value": _pct(dti_annual), "tone": "good" if dti_annual <= 36 else ("warn" if dti_annual <= 60 else "bad")},
            {"label": "Reserve Coverage", "value": f"{ef_months:.1f} mos", "tone": "good" if ef_months >= 6 else ("warn" if ef_months >= 3 else "bad")},
            {"label": "Retirement On-Track", "value": _pct(on_track_pct, 0), "tone": "good" if on_track_pct >= 100 else "warn"},
        ],
        "tables": [],
        "chart": {
            "type": "bars",
            "title": "Quick Snapshot Ratios (%)",
            "items": [
                {"label": "Savings Rate", "value": round(_clamp(savings_rate), 1)},
                {"label": "Retirement Track", "value": round(_clamp(on_track_pct), 1)},
                {"label": "Overall Score", "value": round(score, 1)},
            ],
        },
        "recommendations": recs[:3],
        "plan_patch": {
            "health_score": round(score, 1),
            "grade": score_grade(score),
            "signal": score_signal(score),
            "cash_flow": {**cf, "monthly_income": income},
            "retirement": {**ret, "current_age": age, "retirement_age": retire_age},
        },
    }


def calc_networth(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    inv = plan.get("investments") or {}
    debt = plan.get("debt") or {}
    cf = plan.get("cash_flow") or {}
    ret = plan.get("retirement") or {}

    cash = _f(inputs.get("cash_assets"), 15000)
    investments = _f(inputs.get("investment_assets"), _f(inv.get("total_value"), 184000))
    real_estate = _f(inputs.get("real_estate_assets"), 0)
    other_assets = _f(inputs.get("other_assets"), 15000)
    mortgage = _f(inputs.get("mortgage_debt"), 0)
    other_debt = _f(inputs.get("other_debt"), sum(_f(a.get("balance")) for a in (debt.get("accounts") or [])))
    age = int(_f(inputs.get("age"), _f(ret.get("current_age"), 38)))
    annual_income = _f(inputs.get("annual_income"), _f(cf.get("monthly_income"), 9200) * 12.0)

    total_assets = cash + investments + real_estate + other_assets
    total_liabilities = mortgage + other_debt
    net_worth = total_assets - total_liabilities
    expected_mnd = (age * annual_income) / 10.0 if age > 0 else 0.0
    mnd_ratio = (net_worth / expected_mnd) if expected_mnd > 0 else 1.0

    milestones = [100_000, 250_000, 500_000, 1_000_000, 5_000_000, 10_000_000]
    next_ms = next((m for m in milestones if m > net_worth), 10_000_000)
    ms_gap = max(0.0, next_ms - net_worth)

    if mnd_ratio >= 2.0:
        tier = "Prodigious Accumulator (PAW)"
    elif mnd_ratio >= 1.0:
        tier = "Average Accumulator (AAW)"
    else:
        tier = "Under Accumulator (UAW)"

    score = _clamp(40.0 + mnd_ratio * 35.0)
    return {
        "skill": "finance-networth",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"Net worth is {_money(net_worth)} ({tier}). Next milestone: {_money(next_ms)} ({_money(ms_gap)} away).",
        "metrics": [
            {"label": "Total Assets", "value": _money(total_assets), "tone": "good"},
            {"label": "Total Liabilities", "value": _money(total_liabilities), "tone": "warn" if total_liabilities > 0 else "good"},
            {"label": "Net Worth", "value": _money(net_worth), "tone": "good" if net_worth >= 0 else "bad"},
            {"label": "MND Benchmark", "value": _money(expected_mnd), "tone": "neutral"},
            {"label": "Next Milestone", "value": _money(next_ms), "tone": "neutral"},
        ],
        "tables": [
            {
                "title": "Balance Sheet Breakdown",
                "columns": ["Line Item", "Type", "Amount"],
                "rows": [
                    ["Cash & Liquid", "Asset", _money(cash)],
                    ["Investments & Retirement", "Asset", _money(investments)],
                    ["Real Estate", "Asset", _money(real_estate)],
                    ["Other Assets", "Asset", _money(other_assets)],
                    ["Mortgage", "Liability", _money(-mortgage)],
                    ["Other Debts", "Liability", _money(-other_debt)],
                    ["NET WORTH", "Total", _money(net_worth)],
                ],
            }
        ],
        "chart": {
            "type": "donut",
            "title": "Asset Composition",
            "items": [
                {"label": "Cash", "value": round(cash, 2)},
                {"label": "Investments", "value": round(investments, 2)},
                {"label": "Real Estate", "value": round(real_estate, 2)},
                {"label": "Other", "value": round(other_assets, 2)},
            ],
        },
        "recommendations": [
            f"Wealth accumulation tier: {tier} (ratio {mnd_ratio:.2f}x of Millionaire Next Door target).",
            f"Focus on closing the {_money(ms_gap)} gap to reach {_money(next_ms)}.",
        ],
        "plan_patch": {"investments": {**inv, "total_value": investments}},
    }


# ---------------------------------------------------------------------------
# Stage 2: Foundation & Defense
# ---------------------------------------------------------------------------
def calc_budget(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cf = plan.get("cash_flow") or {}
    income = _f(inputs.get("monthly_income"), _f(cf.get("monthly_income"), 9200))
    needs = _f(inputs.get("monthly_needs"), 4500)
    wants = _f(inputs.get("monthly_wants"), 1500)
    debt_savings = _f(inputs.get("monthly_savings_debt"), max(0.0, income - needs - wants))

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

    return {
        "skill": "finance-budget",
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
                "expenses": [("Essential Needs", needs), ("Discretionary Wants", wants)],
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
        "skill": "finance-emergency",
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
        "skill": "finance-debt",
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


# ---------------------------------------------------------------------------
# Stage 3: Growth & Optimization
# ---------------------------------------------------------------------------
def calc_portfolio(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    inv = plan.get("investments") or {}
    ret = plan.get("retirement") or {}
    total_value = _f(inputs.get("total_value"), _f(inv.get("total_value"), 184000))
    age = int(_f(inputs.get("age"), _f(ret.get("current_age"), 38)))
    expense_ratio = _f(inputs.get("avg_expense_ratio"), 0.08)

    us_stocks = _f(inputs.get("us_stocks_pct"), 58)
    intl_stocks = _f(inputs.get("intl_stocks_pct"), 14)
    bonds = _f(inputs.get("bonds_pct"), 18)
    reits = _f(inputs.get("reits_pct"), 6)
    cash = _f(inputs.get("cash_pct"), 4)

    target_equity = _clamp(110 - age, 30, 90)
    target_us = round(target_equity * 0.70, 1)
    target_intl = round(target_equity * 0.30, 1)
    target_bonds = round(max(5.0, 100.0 - target_equity - 5.0), 1)
    target_reits = 3.0
    target_cash = round(max(0.0, 100.0 - (target_us + target_intl + target_bonds + target_reits)), 1)

    alloc = [
        {"name": "US Stocks", "pct": us_stocks, "target_pct": target_us},
        {"name": "Intl Stocks", "pct": intl_stocks, "target_pct": target_intl},
        {"name": "Bonds", "pct": bonds, "target_pct": target_bonds},
        {"name": "Real Estate (REIT)", "pct": reits, "target_pct": target_reits},
        {"name": "Cash / MM", "pct": cash, "target_pct": target_cash},
    ]
    max_drift = max(abs(a["pct"] - a["target_pct"]) for a in alloc)
    annual_fee = total_value * (expense_ratio / 100.0)
    score = _clamp(95.0 - max_drift * 1.8 - max(0.0, (expense_ratio - 0.10) * 60.0))

    rows = []
    for a in alloc:
        diff = a["pct"] - a["target_pct"]
        trade = total_value * (-diff / 100.0)
        action = f"Buy {_money(trade)}" if trade > 50 else (f"Trim {_money(-trade)}" if trade < -50 else "On target")
        rows.append([a["name"], _pct(a["pct"]), _pct(a["target_pct"]), f"{'+' if diff >= 0 else ''}{diff:.1f}%", action])

    return {
        "skill": "finance-portfolio",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"Portfolio {_money(total_value)} — max drift {max_drift:.1f}pp, weighted ER {_pct(expense_ratio, 2)} ({_money(annual_fee)}/yr).",
        "metrics": [
            {"label": "Portfolio Value", "value": _money(total_value), "tone": "neutral"},
            {"label": "Max Drift", "value": f"{max_drift:.1f} pp", "tone": "good" if max_drift <= 5 else "warn"},
            {"label": "Avg Expense Ratio", "value": _pct(expense_ratio, 2), "tone": "good" if expense_ratio <= 0.15 else "bad"},
            {"label": "Annual Fee Drag", "value": _money(annual_fee), "tone": "good" if expense_ratio <= 0.15 else "warn"},
        ],
        "tables": [{"title": "Allocation & Rebalancing Trades", "columns": ["Asset Class", "Current", "Target", "Drift", "Trade"], "rows": rows}],
        "chart": {
            "type": "donut",
            "title": "Current Asset Allocation (%)",
            "items": [{"label": a["name"], "value": a["pct"]} for a in alloc if a["pct"] > 0],
        },
        "recommendations": [
            "Rebalance any asset class drifting >5 percentage points from target using new contributions first to avoid capital gains.",
            "Target weighted expense ratio <=0.10% using broad index ETFs.",
        ],
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "investments": round(score, 1)},
            "investments": {"total_value": total_value, "allocation": alloc},
        },
    }


SCREEN_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "3-fund": {
        "title": "Boglehead 3-Fund Index",
        "expected_return": "7.5% nominal",
        "avg_er": "0.04%",
        "tickers": [
            ["VTI / FSKAX", "US Total Stock Market", "60%", "0.03%"],
            ["VXUS / FTIHX", "Total International Stock", "20%", "0.07%"],
            ["BND / FXNAX", "US Total Bond Market", "20%", "0.03%"],
        ],
    },
    "dividend": {
        "title": "Dividend Growth",
        "expected_return": "7.0% nominal",
        "avg_er": "0.06%",
        "tickers": [
            ["SCHD", "US Dividend Equity", "40%", "0.06%"],
            ["VIG", "Dividend Appreciation", "35%", "0.06%"],
            ["VYMI", "International High Dividend", "15%", "0.22%"],
            ["SGOV", "Short-Term Treasuries", "10%", "0.09%"],
        ],
    },
    "bonds": {
        "title": "Conservative Bond & Income",
        "expected_return": "4.8% nominal",
        "avg_er": "0.06%",
        "tickers": [
            ["BND", "Total US Bond Market", "50%", "0.03%"],
            ["VTIP", "Short-Term TIPS (Inflation)", "25%", "0.04%"],
            ["SGOV", "0-3 Month US Treasuries", "25%", "0.09%"],
        ],
    },
    "reits": {
        "title": "Real Estate (REIT) Tilt",
        "expected_return": "7.2% nominal",
        "avg_er": "0.10%",
        "tickers": [
            ["VNQ", "US Real Estate Index", "50%", "0.12%"],
            ["VNQI", "Global ex-US Real Estate", "20%", "0.12%"],
            ["VTI", "Core US Equity Ballast", "30%", "0.03%"],
        ],
    },
    "esg": {
        "title": "ESG Screened Core",
        "expected_return": "7.3% nominal",
        "avg_er": "0.10%",
        "tickers": [
            ["ESGV", "US ESG Stock ETF", "60%", "0.09%"],
            ["VSGX", "International ESG Stock ETF", "20%", "0.12%"],
            ["BGRN", "Global Green Bond ETF", "20%", "0.20%"],
        ],
    },
}


def calc_screen(inputs: Dict[str, Any], _plan: Dict[str, Any]) -> Dict[str, Any]:
    key = str(inputs.get("strategy") or "3-fund").lower()
    strat = SCREEN_STRATEGIES.get(key, SCREEN_STRATEGIES["3-fund"])
    amount = _f(inputs.get("investment_amount"), 25000)

    rows = []
    chart_items = []
    for ticker, desc, weight_str, er in strat["tickers"]:
        w = float(weight_str.replace("%", ""))
        rows.append([ticker, desc, weight_str, er, _money(amount * w / 100.0)])
        chart_items.append({"label": ticker, "value": w})

    return {
        "skill": "finance-screen",
        "score": None,
        "grade": None,
        "summary": f"{strat['title']} model — expected {strat['expected_return']}, avg ER {strat['avg_er']}.",
        "metrics": [
            {"label": "Strategy", "value": strat["title"], "tone": "neutral"},
            {"label": "Amount to Allocate", "value": _money(amount), "tone": "neutral"},
            {"label": "Expected Return", "value": strat["expected_return"], "tone": "good"},
            {"label": "Avg Expense Ratio", "value": strat["avg_er"], "tone": "good"},
        ],
        "tables": [{"title": "Screened Model Portfolio", "columns": ["Ticker", "Asset Role", "Weight", "ER", "Allocation"], "rows": rows}],
        "chart": {"type": "donut", "title": f"{strat['title']} Weights (%)", "items": chart_items},
        "recommendations": [
            "Verify fund availability and expense ratios at your brokerage before purchasing.",
            "Educational screening model only — not a recommendation to buy any specific security.",
        ],
        "plan_patch": {},
    }


def calc_taxes(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cf = plan.get("cash_flow") or {}
    gross_income = _f(inputs.get("gross_annual_income"), _f(cf.get("monthly_income"), 9200) * 12.0)
    marginal_rate = _f(inputs.get("marginal_tax_rate"), 24.0) / 100.0
    cur_401k = _f(inputs.get("current_401k"), 11000)
    cur_hsa = _f(inputs.get("current_hsa"), 0)
    cur_ira = _f(inputs.get("current_ira"), 0)
    hsa_eligible = bool(inputs.get("hsa_eligible", True))
    family_hsa = bool(inputs.get("family_hsa", False))
    harvestable_losses = _f(inputs.get("harvestable_losses"), 0)

    limit_401k = 23500.0
    limit_hsa = (8550.0 if family_hsa else 4300.0) if hsa_eligible else 0.0
    limit_ira = 7000.0

    rem_401k = max(0.0, limit_401k - cur_401k)
    rem_hsa = max(0.0, limit_hsa - cur_hsa)
    rem_ira = max(0.0, limit_ira - cur_ira)
    tlh_ded = min(3000.0, max(0.0, harvestable_losses))

    save_401k = rem_401k * marginal_rate
    save_hsa = rem_hsa * (marginal_rate + 0.0765)
    save_tlh = tlh_ded * marginal_rate
    total_savings = save_401k + save_hsa + save_tlh

    used_total = cur_401k + cur_hsa + cur_ira
    avail_total = limit_401k + limit_hsa + limit_ira
    score = _clamp((used_total / avail_total * 100.0) if avail_total > 0 else 80.0)

    return {
        "skill": "finance-taxes",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"Estimated {_money(total_savings)}/yr in untapped tax savings at {_pct(marginal_rate * 100, 0)} marginal bracket.",
        "metrics": [
            {"label": "Gross Annual Income", "value": _money(gross_income), "tone": "neutral"},
            {"label": "Est. Annual Tax Savings", "value": _money(total_savings), "tone": "good"},
            {"label": "Unused 401(k) Space", "value": _money(rem_401k), "tone": "warn" if rem_401k > 0 else "good"},
            {"label": "Unused HSA Space", "value": _money(rem_hsa), "tone": "warn" if rem_hsa > 0 else "good"},
        ],
        "tables": [
            {
                "title": "Tax-Advantaged Optimization Opportunities",
                "columns": ["Strategy", "Current", "Annual Limit", "Remaining", "Est. Tax Saved"],
                "rows": [
                    ["Traditional 401(k)", _money(cur_401k), _money(limit_401k), _money(rem_401k), _money(save_401k)],
                    ["HSA (Triple Tax-Free)", _money(cur_hsa), _money(limit_hsa), _money(rem_hsa), _money(save_hsa)],
                    ["IRA / Backdoor Roth", _money(cur_ira), _money(limit_ira), _money(rem_ira), "Tax-free growth"],
                    ["Tax-Loss Harvesting", _money(harvestable_losses), "$3,000 ord. cap", _money(tlh_ded), _money(save_tlh)],
                ],
            }
        ],
        "chart": {
            "type": "bars",
            "title": "Estimated Tax Savings by Lever ($)",
            "items": [
                {"label": "401(k)", "value": round(save_401k, 2)},
                {"label": "HSA", "value": round(save_hsa, 2)},
                {"label": "Loss Harvest", "value": round(save_tlh, 2)},
            ],
        },
        "recommendations": [
            f"Prioritize HSA ({_money(rem_hsa)} remaining) and 401(k) ({_money(rem_401k)} remaining) to capture {_money(save_401k + save_hsa)}/yr.",
            "Consult a CPA before executing Roth conversions or Backdoor Roth (watch pro-rata rule).",
        ],
        "plan_patch": {},
    }


# ---------------------------------------------------------------------------
# Stage 4: Horizons & Trade-Offs
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Stage 5: Synthesis & Export
# ---------------------------------------------------------------------------
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
        "skill": "finance-analyze",
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
        "skill": "finance-report-pdf",
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


CALCULATORS = {
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
