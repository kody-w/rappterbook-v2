"""Tests for scripts/health.py."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.health import (
    DEGRADED_THRESHOLD,
    HEALTHY_THRESHOLD,
    STALE_THRESHOLD,
    build_health_report,
    check_integrity,
    compute_status,
    count_events,
    count_frames,
    get_last_event_time,
    ping_external,
    run_health_check,
    write_health_json,
)
from tests.conftest import write_event_file


class TestComputeStatus:
    """Test status computation from age."""

    def test_healthy(self) -> None:
        """Recent events produce healthy status."""
        assert compute_status(60) == "healthy"  # 1 minute

    def test_stale(self) -> None:
        """Events 3 hours old produce stale status."""
        assert compute_status(3 * 3600) == "stale"

    def test_degraded(self) -> None:
        """Events 12 hours old produce degraded status."""
        assert compute_status(12 * 3600) == "degraded"

    def test_dead(self) -> None:
        """Events 48 hours old produce dead status."""
        assert compute_status(48 * 3600) == "dead"

    def test_unknown(self) -> None:
        """None age produces unknown status."""
        assert compute_status(None) == "unknown"

    def test_boundary_healthy(self) -> None:
        """Just under healthy threshold is healthy."""
        assert compute_status(HEALTHY_THRESHOLD - 1) == "healthy"

    def test_boundary_stale(self) -> None:
        """At stale threshold is stale."""
        assert compute_status(HEALTHY_THRESHOLD + 1) == "stale"

    def test_boundary_degraded(self) -> None:
        """At degraded threshold is degraded."""
        assert compute_status(STALE_THRESHOLD + 1) == "degraded"

    def test_boundary_dead(self) -> None:
        """Past degraded threshold is dead."""
        assert compute_status(DEGRADED_THRESHOLD + 1) == "dead"


class TestCountEvents:
    """Test event counting."""

    def test_no_events(self, tmp_state: Path) -> None:
        """Empty events directory returns 0."""
        assert count_events(tmp_state) == 0

    def test_single_event(self, tmp_state: Path) -> None:
        """Single event is counted."""
        write_event_file(tmp_state, 1, [{"type": "test"}])
        assert count_events(tmp_state) == 1

    def test_multiple_events(self, tmp_state: Path) -> None:
        """Multiple events across frames are counted."""
        write_event_file(tmp_state, 1, [{"type": "a"}, {"type": "b"}], timestamp_ms=1000)
        write_event_file(tmp_state, 2, [{"type": "c"}], timestamp_ms=2000)
        assert count_events(tmp_state) == 3

    def test_no_events_dir(self, tmp_path: Path) -> None:
        """Missing events directory returns 0."""
        assert count_events(tmp_path) == 0


class TestCountFrames:
    """Test frame counting."""

    def test_no_frames(self, tmp_state: Path) -> None:
        """Empty events directory returns 0."""
        assert count_frames(tmp_state) == 0

    def test_single_frame(self, tmp_state: Path) -> None:
        """Single frame is counted."""
        write_event_file(tmp_state, 1, [{"type": "test"}])
        assert count_frames(tmp_state) == 1

    def test_multiple_frames(self, tmp_state: Path) -> None:
        """Multiple frames are counted."""
        write_event_file(tmp_state, 1, [{"type": "a"}], timestamp_ms=1000)
        write_event_file(tmp_state, 2, [{"type": "b"}], timestamp_ms=2000)
        write_event_file(tmp_state, 3, [{"type": "c"}], timestamp_ms=3000)
        assert count_frames(tmp_state) == 3


class TestGetLastEventTime:
    """Test last event time detection."""

    def test_no_events(self, tmp_state: Path) -> None:
        """No events returns None."""
        assert get_last_event_time(tmp_state) is None

    def test_single_event(self, tmp_state: Path) -> None:
        """Single event returns its timestamp."""
        ts = int(time.time() * 1000)
        write_event_file(tmp_state, 1, [{"type": "test"}], timestamp_ms=ts)
        result = get_last_event_time(tmp_state)
        assert result is not None
        assert abs(result - ts / 1000.0) < 1

    def test_latest_across_frames(self, tmp_state: Path) -> None:
        """Returns the latest timestamp across frames."""
        write_event_file(tmp_state, 1, [{"type": "old"}], timestamp_ms=1000000)
        write_event_file(tmp_state, 10, [{"type": "new"}], timestamp_ms=9999000)
        result = get_last_event_time(tmp_state)
        assert result is not None
        assert result == 9999.0


class TestCheckIntegrity:
    """Test integrity checking."""

    def test_empty_is_ok(self, tmp_state: Path) -> None:
        """Empty state passes integrity check."""
        result = check_integrity(tmp_state)
        assert result["ok"] is True

    def test_valid_event_passes(self, tmp_state: Path) -> None:
        """Valid event file passes."""
        write_event_file(tmp_state, 1, [{"type": "test"}])
        result = check_integrity(tmp_state)
        assert result["ok"] is True

    def test_corrupt_json_fails(self, tmp_state: Path) -> None:
        """Corrupt JSON is flagged."""
        frame_dir = tmp_state / "events" / "frame-000001"
        frame_dir.mkdir(parents=True)
        (frame_dir / "bad.json").write_text("not json!!!")
        result = check_integrity(tmp_state)
        assert result["ok"] is False
        assert len(result["issues"]) > 0

    def test_missing_events_key(self, tmp_state: Path) -> None:
        """Event file without 'events' key is flagged."""
        frame_dir = tmp_state / "events" / "frame-000001"
        frame_dir.mkdir(parents=True)
        (frame_dir / "1000.json").write_text(json.dumps({"frame": 1}))
        result = check_integrity(tmp_state)
        assert result["ok"] is False


class TestBuildHealthReport:
    """Test full health report generation."""

    def test_report_structure(self, tmp_state: Path) -> None:
        """Report has all required fields."""
        report = build_health_report(tmp_state)
        assert "status" in report
        assert "total_events" in report
        assert "total_frames" in report
        assert "integrity" in report
        assert "checked_at" in report

    def test_healthy_report(self, tmp_state: Path) -> None:
        """Recent events produce healthy report."""
        ts = int(time.time() * 1000)
        write_event_file(tmp_state, 1, [{"type": "test"}], timestamp_ms=ts)
        report = build_health_report(tmp_state)
        assert report["status"] == "healthy"


class TestWriteHealthJson:
    """Test health JSON file writing."""

    def test_writes_file(self, tmp_path: Path) -> None:
        """Writes a valid JSON file."""
        output = tmp_path / "health.json"
        write_health_json({"status": "healthy"}, output)
        assert output.is_file()
        data = json.loads(output.read_text())
        assert data["status"] == "healthy"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Creates parent directories if needed."""
        output = tmp_path / "deep" / "nested" / "health.json"
        write_health_json({"status": "ok"}, output)
        assert output.is_file()


class TestPingExternal:
    """Test external health pinging."""

    def test_empty_url(self) -> None:
        """Empty URL returns False."""
        assert ping_external("", "healthy") is False

    @patch("scripts.health.urllib.request.urlopen")
    def test_successful_ping(self, mock_urlopen: MagicMock) -> None:
        """Successful ping returns True."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        assert ping_external("https://hc.example.com/ping/abc", "healthy") is True

    @patch("scripts.health.urllib.request.urlopen")
    def test_failed_ping(self, mock_urlopen: MagicMock) -> None:
        """Network error returns False."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("network error")
        assert ping_external("https://hc.example.com/ping/abc", "healthy") is False


class TestRunHealthCheck:
    """Test the combined health check function."""

    def test_returns_report(self, tmp_state: Path) -> None:
        """Returns a health report."""
        report = run_health_check(tmp_state)
        assert "status" in report

    def test_writes_output(self, tmp_state: Path, tmp_path: Path) -> None:
        """Writes output file when path specified."""
        output = tmp_path / "out" / "health.json"
        run_health_check(tmp_state, output_path=output)
        assert output.is_file()
