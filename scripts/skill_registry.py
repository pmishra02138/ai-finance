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

USER_DESCRIPTIONS: Dict[str, str] = {
    "finance-quick": "Get a fast 60-second financial health check from your income, expenses, savings, debt, and retirement age.",
    "finance-networth": "Calculate your total assets, liabilities, and net worth, and track progress toward your next wealth milestone.",
    "finance-budget": "Analyze your monthly income and spending using the 50/30/20 framework to find extra savings.",
    "finance-emergency": "Determine your ideal emergency fund target in months of expenses and see how fast you can build it.",
    "finance-debt": "Compare Avalanche vs. Snowball payoff strategies to see how quickly you can become debt-free and how much interest you save.",
    "finance-portfolio": "Review your investment mix against age-based targets, spot allocation drift, and calculate exact rebalancing trades.",
    "finance-screen": "Explore model ETF and index strategies (3-Fund, Dividend Growth, Bonds, REITs, or ESG) tailored to your investment amount.",
    "finance-taxes": "Estimate annual tax savings from 401(k), HSA, IRA, and tax-loss harvesting opportunities—including age 50+ catch-up limits.",
    "finance-retirement": "Project your retirement nest egg across conservative, moderate, and aggressive return scenarios and measure any savings gap.",
    "finance-fire": "Calculate your Lean, Regular, Fat, and Coast Financial Independence numbers and estimate years to early retirement.",
    "finance-goals": "Plan major milestones like a home down payment, college fund, or sabbatical with required monthly savings and timelines.",
    "finance-compare": "Compare two financial choices side-by-side over time (such as renting vs. buying) including opportunity cost.",
    "finance-analyze": "Combine all five financial pillars into a composite Financial Health Score (0–100), grade, and top priority focus.",
    "finance-report-pdf": "Review your synced plan readiness and export a polished 9-page PDF financial report.",
}


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
                "description": USER_DESCRIPTIONS.get(skill_name) or meta.get("description", ""),
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
