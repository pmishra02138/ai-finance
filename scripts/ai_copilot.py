"""Backward-compatible thin shim for `scripts/copilot/`."""

from copilot import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL,
    OFFLINE_DISCLAIMER,
    CopilotAPIError,
    CopilotConfigError,
    ask_copilot,
    build_plan_context,
    get_env_setting,
    summarize_plan_offline,
)

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
