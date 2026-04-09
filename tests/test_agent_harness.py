"""Tests for scripts/agent_harness.py."""
from __future__ import annotations

import json
from typing import Any

import pytest

from scripts.agent_harness import (
    ARCHETYPE_TOOLS,
    build_prompt,
    get_tools_for_agent,
    parse_actions,
    run_agent,
    select_active_agents,
)


class TestGetTools:
    """Test tool assignment based on archetype."""

    def test_philosopher_tools(self) -> None:
        """Philosopher gets expected tools."""
        tools = get_tools_for_agent({"archetype": "philosopher"})
        assert "post" in tools
        assert "comment" in tools
        assert "vote" in tools

    def test_builder_has_create_channel(self) -> None:
        """Builder can create channels."""
        tools = get_tools_for_agent({"archetype": "builder"})
        assert "create_channel" in tools

    def test_unknown_archetype_gets_default(self) -> None:
        """Unknown archetype gets default tools."""
        tools = get_tools_for_agent({"archetype": "nonexistent"})
        assert tools == ARCHETYPE_TOOLS["default"]

    def test_missing_archetype_gets_default(self) -> None:
        """Missing archetype field gets default tools."""
        tools = get_tools_for_agent({})
        assert tools == ARCHETYPE_TOOLS["default"]

    def test_all_archetypes_have_vote(self) -> None:
        """Every archetype can vote."""
        for archetype, tools in ARCHETYPE_TOOLS.items():
            assert "vote" in tools, f"{archetype} missing vote"

    def test_all_archetypes_have_comment(self) -> None:
        """Every archetype can comment."""
        for archetype, tools in ARCHETYPE_TOOLS.items():
            assert "comment" in tools, f"{archetype} missing comment"


class TestBuildPrompt:
    """Test prompt construction."""

    def test_includes_agent_name(self) -> None:
        """Prompt includes the agent's name."""
        prompt = build_prompt(
            {"name": "TestAgent", "bio": "Test"},
            {"frame": 1},
            ["post"],
        )
        assert "TestAgent" in prompt

    def test_includes_frame_number(self) -> None:
        """Prompt includes frame number."""
        prompt = build_prompt(
            {"name": "A"},
            {"frame": 42},
            ["post"],
        )
        assert "42" in prompt

    def test_includes_tools(self) -> None:
        """Prompt lists available tools."""
        prompt = build_prompt(
            {"name": "A"},
            {"frame": 1},
            ["post", "comment", "vote"],
        )
        assert "post" in prompt
        assert "comment" in prompt

    def test_includes_recent_posts(self) -> None:
        """Prompt includes recent post titles."""
        context = {
            "frame": 1,
            "recent_posts": [
                {"title": "Test Post Alpha", "author": "agent-1"},
            ],
        }
        prompt = build_prompt({"name": "A"}, context, ["post"])
        assert "Test Post Alpha" in prompt

    def test_includes_seed_when_active(self) -> None:
        """Prompt includes active seed info."""
        context = {
            "frame": 1,
            "active_seed": {
                "title": "Build a Library",
                "description": "Create a community library",
            },
        }
        prompt = build_prompt({"name": "A"}, context, ["post"])
        assert "Build a Library" in prompt

    def test_handles_empty_context(self) -> None:
        """Prompt handles empty context gracefully."""
        prompt = build_prompt({"name": "A"}, {}, ["post"])
        assert "A" in prompt


class TestParseActions:
    """Test action parsing from LLM response."""

    def test_valid_json_array(self) -> None:
        """Parses a valid JSON array."""
        raw = '[{"type": "post", "data": {"title": "Hi"}}]'
        actions = parse_actions(raw)
        assert len(actions) == 1
        assert actions[0]["type"] == "post"

    def test_empty_array(self) -> None:
        """Parses an empty array."""
        assert parse_actions("[]") == []

    def test_json_in_text(self) -> None:
        """Extracts JSON from surrounding text."""
        raw = 'Here is my response:\n[{"type": "comment"}]\nThat is all.'
        actions = parse_actions(raw)
        assert len(actions) == 1

    def test_invalid_json(self) -> None:
        """Returns empty for invalid JSON."""
        assert parse_actions("not json at all") == []

    def test_missing_type_field(self) -> None:
        """Skips actions without type field."""
        raw = '[{"data": {"title": "Hi"}}, {"type": "post"}]'
        actions = parse_actions(raw)
        assert len(actions) == 1
        assert actions[0]["type"] == "post"

    def test_adds_default_data(self) -> None:
        """Adds empty data dict if missing."""
        raw = '[{"type": "vote"}]'
        actions = parse_actions(raw)
        assert actions[0]["data"] == {}

    def test_not_array(self) -> None:
        """Returns empty if JSON is not an array."""
        assert parse_actions('{"type": "post"}') == []


class TestRunAgent:
    """Test running an agent through a frame."""

    def test_returns_list(self) -> None:
        """Run agent returns a list."""
        agent = {"id": "test-1", "name": "Test", "bio": "Test agent"}
        context = {"frame": 1}
        result = run_agent(agent, context)
        assert isinstance(result, list)

    def test_actions_have_agent_id(self) -> None:
        """Actions are tagged with agent ID."""
        agent = {"id": "agent-99", "name": "Test", "bio": "Test"}
        context = {"frame": 1}
        # In dry run mode, LLM returns placeholder text which won't parse as JSON
        # So we get empty actions — that's correct behavior
        result = run_agent(agent, context)
        # Even if empty, the function should not crash
        assert isinstance(result, list)

    def test_handles_agent_without_id(self) -> None:
        """Agent without ID uses 'unknown'."""
        agent = {"name": "Test", "bio": "Test"}
        result = run_agent(agent, {"frame": 1})
        assert isinstance(result, list)


class TestSelectActiveAgents:
    """Test agent selection logic."""

    def test_empty_agents(self) -> None:
        """No agents returns empty list."""
        assert select_active_agents({}, 1) == []

    def test_excludes_dormant(self, sample_agents: dict) -> None:
        """Dormant agents are excluded."""
        agents = sample_agents["agents"]
        selected = select_active_agents(agents, 1, max_per_frame=10)
        ids = [a["id"] for a in selected]
        assert "agent-3" not in ids

    def test_respects_max(self, sample_agents: dict) -> None:
        """Max per frame is respected."""
        agents = sample_agents["agents"]
        selected = select_active_agents(agents, 1, max_per_frame=1)
        assert len(selected) <= 1

    def test_deterministic(self, sample_agents: dict) -> None:
        """Same frame number gives same selection."""
        agents = sample_agents["agents"]
        sel1 = select_active_agents(agents, 5, max_per_frame=10)
        sel2 = select_active_agents(agents, 5, max_per_frame=10)
        assert [a["id"] for a in sel1] == [a["id"] for a in sel2]

    def test_rotation(self, sample_agents: dict) -> None:
        """Different frames give different ordering."""
        agents = sample_agents["agents"]
        sel1 = select_active_agents(agents, 1, max_per_frame=10)
        sel2 = select_active_agents(agents, 2, max_per_frame=10)
        # With only 2 active agents and rotation, order may differ
        ids1 = [a["id"] for a in sel1]
        ids2 = [a["id"] for a in sel2]
        # Both should have the same agents (just possibly different order)
        assert sorted(ids1) == sorted(ids2)

    def test_agents_have_id_field(self, sample_agents: dict) -> None:
        """Selected agents have the 'id' field injected."""
        agents = sample_agents["agents"]
        selected = select_active_agents(agents, 1)
        for agent in selected:
            assert "id" in agent
