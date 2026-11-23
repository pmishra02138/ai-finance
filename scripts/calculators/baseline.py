"""Stage 1 calculators: Baseline & Triage (Cash Flow & Budget, Net Worth)."""

from __future__ import annotations

from typing import Any, Dict

from .common import _clamp, _f, _gross_annual_income, _money, _pct, score_grade


def calc_budget(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cf = plan.get("cash_flow") or {}
    income = _f(inputs.get("monthly_income"), _f(cf.get("monthly_income"), 9200))
    if "monthly_needs" in inputs or "monthly_wants" in inputs:
        needs = _f(inputs.get("monthly_needs"), 4600)
        wants = _f(inputs.get("monthly_wants"), 1600)
    elif "monthly_expenses" in inputs:
        total_exp = max(0.0, _f(inputs.get("monthly_expenses"), 6200))
        needs = total_exp * 0.75
        wants = total_exp * 0.25
    else:
        needs = 4600.0
        wants = 1600.0
    liquid_cash = max(0.0, _f(inputs.get("liquid_cash"), 15000))

    total_out = needs + wants
    surplus = income - total_out
    needs_pct = (needs / income * 100.0) if income > 0 else 0.0
    wants_pct = (wants / income * 100.0) if income > 0 else 0.0
    save_pct = (surplus / income * 100.0) if income > 0 else 0.0
    ef_months = (liquid_cash / needs) if needs > 0 else (liquid_cash / total_out if total_out > 0 else 0.0)

    if income <= 0:
        score = 0.0
    else:
        score = _clamp(
            (40.0 if save_pct >= 20 else max(0.0, save_pct * 2.0))
            + (35.0 if needs_pct <= 50 else max(0.0, 35.0 - (needs_pct - 50.0) * 1.2))
            + (25.0 if wants_pct <= 30 else max(0.0, 25.0 - (wants_pct - 30.0) * 1.2))
        )
    recs = []
    if income <= 0:
        recs.append("Enter positive monthly take-home income to calculate your 50/30/20 cash-flow score.")
    if needs_pct > 50:
        recs.append(f"Needs are {_pct(needs_pct)} (target <=50%). Look to trim {_money(needs - income * 0.50)}/mo in fixed bills.")
    if wants_pct > 30:
        recs.append(f"Wants are {_pct(wants_pct)} (target <=30%). Trimming {_money(wants - income * 0.30)}/mo boosts savings immediately.")
    if save_pct < 20:
        recs.append(f"Savings rate is {_pct(save_pct)}. Automate {_money(max(0.0, income * 0.20 - surplus))}/mo extra into savings/investments.")
    if ef_months < 3:
        recs.append(f"Liquid cash covers {ef_months:.1f} months of essential needs; prioritize building reserves in Stage 2.")
    if not recs:
        recs.append("Cash flow meets or exceeds the 50/30/20 benchmark with healthy liquid reserves.")

    existing_expenses = cf.get("expenses") or []
    return {
        "module": "finance-budget",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"50/30/20 Split (Take-Home): Needs {_pct(needs_pct)} / Wants {_pct(wants_pct)} / Savings {_pct(save_pct)} ({_money(surplus)}/mo surplus, {ef_months:.1f} mos liquid runway).",
        "metrics": [
            {"label": "Monthly Take-Home", "value": _money(income), "tone": "neutral"},
            {"label": "Needs (Target <=50%)", "value": f"{_money(needs)} ({_pct(needs_pct)})", "tone": "good" if needs_pct <= 50 else "warn"},
            {"label": "Wants (Target <=30%)", "value": f"{_money(wants)} ({_pct(wants_pct)})", "tone": "good" if wants_pct <= 30 else "warn"},
            {"label": "Savings (Target >=20%)", "value": f"{_money(surplus)} ({_pct(save_pct)})", "tone": "good" if save_pct >= 20 else "bad"},
            {"label": "Liquid Reserve Runway", "value": f"{ef_months:.1f} mos", "tone": "good" if ef_months >= 6 else ("warn" if ef_months >= 3 else "bad")},
        ],
        "tables": [
            {
                "title": "50/30/20 Cash Flow Comparison",
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
    annual_income = _f(inputs.get("annual_income"), _gross_annual_income(plan))

    total_assets = cash + investments + real_estate + other_assets
    total_liabilities = mortgage + other_debt
    net_worth = total_assets - total_liabilities
    if age <= 0:
        expected_mnd = 0.0
        bench_label = "MND Benchmark (Gross)"
    elif age < 30:
        # Early-career ramp (~0.6x salary at 26, ~1.2x at 30)
        expected_mnd = annual_income * max(0.25, (age - 22) * 0.15)
        bench_label = "Early-Career Benchmark"
    elif age < 35:
        # Smooth linear ramp from 1.2x at age 30 to 3.5x (Age*Income/10) at age 35
        expected_mnd = annual_income * (1.2 + (age - 30) * (2.3 / 5.0))
        bench_label = "Early-Career Benchmark"
    else:
        expected_mnd = (age * annual_income) / 10.0
        bench_label = "MND Benchmark (Gross)"
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
        "module": "finance-networth",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"Net worth is {_money(net_worth)} ({tier}) vs. {_money(expected_mnd)} MND benchmark (gross income {_money(annual_income)}). Next milestone: {_money(next_ms)}.",
        "metrics": [
            {"label": "Total Assets", "value": _money(total_assets), "tone": "good"},
            {"label": "Total Liabilities", "value": _money(total_liabilities), "tone": "warn" if total_liabilities > 0 else "good"},
            {"label": "Net Worth", "value": _money(net_worth), "tone": "good" if net_worth >= 0 else "bad"},
            {"label": bench_label, "value": _money(expected_mnd), "tone": "neutral"},
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
        "plan_patch": {
            "investments": {**inv, "total_value": investments},
            "cash_flow": {**cf, "gross_annual_income": annual_income},
        },
    }
