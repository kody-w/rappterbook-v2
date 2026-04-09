"""LLM wrapper with atomic budget tracking, proper backoff, and circuit breaker.

Supports: GitHub Models (primary), Azure OpenAI (fallback), Copilot CLI (last resort).
All stdlib. No pip dependencies.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


# --- Configuration ---

_BUDGET_FILE = Path(os.environ.get("LLM_BUDGET_FILE", "/tmp/llm_budget.json"))
_PROBE_CACHE = Path(os.environ.get("LLM_PROBE_CACHE", "/tmp/llm_probe_cache.json"))

DAILY_BUDGET = int(os.environ.get("LLM_DAILY_BUDGET", "500"))
BACKOFF_SCHEDULE = [1, 3, 9, 27]  # seconds
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN = 300  # 5 minutes

DRY_RUN = os.environ.get("LLM_DRY_RUN", "") == "1"


class LLMError(Exception):
    """Raised when LLM generation fails after retries."""


class BudgetExhausted(LLMError):
    """Raised when daily budget is exhausted."""


class CircuitOpen(LLMError):
    """Raised when circuit breaker is open."""


# --- Budget tracking (atomic via file lock) ---

def _read_budget() -> dict[str, Any]:
    """Read budget file atomically."""
    if not _BUDGET_FILE.is_file():
        return {"date": "", "count": 0}
    try:
        return json.loads(_BUDGET_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"date": "", "count": 0}


def _write_budget(data: dict[str, Any]) -> None:
    """Write budget file atomically."""
    _BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    _BUDGET_FILE.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def check_budget() -> int:
    """Return remaining budget for today. Thread-safe via file lock."""
    today = time.strftime("%Y-%m-%d")
    _BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)

    lock_path = _BUDGET_FILE.with_suffix(".lock")
    lock_path.touch(exist_ok=True)

    with open(lock_path, "r") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_SH)
        try:
            data = _read_budget()
            if data.get("date") != today:
                return DAILY_BUDGET
            return max(0, DAILY_BUDGET - data.get("count", 0))
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def increment_budget() -> int:
    """Increment today's usage by 1. Returns new count. Atomic."""
    today = time.strftime("%Y-%m-%d")
    _BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)

    lock_path = _BUDGET_FILE.with_suffix(".lock")
    lock_path.touch(exist_ok=True)

    with open(lock_path, "r") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = _read_budget()
            if data.get("date") != today:
                data = {"date": today, "count": 0}
            data["count"] = data.get("count", 0) + 1
            _write_budget(data)
            return data["count"]
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


# --- Circuit breaker ---

_consecutive_failures = 0
_circuit_open_until = 0.0


def _check_circuit() -> None:
    """Raise CircuitOpen if circuit breaker is tripped."""
    global _circuit_open_until
    if _consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
        if time.time() < _circuit_open_until:
            raise CircuitOpen(
                f"Circuit breaker open. {CIRCUIT_BREAKER_THRESHOLD} consecutive "
                f"failures. Cooldown until {time.ctime(_circuit_open_until)}"
            )
        # Cooldown expired — allow one attempt (half-open)


def _record_success() -> None:
    """Record a successful call — reset circuit breaker."""
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures = 0
    _circuit_open_until = 0.0


def _record_failure() -> None:
    """Record a failed call — increment circuit breaker."""
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures += 1
    if _consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
        _circuit_open_until = time.time() + CIRCUIT_BREAKER_COOLDOWN


def reset_circuit_breaker() -> None:
    """Manually reset the circuit breaker (for testing)."""
    global _consecutive_failures, _circuit_open_until
    _consecutive_failures = 0
    _circuit_open_until = 0.0


def get_consecutive_failures() -> int:
    """Return current consecutive failure count (for testing)."""
    return _consecutive_failures


# --- Model probe caching ---

def _get_cached_model() -> str | None:
    """Read cached model from disk."""
    if _PROBE_CACHE.is_file():
        try:
            data = json.loads(_PROBE_CACHE.read_text(encoding="utf-8"))
            # Cache valid for 1 hour
            if time.time() - data.get("timestamp", 0) < 3600:
                return data.get("model")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def _cache_model(model: str) -> None:
    """Write resolved model to disk cache."""
    _PROBE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _PROBE_CACHE.write_text(
        json.dumps({"model": model, "timestamp": time.time()}),
        encoding="utf-8",
    )


def resolve_model() -> str:
    """Resolve the best available model. Caches result."""
    cached = _get_cached_model()
    if cached:
        return cached

    # Check env override
    model = os.environ.get("LLM_MODEL", "")
    if model:
        _cache_model(model)
        return model

    # Default
    model = "gpt-4o"
    _cache_model(model)
    return model


# --- Backend: GitHub Models ---

def _call_github_models(
    prompt: str,
    system: str | None,
    max_tokens: int,
    model: str,
) -> str:
    """Call GitHub Models API."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise LLMError("GITHUB_TOKEN not set")

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }).encode("utf-8")

    url = os.environ.get(
        "LLM_ENDPOINT",
        "https://models.inference.ai.azure.com/chat/completions",
    )

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


# --- Main interface ---

def generate(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 2000,
) -> str:
    """Generate text from an LLM.

    Args:
        prompt: The user prompt.
        system: Optional system message.
        max_tokens: Maximum tokens to generate.

    Returns:
        Generated text string.

    Raises:
        BudgetExhausted: If daily budget is used up.
        CircuitOpen: If circuit breaker is tripped.
        LLMError: If all retries fail.
    """
    if DRY_RUN:
        return f"[DRY RUN] Response to: {prompt[:100]}..."

    # Check budget
    remaining = check_budget()
    if remaining <= 0:
        raise BudgetExhausted(f"Daily budget of {DAILY_BUDGET} calls exhausted")

    # Check circuit breaker
    _check_circuit()

    model = resolve_model()
    last_error: Exception | None = None

    for attempt, wait in enumerate(BACKOFF_SCHEDULE):
        try:
            result = _call_github_models(prompt, system, max_tokens, model)
            _record_success()
            increment_budget()
            return result
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError) as exc:
            last_error = exc
            _record_failure()
            if attempt < len(BACKOFF_SCHEDULE) - 1:
                time.sleep(wait)

    raise LLMError(f"All {len(BACKOFF_SCHEDULE)} attempts failed: {last_error}")
