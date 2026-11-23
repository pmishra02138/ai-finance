"""Shared numeric, formatting, and compounding helpers for financial calculators."""

from __future__ import annotations

from typing import Any

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


__all__ = [
    "_f",
    "_clamp",
    "_money",
    "_pct",
    "_fv_monthly",
    "score_grade",
    "score_signal",
]
