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
    def test_catalog_has_all_13_modules_in_5_stages(self) -> None:
        cat = get_modules_catalog()
        self.assertEqual(len(cat["stages"]), 5)
        self.assertEqual(cat["total_modules"], 13)
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
            "finance-protection",
            "finance-portfolio",
            "finance-taxes",
            "finance-analyze",
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

    def test_financial_logic_upgrades(self) -> None:
        demo = _demo_data()

        # 1. Protection & Estate module drives categories.protection & protection.items
        prot_missing = run_module(
            "finance-protection",
            {"term_life_status": "Missing", "disability_status": "Missing", "health_status": "Good", "umbrella_status": "Missing", "estate_docs_status": "Missing", "emergency_fund_months": 6},
            demo,
        )
        prot_full = run_module(
            "finance-protection",
            {"term_life_status": "Good", "disability_status": "Good", "health_status": "Good", "umbrella_status": "Good", "estate_docs_status": "Good", "emergency_fund_months": 6},
            demo,
        )
        self.assertLess(prot_missing["score"], 40.0)
        self.assertEqual(prot_full["score"], 100.0)
        self.assertEqual(len(prot_full["plan_patch"]["protection"]["items"]), 6)

        # 2. Quick Snapshot preserves existing 5-pillar score and separates liquid cash vs invested
        q_res = run_module("finance-quick", {"liquid_cash": 10000, "invested_savings": 200000, "monthly_expenses": 5000}, demo)
        self.assertNotIn("health_score", q_res["plan_patch"])
        self.assertEqual(q_res["metrics"][2]["value"], "2.0 mos")

        # 3. High-APR vs Low-APR debt scoring
        low_apr = run_module("finance-debt", {"accounts": [{"name": "Low Loan", "balance": 20000, "apr": 4.0, "min_payment": 300}], "extra_monthly_payment": 0}, {})
        high_apr = run_module("finance-debt", {"accounts": [{"name": "High Card", "balance": 20000, "apr": 22.0, "min_payment": 450}], "extra_monthly_payment": 0}, {})
        self.assertGreater(low_apr["score"], high_apr["score"] + 25.0)

        # 4. Portfolio Review includes consolidated Model ETF template table
        port = run_module("finance-portfolio", {"model_template": "dividend"}, demo)
        self.assertEqual(len(port["tables"]), 2)
        self.assertIn("Dividend Growth", port["tables"][1]["title"])

        # 5. Married Filing Jointly doubles IRA space & low bracket recommends Roth
        tax_mfj = run_module("finance-taxes", {"filing_status": "married", "age": 40, "marginal_tax_rate": 12, "current_ira": 0}, demo)
        rows = {r[0]: r[2] for r in tax_mfj["tables"][0]["rows"]}
        self.assertEqual(rows["IRA / Backdoor Roth (Joint)"], "$14,000")
        self.assertTrue(any("Roth" in r for r in tax_mfj["recommendations"]))

        # 6. Retirement links MC volatility to portfolio allocation & models employer match + withdrawal tax
        bond_plan = {**demo, "investments": {"total_value": 184000, "allocation": [{"name": "Bonds", "pct": 100}]}}
        stock_plan = {**demo, "investments": {"total_value": 184000, "allocation": [{"name": "US Stocks", "pct": 100}]}}
        ret_bond = run_module("finance-retirement", {"employer_match_monthly": 300, "retirement_tax_rate": 15, "social_security_annual": 20000, "social_security_start_age": 67}, bond_plan)
        ret_stock = run_module("finance-retirement", {"employer_match_monthly": 300, "retirement_tax_rate": 15, "social_security_annual": 20000, "social_security_start_age": 67}, stock_plan)
        self.assertLess(ret_bond["monte_carlo"]["volatility_pct"], ret_stock["monte_carlo"]["volatility_pct"])

        # 7. Scenario Compare accounts for ending asset equity (e.g., Home Equity)
        cmp_no_eq = run_module("finance-compare", {"scenario_a_ending_asset": 0, "scenario_b_ending_asset": 0}, demo)
        cmp_with_eq = run_module("finance-compare", {"scenario_a_ending_asset": 0, "scenario_b_ending_asset": 500000}, demo)
        self.assertNotEqual(cmp_no_eq["metrics"][2]["value"], cmp_with_eq["metrics"][2]["value"])

    def test_financial_audit_fixes(self) -> None:
        demo = _demo_data()

        # 1. Retirement blends MC survival & scales drawdown to age 95
        ret_demo = run_module("finance-retirement", {}, demo)
        self.assertLessEqual(ret_demo["score"], 79.0)  # 73.1% MC survival cannot score 100/A+
        ret_early = run_module("finance-retirement", {"retirement_age": 55}, demo)
        self.assertIn("40-Yr", ret_early["monte_carlo"]["success_label"])

        # 2. Goal Planner reports an 80% MC Confidence monthly target >= baseline
        goal = run_module("finance-goals", {}, demo)
        self.assertEqual(goal["metrics"][2]["label"], "80% Confidence Save")

        # 3. Debt detects negative amortization & scores 3% mortgage fairly
        neg = run_module("finance-debt", {"accounts": [{"name": "Card", "balance": 10000, "apr": 24, "min_payment": 150}], "extra_monthly_payment": 0}, {})
        self.assertIn("Negative amortization", neg["summary"])
        mtg = run_module("finance-debt", {"accounts": [{"name": "Mortgage", "balance": 400000, "apr": 3.0, "min_payment": 1700}], "extra_monthly_payment": 0}, {})
        self.assertGreaterEqual(mtg["score"], 85.0)

        # 4. Tax Optimization scores moderate earners fairly
        tax_50k = run_module("finance-taxes", {"gross_annual_income": 50000, "marginal_tax_rate": 12, "current_401k": 3000}, {})
        self.assertGreaterEqual(tax_50k["score"], 25.0)

        # 5. Early-career Net Worth benchmark doesn't crush age 26 high earners
        nw_26 = run_module("finance-networth", {"age": 26, "annual_income": 120000, "cash_assets": 20000, "investment_assets": 30000, "other_assets": 0, "other_debt": 0}, {})
        self.assertGreaterEqual(nw_26["score"], 60.0)

        # 6. Dynamic action items drop resolved items
        clean_plan = {
            **demo,
            "categories": {"cash_flow": 90, "debt": 95, "investments": 90, "retirement": 90, "protection": 95},
            "debt": {"accounts": []},
            "protection": {"items": [{"name": "Will / Estate Plan", "status": "Good", "recommendation": "OK"}]},
            "investments": {"allocation": [{"name": "US Stocks", "pct": 50, "target_pct": 50}]},
            "retirement": {"monte_carlo": {"success_rate_pct": 90.0}},
        }
        syn = run_module("finance-analyze", {}, clean_plan)
        self.assertFalse(any("Will" in a["action"] and "CRITICAL" in a["action"] for a in syn["action_items"]))


if __name__ == "__main__":
    unittest.main()
