"""Plan Insights router: local Ollama (llama3.2), OpenAI/OpenRouter, Gemini, or offline Python summarizer."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from .context import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL,
    CopilotAPIError,
    CopilotConfigError,
    build_plan_context,
    get_env_setting,
)
from .offline import OFFLINE_DISCLAIMER, summarize_plan_offline
from .providers import call_gemini, call_openai_compatible


def ask_copilot(
    message: str,
    history: Optional[List[Dict[str, str]]],
    plan: Dict[str, Any],
    module_runs: List[Dict[str, Any]],
    env_path: Optional[Path] = None,
) -> Dict[str, str]:
    """Send a grounded chat turn to local Ollama (llama3.2), OpenAI/OpenRouter, Gemini, or default offline Python summarizer."""
    clean_msg = (message or "").strip()
    if not clean_msg:
        raise ValueError("Message cannot be empty.")

    base_url = get_env_setting("OPENAI_BASE_URL", env_path=env_path)
    openai_key = get_env_setting("OPENAI_API_KEY", env_path=env_path) or get_env_setting("OPENAI_AI_KEY", env_path=env_path)
    gemini_key = get_env_setting("GEMINI_API_KEY", env_path=env_path)

    if not base_url and not openai_key and not gemini_key:
        return summarize_plan_offline(clean_msg, plan, module_runs)

    plan_context = build_plan_context(plan, module_runs)
    system_prompt = (
        "You are Plan Insights, a strict read-only results summarizer inside the FinPlan web app.\n"
        "RULES:\n"
        "1. ONLY summarize and explain the numbers, scores, Monte Carlo results, and action items present in the ACTIVE FINANCIAL PLAN SNAPSHOT below.\n"
        "2. Do NOT provide general financial advice, market opinions, tax/legal advice, or speculative what-if calculations.\n"
        "3. Do NOT answer off-topic questions unrelated to the user's FinPlan results; politely reply that you can only summarize and explain their saved FinPlan results.\n"
        "4. Never invent balances, rates, or projections. If a metric is missing or 0, state that it has not been saved in the plan yet.\n"
        "5. Keep responses concise and structured (short paragraphs or bullet points).\n\n"
        f"ACTIVE FINANCIAL PLAN SNAPSHOT:\n{plan_context}"
    )

    if base_url:
        local_model = get_env_setting("OPENAI_MODEL", DEFAULT_OLLAMA_MODEL, env_path=env_path) or DEFAULT_OLLAMA_MODEL
        return call_openai_compatible(openai_key or "ollama", local_model, system_prompt, history, clean_msg, base_url=base_url)

    if openai_key:
        openai_model = get_env_setting("OPENAI_MODEL", DEFAULT_OPENAI_MODEL, env_path=env_path) or DEFAULT_OPENAI_MODEL
        return call_openai_compatible(openai_key, openai_model, system_prompt, history, clean_msg)

    gemini_model = get_env_setting("GEMINI_MODEL", DEFAULT_GEMINI_MODEL, env_path=env_path) or DEFAULT_GEMINI_MODEL
    fallback_model = get_env_setting("GEMINI_FALLBACK_MODEL", "", env_path=env_path)
    return call_gemini(gemini_key, gemini_model, fallback_model, system_prompt, history, clean_msg)


__all__ = [
    "CopilotAPIError",
    "CopilotConfigError",
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "OFFLINE_DISCLAIMER",
    "ask_copilot",
    "build_plan_context",
    "get_env_setting",
    "summarize_plan_offline",
]
