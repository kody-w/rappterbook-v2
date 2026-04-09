"""Tests for scripts/state_client.py."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from scripts.state_client import StateClient
from tests.conftest import write_event_file


class TestStateClientInit:
    """Test StateClient initialization."""

    def test_default_state_dir(self) -> None:
        """StateClient uses default state dir when none given."""
        client = StateClient(local_mode=True)
        assert client.state_dir is not None

    def test_custom_state_dir(self, tmp_state: Path) -> None:
        """StateClient accepts a custom state dir."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        assert client.state_dir == tmp_state

    def test_local_mode_flag(self) -> None:
        """Local mode flag is stored correctly."""
        client = StateClient(local_mode=True)
        assert client.local_mode is True

    def test_remote_url_default(self) -> None:
        """Remote URL has a sensible default."""
        client = StateClient(local_mode=True)
        assert "rappterbook-v2-state" in client.remote_url


class TestReadView:
    """Test reading materialized views."""

    def test_read_existing_view(self, tmp_state: Path) -> None:
        """Reading an existing view returns its content."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = client.read_view("agents")
        assert "agents" in result

    def test_read_missing_view(self, tmp_state: Path) -> None:
        """Reading a missing view returns empty dict."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = client.read_view("nonexistent")
        assert result == {}

    def test_read_corrupt_view(self, tmp_state: Path) -> None:
        """Reading a corrupt view returns empty dict."""
        (tmp_state / "views" / "broken.json").write_text("not json!!!")
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = client.read_view("broken")
        assert result == {}

    def test_read_stats_view(self, tmp_state: Path) -> None:
        """Stats view has expected fields."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        stats = client.read_view("stats")
        assert "total_agents" in stats
        assert "total_events" in stats


class TestAppendEvents:
    """Test event writing."""

    def test_append_creates_frame_dir(self, tmp_state: Path) -> None:
        """Appending events creates the frame directory."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        client.append_events(1, [{"type": "test", "data": {}}])
        assert (tmp_state / "events" / "frame-000001").is_dir()

    def test_append_writes_valid_json(self, tmp_state: Path) -> None:
        """Appended events are valid JSON."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        path = client.append_events(1, [{"type": "test", "data": {}}])
        data = json.loads(path.read_text())
        assert data["frame"] == 1
        assert len(data["events"]) == 1

    def test_append_multiple_events(self, tmp_state: Path) -> None:
        """Multiple events in one batch are stored correctly."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        events = [
            {"type": "a", "data": {}},
            {"type": "b", "data": {}},
            {"type": "c", "data": {}},
        ]
        path = client.append_events(1, events)
        data = json.loads(path.read_text())
        assert len(data["events"]) == 3

    def test_append_has_timestamp(self, tmp_state: Path) -> None:
        """Appended events have a timestamp."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        path = client.append_events(1, [{"type": "test"}])
        data = json.loads(path.read_text())
        assert "timestamp_ms" in data
        assert isinstance(data["timestamp_ms"], int)

    def test_append_to_existing_frame(self, tmp_state: Path) -> None:
        """Multiple appends to the same frame create separate files."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        client.append_events(5, [{"type": "first"}])
        time.sleep(0.01)  # Ensure different timestamp
        client.append_events(5, [{"type": "second"}])
        frame_dir = tmp_state / "events" / "frame-000005"
        files = list(frame_dir.glob("*.json"))
        assert len(files) == 2


class TestReadEvents:
    """Test event reading."""

    def test_read_events_empty_frame(self, tmp_state: Path) -> None:
        """Reading events for a nonexistent frame returns empty list."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        assert client.read_events(999) == []

    def test_read_events_existing_frame(self, tmp_state: Path) -> None:
        """Reading events for an existing frame returns them."""
        write_event_file(tmp_state, 1, [{"type": "test"}])
        client = StateClient(state_dir=tmp_state, local_mode=True)
        events = client.read_events(1)
        assert len(events) == 1
        assert events[0]["events"][0]["type"] == "test"


class TestGetLatestFrame:
    """Test frame number tracking."""

    def test_no_frames(self, tmp_state: Path) -> None:
        """No frames returns 0."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        assert client.get_latest_frame() == 0

    def test_single_frame(self, tmp_state: Path) -> None:
        """Single frame returns its number."""
        write_event_file(tmp_state, 42, [{"type": "test"}])
        client = StateClient(state_dir=tmp_state, local_mode=True)
        assert client.get_latest_frame() == 42

    def test_multiple_frames(self, tmp_state: Path) -> None:
        """Multiple frames returns the highest."""
        write_event_file(tmp_state, 1, [{"type": "a"}], timestamp_ms=1000)
        write_event_file(tmp_state, 10, [{"type": "b"}], timestamp_ms=2000)
        write_event_file(tmp_state, 5, [{"type": "c"}], timestamp_ms=3000)
        client = StateClient(state_dir=tmp_state, local_mode=True)
        assert client.get_latest_frame() == 10


class TestHealth:
    """Test health read/write."""

    def test_get_health_default(self, tmp_state: Path) -> None:
        """Default health returns unknown status."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        health = client.get_health()
        assert health["status"] == "unknown"

    def test_write_and_read_health(self, tmp_state: Path) -> None:
        """Written health is readable."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        client.write_health({"status": "healthy", "total_events": 42})
        health = client.get_health()
        assert health["status"] == "healthy"
        assert health["total_events"] == 42


class TestLocalMode:
    """Test local mode behavior."""

    def test_sync_noop(self, tmp_state: Path) -> None:
        """Sync is a no-op in local mode."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        client.sync()  # Should not raise

    def test_push_returns_true(self, tmp_state: Path) -> None:
        """Push returns True in local mode."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        assert client.push() is True

    def test_commit_returns_true(self, tmp_state: Path) -> None:
        """Commit returns True in local mode."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        assert client.commit("test") is True

    def test_clone_or_pull_creates_dir(self, tmp_path: Path) -> None:
        """Clone or pull in local mode creates the directory."""
        state_dir = tmp_path / "new_state"
        client = StateClient(state_dir=state_dir, local_mode=True)
        client.clone_or_pull()
        assert state_dir.is_dir()


class TestListViews:
    """Test view listing."""

    def test_list_views(self, tmp_state: Path) -> None:
        """Lists all available view names."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        views = client.list_views()
        assert "agents" in views
        assert "stats" in views
        assert "trending" in views
