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
            self.assertNotIn(".md", sk["description"].lower())
            self.assertNotIn("subagent", sk["description"].lower())
            self.assertNotIn("/finance", sk["description"].lower())

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

    def test_budget_preserves_detailed_expenses_and_taxes_catchup_and_portfolio_sum(self) -> None:
        demo = _demo_data()
        budget_res = run_skill("finance-budget", {"monthly_income": 9200, "monthly_needs": 4600, "monthly_wants": 1600}, demo)
        self.assertEqual(len(budget_res["plan_patch"]["cash_flow"]["expenses"]), len(demo["cash_flow"]["expenses"]))
        self.assertIn("budget_50_30_20", budget_res["plan_patch"]["cash_flow"])

        tax_res = run_skill("finance-taxes", {"age": 56, "current_401k": 0, "current_hsa": 0, "current_ira": 0}, demo)
        rows = {r[0]: r[2] for r in tax_res["tables"][0]["rows"]}
        self.assertEqual(rows["Traditional 401(k)"], "$31,000")
        self.assertEqual(rows["HSA (Triple Tax-Free)"], "$5,300")
        self.assertEqual(rows["IRA / Backdoor Roth"], "$8,000")

        port_res = run_skill("finance-portfolio", {"us_stocks_pct": 50, "intl_stocks_pct": 10, "bonds_pct": 10, "reits_pct": 0, "cash_pct": 0}, demo)
        self.assertIn("sum to 70.0%", port_res["summary"])

    def test_modular_package_exports_and_scoring_consistency(self) -> None:
        from calculators import baseline, foundation, growth, horizons, synthesis
        from generate_finance_pdf import _demo_data as shim_demo
        from generate_finance_pdf import score_grade as shim_grade
        from generate_finance_pdf import score_signal as shim_signal
        from pdf.demo_data import _demo_data as pkg_demo
        from scoring import score_grade, score_signal

        self.assertIs(shim_grade, score_grade)
        self.assertIs(shim_signal, score_signal)
        self.assertEqual(shim_demo()["client_name"], pkg_demo()["client_name"])
        self.assertIs(CALCULATORS["finance-quick"], baseline.calc_quick)
        self.assertIs(CALCULATORS["finance-debt"], foundation.calc_debt)
        self.assertIs(CALCULATORS["finance-portfolio"], growth.calc_portfolio)
        self.assertIs(CALCULATORS["finance-retirement"], horizons.calc_retirement)
        self.assertIs(CALCULATORS["finance-analyze"], synthesis.calc_analyze)


if __name__ == "__main__":
    unittest.main()
