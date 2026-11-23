#!/usr/bin/env python3
"""
End-to-end test suite for ai-finance.

Covers:
1. Repository & AGY skill integrity (.agents/skills symlinks, YAML frontmatter, disclaimers)
2. Installer & uninstaller E2E in an isolated temporary HOME directory
3. PDF generator CLI & edge-case tests (skipped cleanly if reportlab is absent)
4. Localhost HTTP server E2E tests (health, error handling, and PDF endpoints)
5. Docker configuration presence & sanity checks
"""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
HAS_REPORTLAB = importlib.util.find_spec("reportlab") is not None
HAS_FASTAPI = importlib.util.find_spec("fastapi") is not None
HAS_UVICORN = importlib.util.find_spec("uvicorn") is not None


class TestStructuredSpecs(unittest.TestCase):
    """Verify specs/*.json single source of truth and removal of legacy SKILL.md artifacts."""

    def test_structured_specs_exist_and_legacy_skills_removed(self) -> None:
        specs_dir = REPO_ROOT / "specs"
        self.assertTrue(specs_dir.is_dir(), "specs/ directory missing")
        expected_stages = ["baseline", "foundation", "growth", "horizons", "synthesis"]
        total_modules = 0
        for stage in expected_stages:
            spec_file = specs_dir / f"{stage}.json"
            self.assertTrue(spec_file.is_file(), f"Missing {spec_file}")
            data = json.loads(spec_file.read_text(encoding="utf-8"))
            self.assertEqual(data["id"], stage)
            self.assertIsInstance(data.get("modules"), list)
            total_modules += len(data["modules"])
            for mod in data["modules"]:
                self.assertIn("name", mod)
                self.assertIn("label", mod)
                self.assertIn("description", mod)
                self.assertIn("fields", mod)
                self.assertIn(mod.get("engine"), ("deterministic", "hybrid_monte_carlo"))
        self.assertEqual(total_modules, 10)

        # Ensure legacy SKILL.md artifacts are completely removed
        self.assertFalse((REPO_ROOT / "skills").exists())
        self.assertFalse((REPO_ROOT / "finance").exists())
        self.assertFalse((REPO_ROOT / ".agents" / "skills").exists())
        self.assertFalse((REPO_ROOT / "install.sh").exists())
        self.assertFalse((REPO_ROOT / "uninstall.sh").exists())


class TestPDFGeneratorCLI(unittest.TestCase):
    """Test scripts/generate_finance_pdf.py CLI behavior and edge cases."""

    @unittest.skipUnless(HAS_REPORTLAB, "reportlab not installed in current Python environment")
    def test_demo_pdf_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_pdf = Path(tmp_dir) / "FINANCE-PLAN.pdf"
            res = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "generate_finance_pdf.py"),
                    "--demo",
                    "--output",
                    str(out_pdf),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_pdf.is_file())
            data = out_pdf.read_bytes()
            self.assertTrue(data.startswith(b"%PDF-"))
            self.assertGreater(len(data), 5000)

    @unittest.skipUnless(HAS_REPORTLAB, "reportlab not installed in current Python environment")
    def test_xml_special_chars_and_empty_lists(self) -> None:
        payload = {
            "client_name": "Smith & Co. <VIP>",
            "health_score": 72,
            "executive_summary": "Assets > liabilities & cashflow < target.",
            "categories": {"cash_flow": 80, "debt": 60, "investments": 70, "retirement": 75, "protection": 75},
            "category_notes": {"cash_flow": "A & B <test>"},
            "cash_flow": {"monthly_income": 5000, "expenses": [["Rent & Utilities", 2000]], "commentary": "Save > 20%"},
            "debt": {"accounts": [], "payoff_months": 0, "total_interest": 0},
            "investments": {"total_value": 0, "allocation": [], "commentary": "Start & diversify <soon>"},
            "retirement": {"current_age": 30, "retirement_age": 65, "current_balance": 10000, "target_balance": 1000000, "monthly_contribution": 500, "scenarios": []},
            "protection": {"items": [{"name": "Health & Dental", "status": "Good", "recommendation": "Keep <$500 deductible"}], "commentary": "OK & active"},
            "action_items": [{"action": "Open HSA & invest <10% fees", "category": "Tax", "priority": "High", "impact": "High"}],
            "ninety_day_plan": {"month_1": ["Review & update <beneficiaries>"], "month_2": [], "month_3": [], "after_90_days": "Re-run & check"},
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "plan.json"
            out_pdf = Path(tmp_dir) / "edge.pdf"
            json_path.write_text(json.dumps(payload), encoding="utf-8")
            res = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "generate_finance_pdf.py"),
                    "--data",
                    str(json_path),
                    "--output",
                    str(out_pdf),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertTrue(out_pdf.read_bytes().startswith(b"%PDF-"))

    @unittest.skipUnless(HAS_REPORTLAB, "reportlab not installed in current Python environment")
    def test_non_dict_json_root_fails_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_path = Path(tmp_dir) / "bad.json"
            json_path.write_text("[1, 2, 3]", encoding="utf-8")
            res = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "generate_finance_pdf.py"),
                    "--data",
                    str(json_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("object", res.stderr.lower())


class TestDatabaseLayer(unittest.TestCase):
    """Test SQLite persistence, default user seeding (user/password), sessions, and plan CRUD."""

    def test_default_user_auth_and_plan_crud(self) -> None:
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        import db as finance_db

        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "test.db")
            finance_db.init_db(db_path=db_path, seed_demo_payload={"client_name": "Seeded", "health_score": 70, "grade": "B"})

            # Default user / password works
            auth = finance_db.authenticate_user("user", "password", db_path=db_path)
            self.assertIsNotNone(auth)
            self.assertEqual(auth["user"]["username"], "user")
            token = auth["token"]
            user_id = auth["user"]["id"]

            # Wrong password fails
            self.assertIsNone(finance_db.authenticate_user("user", "wrong", db_path=db_path))

            # Token lookup
            me = finance_db.get_user_by_token(token, db_path=db_path)
            self.assertEqual(me["username"], "user")

            # Seeded plan exists
            plans = finance_db.list_plans(user_id, db_path=db_path)
            self.assertEqual(len(plans), 1)

            # Create / get / update / delete plan
            created = finance_db.create_plan(user_id, "My Plan", 82.0, "A-", {"client_name": "My Plan"}, db_path=db_path)
            fetched = finance_db.get_plan(user_id, created["id"], db_path=db_path)
            self.assertEqual(fetched["title"], "My Plan")

            updated = finance_db.update_plan(user_id, created["id"], "Updated Plan", 90.0, "A+", {"client_name": "Updated Plan"}, db_path=db_path)
            self.assertEqual(updated["title"], "Updated Plan")
            self.assertEqual(updated["grade"], "A+")

            finance_db.upsert_module_run(user_id, created["id"], "finance-budget", {"monthly_income": 9000}, {"score": 88.0}, db_path=db_path)
            self.assertEqual(len(finance_db.list_module_runs(user_id, created["id"], db_path=db_path)), 1)
            reset = finance_db.reset_plan(user_id, created["id"], 0.0, "--", {"client_name": "Updated Plan", "health_score": 0}, db_path=db_path)
            self.assertEqual(reset["health_score"], 0.0)
            self.assertEqual(reset["grade"], "--")
            self.assertEqual(len(finance_db.list_module_runs(user_id, created["id"], db_path=db_path)), 0)

            self.assertTrue(finance_db.delete_plan(user_id, created["id"], db_path=db_path))
            self.assertIsNone(finance_db.get_plan(user_id, created["id"], db_path=db_path))

            # Revoke token
            finance_db.revoke_token(token, db_path=db_path)
            self.assertIsNone(finance_db.get_user_by_token(token, db_path=db_path))

            # Custom default credentials via environment variables
            custom_db = str(Path(tmp_dir) / "custom_creds.db")
            old_u = os.environ.get("FINPLAN_DEFAULT_USER")
            old_p = os.environ.get("FINPLAN_DEFAULT_PASSWORD")
            try:
                os.environ["FINPLAN_DEFAULT_USER"] = "pankaj"
                os.environ["FINPLAN_DEFAULT_PASSWORD"] = "s3cr3tPass"
                finance_db.init_db(db_path=custom_db, seed_demo_payload={"client_name": "Pankaj Plan", "health_score": 80, "grade": "B+"})
                self.assertIsNone(finance_db.authenticate_user("user", "password", db_path=custom_db))
                custom_auth = finance_db.authenticate_user("pankaj", "s3cr3tPass", db_path=custom_db)
                self.assertIsNotNone(custom_auth)
            finally:
                if old_u is None:
                    os.environ.pop("FINPLAN_DEFAULT_USER", None)
                else:
                    os.environ["FINPLAN_DEFAULT_USER"] = old_u
                if old_p is None:
                    os.environ.pop("FINPLAN_DEFAULT_PASSWORD", None)
                else:
                    os.environ["FINPLAN_DEFAULT_PASSWORD"] = old_p


class TestLocalhostServerE2E(unittest.TestCase):
    """Test unified single-port FastAPI + SQLite + static frontend end-to-end."""

    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    @unittest.skipUnless(
        HAS_REPORTLAB and HAS_FASTAPI and HAS_UVICORN,
        "reportlab, fastapi, and uvicorn must be installed in current Python environment",
    )
    def test_fullstack_auth_crud_pdf_and_single_port_ui(self) -> None:
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        import uvicorn
        import server as pdf_server

        port = self._free_port()

        with tempfile.TemporaryDirectory() as tmp_dir:
            prev_db = os.environ.get("AI_FINANCE_DB_PATH")
            os.environ["AI_FINANCE_DB_PATH"] = str(Path(tmp_dir) / "e2e.db")

            config = uvicorn.Config(pdf_server.app, host="127.0.0.1", port=port, log_level="error")
            uv_server = uvicorn.Server(config)
            api_thread = threading.Thread(target=uv_server.run, daemon=True)
            api_thread.start()

            try:
                base = f"http://127.0.0.1:{port}"

                # Wait for single-port server
                ready = False
                for _ in range(40):
                    try:
                        with urllib.request.urlopen(f"{base}/api/health") as resp:
                            if resp.status == 200:
                                ready = True
                                break
                    except Exception:
                        time.sleep(0.1)
                self.assertTrue(ready, f"Server not ready at {base}/api/health")

                # 1. Static frontend assets & 404 for missing extensioned files
                for asset, snippet in (
                    ("/", "AI Personal Finance Advisor"),
                    ("/styles.css", ".topbar"),
                    ("/charts.js", "FinanceCharts"),
                    ("/modules.js", "FinanceModules"),
                    ("/app.js", "/auth/login"),
                ):
                    with urllib.request.urlopen(f"{base}{asset}") as resp:
                        self.assertEqual(resp.status, 200)
                        self.assertIn(snippet, resp.read().decode("utf-8"))

                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(f"{base}/does-not-exist.js")
                self.assertEqual(ctx.exception.code, 404)

                app_js = (REPO_ROOT / "frontend" / "public" / "app.js").read_text(encoding="utf-8")
                self.assertNotIn("SQLite", app_js)
                self.assertNotIn(".md", app_js)

                # 2. /api/modules returns all 10 modules across 5 stages
                with urllib.request.urlopen(f"{base}/api/modules") as resp:
                    self.assertEqual(resp.status, 200)
                    catalog = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(len(catalog["stages"]), 5)
                    self.assertEqual(catalog["total_modules"], 10)

                # 3. User registration works & duplicate returns 409
                reg_req = urllib.request.Request(
                    f"{base}/api/auth/register",
                    data=json.dumps({"username": "alice_test", "password": "secret123"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(reg_req) as resp:
                    self.assertEqual(resp.status, 201)
                    reg_data = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(reg_data["user"]["username"], "alice_test")

                dup_req = urllib.request.Request(
                    f"{base}/api/auth/register",
                    data=json.dumps({"username": "alice_test", "password": "secret123"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(dup_req)
                self.assertEqual(ctx.exception.code, 409)

                # 4. Unauthenticated /api/plans returns 401
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(f"{base}/api/plans")
                self.assertEqual(ctx.exception.code, 401)

                # 5. Login with wrong password returns 401
                bad_login = urllib.request.Request(
                    f"{base}/api/auth/login",
                    data=json.dumps({"username": "user", "password": "bad"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(bad_login)
                self.assertEqual(ctx.exception.code, 401)

                # 6. Login with default user/password succeeds
                login_req = urllib.request.Request(
                    f"{base}/api/auth/login",
                    data=json.dumps({"username": "user", "password": "password"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(login_req) as resp:
                    self.assertEqual(resp.status, 200)
                    auth_data = json.loads(resp.read().decode("utf-8"))
                token = auth_data["token"]
                self.assertEqual(auth_data["user"]["username"], "user")
                auth_headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

                # 7. /api/auth/me & seeded /api/plans
                with urllib.request.urlopen(urllib.request.Request(f"{base}/api/auth/me", headers=auth_headers)) as resp:
                    self.assertEqual(json.loads(resp.read().decode("utf-8"))["username"], "user")

                with urllib.request.urlopen(urllib.request.Request(f"{base}/api/plans", headers=auth_headers)) as resp:
                    plans = json.loads(resp.read().decode("utf-8"))["plans"]
                    self.assertGreaterEqual(len(plans), 1)

                # 8. Create -> Update -> Run all 14 skills -> PDF -> Delete
                create_req = urllib.request.Request(
                    f"{base}/api/plans",
                    data=json.dumps({"title": "E2E & Test Plan", "payload": {"client_name": "E2E & Test", "health_score": 85}}).encode("utf-8"),
                    headers=auth_headers,
                    method="POST",
                )
                with urllib.request.urlopen(create_req) as resp:
                    self.assertEqual(resp.status, 201)
                    created = json.loads(resp.read().decode("utf-8"))
                plan_id = created["id"]

                update_req = urllib.request.Request(
                    f"{base}/api/plans/{plan_id}",
                    data=json.dumps({"title": "E2E Updated", "payload": {"client_name": "E2E Updated", "health_score": 92}}).encode("utf-8"),
                    headers=auth_headers,
                    method="PUT",
                )
                with urllib.request.urlopen(update_req) as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(json.loads(resp.read().decode("utf-8"))["grade"], "A+")

                for mod in catalog["modules"]:
                    self.assertIn("fields", mod)
                    self.assertIn("engine", mod)
                    run_req = urllib.request.Request(
                        f"{base}/api/plans/{plan_id}/modules/{mod['name']}/run",
                        data=json.dumps({"inputs": {}, "sync_to_plan": True}).encode("utf-8"),
                        headers=auth_headers,
                        method="POST",
                    )
                    with urllib.request.urlopen(run_req) as resp:
                        self.assertEqual(resp.status, 200)
                        run_body = json.loads(resp.read().decode("utf-8"))
                        self.assertEqual(run_body["result"]["module"], mod["name"])
                        if mod["engine"] == "hybrid_monte_carlo":
                            self.assertIn("monte_carlo", run_body["result"])
                            self.assertEqual(run_body["result"]["monte_carlo"]["trials"], 1000)

                # Verify syncing a category module (debt = $0 -> 100) recalculates composite health_score
                debt_sync_req = urllib.request.Request(
                    f"{base}/api/plans/{plan_id}/modules/finance-debt/run",
                    data=json.dumps({"inputs": {"accounts": [], "extra_monthly_payment": 0}, "sync_to_plan": True}).encode("utf-8"),
                    headers=auth_headers,
                    method="POST",
                )
                with urllib.request.urlopen(debt_sync_req) as resp:
                    self.assertEqual(resp.status, 200)
                    debt_sync_body = json.loads(resp.read().decode("utf-8"))
                    self.assertIsNotNone(debt_sync_body["updated_plan"])
                    self.assertEqual(debt_sync_body["updated_plan"]["payload"]["categories"]["debt"], 100.0)
                    self.assertNotEqual(debt_sync_body["updated_plan"]["health_score"], 92.0)

                with urllib.request.urlopen(urllib.request.Request(f"{base}/api/plans/{plan_id}/modules", headers=auth_headers)) as resp:
                    runs_body = json.loads(resp.read().decode("utf-8"))
                    self.assertEqual(len(runs_body["completed_modules"]), 13)

                with urllib.request.urlopen(urllib.request.Request(f"{base}/api/plans/{plan_id}/pdf", headers=auth_headers)) as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertEqual(resp.headers.get("Content-Type"), "application/pdf")
                    self.assertTrue(resp.read().startswith(b"%PDF-"))

                del_req = urllib.request.Request(f"{base}/api/plans/{plan_id}", headers=auth_headers, method="DELETE")
                with urllib.request.urlopen(del_req) as resp:
                    self.assertEqual(resp.status, 200)

                # 9. Direct /api/demo & /api/generate & 422 validation
                with urllib.request.urlopen(f"{base}/api/demo") as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertTrue(resp.read().startswith(b"%PDF-"))

                bad_req = urllib.request.Request(
                    f"{base}/api/generate",
                    data=b"[1, 2, 3]",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(bad_req)
                self.assertEqual(ctx.exception.code, 422)

                # 10. Logout revokes session
                logout_req = urllib.request.Request(f"{base}/api/auth/logout", headers=auth_headers, method="POST")
                with urllib.request.urlopen(logout_req) as resp:
                    self.assertEqual(resp.status, 200)
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(urllib.request.Request(f"{base}/api/auth/me", headers=auth_headers))
                self.assertEqual(ctx.exception.code, 401)
            finally:
                uv_server.should_exit = True
                api_thread.join(timeout=5)
                if prev_db is None:
                    os.environ.pop("AI_FINANCE_DB_PATH", None)
                else:
                    os.environ["AI_FINANCE_DB_PATH"] = prev_db


class TestDockerConfigs(unittest.TestCase):
    """Verify single-port Docker & uv files are valid and consistent."""

    def test_docker_files_exist_and_expose_8787(self) -> None:
        dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        reqs = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("8787", dockerfile)
        self.assertIn("USER aifinance", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("uv sync", dockerfile)
        self.assertIn("scripts.server:app", dockerfile)
        self.assertIn("127.0.0.1:8787:8787", compose)
        self.assertNotIn("3000:3000", compose)
        self.assertIn("fastapi", pyproject)
        self.assertIn("reportlab>=4.0.0", pyproject)
        self.assertIn("reportlab>=4.0.0", reqs)


if __name__ == "__main__":
    unittest.main()
