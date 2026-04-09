"""Shared test fixtures for Rappterbook v2."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure scripts package is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Force test-safe defaults
os.environ["LLM_DRY_RUN"] = "1"
os.environ["LOCAL_MODE"] = "1"


@pytest.fixture
def tmp_state(tmp_path: Path) -> Path:
    """Create a temporary state directory with required subdirectories.

    Returns the path to the state directory.
    """
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "events").mkdir()
    (state_dir / "views").mkdir()
    (state_dir / "inbox").mkdir()

    # Write empty default views
    defaults = {
        "agents": {"agents": {}},
        "stats": {
            "total_agents": 0,
            "total_posts": 0,
            "total_comments": 0,
            "total_events": 0,
            "total_frames": 0,
        },
        "trending": {"trending": []},
        "recent_posts": {"posts": []},
        "recent_events": {"events": []},
        "seeds": {"seeds": {}},
    }
    for name, data in defaults.items():
        (state_dir / "views" / f"{name}.json").write_text(
            json.dumps(data), encoding="utf-8"
        )

    return state_dir


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    """Create a temporary docs directory."""
    d = tmp_path / "docs"
    d.mkdir()
    return d


@pytest.fixture
def sample_agents() -> dict:
    """Sample agents dict for testing."""
    return {
        "agents": {
            "agent-1": {
                "name": "Alice",
                "bio": "A philosopher agent",
                "framework": "gpt-4",
                "archetype": "philosopher",
                "interests": ["ethics", "logic"],
                "status": "active",
            },
            "agent-2": {
                "name": "Bob",
                "bio": "A builder agent",
                "framework": "claude",
                "archetype": "builder",
                "interests": ["code", "systems"],
                "status": "active",
            },
            "agent-3": {
                "name": "Charlie",
                "bio": "A dormant agent",
                "framework": "gpt-4",
                "archetype": "socialite",
                "interests": ["networking"],
                "status": "dormant",
            },
        }
    }


@pytest.fixture
def repo_root() -> Path:
    """Return the repo root path."""
    return REPO_ROOT


def write_event_file(
    state_dir: Path,
    frame: int,
    events: list[dict],
    timestamp_ms: int | None = None,
) -> Path:
    """Helper to write an event file for testing.

    Args:
        state_dir: State directory path.
        frame: Frame number.
        events: List of event dicts.
        timestamp_ms: Optional timestamp override.

    Returns:
        Path to the created event file.
    """
    import time

    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    frame_dir = state_dir / "events" / f"frame-{frame:06d}"
    frame_dir.mkdir(parents=True, exist_ok=True)

    event_file = frame_dir / f"{timestamp_ms}.json"
    event_file.write_text(
        json.dumps({
            "frame": frame,
            "timestamp_ms": timestamp_ms,
            "events": events,
        }),
        encoding="utf-8",
    )
    return event_file


def write_inbox_delta(
    state_dir: Path,
    agent_id: str,
    action: str,
    data: dict,
) -> Path:
    """Helper to write an inbox delta file for testing.

    Args:
        state_dir: State directory path.
        agent_id: Agent identifier.
        action: Action type.
        data: Action data.

    Returns:
        Path to the created delta file.
    """
    import time

    inbox_dir = state_dir / "inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time() * 1000)
    delta_file = inbox_dir / f"{agent_id}-{ts}.json"

    payload = {"action": action, "agent_id": agent_id}
    payload.update(data)

    delta_file.write_text(json.dumps(payload), encoding="utf-8")
    return delta_file
