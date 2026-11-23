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

from ai_copilot import OFFLINE_DISCLAIMER, ask_copilot, build_plan_context, get_env_setting


class TestFinPlanCopilot(unittest.TestCase):
    def test_dotenv_loading_and_offline_default_summarizer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text('GEMINI_API_KEY="test-key-from-dotenv"\nGEMINI_MODEL=gemini-3.8-flash\n', encoding="utf-8")

            old_g = os.environ.pop("GEMINI_API_KEY", None)
            old_o1 = os.environ.pop("OPENAI_API_KEY", None)
            old_o2 = os.environ.pop("OPENAI_AI_KEY", None)
            old_b = os.environ.pop("OPENAI_BASE_URL", None)
            try:
                self.assertEqual(get_env_setting("GEMINI_API_KEY", env_path=env_file), "test-key-from-dotenv")

                empty_env = Path(tmp_dir) / "empty.env"
                empty_env.write_text("# empty\n", encoding="utf-8")
                plan = {
                    "title": "My Plan",
                    "health_score": 75.0,
                    "grade": "B",
                    "payload": {
                        "categories": {"cash_flow": 80, "debt": 70, "investments": 75, "retirement": 75, "protection": 75},
                        "action_items": [{"action": "Increase 401(k)", "category": "Retirement", "priority": "High"}],
                    },
                }
                res = ask_copilot("Why is my score 75?", [], plan, [], env_path=empty_env)
                self.assertEqual(res["model"], "offline-python")
                self.assertIn("75.0/100", res["reply"])
                self.assertIn("limited capacity", res["reply"])
                self.assertIn(OFFLINE_DISCLAIMER, res["reply"])
            finally:
                if old_g is not None:
                    os.environ["GEMINI_API_KEY"] = old_g
                if old_o1 is not None:
                    os.environ["OPENAI_API_KEY"] = old_o1
                if old_o2 is not None:
                    os.environ["OPENAI_AI_KEY"] = old_o2
                if old_b is not None:
                    os.environ["OPENAI_BASE_URL"] = old_b

    def test_local_ollama_llama32_routing_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            env_file = Path(tmp_dir) / ".env"
            env_file.write_text("OPENAI_BASE_URL=http://localhost:11434/v1/chat/completions\n", encoding="utf-8")
            plan = {"title": "Local Plan", "health_score": 80.0, "grade": "A-", "payload": {"categories": {"cash_flow": 80}}}
            fake_resp = io.BytesIO(
                json.dumps({"choices": [{"message": {"content": "Local llama3.2 summary: score is 80.0."}}]}).encode("utf-8")
            )
            fake_resp.__enter__ = lambda s=fake_resp: s
            fake_resp.__exit__ = lambda *args: None

            old_b = os.environ.pop("OPENAI_BASE_URL", None)
            old_m = os.environ.pop("OPENAI_MODEL", None)
            try:
                with patch("copilot.providers.urllib.request.urlopen", return_value=fake_resp) as mock_open:
                    res = ask_copilot("Summarize my score", [], plan, [], env_path=env_file)
                self.assertEqual(res["model"], "llama3.2:latest")
                self.assertIn("llama3.2", res["reply"])
                req_obj = mock_open.call_args[0][0]
                self.assertEqual(req_obj.full_url, "http://localhost:11434/v1/chat/completions")
            finally:
                if old_b is not None:
                    os.environ["OPENAI_BASE_URL"] = old_b
                if old_m is not None:
                    os.environ["OPENAI_MODEL"] = old_m

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
                with patch("copilot.providers.urllib.request.urlopen", return_value=fake_resp) as mock_open:
                    res = ask_copilot("Why is my score 81.5?", [{"role": "user", "content": "Hi"}], plan, [], env_path=env_file)
                self.assertIn("81.5", res["reply"])
                self.assertEqual(res["model"], "gemini-3.8-flash")
                self.assertTrue(mock_open.called)
            finally:
                if old_key is not None:
                    os.environ["GEMINI_API_KEY"] = old_key
