#!/usr/bin/env python3
"""Unit tests for all 14 deterministic financial calculators and the skill registry."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from calculators import CALCULATORS, run_skill
from generate_finance_pdf import _demo_data
from skill_registry import VALID_SKILL_NAMES, get_skills_catalog


class TestSkillRegistryAndCalculators(unittest.TestCase):
    def test_catalog_has_all_14_skills_in_5_stages(self) -> None:
        cat = get_skills_catalog()
        self.assertEqual(len(cat["stages"]), 5)
        self.assertEqual(cat["total_skills"], 14)
        self.assertEqual(set(CALCULATORS.keys()), VALID_SKILL_NAMES)
        for sk in cat["skills"]:
            self.assertTrue(sk["description"], f"Missing description for {sk['name']}")

    def test_all_14_skills_run_with_demo_plan(self) -> None:
        demo = _demo_data()
        for skill_name in VALID_SKILL_NAMES:
            res = run_skill(skill_name, {}, demo)
            self.assertEqual(res["skill"], skill_name)
            self.assertIn("summary", res)
            self.assertIn("metrics", res)
            self.assertIn("recommendations", res)

    def test_avalanche_beats_or_equals_snowball_interest(self) -> None:
        accounts = [
            {"name": "High APR Card", "balance": 10000, "apr": 24.0, "min_payment": 250},
            {"name": "Low APR Loan", "balance": 3000, "apr": 5.0, "min_payment": 100},
        ]
        res = run_skill("finance-debt", {"accounts": accounts, "extra_monthly_payment": 300}, {})
        av_int = res["chart"]["items"][0]["value"]
        sn_int = res["chart"]["items"][1]["value"]
        self.assertLess(av_int, sn_int)

    def test_edge_cases_zero_debt_zero_income_zero_apr(self) -> None:
        # Zero debt
        debt_res = run_skill("finance-debt", {"accounts": [], "extra_monthly_payment": 0}, {})
        self.assertEqual(debt_res["score"], 100.0)

        # Zero APR debt
        zero_apr = run_skill(
            "finance-debt",
            {"accounts": [{"name": "0% Promo", "balance": 1200, "apr": 0.0, "min_payment": 100}], "extra_monthly_payment": 0},
            {},
        )
        self.assertEqual(zero_apr["chart"]["items"][0]["value"], 0.0)

        # Zero income in quick & budget (no ZeroDivisionError)
        quick_res = run_skill("finance-quick", {"monthly_income": 0, "monthly_expenses": 0, "total_savings": 0, "total_debt": 0}, {})
        self.assertIsNotNone(quick_res["score"])
        budget_res = run_skill("finance-budget", {"monthly_income": 0, "monthly_needs": 0, "monthly_wants": 0}, {})
        self.assertIsNotNone(budget_res["score"])

        # Over-funded retirement
        ret_res = run_skill(
            "finance-retirement",
            {"current_age": 50, "retirement_age": 65, "current_balance": 2_000_000, "monthly_contribution": 0, "desired_annual_spending": 50000},
            {},
        )
        self.assertEqual(ret_res["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
