"""Tests for scripts/orchestrator.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.orchestrator import (
    Config,
    step_commit_and_push,
    step_compute_trending,
    step_health_check,
    step_health_update,
    step_materialize,
    step_process_inbox,
    step_reconcile,
    step_run_frame,
    tick,
)
from scripts.state_client import StateClient
from tests.conftest import write_inbox_delta


class TestConfig:
    """Test configuration defaults."""

    def test_default_config(self) -> None:
        """Default config has sensible values."""
        config = Config()
        assert config.max_agents_per_frame == 10
        assert isinstance(config.skip_steps, list)

    def test_custom_state_dir(self, tmp_path: Path) -> None:
        """Custom state dir is accepted."""
        config = Config(state_dir=tmp_path)
        assert config.state_dir == tmp_path

    def test_dry_run_flag(self) -> None:
        """Dry run flag defaults from env."""
        config = Config(dry_run=True)
        assert config.dry_run is True

    def test_skip_steps(self) -> None:
        """Skip steps list is configurable."""
        config = Config(skip_steps=["run_frame", "compute_trending"])
        assert "run_frame" in config.skip_steps


class TestStepHealthCheck:
    """Test step 1: health check."""

    def test_returns_health(self, tmp_state: Path) -> None:
        """Health check returns health dict."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        health = step_health_check(client, config)
        assert isinstance(health, dict)


class TestStepProcessInbox:
    """Test step 2: inbox processing."""

    def test_empty_inbox(self, tmp_state: Path) -> None:
        """Empty inbox returns no events."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        events = step_process_inbox(client, config)
        assert events == []

    def test_process_register_action(self, tmp_state: Path) -> None:
        """Register action in inbox produces event."""
        write_inbox_delta(tmp_state, "agent-1", "register_agent", {
            "name": "Test Agent",
            "framework": "gpt-4",
            "bio": "A test agent",
        })
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        events = step_process_inbox(client, config)
        assert len(events) == 1
        assert events[0]["type"] == "agent.registered"

    def test_processed_files_removed(self, tmp_state: Path) -> None:
        """Processed inbox files are deleted."""
        write_inbox_delta(tmp_state, "agent-1", "register_agent", {
            "name": "Test", "framework": "gpt", "bio": "hi"
        })
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        step_process_inbox(client, config)
        inbox = tmp_state / "inbox"
        remaining = list(inbox.glob("*.json"))
        assert len(remaining) == 0

    def test_invalid_action_skipped(self, tmp_state: Path) -> None:
        """Invalid action type is skipped without crash."""
        write_inbox_delta(tmp_state, "agent-1", "nonexistent_action", {})
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        events = step_process_inbox(client, config)
        assert events == []

    def test_corrupt_json_skipped(self, tmp_state: Path) -> None:
        """Corrupt JSON files are skipped."""
        inbox = tmp_state / "inbox"
        (inbox / "bad.json").write_text("not json!!!")
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        events = step_process_inbox(client, config)
        assert events == []

    def test_no_inbox_dir(self, tmp_state: Path) -> None:
        """Missing inbox directory returns empty."""
        import shutil
        shutil.rmtree(tmp_state / "inbox")
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        events = step_process_inbox(client, config)
        assert events == []


class TestStepRunFrame:
    """Test step 3: frame execution."""

    def test_returns_frame_result(self, tmp_state: Path) -> None:
        """Run frame returns result with events."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        result = step_run_frame(client, config)
        assert "frame" in result
        assert "events" in result


class TestStepMaterialize:
    """Test step 4: view materialization."""

    def test_creates_views_dir(self, tmp_state: Path) -> None:
        """Materialize creates views directory."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        step_materialize(client, [], config)
        assert (tmp_state / "views").is_dir()

    def test_agent_registered_updates_view(self, tmp_state: Path) -> None:
        """Agent registration event updates agents view."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        events = [{
            "type": "agent.registered",
            "data": {
                "agent_id": "new-agent",
                "name": "New Agent",
                "status": "active",
            },
        }]
        step_materialize(client, events, config)
        agents = client.read_view("agents")
        assert "new-agent" in agents["agents"]

    def test_stats_counter_increments(self, tmp_state: Path) -> None:
        """Stats counters increment on events."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        events = [
            {"type": "agent.registered", "data": {"agent_id": "a1"}},
            {"type": "agent.registered", "data": {"agent_id": "a2"}},
        ]
        step_materialize(client, events, config)
        stats = client.read_view("stats")
        assert stats["total_agents"] == 2

    def test_empty_events_noop(self, tmp_state: Path) -> None:
        """Empty event list doesn't crash."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        step_materialize(client, [], config)


class TestStepComputeTrending:
    """Test step 5: trending computation."""

    def test_creates_trending_file(self, tmp_state: Path) -> None:
        """Trending step ensures trending.json exists."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        step_compute_trending(client, config)
        assert (tmp_state / "views" / "trending.json").is_file()


class TestStepReconcile:
    """Test step 6: state reconciliation."""

    def test_returns_ok(self, tmp_state: Path) -> None:
        """Reconcile returns ok status."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        result = step_reconcile(client, config)
        assert result["ok"] is True

    def test_creates_directories(self, tmp_state: Path) -> None:
        """Reconcile creates required directories."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True)
        step_reconcile(client, config)
        assert (tmp_state / "views").is_dir()
        assert (tmp_state / "events").is_dir()


class TestStepHealthUpdate:
    """Test step 7: health update."""

    def test_returns_report(self, tmp_state: Path, docs_dir: Path) -> None:
        """Health update returns a report."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True, docs_dir=docs_dir)
        report = step_health_update(client, config)
        assert "status" in report

    def test_writes_to_docs(self, tmp_state: Path, docs_dir: Path) -> None:
        """Health update writes health.json to docs."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, local_mode=True, docs_dir=docs_dir)
        step_health_update(client, config)
        assert (docs_dir / "health.json").is_file()


class TestStepCommitAndPush:
    """Test step 8: commit and push."""

    def test_dry_run_noop(self, tmp_state: Path) -> None:
        """Dry run returns True without doing anything."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        config = Config(state_dir=tmp_state, dry_run=True)
        assert step_commit_and_push(client, 1, config) is True


class TestTick:
    """Test the full tick cycle."""

    def test_tick_succeeds(self, tmp_state: Path, docs_dir: Path) -> None:
        """Full tick completes successfully."""
        config = Config(
            state_dir=tmp_state,
            local_mode=True,
            dry_run=True,
            docs_dir=docs_dir,
        )
        result = tick(config)
        assert result["success"] is True

    def test_tick_runs_all_steps(self, tmp_state: Path, docs_dir: Path) -> None:
        """Tick runs all steps."""
        config = Config(
            state_dir=tmp_state,
            local_mode=True,
            dry_run=True,
            docs_dir=docs_dir,
        )
        result = tick(config)
        assert "health_check" in result["steps"]
        assert "process_inbox" in result["steps"]
        assert "run_frame" in result["steps"]
        assert "materialize" in result["steps"]

    def test_tick_with_skip_steps(self, tmp_state: Path, docs_dir: Path) -> None:
        """Skipped steps are not run."""
        config = Config(
            state_dir=tmp_state,
            local_mode=True,
            dry_run=True,
            docs_dir=docs_dir,
            skip_steps=["run_frame", "compute_trending"],
        )
        result = tick(config)
        assert "run_frame" not in result["steps"]
        assert "compute_trending" not in result["steps"]

    def test_tick_has_timestamps(self, tmp_state: Path, docs_dir: Path) -> None:
        """Tick result includes timestamps."""
        config = Config(
            state_dir=tmp_state,
            local_mode=True,
            dry_run=True,
            docs_dir=docs_dir,
        )
        result = tick(config)
        assert "started_at" in result
        assert "completed_at" in result

    def test_tick_with_inbox_events(self, tmp_state: Path, docs_dir: Path) -> None:
        """Tick processes inbox events."""
        write_inbox_delta(tmp_state, "agent-1", "register_agent", {
            "name": "Test", "framework": "gpt", "bio": "hi"
        })
        config = Config(
            state_dir=tmp_state,
            local_mode=True,
            dry_run=True,
            docs_dir=docs_dir,
        )
        result = tick(config)
        assert result["success"] is True
        assert result["steps"]["process_inbox"]["events_count"] == 1

    def test_tick_health_runs_on_failure(self, tmp_state: Path, docs_dir: Path) -> None:
        """Health update runs even if earlier step fails."""
        config = Config(
            state_dir=tmp_state,
            local_mode=True,
            dry_run=True,
            docs_dir=docs_dir,
        )
        # Force a failure by making process_inbox raise
        with patch("scripts.orchestrator.step_process_inbox", side_effect=Exception("boom")):
            result = tick(config)
            assert result["success"] is False
            assert "error" in result
