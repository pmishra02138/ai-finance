#!/usr/bin/env python3
"""
Dynamic skill registry for AI Personal Finance Advisor.

Reads YAML frontmatter from skills/finance-*/SKILL.md and organizes all 14
skills into the 5-stage guided planning sequence.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"

STAGES: List[Dict[str, Any]] = [
    {
        "id": "baseline",
        "title": "1. Baseline & Triage",
        "subtitle": "Capture where you stand today",
        "skills": [
            {"name": "finance-quick", "label": "Quick Snapshot"},
            {"name": "finance-networth", "label": "Net Worth Tracker"},
        ],
    },
    {
        "id": "foundation",
        "title": "2. Foundation & Defense",
        "subtitle": "Optimize cash flow, safety net, and debt",
        "skills": [
            {"name": "finance-budget", "label": "Budget & Cash Flow"},
            {"name": "finance-emergency", "label": "Emergency Fund"},
            {"name": "finance-debt", "label": "Debt Payoff"},
        ],
    },
    {
        "id": "growth",
        "title": "3. Growth & Optimization",
        "subtitle": "Portfolio allocation, screening, and taxes",
        "skills": [
            {"name": "finance-portfolio", "label": "Portfolio Review"},
            {"name": "finance-screen", "label": "Investment Screener"},
            {"name": "finance-taxes", "label": "Tax Optimization"},
        ],
    },
    {
        "id": "horizons",
        "title": "4. Horizons & Trade-Offs",
        "subtitle": "Retirement, FIRE, goals, and comparisons",
        "skills": [
            {"name": "finance-retirement", "label": "Retirement Planner"},
            {"name": "finance-fire", "label": "FIRE Calculator"},
            {"name": "finance-goals", "label": "Goal Planner"},
            {"name": "finance-compare", "label": "Scenario Compare"},
        ],
    },
    {
        "id": "synthesis",
        "title": "5. Synthesis & Export",
        "subtitle": "Full 5-pillar score and client-ready PDF",
        "skills": [
            {"name": "finance-analyze", "label": "Full Health Analysis"},
            {"name": "finance-report-pdf", "label": "PDF Report Export"},
        ],
    },
]

VALID_SKILL_NAMES = {s["name"] for stage in STAGES for s in stage["skills"]}


def _parse_frontmatter(skill_md: Path) -> Dict[str, str]:
    if not skill_md.is_file():
        return {}
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = parts[1]
    out: Dict[str, str] = {}
    m_name = re.search(r"(?m)^name:\s*(.+)$", fm)
    m_desc = re.search(r"(?m)^description:\s*(.+)$", fm)
    if m_name:
        out["name"] = m_name.group(1).strip().strip('"').strip("'")
    if m_desc:
        out["description"] = m_desc.group(1).strip().strip('"').strip("'")
    return out


def get_skills_catalog() -> Dict[str, Any]:
    """Return the 5 stages with all 14 skills enriched from skills/*/SKILL.md."""
    stages_out: List[Dict[str, Any]] = []
    flat_skills: List[Dict[str, Any]] = []

    for stage in STAGES:
        enriched_skills: List[Dict[str, Any]] = []
        for item in stage["skills"]:
            skill_name = item["name"]
            meta = _parse_frontmatter(SKILLS_DIR / skill_name / "SKILL.md")
            entry = {
                "name": skill_name,
                "label": item["label"],
                "stage_id": stage["id"],
                "stage_title": stage["title"],
                "description": meta.get("description", ""),
            }
            enriched_skills.append(entry)
            flat_skills.append(entry)
        stages_out.append(
            {
                "id": stage["id"],
                "title": stage["title"],
                "subtitle": stage["subtitle"],
                "skills": enriched_skills,
            }
        )

    return {"stages": stages_out, "skills": flat_skills, "total_skills": len(flat_skills)}
