"""Pure-stdlib HTTP clients for Ollama, OpenAI/OpenRouter, and Gemini."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

from .context import CopilotAPIError


def call_openai_compatible(
    api_key: str,
    model: str,
    system_prompt: str,
    history: Optional[List[Dict[str, str]]],
    clean_msg: str,
    base_url: str = "",
) -> Dict[str, str]:
    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for turn in (history or [])[-10:]:
        role = "assistant" if turn.get("role") == "assistant" else "user"
        text = str(turn.get("content") or "").strip()
        if text:
            messages.append({"role": role, "content": text[:2000]})
    messages.append({"role": "user", "content": clean_msg[:2000]})

    custom_url = (base_url or "").strip()
    is_openrouter = (not custom_url) and api_key.startswith("sk-or-v1-")
    if custom_url:
        endpoint = custom_url if custom_url.endswith("/chat/completions") else custom_url.rstrip("/") + "/v1/chat/completions"
        effective_model = model
    elif is_openrouter:
        endpoint = "https://openrouter.ai/api/v1/chat/completions"
        effective_model = f"openai/{model}" if "/" not in model else model
    else:
        endpoint = "https://api.openai.com/v1/chat/completions"
        effective_model = model

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
                "Authorization": f"Bearer {api_key or 'ollama'}",
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
            last_exc = CopilotAPIError("AI provider took too long to respond (timeout). Please try again.")
            if attempt == 0:
                time.sleep(1.0)
                continue
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="ignore")
            if exc.code in (429, 500, 503):
                last_exc = CopilotAPIError("AI provider is temporarily busy (rate limit or high demand). Please try again in a few seconds.")
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break
            raise CopilotAPIError(f"AI API error ({exc.code}): {err_body[:240]}") from exc
        except Exception as exc:
            if "timed out" in str(exc).lower():
                last_exc = CopilotAPIError("AI provider took too long to respond (timeout). Please try again.")
                if attempt == 0:
                    time.sleep(1.0)
                    continue
                break
            raise CopilotAPIError(f"Failed to reach AI endpoint ({endpoint}): {exc}") from exc

    if last_exc is not None:
        raise last_exc

    return {"reply": reply, "model": effective_model}


def call_gemini(
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
