#!/usr/bin/env python3
"""Unit tests for all 14 financial calculators, Monte Carlo simulations, and the module registry."""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from calculators import CALCULATORS, run_module
from generate_finance_pdf import _demo_data
from module_registry import VALID_MODULE_NAMES, get_modules_catalog


class TestModuleRegistryAndCalculators(unittest.TestCase):
    def test_catalog_has_all_14_modules_in_5_stages(self) -> None:
        cat = get_modules_catalog()
        self.assertEqual(len(cat["stages"]), 5)
        self.assertEqual(cat["total_modules"], 14)
        self.assertEqual(set(CALCULATORS.keys()), VALID_MODULE_NAMES)
        for mod in cat["modules"]:
            self.assertTrue(mod["description"], f"Missing description for {mod['name']}")
            self.assertNotIn(".md", mod["description"].lower())
            self.assertNotIn("subagent", mod["description"].lower())
            self.assertNotIn("/finance", mod["description"].lower())

    def test_all_14_modules_run_with_demo_plan(self) -> None:
        demo = _demo_data()
        for module_name in VALID_MODULE_NAMES:
            res = run_module(module_name, {}, demo)
            self.assertEqual(res["module"], module_name)
            self.assertIn("summary", res)
            self.assertIn("metrics", res)
            self.assertIn("recommendations", res)

    def test_avalanche_beats_or_equals_snowball_interest(self) -> None:
        accounts = [
            {"name": "High APR Card", "balance": 10000, "apr": 24.0, "min_payment": 250},
            {"name": "Low APR Loan", "balance": 3000, "apr": 5.0, "min_payment": 100},
        ]
        res = run_module("finance-debt", {"accounts": accounts, "extra_monthly_payment": 300}, {})
        av_int = res["chart"]["items"][0]["value"]
        sn_int = res["chart"]["items"][1]["value"]
        self.assertLess(av_int, sn_int)

    def test_edge_cases_zero_debt_zero_income_zero_apr(self) -> None:
        debt_res = run_module("finance-debt", {"accounts": [], "extra_monthly_payment": 0}, {})
        self.assertEqual(debt_res["score"], 100.0)

        zero_apr = run_module(
            "finance-debt",
            {"accounts": [{"name": "0% Promo", "balance": 1200, "apr": 0.0, "min_payment": 100}], "extra_monthly_payment": 0},
            {},
        )
        self.assertEqual(zero_apr["chart"]["items"][0]["value"], 0.0)

        quick_res = run_module("finance-quick", {"monthly_income": 0, "monthly_expenses": 0, "total_savings": 0, "total_debt": 0}, {})
        self.assertIsNotNone(quick_res["score"])
        budget_res = run_module("finance-budget", {"monthly_income": 0, "monthly_needs": 0, "monthly_wants": 0}, {})
        self.assertIsNotNone(budget_res["score"])

        ret_res = run_module(
            "finance-retirement",
            {"current_age": 50, "retirement_age": 65, "current_balance": 2_000_000, "monthly_contribution": 0, "desired_annual_spending": 50000},
            {},
        )
        self.assertEqual(ret_res["score"], 100.0)

    def test_budget_preserves_detailed_expenses_and_taxes_catchup_and_portfolio_sum(self) -> None:
        demo = _demo_data()
        budget_res = run_module("finance-budget", {"monthly_income": 9200, "monthly_needs": 4600, "monthly_wants": 1600}, demo)
        self.assertEqual(len(budget_res["plan_patch"]["cash_flow"]["expenses"]), len(demo["cash_flow"]["expenses"]))
        self.assertIn("budget_50_30_20", budget_res["plan_patch"]["cash_flow"])

        tax_res = run_module("finance-taxes", {"age": 56, "current_401k": 0, "current_hsa": 0, "current_ira": 0}, demo)
        rows = {r[0]: r[2] for r in tax_res["tables"][0]["rows"]}
        self.assertEqual(rows["Traditional 401(k)"], "$31,000")
        self.assertEqual(rows["HSA (Triple Tax-Free)"], "$5,300")
        self.assertEqual(rows["IRA / Backdoor Roth"], "$8,000")

        port_res = run_module("finance-portfolio", {"us_stocks_pct": 50, "intl_stocks_pct": 10, "bonds_pct": 10, "reits_pct": 0, "cash_pct": 0}, demo)
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

    def test_monte_carlo_stage4_reproducibility_percentiles_and_speed(self) -> None:
        demo = _demo_data()
        mc_modules = ("finance-retirement", "finance-fire", "finance-goals", "finance-compare")
        det_modules = (
            "finance-quick",
            "finance-networth",
            "finance-budget",
            "finance-emergency",
            "finance-debt",
            "finance-portfolio",
            "finance-screen",
            "finance-taxes",
            "finance-analyze",
            "finance-report-pdf",
        )

        start = time.perf_counter()
        for name in mc_modules:
            res1 = run_module(name, {}, demo)
            res2 = run_module(name, {}, demo)
            self.assertIn("monte_carlo", res1, f"{name} missing monte_carlo payload")
            mc = res1["monte_carlo"]
            self.assertEqual(mc, res2["monte_carlo"])
            self.assertEqual(mc["trials"], 1000)
            self.assertGreaterEqual(mc["success_rate_pct"], 0.0)
            self.assertLessEqual(mc["success_rate_pct"], 100.0)
            raws = [p["raw"] for p in mc["percentiles"]]
            self.assertEqual(len(raws), 3)
            self.assertLessEqual(raws[0], raws[1])
            self.assertLessEqual(raws[1], raws[2])
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 1.5, f"Monte Carlo suite too slow: {elapsed:.2f}s")

        for name in det_modules:
            res = run_module(name, {}, demo)
            self.assertNotIn("monte_carlo", res, f"Deterministic module {name} should not include monte_carlo")

    def test_specs_drive_catalog_fields_and_engines(self) -> None:
        cat = get_modules_catalog()
        for mod in cat["modules"]:
            self.assertIn("fields", mod)
            self.assertIsInstance(mod["fields"], list)
            self.assertIn(mod["engine"], ("deterministic", "hybrid_monte_carlo"))
            if mod["stage_id"] == "horizons":
                self.assertEqual(mod["engine"], "hybrid_monte_carlo")
            else:
                self.assertEqual(mod["engine"], "deterministic")


if __name__ == "__main__":
    unittest.main()
