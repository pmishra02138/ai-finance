"""Stage 2 calculators: Foundation & Defense (Emergency Fund, Debt Payoff, Protection & Estate)."""

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

    prot = plan.get("protection") or {}
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
            "Run Protection & Estate next to score insurance and estate planning alongside your emergency fund.",
        ],
        "plan_patch": {
            "protection": {**prot, "emergency_fund_months": round(months_covered, 1)},
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
    high_apr_bal = sum(_f(a.get("balance")) for a in accounts if _f(a.get("apr")) > 7.0)
    low_apr_bal = max(0.0, total_bal - high_apr_bal)
    weighted_apr = (
        sum(_f(a.get("balance")) * _f(a.get("apr")) for a in accounts) / total_bal if total_bal > 0 else 0.0
    )

    av_months, av_int, av_order = _simulate_debt_payoff(accounts, extra, "avalanche")
    sn_months, sn_int, _ = _simulate_debt_payoff(accounts, extra, "snowball")
    int_saved = max(0.0, round(sn_int - av_int, 2))

    # Detect negative amortization (minimum payment < monthly interest when extra == 0)
    neg_amort_alerts: List[str] = []
    for acc in accounts:
        bal = max(0.0, _f(acc.get("balance")))
        apr = max(0.0, _f(acc.get("apr")))
        min_pmt = max(0.0, _f(acc.get("min_payment")))
        monthly_int = bal * (apr / 100.0 / 12.0)
        if bal > 0 and min_pmt > 0 and min_pmt <= monthly_int and extra <= 0:
            req_pmt = math.ceil(monthly_int + max(25.0, bal * 0.01))
            neg_amort_alerts.append(
                f"{acc.get('name', 'Debt')}: min payment ({_money(min_pmt)}/mo) is below monthly interest ({_money(monthly_int)}/mo) — pay at least {_money(req_pmt)}/mo to stop balance growth."
            )

    # Separate high-APR (>7%), mid-APR (5-7%), and low-APR (<=5%) fixed debt in scoring
    if total_bal <= 0:
        score = 100.0
    else:
        high_share = high_apr_bal / total_bal
        mid_apr_bal = sum(_f(a.get("balance")) for a in accounts if 5.0 < _f(a.get("apr")) <= 7.0)
        mid_share = mid_apr_bal / total_bal
        high_apr_penalty = high_share * min(45.0, weighted_apr * 2.2)
        low_apr_penalty = (1.0 - high_share) * min(12.0, weighted_apr * 1.5)
        if high_apr_bal > 0:
            duration_penalty = min(25.0, av_months * 0.45)
        elif mid_share > 0:
            duration_penalty = min(12.0, av_months * 0.12)
        else:
            # Low-APR (<=5%) long-term amortized debt (e.g. 3% mortgage) carries minimal penalty
            duration_penalty = min(5.0, av_months * 0.015)
        neg_amort_penalty = 15.0 if neg_amort_alerts else 0.0
        score = _clamp(98.0 - high_apr_penalty - low_apr_penalty - duration_penalty - neg_amort_penalty)

    recs = (
        ["Maintain zero high-interest consumer debt and redirect surplus into investments."]
        if total_bal <= 0
        else [
            *neg_amort_alerts,
            f"Direct {_money(extra)}/mo extra to '{av_order[0]['name']}' ({_pct(av_order[0]['apr'])} APR) first.",
            (
                f"Prioritize eliminating {_money(high_apr_bal)} in high-APR debt (>7%) before taxable investing."
                if high_apr_bal > 0
                else "All balances are <=7% APR — balance extra payoff against tax-advantaged retirement investing."
            ),
            f"Minimum payments total {_money(total_min)}/mo; automate all minimums to avoid late fees.",
        ]
    )

    return {
        "module": "finance-debt",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": (
            "Debt-free! No active balances."
            if total_bal <= 0
            else (
                f"WARNING: Negative amortization detected ({len(neg_amort_alerts)} account(s)) — minimum payments do not cover monthly interest."
                if neg_amort_alerts
                else f"Avalanche pays off {_money(total_bal)} ({_money(high_apr_bal)} high-APR >7%) in {av_months} mos ({_money(av_int)} interest), saving {_money(int_saved)} vs. Snowball."
            )
        ),
        "metrics": [
            {"label": "Total Debt", "value": _money(total_bal), "tone": "good" if total_bal == 0 else "warn"},
            {"label": "High-APR Debt (>7%)", "value": _money(high_apr_bal), "tone": "good" if high_apr_bal == 0 else "bad"},
            {"label": "Low-APR Debt (<=7%)", "value": _money(low_apr_bal), "tone": "neutral"},
            {"label": "Avalanche Payoff", "value": "Neg. Amortization!" if neg_amort_alerts else f"{av_months} mos ({_money(av_int)} int.)", "tone": "bad" if neg_amort_alerts else "neutral"},
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
        "recommendations": recs[:4],
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


def _status_points(status: str) -> float:
    st = (status or "").strip().lower()
    if st == "good":
        return 1.0
    if st == "partial":
        return 0.55
    return 0.0


def calc_protection(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    """Full Protection & Estate pillar audit (insurance + estate documents + emergency buffer)."""
    prot = plan.get("protection") or {}
    term_life = str(inputs.get("term_life_status") or "Good")
    disability = str(inputs.get("disability_status") or "Partial")
    health = str(inputs.get("health_status") or "Good")
    umbrella = str(inputs.get("umbrella_status") or "Partial")
    estate = str(inputs.get("estate_docs_status") or "Missing")
    ef_months = _f(inputs.get("emergency_fund_months"), _f(prot.get("emergency_fund_months"), 4.0))

    ef_status = "Good" if ef_months >= 6 else ("Partial" if ef_months >= 3 else "Missing")
    ef_ratio = _clamp(ef_months / 6.0, 0.0, 1.0)

    # Weighted 0-100 Protection score
    score = round(
        _clamp(
            _status_points(estate) * 25.0
            + _status_points(disability) * 20.0
            + _status_points(term_life) * 18.0
            + _status_points(health) * 15.0
            + _status_points(umbrella) * 10.0
            + ef_ratio * 12.0
        ),
        1,
    )

    rec_map = {
        "Term Life Insurance": {
            "Good": "Coverage in place — review every 3-5 years or after major life events.",
            "Partial": "Employer group life is rarely portable; price an individual 20-year term policy.",
            "Missing": "CRITICAL if dependents rely on your income — lock in 10-12x income term life.",
        },
        "Disability Insurance": {
            "Good": "Strong income protection in place.",
            "Partial": "Employer LTD often caps benefits or is taxable; evaluate supplemental own-occupation coverage.",
            "Missing": "HIGH PRIORITY — your earning power is your largest asset; secure long-term disability coverage.",
        },
        "Health Insurance": {
            "Good": "Maintain coverage and maximize HSA if enrolled in an HDHP.",
            "Partial": "Verify out-of-pocket maximum is covered by your emergency fund.",
            "Missing": "CRITICAL — obtain health coverage immediately to avoid catastrophic medical debt.",
        },
        "Auto / Home & Umbrella": {
            "Good": "Liability protection aligned with asset level.",
            "Partial": "Consider adding a $1M umbrella policy once net worth or income grows.",
            "Missing": "Add $1M+ umbrella liability insurance to protect accumulated net worth.",
        },
        "Will / Estate Plan": {
            "Good": "Documents current — review beneficiaries annually.",
            "Partial": "Complete formal will, durable POA, and healthcare directive.",
            "Missing": "CRITICAL — draft will, power of attorney, healthcare directive, and audit account beneficiaries.",
        },
    }

    items = [
        {"name": "Term Life Insurance", "status": term_life, "recommendation": rec_map["Term Life Insurance"].get(term_life, "Review coverage.")},
        {"name": "Disability Insurance", "status": disability, "recommendation": rec_map["Disability Insurance"].get(disability, "Review coverage.")},
        {"name": "Health Insurance", "status": health, "recommendation": rec_map["Health Insurance"].get(health, "Review coverage.")},
        {"name": "Auto / Home & Umbrella", "status": umbrella, "recommendation": rec_map["Auto / Home & Umbrella"].get(umbrella, "Review coverage.")},
        {"name": "Will / Estate Plan", "status": estate, "recommendation": rec_map["Will / Estate Plan"].get(estate, "Review documents.")},
        {
            "name": "Emergency Fund",
            "status": ef_status,
            "recommendation": f"{ef_months:.1f} months of essential expenses covered (target 6 months).",
        },
    ]

    gaps = [it["name"] for it in items if it["status"].lower() in ("missing", "partial")]
    recs = [f"{it['name']} ({it['status']}): {it['recommendation']}" for it in items if it["status"].lower() != "good"]
    if not recs:
        recs.append("All core insurance, estate, and liquidity protections are in strong shape — review annually.")

    commentary = (
        f"Top protection priorities: {', '.join(gaps[:3])}."
        if gaps
        else "Comprehensive protection across insurance, estate planning, and liquid reserves."
    )

    return {
        "module": "finance-protection",
        "score": score,
        "grade": score_grade(score),
        "summary": f"Protection & Estate Score: {score}/100 ({score_grade(score)}). " + (f"{len(gaps)} area(s) need attention: {', '.join(gaps[:3])}." if gaps else "All 6 protection areas covered."),
        "metrics": [
            {"label": "Protection Score", "value": f"{score}/100", "tone": "good" if score >= 75 else ("warn" if score >= 50 else "bad")},
            {"label": "Estate Docs", "value": estate, "tone": "good" if estate == "Good" else ("warn" if estate == "Partial" else "bad")},
            {"label": "Disability (LTD)", "value": disability, "tone": "good" if disability == "Good" else ("warn" if disability == "Partial" else "bad")},
            {"label": "Emergency Runway", "value": f"{ef_months:.1f} mos", "tone": "good" if ef_months >= 6 else ("warn" if ef_months >= 3 else "bad")},
        ],
        "tables": [
            {
                "title": "Protection & Estate Scorecard",
                "columns": ["Coverage Area", "Status", "Recommendation"],
                "rows": [[it["name"], it["status"], it["recommendation"]] for it in items],
            }
        ],
        "chart": {
            "type": "bars",
            "title": "Protection Coverage Readiness (%)",
            "items": [
                {"label": "Estate Docs", "value": round(_status_points(estate) * 100)},
                {"label": "Disability", "value": round(_status_points(disability) * 100)},
                {"label": "Term Life", "value": round(_status_points(term_life) * 100)},
                {"label": "Health", "value": round(_status_points(health) * 100)},
                {"label": "Umbrella", "value": round(_status_points(umbrella) * 100)},
                {"label": "Emergency", "value": round(ef_ratio * 100)},
            ],
        },
        "recommendations": recs[:4],
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "protection": score},
            "protection": {
                "emergency_fund_months": round(ef_months, 1),
                "items": items,
                "commentary": commentary,
            },
        },
    }
