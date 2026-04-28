"""
ATLAS LLM-Client — OpenRouter via OpenAI-SDK.

Verbesserungen:
- chat_stream(): Token-Streaming mit Generator-Interface
- chat_with_tools(): Tool-Use-Loop (OpenAI function-calling)
- Exponential Backoff mit konfigurierbaren Retries
- Modell- und Temperatur-Config per Agent aus models.yaml
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Generator
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI, APIError, RateLimitError, APIConnectionError

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
MODELS_CONFIG = BASE_DIR / "atlas_config" / "models.yaml"

_cfg_cache: dict | None = None


def _load_config() -> dict:
    global _cfg_cache
    if _cfg_cache is None:
        if MODELS_CONFIG.exists():
            _cfg_cache = yaml.safe_load(MODELS_CONFIG.read_text(encoding="utf-8")) or {}
        else:
            _cfg_cache = {}
    return _cfg_cache


def get_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        timeout=60.0,
    )


def get_model(agent_name: str) -> str:
    cfg = _load_config()
    return (
        cfg.get("agents", {}).get(agent_name)
        or os.getenv("ATLAS_DEFAULT_MODEL")
        or cfg.get("default", "minimax/minimax-m2.5")
    )


def get_temperature(agent_name: str) -> float:
    cfg = _load_config()
    temps = cfg.get("temperature", {})
    val = temps.get(agent_name) or temps.get("default", 0.2)
    return float(val)


def get_max_tokens(agent_name: str) -> int:
    cfg = _load_config()
    tokens = cfg.get("max_tokens", {})
    val = tokens.get(agent_name) or tokens.get("default", 4096)
    return int(val)


# ── Einfacher Chat (non-streaming) ────────────────────────────────────────────

def chat(
    messages: list[dict],
    agent_name: str = "default",
    retries: int = 3,
    extra_kwargs: dict | None = None,
) -> str:
    """Synchroner LLM-Aufruf mit Exponential Backoff."""
    client = get_client()
    model = get_model(agent_name)
    temperature = get_temperature(agent_name)
    max_tokens = get_max_tokens(agent_name)
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **(extra_kwargs or {}),
    )
    _RETRYABLE = (RateLimitError, APIConnectionError)
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except _RETRYABLE as e:
            last_err = e
            wait = 2 ** attempt
            time.sleep(wait)
        except APIError as e:
            raise RuntimeError(f"LLM API Error: {e}") from e
        except Exception as e:
            raise RuntimeError(f"LLM Fehler: {e}") from e
    raise RuntimeError(f"LLM nach {retries} Versuchen fehlgeschlagen: {last_err}") from last_err


# ── Streaming Chat ────────────────────────────────────────────────────────────

def chat_stream(
    messages: list[dict],
    agent_name: str = "default",
) -> Generator[str, None, None]:
    """
    Streaming LLM-Aufruf. Yieldet Token-Chunks.
    Usage:
        for chunk in chat_stream(messages, "plm_coordinator"):
            print(chunk, end="", flush=True)
    """
    client = get_client()
    model = get_model(agent_name)
    temperature = get_temperature(agent_name)
    max_tokens = get_max_tokens(agent_name)
    try:
        with client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        ) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
    except Exception as e:
        yield f"\n[STREAM ERROR] {e}"


# ── Tool-Use Loop ─────────────────────────────────────────────────────────────

def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    agent_name: str = "default",
    max_tool_rounds: int = 5,
    stream_callback=None,
) -> tuple[str, list[dict]]:
    """
    Tool-Use-Loop nach OpenAI-Standard (function calling).

    Args:
        messages: Chat-Nachrichten
        tools: OpenAI-kompatible Tool-Definitionen
        agent_name: Für Modell/Temperatur-Lookup
        max_tool_rounds: Max. Iterationen im Tool-Use-Loop
        stream_callback: Optionale Funktion(chunk: str) für Streaming-Output

    Returns:
        (final_text, tool_calls_log)
    """
    from atlas_core.tools import execute_tool

    client = get_client()
    model = get_model(agent_name)
    temperature = get_temperature(agent_name)
    max_tokens = get_max_tokens(agent_name)

    current_messages = list(messages)
    tool_calls_log: list[dict] = []

    for round_num in range(max_tool_rounds):
        kwargs = dict(
            model=model,
            messages=current_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            if stream_callback and not tools:
                # Streaming nur wenn keine Tools (OpenRouter streamt Tool-Calls nicht immer korrekt)
                text = ""
                with client.chat.completions.create(**kwargs, stream=True) as stream:
                    for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if delta and delta.content:
                            stream_callback(delta.content)
                            text += delta.content
                return text, tool_calls_log

            resp = client.chat.completions.create(**kwargs)
            choice = resp.choices[0]
            msg = choice.message

            # Kein Tool-Call → fertig
            if not (msg.tool_calls):
                text = msg.content or ""
                if stream_callback:
                    stream_callback(text)
                return text, tool_calls_log

            # Tool-Calls ausführen
            current_messages.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = tc.function.arguments
                tool_result = execute_tool(fn_name, fn_args)
                tool_calls_log.append({
                    "tool": fn_name,
                    "args": fn_args,
                    "result_preview": tool_result[:200],
                })
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })

            # Nächste Runde ohne Tools um finale Antwort zu generieren
            if round_num == max_tool_rounds - 1:
                kwargs.pop("tools", None)
                kwargs.pop("tool_choice", None)

        except Exception as e:
            return f"[LLM Fehler] {e}", tool_calls_log

    # Finale Antwort nach allen Tool-Rounds
    try:
        kwargs_final = dict(model=model, messages=current_messages, temperature=temperature, max_tokens=max_tokens)
        resp = client.chat.completions.create(**kwargs_final)
        text = resp.choices[0].message.content or ""
        if stream_callback:
            stream_callback(text)
        return text, tool_calls_log
    except Exception as e:
        return f"[LLM Fehler in finaler Runde] {e}", tool_calls_log
