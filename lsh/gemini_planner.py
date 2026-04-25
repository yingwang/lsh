"""Gemini Flash planner — free-tier LLM integration for lsh."""

from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
from typing import Any, Dict

from lsh.planner import Planner
from lsh.schema import Plan, parse_plan

_FALLBACK_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
]

_DEFAULT_MODEL = "gemini-2.0-flash"
_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_SYSTEM_PROMPT = """\
You are lsh, a safe shell assistant. Given a natural language task and optional \
context (cwd, OS, recent files), produce a JSON execution plan.

The JSON must match this schema exactly:
{
  "intent": "<short description of what the plan does>",
  "risk": "low" | "medium" | "high",
  "requires_confirmation": true | false,
  "steps": [<one or more step objects>]
}

Each step is ONE of:
  {"action": "list_files",  "args": {"path": ".", "recursive": false}}
  {"action": "find_files",  "args": {"path": ".", "pattern": "*.py"}}
  {"action": "read_file",   "args": {"path": "README.md", "max_bytes": 20000}}
  {"action": "run_command", "args": {"command": "git status"}}

Rules:
- Output ONLY the JSON object, no markdown fences, no extra text.
- risk is "low" for read-only actions, "medium" for commands that modify local \
state, "high" for anything that deletes data or touches the network.
- requires_confirmation must be true when risk is "medium" or "high".
- Prefer safe built-in actions (list_files, find_files, read_file) over \
run_command when possible.
- For run_command, give the exact shell command string.
- Never suggest rm, sudo, chmod, chown, mkfs, dd, eval, or pipe-to-shell.
"""


def _call_gemini_raw(
    prompt: str,
    api_key: str,
    model: str = _DEFAULT_MODEL,
    system: str = _SYSTEM_PROMPT,
    json_mode: bool = True,
) -> str:
    """Call Gemini API and return the text response."""
    gen_config: Dict[str, Any] = {"temperature": 0.1}
    if json_mode:
        gen_config["responseMimeType"] = "application/json"
    payload = json.dumps({
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": gen_config,
    }).encode()

    url = f"{_BASE_URL}/{model}:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Gemini API error {exc.code}: {detail}"
        ) from exc

    return body["candidates"][0]["content"]["parts"][0]["text"]


def _call_with_fallback(
    prompt: str,
    api_key: str,
    model: str | None = None,
    system: str = _SYSTEM_PROMPT,
    json_mode: bool = True,
) -> str:
    """Try models in order, skip 429s."""
    models = [model] if model else _FALLBACK_MODELS
    last_err: Exception | None = None
    for m in models:
        try:
            return _call_gemini_raw(prompt, api_key, m, system, json_mode)
        except RuntimeError as exc:
            last_err = exc
            if "429" in str(exc):
                continue
            raise
    raise last_err  # type: ignore[misc]


def _extract_json(text: str) -> str:
    """Strip markdown fences if the model wraps the JSON."""
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


class GeminiPlanner(Planner):
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY or pass api_key="
            )
        self.model = model or os.environ.get("GEMINI_MODEL")

    def plan(self, user_input: str, context: Dict[str, Any]) -> Plan:
        ctx_lines = []
        if context.get("cwd"):
            ctx_lines.append(f"cwd: {context['cwd']}")
        if context.get("os"):
            ctx_lines.append(f"os: {context['os']}")
        if context.get("files"):
            ctx_lines.append(f"files in cwd: {', '.join(context['files'][:20])}")

        prompt = f"Task: {user_input}"
        if ctx_lines:
            prompt = "\n".join(ctx_lines) + "\n\n" + prompt

        raw = _call_with_fallback(prompt, self.api_key, self.model)
        cleaned = _extract_json(raw)
        data = json.loads(cleaned)
        return parse_plan(data)


def gemini_explain_error(command: str, stderr: str, api_key: str | None = None) -> str:
    """Use Gemini to explain a command failure."""
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return ""
    prompt = f"Command: {command}\nStderr:\n{stderr[:2000]}\n\nExplain why this command failed in 1-2 sentences."
    system = "You are a shell expert. Give a concise, plain-text explanation. No markdown."
    return _call_with_fallback(prompt, key, system=system, json_mode=False).strip()


def gemini_repair(command: str, stdout: str, stderr: str, api_key: str | None = None) -> str:
    """Use Gemini to suggest a repair for a failed command."""
    key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not key:
        return ""
    prompt = (
        f"Command: {command}\n"
        f"Stdout:\n{stdout[:1000]}\n"
        f"Stderr:\n{stderr[:2000]}\n\n"
        "Suggest a corrected command or fix in 1-3 sentences. "
        "Do not suggest rm, sudo, or destructive operations."
    )
    system = "You are a shell expert. Give a concise, plain-text repair suggestion. No markdown."
    return _call_with_fallback(prompt, key, system=system, json_mode=False).strip()
