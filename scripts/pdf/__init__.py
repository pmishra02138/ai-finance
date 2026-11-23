"""Modular ReportLab PDF generation package for AI Personal Finance Advisor."""

from __future__ import annotations

try:
    from scoring import score_grade, score_signal
except ImportError:  # pragma: no cover - when imported as scripts.pdf
    from ..scoring import score_grade, score_signal

from .demo_data import _demo_data
from .pages import (
    build_90_day_plan,
    build_action_items,
    build_cash_flow,
    build_cover,
    build_debt_summary,
    build_investments,
    build_pdf,
    build_protection,
    build_retirement,
    build_score_dashboard,
)

__all__ = [
    "build_pdf",
    "_demo_data",
    "score_grade",
    "score_signal",
    "build_cover",
    "build_score_dashboard",
    "build_cash_flow",
    "build_debt_summary",
    "build_investments",
    "build_retirement",
    "build_protection",
    "build_action_items",
    "build_90_day_plan",
]
