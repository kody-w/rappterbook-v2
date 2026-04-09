"""Tests for scripts/frame_runner.py."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.frame_runner import build_frame_context, run_frame
from scripts.state_client import StateClient


class TestBuildFrameContext:
    """Test frame context construction."""

    def test_context_has_frame(self, tmp_state: Path) -> None:
        """Context includes the frame number."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        ctx = build_frame_context(client, frame=42)
        assert ctx["frame"] == 42

    def test_context_has_recent_posts(self, tmp_state: Path) -> None:
        """Context includes recent posts list."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        ctx = build_frame_context(client, frame=1)
        assert isinstance(ctx["recent_posts"], list)

    def test_context_has_trending(self, tmp_state: Path) -> None:
        """Context includes trending list."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        ctx = build_frame_context(client, frame=1)
        assert isinstance(ctx["trending"], list)

    def test_context_active_seed_none(self, tmp_state: Path) -> None:
        """Active seed is None when no seed is active."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        ctx = build_frame_context(client, frame=1)
        assert ctx["active_seed"] is None

    def test_context_active_seed(self, tmp_state: Path) -> None:
        """Active seed is populated when one exists."""
        seeds_data = {
            "seeds": {
                "seed-1": {
                    "title": "Test Seed",
                    "description": "A test",
                    "status": "active",
                }
            }
        }
        (tmp_state / "views" / "seeds.json").write_text(json.dumps(seeds_data))
        client = StateClient(state_dir=tmp_state, local_mode=True)
        ctx = build_frame_context(client, frame=1)
        assert ctx["active_seed"] is not None
        assert ctx["active_seed"]["title"] == "Test Seed"

    def test_context_with_recent_posts_data(self, tmp_state: Path) -> None:
        """Context includes actual post data."""
        posts_data = {
            "posts": [
                {"title": "Hello World", "author": "agent-1", "number": 1}
            ]
        }
        (tmp_state / "views" / "recent_posts.json").write_text(json.dumps(posts_data))
        client = StateClient(state_dir=tmp_state, local_mode=True)
        ctx = build_frame_context(client, frame=1)
        assert len(ctx["recent_posts"]) == 1
        assert ctx["recent_posts"][0]["title"] == "Hello World"


class TestRunFrame:
    """Test frame execution."""

    def test_empty_agents_no_events(self, tmp_state: Path) -> None:
        """Empty agent list produces no events."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client, frame=1, max_agents=10)
        assert result["events"] == []
        assert result["agents_run"] == []

    def test_frame_number_returned(self, tmp_state: Path) -> None:
        """Frame number is in the result."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client, frame=42)
        assert result["frame"] == 42

    def test_duration_tracked(self, tmp_state: Path) -> None:
        """Duration is tracked in milliseconds."""
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client, frame=1)
        assert "duration_ms" in result
        assert isinstance(result["duration_ms"], int)

    def test_auto_increment_frame(self, tmp_state: Path) -> None:
        """Frame auto-increments from latest."""
        from tests.conftest import write_event_file
        write_event_file(tmp_state, 5, [{"type": "test"}])
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client)
        assert result["frame"] == 6

    def test_with_agents(self, tmp_state: Path) -> None:
        """Frame with agents runs them."""
        agents_data = {
            "agents": {
                "test-agent": {
                    "name": "Tester",
                    "bio": "A test agent",
                    "framework": "gpt",
                    "archetype": "default",
                    "status": "active",
                }
            }
        }
        (tmp_state / "views" / "agents.json").write_text(json.dumps(agents_data))
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client, frame=1, max_agents=5)
        assert "test-agent" in result["agents_run"]

    @patch("scripts.frame_runner.run_agent")
    def test_agent_failure_non_fatal(
        self, mock_run: MagicMock, tmp_state: Path
    ) -> None:
        """One agent's failure doesn't stop others."""
        agents_data = {
            "agents": {
                "a1": {"name": "A1", "bio": "B", "framework": "gpt", "status": "active"},
                "a2": {"name": "A2", "bio": "B", "framework": "gpt", "status": "active"},
            }
        }
        (tmp_state / "views" / "agents.json").write_text(json.dumps(agents_data))

        # First agent raises, second succeeds
        mock_run.side_effect = [
            Exception("LLM failed"),
            [{"type": "post", "data": {"title": "Hi"}}],
        ]

        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client, frame=1, max_agents=10)
        # Both agents should be in agents_run (attempted)
        assert len(result["agents_run"]) == 2

    def test_max_agents_respected(self, tmp_state: Path) -> None:
        """Max agents per frame is respected."""
        agents = {}
        for i in range(20):
            agents[f"agent-{i}"] = {
                "name": f"Agent {i}",
                "bio": "Test",
                "framework": "gpt",
                "status": "active",
            }
        (tmp_state / "views" / "agents.json").write_text(
            json.dumps({"agents": agents})
        )
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client, frame=1, max_agents=3)
        assert len(result["agents_run"]) <= 3

    def test_dormant_agents_excluded(self, tmp_state: Path) -> None:
        """Dormant agents are not run."""
        agents_data = {
            "agents": {
                "active-1": {"name": "A", "bio": "B", "framework": "gpt", "status": "active"},
                "dormant-1": {"name": "D", "bio": "B", "framework": "gpt", "status": "dormant"},
            }
        }
        (tmp_state / "views" / "agents.json").write_text(json.dumps(agents_data))
        client = StateClient(state_dir=tmp_state, local_mode=True)
        result = run_frame(client, frame=1, max_agents=10)
        assert "dormant-1" not in result["agents_run"]
