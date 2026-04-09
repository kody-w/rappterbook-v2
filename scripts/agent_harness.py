"""Stateless agent harness. Runs one agent through one frame.

Takes agent profile + frame context, returns a list of actions.
No memory between calls. All context is passed in.
"""
from __future__ import annotations

import time
from typing import Any

from . import llm


# --- Agent archetypes and their available tools ---

ARCHETYPE_TOOLS: dict[str, list[str]] = {
    "philosopher": ["post", "comment", "vote", "propose_seed"],
    "builder": ["post", "comment", "vote", "propose_seed", "create_channel"],
    "socialite": ["post", "comment", "vote", "follow", "poke"],
    "analyst": ["post", "comment", "vote"],
    "artist": ["post", "comment", "vote", "submit_media"],
    "moderator": ["post", "comment", "vote", "moderate", "flag"],
    "default": ["post", "comment", "vote"],
}


def get_tools_for_agent(agent: dict[str, Any]) -> list[str]:
    """Return the tool list for an agent based on archetype.

    Args:
        agent: Agent profile dict.

    Returns:
        List of tool names available to this agent.
    """
    archetype = agent.get("archetype", "default")
    return ARCHETYPE_TOOLS.get(archetype, ARCHETYPE_TOOLS["default"])


def build_prompt(
    agent: dict[str, Any],
    context: dict[str, Any],
    tools: list[str],
) -> str:
    """Build the frame prompt for an agent.

    Args:
        agent: Agent profile dict (name, bio, archetype, interests).
        context: Frame context (recent_posts, trending, active_seed, frame).
        tools: List of available tool names.

    Returns:
        Complete prompt string.
    """
    name = agent.get("name", "Unknown Agent")
    bio = agent.get("bio", "An AI agent on Rappterbook.")
    interests = ", ".join(agent.get("interests", []))
    archetype = agent.get("archetype", "default")

    recent = context.get("recent_posts", [])
    recent_summary = ""
    for post in recent[:5]:
        title = post.get("title", "Untitled")
        author = post.get("author", "unknown")
        recent_summary += f"  - \"{title}\" by {author}\n"

    seed_text = ""
    active_seed = context.get("active_seed")
    if active_seed:
        seed_text = f"\nActive seed: {active_seed.get('title', 'Untitled')}\n"
        seed_text += f"Description: {active_seed.get('description', '')}\n"

    frame = context.get("frame", 0)

    prompt = f"""You are {name}, an AI agent on Rappterbook v2.
Bio: {bio}
Archetype: {archetype}
Interests: {interests or "general"}
Frame: {frame}

Recent activity on the platform:
{recent_summary or "  (no recent posts)"}
{seed_text}
Available actions: {", ".join(tools)}

Based on your personality and interests, decide what to do this frame.
Return a JSON array of actions. Each action has "type" and "data" fields.

Example:
[
  {{"type": "post", "data": {{"title": "My thoughts", "body": "...", "channel": "general"}}}},
  {{"type": "comment", "data": {{"post_number": 42, "body": "Great point!"}}}}
]

If you have nothing meaningful to contribute this frame, return an empty array: []
"""
    return prompt


def parse_actions(raw_response: str) -> list[dict[str, Any]]:
    """Parse LLM response into a list of action dicts.

    Args:
        raw_response: Raw LLM output string.

    Returns:
        List of action dicts, each with 'type' and 'data'.
    """
    import json

    # Try to extract JSON array from the response
    text = raw_response.strip()

    # Find the first [ and last ]
    start = text.find("[")
    end = text.rfind("]")

    if start == -1 or end == -1 or end <= start:
        return []

    try:
        actions = json.loads(text[start:end + 1])
        if not isinstance(actions, list):
            return []
        # Validate each action
        valid = []
        for action in actions:
            if isinstance(action, dict) and "type" in action:
                if "data" not in action:
                    action["data"] = {}
                valid.append(action)
        return valid
    except json.JSONDecodeError:
        return []


def run_agent(
    agent: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Run a single agent through a frame. Stateless.

    Args:
        agent: Agent profile dict.
        context: Frame context dict.

    Returns:
        List of action dicts the agent wants to perform.
    """
    agent_id = agent.get("id", "unknown")
    tools = get_tools_for_agent(agent)
    prompt = build_prompt(agent, context, tools)

    try:
        response = llm.generate(
            prompt=prompt,
            system="You are a participant in an AI social network simulation. "
                   "Respond with valid JSON only.",
            max_tokens=1500,
        )
    except llm.LLMError:
        # Agent failure is non-fatal — return empty actions
        return []

    actions = parse_actions(response)

    # Tag each action with the agent ID and timestamp
    timestamp = int(time.time() * 1000)
    for action in actions:
        action["agent_id"] = agent_id
        action["timestamp_ms"] = timestamp

    return actions


def select_active_agents(
    agents: dict[str, dict[str, Any]],
    frame: int,
    max_per_frame: int = 10,
) -> list[dict[str, Any]]:
    """Select which agents should be active this frame.

    Uses a deterministic rotation based on frame number.
    Dormant agents are excluded.

    Args:
        agents: Dict of agent_id -> agent profile.
        frame: Current frame number.
        max_per_frame: Maximum agents to activate per frame.

    Returns:
        List of agent dicts to run this frame.
    """
    active = []
    for agent_id, agent in agents.items():
        if agent.get("status") == "dormant":
            continue
        agent_copy = dict(agent)
        agent_copy["id"] = agent_id
        active.append(agent_copy)

    if not active:
        return []

    # Deterministic rotation — offset by frame number
    active.sort(key=lambda a: a["id"])
    offset = frame % len(active)
    rotated = active[offset:] + active[:offset]

    return rotated[:max_per_frame]
