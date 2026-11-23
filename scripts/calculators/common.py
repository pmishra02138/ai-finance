"""Shared numeric, formatting, compounding, and income/allocation helpers."""

from __future__ import annotations

from typing import Any, Dict, Tuple

try:
    from scoring import score_grade, score_signal
except ImportError:  # pragma: no cover - when imported as scripts.calculators.*
    from ..scoring import score_grade, score_signal


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


def _gross_annual_income(plan: Dict[str, Any], default: float = 145000.0) -> float:
    """Resolve pre-tax gross annual income cleanly from cash_flow (separate from net take-home)."""
    cf = plan.get("cash_flow") or {}
    if cf.get("gross_annual_income") is not None:
        return _f(cf.get("gross_annual_income"), default)
    monthly_net = _f(cf.get("monthly_income"), 0.0)
    if monthly_net > 0:
        # Estimate gross from net take-home assuming ~24% effective tax/deductions
        return round(monthly_net * 12.0 / 0.76, 0)
    return default


def _portfolio_return_vol(
    plan: Dict[str, Any],
    default_return: float = 0.06,
    default_vol: float = 0.14,
) -> Tuple[float, float, float]:
    """Derive expected real return and annual volatility from synced portfolio equity share.

    Returns (expected_real_return, annual_volatility, equity_pct).
    """
    inv = plan.get("investments") or {}
    alloc = inv.get("allocation") or []
    if not alloc:
        return default_return, default_vol, 75.0

    total_pct = sum(max(0.0, _f(a.get("pct"))) for a in alloc)
    if total_pct <= 0:
        return default_return, default_vol, 75.0

    equity_raw = 0.0
    for a in alloc:
        name = str(a.get("name") or "").lower()
        if any(k in name for k in ("stock", "equit", "reit", "real estate")):
            equity_raw += max(0.0, _f(a.get("pct")))
    eq_frac = _clamp(equity_raw / total_pct, 0.0, 1.0)
    # 0% equity (all bonds/cash) -> ~3.0% real return, 4.5% vol
    # 100% equity -> ~7.5% real return, 17.0% vol
    exp_return = round(0.030 + 0.045 * eq_frac, 4)
    exp_vol = round(0.045 + 0.125 * eq_frac, 4)
    return exp_return, exp_vol, round(eq_frac * 100.0, 1)


__all__ = [
    "_f",
    "_clamp",
    "_money",
    "_pct",
    "_fv_monthly",
    "_gross_annual_income",
    "_portfolio_return_vol",
    "score_grade",
    "score_signal",
]
