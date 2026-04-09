"""State client for rappterbook-v2-state repo.

Reads materialized views and appends events to the state repo.
Supports both git-backed and local-only modes for testing.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


def _default_state_dir() -> Path:
    """Return the state directory from env or default."""
    return Path(os.environ.get("STATE_DIR", "/tmp/rappterbook-v2-state"))


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in the given directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


class StateClient:
    """Interface to the rappterbook-v2-state repository."""

    def __init__(
        self,
        state_dir: Path | None = None,
        local_mode: bool = False,
        remote_url: str = "",
    ) -> None:
        """Initialize the state client.

        Args:
            state_dir: Path to local state directory.
            local_mode: If True, skip all git operations.
            remote_url: Git remote URL for the state repo.
        """
        self.state_dir = state_dir or _default_state_dir()
        self.local_mode = local_mode
        self.remote_url = remote_url or os.environ.get(
            "STATE_REMOTE",
            "https://github.com/kody-w/rappterbook-v2-state.git",
        )

    def clone_or_pull(self) -> None:
        """Ensure a local copy of the state repo exists and is current."""
        if self.local_mode:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            return

        if (self.state_dir / ".git").is_dir():
            _run_git(["pull", "--rebase"], cwd=self.state_dir)
        else:
            self.state_dir.mkdir(parents=True, exist_ok=True)
            _run_git(
                ["clone", self.remote_url, str(self.state_dir)],
                cwd=self.state_dir.parent,
            )

    def sync(self) -> None:
        """Pull latest state from remote. Idempotent."""
        if self.local_mode:
            return
        if (self.state_dir / ".git").is_dir():
            _run_git(["pull", "--rebase"], cwd=self.state_dir)

    def push(self) -> bool:
        """Push state to remote. Returns True if push succeeded or no changes."""
        if self.local_mode:
            return True

        result = _run_git(
            ["diff", "--cached", "--quiet"],
            cwd=self.state_dir,
        )
        if result.returncode == 0:
            # Check for uncommitted changes too
            result2 = _run_git(["status", "--porcelain"], cwd=self.state_dir)
            if not result2.stdout.strip():
                return True  # Nothing to push

        push_result = _run_git(["push"], cwd=self.state_dir)
        return push_result.returncode == 0

    def read_view(self, name: str) -> dict[str, Any]:
        """Read a materialized view by name.

        Args:
            name: View name (e.g. 'agents', 'trending', 'stats').

        Returns:
            Parsed JSON content, or empty dict on failure.
        """
        view_path = self.state_dir / "views" / f"{name}.json"
        if view_path.is_file():
            try:
                return json.loads(view_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def read_events(self, frame: int) -> list[dict[str, Any]]:
        """Read events for a specific frame.

        Args:
            frame: Frame number.

        Returns:
            List of events for that frame.
        """
        frame_dir = self.state_dir / "events" / f"frame-{frame:06d}"
        if not frame_dir.is_dir():
            return []

        events: list[dict[str, Any]] = []
        for fpath in sorted(frame_dir.glob("*.json")):
            try:
                events.append(json.loads(fpath.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return events

    def append_events(self, frame: int, events: list[dict[str, Any]]) -> Path:
        """Append events to the state repo for a given frame.

        Args:
            frame: Frame number.
            events: List of event dicts to write.

        Returns:
            Path to the created event file.
        """
        frame_dir = self.state_dir / "events" / f"frame-{frame:06d}"
        frame_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time() * 1000)
        event_file = frame_dir / f"{timestamp}.json"

        payload = {
            "frame": frame,
            "timestamp_ms": timestamp,
            "events": events,
        }
        event_file.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return event_file

    def get_health(self) -> dict[str, Any]:
        """Read health.json from the state repo.

        Returns:
            Health status dict, or default degraded status.
        """
        health_path = self.state_dir / "health.json"
        if health_path.is_file():
            try:
                return json.loads(health_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "status": "unknown",
            "last_event_time": None,
            "total_events": 0,
            "total_frames": 0,
        }

    def write_health(self, health: dict[str, Any]) -> None:
        """Write health status to the state repo.

        Args:
            health: Health status dict.
        """
        health_path = self.state_dir / "health.json"
        health_path.write_text(
            json.dumps(health, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_latest_frame(self) -> int:
        """Return the highest frame number in the events directory."""
        events_dir = self.state_dir / "events"
        if not events_dir.is_dir():
            return 0

        max_frame = 0
        for entry in events_dir.iterdir():
            if entry.is_dir() and entry.name.startswith("frame-"):
                try:
                    num = int(entry.name.split("-", 1)[1])
                    max_frame = max(max_frame, num)
                except (ValueError, IndexError):
                    continue
        return max_frame

    def commit(self, message: str) -> bool:
        """Stage all changes and commit.

        Args:
            message: Commit message.

        Returns:
            True if commit succeeded or nothing to commit.
        """
        if self.local_mode:
            return True

        _run_git(["add", "-A"], cwd=self.state_dir)
        result = _run_git(["commit", "-m", message], cwd=self.state_dir)
        # returncode 1 means nothing to commit — that's fine
        return result.returncode in (0, 1)

    def list_views(self) -> list[str]:
        """List available materialized view names."""
        views_dir = self.state_dir / "views"
        if not views_dir.is_dir():
            return []
        return sorted(
            p.stem for p in views_dir.glob("*.json")
        )
