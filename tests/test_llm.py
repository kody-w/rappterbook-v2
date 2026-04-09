"""Tests for scripts/llm.py."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# Set dry run before importing
os.environ["LLM_DRY_RUN"] = "1"

from scripts.llm import (
    BACKOFF_SCHEDULE,
    BudgetExhausted,
    CircuitOpen,
    LLMError,
    check_budget,
    generate,
    get_consecutive_failures,
    increment_budget,
    reset_circuit_breaker,
    resolve_model,
)


class TestDryRun:
    """Test dry run mode."""

    def test_dry_run_returns_placeholder(self) -> None:
        """Dry run returns a placeholder string."""
        result = generate("Hello world")
        assert "[DRY RUN]" in result

    def test_dry_run_includes_prompt_snippet(self) -> None:
        """Dry run includes part of the prompt."""
        result = generate("Test prompt about quantum physics")
        assert "Test prompt" in result

    def test_dry_run_with_system(self) -> None:
        """Dry run works with system message."""
        result = generate("Hello", system="Be helpful")
        assert "[DRY RUN]" in result


class TestBudget:
    """Test budget tracking."""

    def test_check_budget_fresh_day(self, tmp_path: Path) -> None:
        """Fresh day has full budget."""
        budget_file = tmp_path / "budget.json"
        with patch("scripts.llm._BUDGET_FILE", budget_file):
            remaining = check_budget()
            assert remaining > 0

    def test_increment_budget(self, tmp_path: Path) -> None:
        """Incrementing budget increases count."""
        budget_file = tmp_path / "budget.json"
        with patch("scripts.llm._BUDGET_FILE", budget_file):
            count1 = increment_budget()
            count2 = increment_budget()
            assert count2 == count1 + 1

    def test_budget_resets_daily(self, tmp_path: Path) -> None:
        """Budget resets when date changes."""
        budget_file = tmp_path / "budget.json"
        # Write yesterday's data
        budget_file.write_text(json.dumps({
            "date": "1999-01-01",
            "count": 999,
        }))
        with patch("scripts.llm._BUDGET_FILE", budget_file):
            remaining = check_budget()
            assert remaining > 0  # Reset because date changed

    def test_budget_enforcement(self, tmp_path: Path) -> None:
        """Budget of 0 raises BudgetExhausted."""
        budget_file = tmp_path / "budget.json"
        today = time.strftime("%Y-%m-%d")
        budget_file.write_text(json.dumps({
            "date": today,
            "count": 99999,
        }))
        with patch("scripts.llm._BUDGET_FILE", budget_file):
            with patch("scripts.llm.DRY_RUN", False):
                with pytest.raises(BudgetExhausted):
                    generate("test")


class TestCircuitBreaker:
    """Test circuit breaker behavior."""

    def setup_method(self) -> None:
        """Reset circuit breaker before each test."""
        reset_circuit_breaker()

    def test_initial_state(self) -> None:
        """Circuit breaker starts with 0 failures."""
        assert get_consecutive_failures() == 0

    def test_reset(self) -> None:
        """Reset clears the circuit breaker."""
        reset_circuit_breaker()
        assert get_consecutive_failures() == 0

    def test_circuit_opens_after_threshold(self) -> None:
        """Circuit opens after 3 consecutive failures."""
        from scripts.llm import _record_failure, _check_circuit

        for _ in range(3):
            _record_failure()

        with pytest.raises(CircuitOpen):
            _check_circuit()

    def test_circuit_closed_below_threshold(self) -> None:
        """Circuit stays closed below threshold."""
        from scripts.llm import _record_failure, _check_circuit

        _record_failure()
        _record_failure()
        _check_circuit()  # Should not raise


class TestBackoff:
    """Test backoff schedule."""

    def test_backoff_progression(self) -> None:
        """Backoff follows 1, 3, 9, 27 pattern."""
        assert BACKOFF_SCHEDULE == [1, 3, 9, 27]

    def test_four_retries(self) -> None:
        """There are 4 retry attempts."""
        assert len(BACKOFF_SCHEDULE) == 4


class TestModelResolution:
    """Test model probe caching."""

    def test_resolve_model_returns_string(self, tmp_path: Path) -> None:
        """Resolved model is a string."""
        cache = tmp_path / "probe.json"
        with patch("scripts.llm._PROBE_CACHE", cache):
            model = resolve_model()
            assert isinstance(model, str)
            assert len(model) > 0

    def test_resolve_model_caches(self, tmp_path: Path) -> None:
        """Second resolution reads from cache."""
        cache = tmp_path / "probe.json"
        with patch("scripts.llm._PROBE_CACHE", cache):
            model1 = resolve_model()
            model2 = resolve_model()
            assert model1 == model2

    def test_resolve_model_env_override(self, tmp_path: Path) -> None:
        """LLM_MODEL env var overrides probe."""
        cache = tmp_path / "probe.json"
        with patch("scripts.llm._PROBE_CACHE", cache):
            with patch.dict(os.environ, {"LLM_MODEL": "custom-model"}):
                model = resolve_model()
                assert model == "custom-model"


class TestGenerate:
    """Test the generate function."""

    def test_generate_returns_string(self) -> None:
        """Generate returns a string."""
        result = generate("test")
        assert isinstance(result, str)

    def test_generate_not_empty(self) -> None:
        """Generate returns non-empty string."""
        result = generate("test")
        assert len(result) > 0
