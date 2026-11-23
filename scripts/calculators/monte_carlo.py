"""Pure-stdlib log-normal Monte Carlo simulation engine for long-horizon financial modeling.

Uses log-normal return compounding to avoid arithmetic-mean drift over 30-40 year horizons,
with a fixed seed by default for reproducible results (~15-25 ms for 1,000 trials).
"""

from __future__ import annotations

import math
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


def _lognormal_return(rng: random.Random, mean: float, vol: float) -> float:
    """Draw a log-normal annual return with expected growth ~mean and volatility ~vol."""
    if vol <= 0:
        return mean
    # Log-normal drift adjustment: E[exp((mu - 0.5*sigma^2) + sigma*Z)] = exp(mu)
    mu = math.log(max(0.05, 1.0 + mean))
    z = rng.gauss(0.0, 1.0)
    r = math.exp((mu - 0.5 * vol * vol) + vol * z) - 1.0
    return max(-0.65, r)


def simulate_retirement_mc(
    current_balance: float,
    monthly_contribution: float,
    years_to_retire: int,
    retirement_age: int,
    annual_gross_spending: float,
    social_security_annual: float = 0.0,
    social_security_start_age: int = 67,
    drawdown_years: int = 30,
    accum_return: float = 0.06,
    accum_vol: float = 0.14,
    retire_return: float = 0.045,
    retire_vol: float = 0.10,
    trials: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Simulate log-normal accumulation to retirement followed by age-aware drawdown."""
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
            r = _lognormal_return(rng, accum_return, accum_vol)
            bal = max(0.0, bal * (1.0 + r) + annual_contrib)
        retire_balances.append(bal)

        survived = True
        for y in range(draw_yrs):
            cur_age = retirement_age + y
            ss = social_security_annual if cur_age >= social_security_start_age else 0.0
            withdrawal = max(0.0, annual_gross_spending - ss)
            r = _lognormal_return(rng, retire_return, retire_vol)
            bal = bal * (1.0 + r) - withdrawal
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
    annual_gross_withdrawal: float,
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
            r = _lognormal_return(rng, real_return, volatility)
            bal = bal * (1.0 + r) - annual_gross_withdrawal
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
    """Simulate ending value of a goal funding plan under log-normal market volatility."""
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
            r = _lognormal_return(rng, expected_return, volatility)
            bal = max(0.0, bal * (1.0 + r) + annual_contrib)
        if rem_frac > 1e-6:
            r = _lognormal_return(rng, expected_return * rem_frac, volatility * (rem_frac ** 0.5))
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
    ending_asset_a: float,
    diff_upfront_b: float,
    monthly_invest_b: float,
    total_cost_b: float,
    ending_asset_b: float,
    years: int,
    expected_return: float,
    volatility: float = 0.14,
    trials: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare two scenarios (including ending asset equity) across shared log-normal paths."""
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
            r = _lognormal_return(rng, expected_return, volatility)
            bal_a = max(0.0, bal_a * (1.0 + r) + ann_a)
            bal_b = max(0.0, bal_b * (1.0 + r) + ann_b)
        fvs_a.append(bal_a)
        fvs_b.append(bal_b)
        net_a = bal_a + ending_asset_a - total_cost_a
        net_b = bal_b + ending_asset_b - total_cost_b
        if net_a >= net_b:
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
