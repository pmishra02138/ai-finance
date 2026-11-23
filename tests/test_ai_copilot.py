#!/usr/bin/env python3
"""Unit tests for FinPlan Copilot (.env loading, plan context grounding, and Gemini API handling)."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ai_copilot import CopilotConfigError, ask_copilot, build_plan_context, get_env_setting


class TestFinPlanCopilot(unittest.TestCase):
    def test_dotenv_loading_and_missing_key_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text('GEMINI_API_KEY="test-key-from-dotenv"\nGEMINI_MODEL=gemini-3.8-flash\n', encoding="utf-8")

            old_key = os.environ.pop("GEMINI_API_KEY", None)
            try:
                self.assertEqual(get_env_setting("GEMINI_API_KEY", env_path=env_file), "test-key-from-dotenv")

                empty_env = Path(tmp_dir) / "empty.env"
                empty_env.write_text("# empty\n", encoding="utf-8")
                with self.assertRaises(CopilotConfigError):
                    ask_copilot("Why is my score 75?", [], {"title": "My Plan", "payload": {}}, [], env_path=empty_env)
            finally:
                if old_key is not None:
                    os.environ["GEMINI_API_KEY"] = old_key

    def test_ask_copilot_grounds_plan_and_parses_gemini_reply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("GEMINI_API_KEY=fake-key-123\n", encoding="utf-8")
            plan = {
                "title": "Family 2026",
                "health_score": 81.5,
                "grade": "A-",
                "payload": {
                    "categories": {"cash_flow": 85, "debt": 72, "investments": 80, "retirement": 84, "protection": 86},
                    "cash_flow": {"monthly_income": 9200},
                },
            }
            ctx = build_plan_context(plan, [{"module_name": "finance-budget", "score": 85.0, "outputs": {"summary": "50/30/20 looks healthy"}}])
            self.assertIn("Family 2026", ctx)
            self.assertIn("81.5", ctx)

            fake_resp = io.BytesIO(
                json.dumps({"candidates": [{"content": {"parts": [{"text": "Your score is 81.5 (A-) driven by strong Cash Flow."}]}}]}).encode("utf-8")
            )
            fake_resp.__enter__ = lambda s=fake_resp: s
            fake_resp.__exit__ = lambda *args: None

            old_key = os.environ.pop("GEMINI_API_KEY", None)
            try:
                with patch("ai_copilot.urllib.request.urlopen", return_value=fake_resp) as mock_open:
                    res = ask_copilot("Why is my score 81.5?", [{"role": "user", "content": "Hi"}], plan, [], env_path=env_file)
                self.assertIn("81.5", res["reply"])
                self.assertEqual(res["model"], "gemini-3.8-flash")
                self.assertTrue(mock_open.called)
            finally:
                if old_key is not None:
                    os.environ["GEMINI_API_KEY"] = old_key
