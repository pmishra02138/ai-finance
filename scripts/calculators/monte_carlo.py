"""Pure-stdlib Monte Carlo simulation engine for long-horizon financial modeling.

Uses a fixed seed by default for deterministic reproducibility across repeated runs,
executing 1,000 trials in ~15-25 ms with zero external dependencies.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List


def _percentile(sorted_vals: List[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def _annual_return(rng: random.Random, mean: float, vol: float) -> float:
    if vol <= 0:
        return mean
    # Clamp extreme left tail to -65% single-year crash to prevent nonsensical negative factors
    return max(-0.65, rng.gauss(mean, vol))


def simulate_retirement_mc(
    current_balance: float,
    monthly_contribution: float,
    years_to_retire: int,
    annual_withdrawal: float,
    drawdown_years: int = 30,
    accum_return: float = 0.06,
    accum_vol: float = 0.14,
    retire_return: float = 0.045,
    retire_vol: float = 0.10,
    trials: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Simulate accumulation to retirement followed by a multi-decade drawdown phase."""
    rng = random.Random(seed)
    annual_contrib = max(0.0, monthly_contribution * 12.0)
    accum_yrs = max(0, int(years_to_retire))
    draw_yrs = max(1, int(drawdown_years))
    n = max(100, int(trials))

    retire_balances: List[float] = []
    ending_balances: List[float] = []
    successes = 0

    for _ in range(n):
        bal = max(0.0, current_balance)
        for _y in range(accum_yrs):
            r = _annual_return(rng, accum_return, accum_vol)
            bal = max(0.0, bal * (1.0 + r) + annual_contrib)
        retire_balances.append(bal)

        survived = True
        for _y in range(draw_yrs):
            r = _annual_return(rng, retire_return, retire_vol)
            bal = bal * (1.0 + r) - annual_withdrawal
            if bal <= 0.0:
                bal = 0.0
                survived = False
                break
        if survived:
            successes += 1
        ending_balances.append(bal)

    retire_balances.sort()
    ending_balances.sort()
    return {
        "trials": n,
        "drawdown_years": draw_yrs,
        "volatility_pct": round(accum_vol * 100.0, 1),
        "success_rate_pct": round(successes / n * 100.0, 1),
        "retire_p10": round(_percentile(retire_balances, 10)),
        "retire_p50": round(_percentile(retire_balances, 50)),
        "retire_p90": round(_percentile(retire_balances, 90)),
        "ending_p10": round(_percentile(ending_balances, 10)),
        "ending_p50": round(_percentile(ending_balances, 50)),
        "ending_p90": round(_percentile(ending_balances, 90)),
    }


def simulate_fire_mc(
    fi_target: float,
    annual_expenses: float,
    drawdown_years: int = 40,
    real_return: float = 0.06,
    volatility: float = 0.14,
    trials: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Stress-test a FIRE portfolio across an extended early-retirement drawdown horizon."""
    rng = random.Random(seed)
    n = max(100, int(trials))
    draw_yrs = max(1, int(drawdown_years))

    ending_balances: List[float] = []
    successes = 0

    for _ in range(n):
        bal = max(0.0, fi_target)
        survived = True
        for _y in range(draw_yrs):
            r = _annual_return(rng, real_return, volatility)
            bal = bal * (1.0 + r) - annual_expenses
            if bal <= 0.0:
                bal = 0.0
                survived = False
                break
        if survived:
            successes += 1
        ending_balances.append(bal)

    ending_balances.sort()
    return {
        "trials": n,
        "drawdown_years": draw_yrs,
        "volatility_pct": round(volatility * 100.0, 1),
        "success_rate_pct": round(successes / n * 100.0, 1),
        "ending_p10": round(_percentile(ending_balances, 10)),
        "ending_p50": round(_percentile(ending_balances, 50)),
        "ending_p90": round(_percentile(ending_balances, 90)),
    }


def simulate_goal_mc(
    current_saved: float,
    monthly_contribution: float,
    years: float,
    target_amount: float,
    expected_return: float,
    volatility: float,
    trials: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Simulate ending value of a goal funding plan under market volatility."""
    rng = random.Random(seed)
    n = max(100, int(trials))
    whole_years = int(years)
    rem_frac = max(0.0, years - whole_years)
    annual_contrib = max(0.0, monthly_contribution * 12.0)

    endings: List[float] = []
    hits = 0

    for _ in range(n):
        bal = max(0.0, current_saved)
        for _y in range(whole_years):
            r = _annual_return(rng, expected_return, volatility)
            bal = max(0.0, bal * (1.0 + r) + annual_contrib)
        if rem_frac > 1e-6:
            r = _annual_return(rng, expected_return * rem_frac, volatility * (rem_frac ** 0.5))
            bal = max(0.0, bal * (1.0 + r) + annual_contrib * rem_frac)
        if bal >= target_amount - 1.0:
            hits += 1
        endings.append(bal)

    endings.sort()
    return {
        "trials": n,
        "volatility_pct": round(volatility * 100.0, 1),
        "success_rate_pct": round(hits / n * 100.0, 1),
        "p10": round(_percentile(endings, 10)),
        "p50": round(_percentile(endings, 50)),
        "p90": round(_percentile(endings, 90)),
    }


def simulate_compare_mc(
    diff_upfront_a: float,
    monthly_invest_a: float,
    total_cost_a: float,
    diff_upfront_b: float,
    monthly_invest_b: float,
    total_cost_b: float,
    years: int,
    expected_return: float,
    volatility: float = 0.14,
    trials: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare two scenarios across shared randomized market paths."""
    rng = random.Random(seed)
    n = max(100, int(trials))
    yrs = max(1, int(years))
    ann_a = max(0.0, monthly_invest_a * 12.0)
    ann_b = max(0.0, monthly_invest_b * 12.0)

    fvs_a: List[float] = []
    fvs_b: List[float] = []
    a_wins = 0

    for _ in range(n):
        bal_a = max(0.0, diff_upfront_a)
        bal_b = max(0.0, diff_upfront_b)
        for _y in range(yrs):
            # Shared market return per year so both scenarios experience the same market path
            r = _annual_return(rng, expected_return, volatility)
            bal_a = max(0.0, bal_a * (1.0 + r) + ann_a)
            bal_b = max(0.0, bal_b * (1.0 + r) + ann_b)
        fvs_a.append(bal_a)
        fvs_b.append(bal_b)
        if (bal_a - total_cost_a) >= (bal_b - total_cost_b):
            a_wins += 1

    fvs_a.sort()
    fvs_b.sort()
    a_win_pct = round(a_wins / n * 100.0, 1)
    return {
        "trials": n,
        "volatility_pct": round(volatility * 100.0, 1),
        "a_win_rate_pct": a_win_pct,
        "b_win_rate_pct": round(100.0 - a_win_pct, 1),
        "fv_a_p10": round(_percentile(fvs_a, 10)),
        "fv_a_p50": round(_percentile(fvs_a, 50)),
        "fv_a_p90": round(_percentile(fvs_a, 90)),
        "fv_b_p10": round(_percentile(fvs_b, 10)),
        "fv_b_p50": round(_percentile(fvs_b, 50)),
        "fv_b_p90": round(_percentile(fvs_b, 90)),
    }
