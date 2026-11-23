"""Plan Insights: Pure-stdlib OpenAI & Gemini chat helper grounded in the user's active financial plan."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class CopilotConfigError(RuntimeError):
    """Raised when no AI provider API key is configured."""


class CopilotAPIError(RuntimeError):
    """Raised when the upstream AI API call fails."""


def _parse_dotenv(env_file: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not env_file.is_file():
        return values
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def get_env_setting(name: str, default: str = "", env_path: Optional[Path] = None) -> str:
    direct = os.environ.get(name, "").strip()
    if direct:
        return direct
    dotenv_vals = _parse_dotenv(env_path or (REPO_ROOT / ".env"))
    return dotenv_vals.get(name, default).strip()


def build_plan_context(plan: Dict[str, Any], module_runs: List[Dict[str, Any]]) -> str:
    """Summarize the active plan and saved module runs for grounded LLM context."""
    payload = plan.get("payload") or {}
    cats = payload.get("categories") or {}
    cf = payload.get("cash_flow") or {}
    debt = payload.get("debt") or {}
    inv = payload.get("investments") or {}
    ret = payload.get("retirement") or {}
    prot = payload.get("protection") or {}
    mc = ret.get("monte_carlo") or {}

    summary_obj = {
        "plan_title": plan.get("title") or payload.get("client_name") or "Personal Financial Plan",
        "health_score": plan.get("health_score", payload.get("health_score", 0)),
        "grade": plan.get("grade", payload.get("grade", "--")),
        "signal": payload.get("signal", ""),
        "pillar_scores": {
            "cash_flow": cats.get("cash_flow", 0),
            "debt": cats.get("debt", 0),
            "investments": cats.get("investments", 0),
            "retirement": cats.get("retirement", 0),
            "protection": cats.get("protection", 0),
        },
        "cash_flow": {
            "monthly_income": cf.get("monthly_income", 0),
            "gross_annual_income": cf.get("gross_annual_income", 0),
            "budget_50_30_20": cf.get("budget_50_30_20"),
        },
        "debt_accounts": debt.get("accounts") or [],
        "investments": {
            "total_value": inv.get("total_value", 0),
            "allocation": inv.get("allocation") or [],
        },
        "retirement": {
            "current_age": ret.get("current_age"),
            "retirement_age": ret.get("retirement_age"),
            "current_balance": ret.get("current_balance"),
            "target_balance": ret.get("target_balance"),
            "monthly_contribution": ret.get("monthly_contribution"),
            "employer_match_monthly": ret.get("employer_match_monthly"),
            "monte_carlo_survival_pct": mc.get("success_rate_pct"),
            "monte_carlo_median": mc.get("retire_p50"),
        },
        "protection_items": prot.get("items") or [],
        "top_action_items": (payload.get("action_items") or [])[:5],
        "saved_module_summaries": [
            {
                "module": r.get("module_name"),
                "score": r.get("score"),
                "summary": (r.get("outputs") or {}).get("summary", ""),
            }
            for r in (module_runs or [])
        ],
    }
    return json.dumps(summary_obj, indent=2)


def _call_openai(
    api_key: str,
    model: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]],
    clean_msg: str,
) -> Dict[str, str]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in (history or [])[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("content") or "").strip()
        if text:
            messages.append({"role": role, "content": text[:2000]})
    messages.append({"role": "user", "content": clean_msg[:2000]})

    is_openrouter = api_key.startswith("sk-or-v1-")
    endpoint = "https://openrouter.ai/api/v1/chat/completions" if is_openrouter else "https://api.openai.com/v1/chat/completions"
    effective_model = f"openai/{model}" if (is_openrouter and "/" not in model) else model

    body = json.dumps(
        {
            "model": effective_model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2500,
        }
    ).encode("utf-8")

    last_exc: Optional[Exception] = None
    reply = ""
    for attempt in range(2):
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            choices = data.get("choices") or []
            reply = str(((choices[0].get("message") or {}).get("content") or "") if choices else "").strip()
            if not reply:
                last_exc = CopilotAPIError("AI model returned an empty response. Please try again.")
                if attempt == 0:
                    time.sleep(0.5)
                    continue
                break
            last_exc = None
            break
        except TimeoutError:
            last_exc = CopilotAPIError("OpenAI took too long to respond (timeout). Please try again.")
            if attempt == 0:
                time.sleep(1.0)
                continue
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            if exc.code in (429, 500, 503):
                last_exc = CopilotAPIError("OpenAI is temporarily busy (rate limit or high demand). Please try again in a few seconds.")
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break
            raise CopilotAPIError(f"OpenAI API error ({exc.code}): {err_body[:240]}") from exc
        except Exception as exc:
            if "timed out" in str(exc).lower():
                last_exc = CopilotAPIError("OpenAI took too long to respond (timeout). Please try again.")
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break
            raise CopilotAPIError(f"Failed to reach OpenAI API: {exc}") from exc

    if last_exc is not None:
        raise last_exc

    return {"reply": reply, "model": model}


def _call_gemini(
    api_key: str,
    model: str,
    fallback_model: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]],
    clean_msg: str,
) -> Dict[str, str]:
    contents: List[Dict[str, Any]] = []
    for turn in (history or [])[-10:]:
        role = "model" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text[:2000]}]})
    contents.append({"role": "user", "parts": [{"text": clean_msg[:2000]}]})

    body = json.dumps(
        {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800},
        }
    ).encode("utf-8")

    models_to_try = [model]
    if fallback_model and fallback_model != model:
        models_to_try.append(fallback_model)

    raw = ""
    used_model = model
    last_exc: Optional[Exception] = None

    for candidate_model in models_to_try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{urllib.parse.quote(candidate_model, safe='')}:generateContent?key={urllib.parse.quote(api_key, safe='')}"
        )
        for attempt in range(2):
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=45) as resp:
                    raw = resp.read().decode("utf-8")
                used_model = candidate_model
                last_exc = None
                break
            except TimeoutError:
                last_exc = CopilotAPIError("Gemini took too long to respond (timeout). Please try again.")
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break
            except urllib.error.HTTPError as exc:
                err_body = exc.read().decode("utf-8", errors="ignore")
                if exc.code in (429, 500, 503):
                    last_exc = CopilotAPIError("Gemini is temporarily busy (high demand). Please try again in a few seconds.")
                    if attempt == 0:
                        time.sleep(1.0)
                        continue
                    break
                raise CopilotAPIError(f"Gemini API error ({exc.code}): {err_body[:240]}") from exc
            except Exception as exc:
                if "timed out" in str(exc).lower():
                    last_exc = CopilotAPIError("Gemini took too long to respond (timeout). Please try again.")
                    if attempt == 0:
                        time.sleep(1.0)
                        continue
                    break
                raise CopilotAPIError(f"Failed to reach Gemini API: {exc}") from exc
        if last_exc is None:
            break

    if last_exc is not None:
        raise last_exc

    try:
        data = json.loads(raw)
        candidates = data.get("candidates") or []
        parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
        reply = "".join(str(p.get("text") or "") for p in parts).strip()
    except Exception as exc:
        raise CopilotAPIError(f"Unexpected Gemini response format: {exc}") from exc

    if not reply:
        raise CopilotAPIError("Gemini returned an empty response.")

    return {"reply": reply, "model": used_model}


def ask_copilot(
    message: str,
    history: Optional[List[Dict[str, str]]],
    plan: Dict[str, Any],
    module_runs: List[Dict[str, Any]],
    env_path: Optional[Path] = None,
) -> Dict[str, str]:
    """Send a grounded chat turn to OpenAI (preferred when configured) or Gemini."""
    clean_msg = (message or "").strip()
    if not clean_msg:
        raise ValueError("Message cannot be empty.")

    openai_key = get_env_setting("OPENAI_API_KEY", env_path=env_path) or get_env_setting("OPENAI_AI_KEY", env_path=env_path)
    gemini_key = get_env_setting("GEMINI_API_KEY", env_path=env_path)
    if not openai_key and not gemini_key:
        raise CopilotConfigError(
            "No AI API key is configured. Add OPENAI_API_KEY (or GEMINI_API_KEY) to your .env file to enable Plan Insights."
        )

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

    if openai_key:
        openai_model = get_env_setting("OPENAI_MODEL", DEFAULT_OPENAI_MODEL, env_path=env_path) or DEFAULT_OPENAI_MODEL
        return _call_openai(openai_key, openai_model, system_prompt, history, clean_msg)

    gemini_model = get_env_setting("GEMINI_MODEL", DEFAULT_GEMINI_MODEL, env_path=env_path) or DEFAULT_GEMINI_MODEL
    fallback_model = get_env_setting("GEMINI_FALLBACK_MODEL", "", env_path=env_path)
    return _call_gemini(gemini_key, gemini_model, fallback_model, system_prompt, history, clean_msg)
