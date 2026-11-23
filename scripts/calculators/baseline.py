"""Stage 1 calculators: Baseline & Triage (Quick Snapshot, Net Worth)."""

from __future__ import annotations

from typing import Any, Dict

from .common import _clamp, _f, _fv_monthly, _gross_annual_income, _money, _pct, score_grade, score_signal


def calc_quick(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cf = plan.get("cash_flow") or {}
    ret = plan.get("retirement") or {}
    inv = plan.get("investments") or {}
    debt = plan.get("debt") or {}
    cats = plan.get("categories") or {}

    default_exp = sum(_f(x[1] if isinstance(x, (list, tuple)) else x.get("amount", 0)) for x in (cf.get("expenses") or []))
    default_debt = sum(_f(a.get("balance")) for a in (debt.get("accounts") or []))

    income = _f(inputs.get("monthly_income"), _f(cf.get("monthly_income"), 8000))
    expenses = _f(inputs.get("monthly_expenses"), default_exp or 5500)
    # Separate liquid cash (reserves) from invested retirement savings; support legacy total_savings fallback
    legacy_total = inputs.get("total_savings")
    liquid_cash = _f(inputs.get("liquid_cash"), _f(legacy_total, 15000) if legacy_total is not None else 15000)
    invested_savings = _f(
        inputs.get("invested_savings"),
        _f(legacy_total, _f(inv.get("total_value"), _f(ret.get("current_balance"), 50000)))
        if legacy_total is not None
        else _f(inv.get("total_value"), _f(ret.get("current_balance"), 50000)),
    )
    total_debt = _f(inputs.get("total_debt"), default_debt)
    age = int(_f(inputs.get("age"), _f(ret.get("current_age"), 35)))
    retire_age = int(_f(inputs.get("retirement_age"), _f(ret.get("retirement_age"), 65)))

    surplus = income - expenses
    savings_rate = (surplus / income * 100.0) if income > 0 else 0.0
    dti_annual = (total_debt / (income * 12.0) * 100.0) if income > 0 else 0.0
    ef_months = (liquid_cash / expenses) if expenses > 0 else 0.0
    years_left = max(0, retire_age - age)
    projected = _fv_monthly(invested_savings, max(0.0, surplus * 0.5), 0.06, years_left)
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
        recs.append(f"Build liquid cash reserves from {ef_months:.1f} months to 6 months ({_money(expenses * 6)}).")
    if total_debt > 0:
        recs.append(f"Attack {_money(total_debt)} total debt with Avalanche strategy to minimize interest.")
    if on_track_pct < 100:
        recs.append(f"Projected retirement balance ({_money(projected)}) is {_pct(on_track_pct, 0)} of 25x target ({_money(target)}).")
    if not recs:
        recs.append("Strong baseline across savings, liquidity, debt, and retirement trajectory.")

    # Never overwrite an already-populated 5-pillar composite score on sync
    has_detailed_pillars = any(_f(cats.get(k), 0.0) > 0 for k in ("cash_flow", "debt", "investments", "retirement", "protection"))
    plan_patch: Dict[str, Any] = {
        "cash_flow": {**cf, "monthly_income": income},
        "retirement": {**ret, "current_age": age, "retirement_age": retire_age},
    }
    if not has_detailed_pillars:
        plan_patch["health_score"] = round(score, 1)
        plan_patch["grade"] = score_grade(score)
        plan_patch["signal"] = score_signal(score)
    else:
        recs.append("Your detailed 5-pillar Financial Health Score is preserved; update individual stage modules or Full Health Analysis to change it.")

    return {
        "module": "finance-quick",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": f"60-Second Triage: Score {round(score)}/100 ({score_grade(score)}) — {score_signal(score)}.",
        "metrics": [
            {"label": "Monthly Surplus", "value": _money(surplus), "tone": "good" if surplus >= 0 else "bad"},
            {"label": "Savings Rate (Net)", "value": _pct(savings_rate), "tone": "good" if savings_rate >= 20 else ("warn" if savings_rate >= 10 else "bad")},
            {"label": "Liquid Reserve Coverage", "value": f"{ef_months:.1f} mos", "tone": "good" if ef_months >= 6 else ("warn" if ef_months >= 3 else "bad")},
            {"label": "Debt-to-Net-Income", "value": _pct(dti_annual), "tone": "good" if dti_annual <= 36 else ("warn" if dti_annual <= 60 else "bad")},
            {"label": "Retirement On-Track", "value": _pct(on_track_pct, 0), "tone": "good" if on_track_pct >= 100 else "warn"},
        ],
        "tables": [],
        "chart": {
            "type": "bars",
            "title": "Quick Snapshot Ratios (%)",
            "items": [
                {"label": "Savings Rate", "value": round(_clamp(savings_rate), 1)},
                {"label": "Retirement Track", "value": round(_clamp(on_track_pct), 1)},
                {"label": "Triage Score", "value": round(score, 1)},
            ],
        },
        "recommendations": recs[:4],
        "plan_patch": plan_patch,
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
    elif age < 35:
        # Early-career ramp (~0.6x salary at 26, ~1.2x at 30) since Stanley-Danko (Age*Income/10) over-penalizes <35
        expected_mnd = annual_income * max(0.25, (age - 22) * 0.15)
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
