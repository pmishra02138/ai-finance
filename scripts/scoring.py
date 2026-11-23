#!/usr/bin/env python3
"""Shared Financial Health Score grading and signal helpers (pure stdlib)."""

from __future__ import annotations


def score_grade(score: float) -> str:
    """Convert a 0-100 composite or category score into a letter grade."""
    if score >= 90:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 80:
        return "A-"
    if score >= 75:
        return "B+"
    if score >= 70:
        return "B"
    if score >= 65:
        return "B-"
    if score >= 60:
        return "C+"
    if score >= 55:
        return "C"
    if score >= 50:
        return "C-"
    if score >= 45:
        return "D+"
    if score >= 40:
        return "D"
    return "F"


def score_signal(score: float) -> str:
    """Convert a 0-100 score into a plain-English status signal."""
    if score >= 80:
        return "Excellent — On Track"
    if score >= 65:
        return "Healthy — Minor Tune-Up"
    if score >= 50:
        return "Fair — Action Needed"
    if score >= 35:
        return "Weak — Plan Required"
    return "Critical — Immediate Action"
