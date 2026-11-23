"""Stage 3 calculators: Growth & Optimization (Portfolio Review & Model ETFs, Tax Optimization)."""

from __future__ import annotations

from typing import Any, Dict

try:
    from module_registry import get_module_constants
except ImportError:  # pragma: no cover - when imported as scripts.calculators.*
    from ..module_registry import get_module_constants

from .common import _clamp, _f, _gross_annual_income, _money, _pct, score_grade


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
    total_pct = us_stocks + intl_stocks + bonds + reits + cash
    alloc_valid = abs(total_pct - 100.0) <= 0.5

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
    sum_penalty = 0.0 if alloc_valid else min(20.0, abs(total_pct - 100.0) * 0.5)
    score = _clamp(95.0 - max_drift * 1.8 - max(0.0, (expense_ratio - 0.10) * 60.0) - sum_penalty)

    rows = []
    for a in alloc:
        diff = a["pct"] - a["target_pct"]
        trade = total_value * (-diff / 100.0)
        action = f"Buy {_money(trade)}" if trade > 50 else (f"Trim {_money(-trade)}" if trade < -50 else "On target")
        rows.append([a["name"], _pct(a["pct"]), _pct(a["target_pct"]), f"{'+' if diff >= 0 else ''}{diff:.1f}%", action])

    # Consolidated model ETF template table (previously standalone Investment Screener)
    template_key = str(inputs.get("model_template") or "3-fund").lower()
    strat = SCREEN_STRATEGIES.get(template_key, SCREEN_STRATEGIES["3-fund"])
    model_rows = []
    for ticker, desc, weight_str, er in strat["tickers"]:
        w = float(weight_str.replace("%", ""))
        model_rows.append([ticker, desc, weight_str, er, _money(total_value * w / 100.0)])

    recs = [
        "Rebalance any asset class drifting >5 percentage points from target using new contributions first to avoid capital gains.",
        f"Target weighted expense ratio <=0.10% (reference {strat['title']} avg ER: {strat['avg_er']}).",
        "Syncing this allocation automatically calibrates expected return and volatility in Stage 4 Monte Carlo simulations.",
    ]
    if not alloc_valid:
        recs.insert(0, f"Allocation inputs sum to {total_pct:.1f}% instead of 100.0% — adjust weights so rebalancing trades balance.")

    return {
        "module": "finance-portfolio",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": (
            f"Portfolio {_money(total_value)} — max drift {max_drift:.1f}pp, weighted ER {_pct(expense_ratio, 2)} ({_money(annual_fee)}/yr). "
            f"Reference model: {strat['title']} ({strat['expected_return']})."
            + ("" if alloc_valid else f" Warning: weights sum to {total_pct:.1f}% (expected 100%).")
        ),
        "metrics": [
            {"label": "Portfolio Value", "value": _money(total_value), "tone": "neutral"},
            {"label": "Allocation Sum", "value": _pct(total_pct), "tone": "good" if alloc_valid else "bad"},
            {"label": "Max Drift", "value": f"{max_drift:.1f} pp", "tone": "good" if max_drift <= 5 else "warn"},
            {"label": "Avg Expense Ratio", "value": _pct(expense_ratio, 2), "tone": "good" if expense_ratio <= 0.15 else "bad"},
            {"label": "Annual Fee Drag", "value": _money(annual_fee), "tone": "good" if expense_ratio <= 0.15 else "warn"},
        ],
        "tables": [
            {"title": "Allocation & Rebalancing Trades", "columns": ["Asset Class", "Current", "Target", "Drift", "Trade"], "rows": rows},
            {
                "title": f"Reference Model Template: {strat['title']} ({strat['expected_return']}, avg ER {strat['avg_er']})",
                "columns": ["Ticker", "Asset Role", "Weight", "ER", "Model Allocation"],
                "rows": model_rows,
            },
        ],
        "chart": {
            "type": "donut",
            "title": "Current Asset Allocation (%)",
            "items": [{"label": a["name"], "value": a["pct"]} for a in alloc if a["pct"] > 0],
        },
        "recommendations": recs,
        "plan_patch": {
            "categories": {**(plan.get("categories") or {}), "investments": round(score, 1)},
            "investments": {"total_value": total_value, "allocation": alloc},
        },
    }


def calc_taxes(inputs: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    cf = plan.get("cash_flow") or {}
    ret = plan.get("retirement") or {}
    filing_status = str(inputs.get("filing_status") or "single").lower()
    is_married = filing_status == "married"
    age = int(_f(inputs.get("age"), _f(ret.get("current_age"), 38)))
    gross_income = _f(inputs.get("gross_annual_income"), _gross_annual_income(plan))
    marginal_rate_pct = _f(inputs.get("marginal_tax_rate"), 24.0)
    marginal_rate = marginal_rate_pct / 100.0
    cur_401k = _f(inputs.get("current_401k"), 11000)
    cur_hsa = _f(inputs.get("current_hsa"), 0)
    cur_ira = _f(inputs.get("current_ira"), 0)
    hsa_eligible = bool(inputs.get("hsa_eligible", True))
    family_hsa = bool(inputs.get("family_hsa", False))
    harvestable_losses = _f(inputs.get("harvestable_losses"), 0)

    consts = get_module_constants("finance-taxes")
    limit_401k = float(consts.get("limit_401k", 23500.0)) + (float(consts.get("catchup_401k_50", 7500.0)) if age >= 50 else 0.0)
    base_hsa = float(consts.get("limit_hsa_family", 8550.0)) if family_hsa else float(consts.get("limit_hsa_single", 4300.0))
    limit_hsa = (base_hsa + (float(consts.get("catchup_hsa_55", 1000.0)) if age >= 55 else 0.0)) if hsa_eligible else 0.0
    single_ira_limit = float(consts.get("limit_ira", 7000.0)) + (float(consts.get("catchup_ira_50", 1000.0)) if age >= 50 else 0.0)
    limit_ira = single_ira_limit * (2.0 if is_married else 1.0)

    rem_401k = max(0.0, limit_401k - cur_401k)
    rem_hsa = max(0.0, limit_hsa - cur_hsa)
    rem_ira = max(0.0, limit_ira - cur_ira)
    tlh_ded = min(float(consts.get("tlh_ordinary_cap", 3000.0)), max(0.0, harvestable_losses))

    save_401k = rem_401k * marginal_rate
    save_hsa = rem_hsa * (marginal_rate + float(consts.get("fica_rate", 0.0765)))
    save_tlh = tlh_ded * marginal_rate
    total_savings = save_401k + save_hsa + save_tlh

    used_total = cur_401k + cur_hsa + cur_ira
    avail_total = limit_401k + limit_hsa + limit_ira
    # Score against realistic savings capacity (~22% of gross income) rather than full statutory max for moderate earners
    realistic_cap = min(avail_total, max(limit_hsa + 3000.0, gross_income * 0.22)) if gross_income > 0 else avail_total
    score = _clamp((used_total / realistic_cap * 100.0) if realistic_cap > 0 else 80.0)

    recs = [
        f"Prioritize HSA ({_money(rem_hsa)} remaining) and 401(k) ({_money(rem_401k)} remaining) to capture {_money(save_401k + save_hsa)}/yr.",
    ]
    if marginal_rate_pct <= 12.0:
        recs.append("At <=12% marginal bracket, favor Roth 401(k)/Roth IRA contributions to lock in historically low tax rates.")
    else:
        recs.append(f"At {marginal_rate_pct:.0f}% marginal bracket, pre-tax Traditional 401(k) + HSA generally maximize immediate tax leverage.")
    if is_married:
        recs.append(f"Married Filing Jointly doubles combined IRA space to {_money(limit_ira)} (including spousal IRA if one spouse has lower/no earned income).")
    recs.append("Consult a CPA before executing Roth conversions or Backdoor Roth (watch the pro-rata rule).")

    return {
        "module": "finance-taxes",
        "score": round(score, 1),
        "grade": score_grade(score),
        "summary": (
            f"Estimated {_money(total_savings)}/yr in untapped tax savings ({'Married Filing Jointly' if is_married else 'Single'}, "
            f"{_pct(marginal_rate_pct, 0)} bracket on {_money(gross_income)} gross income)."
        ),
        "metrics": [
            {"label": "Gross Annual Income", "value": _money(gross_income), "tone": "neutral"},
            {"label": "Est. Annual Tax Savings", "value": _money(total_savings), "tone": "good"},
            {"label": "Unused 401(k) Space", "value": _money(rem_401k), "tone": "warn" if rem_401k > 0 else "good"},
            {"label": "Unused IRA Space", "value": _money(rem_ira), "tone": "warn" if rem_ira > 0 else "good"},
        ],
        "tables": [
            {
                "title": "Tax-Advantaged Optimization Opportunities",
                "columns": ["Strategy", "Current", "Annual Limit", "Remaining", "Est. Tax Saved"],
                "rows": [
                    ["Traditional 401(k)", _money(cur_401k), _money(limit_401k), _money(rem_401k), _money(save_401k)],
                    ["HSA (Triple Tax-Free)", _money(cur_hsa), _money(limit_hsa), _money(rem_hsa), _money(save_hsa)],
                    ["IRA / Backdoor Roth" + (" (Joint)" if is_married else ""), _money(cur_ira), _money(limit_ira), _money(rem_ira), "Tax-free growth"],
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
        "recommendations": recs,
        "plan_patch": {"cash_flow": {**cf, "gross_annual_income": gross_income}},
    }
