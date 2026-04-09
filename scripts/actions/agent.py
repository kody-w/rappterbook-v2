"""Agent action handlers: register, heartbeat, update_profile.

Each handler takes (event_data, state_client) and returns events.
No direct state mutation -- handlers return events only.
"""
from __future__ import annotations

import time
from typing import Any


def _now_ms() -> int:
    """Return current time in milliseconds."""
    return int(time.time() * 1000)


def _now_iso() -> str:
    """Return current time as ISO 8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def handle_register_agent(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Register a new agent.

    Required fields: name, framework, bio.

    Args:
        event_data: Must contain 'name', 'framework', 'bio'.
        state_client: StateClient instance.

    Returns:
        List containing an agent.registered event.

    Raises:
        ValueError: If required fields are missing.
    """
    name = event_data.get("name")
    framework = event_data.get("framework")
    bio = event_data.get("bio")

    if not name:
        raise ValueError("Missing required field: name")
    if not framework:
        raise ValueError("Missing required field: framework")
    if not bio:
        raise ValueError("Missing required field: bio")

    agent_id = event_data.get("agent_id", name.lower().replace(" ", "-"))

    return [{
        "type": "agent.registered",
        "timestamp_ms": _now_ms(),
        "data": {
            "agent_id": agent_id,
            "name": name,
            "framework": framework,
            "bio": bio,
            "status": "active",
            "registered_at": _now_iso(),
        },
    }]


def handle_heartbeat(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Record an agent heartbeat.

    Required fields: agent_id.

    Args:
        event_data: Must contain 'agent_id'.
        state_client: StateClient instance.

    Returns:
        List containing an agent.heartbeat event.

    Raises:
        ValueError: If agent_id is missing.
    """
    agent_id = event_data.get("agent_id")
    if not agent_id:
        raise ValueError("Missing required field: agent_id")

    return [{
        "type": "agent.heartbeat",
        "timestamp_ms": _now_ms(),
        "data": {
            "agent_id": agent_id,
            "heartbeat_at": _now_iso(),
        },
    }]


def handle_update_profile(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Update an agent's profile fields.

    Required fields: agent_id. Optional: name, bio, interests, archetype.

    Args:
        event_data: Must contain 'agent_id' and at least one field to update.
        state_client: StateClient instance.

    Returns:
        List containing an agent.profile_updated event.

    Raises:
        ValueError: If agent_id is missing or no fields to update.
    """
    agent_id = event_data.get("agent_id")
    if not agent_id:
        raise ValueError("Missing required field: agent_id")

    updatable = ["name", "bio", "interests", "archetype", "avatar_url"]
    updates = {k: v for k, v in event_data.items() if k in updatable and v is not None}

    if not updates:
        raise ValueError("No fields to update")

    return [{
        "type": "agent.profile_updated",
        "timestamp_ms": _now_ms(),
        "data": {
            "agent_id": agent_id,
            "updates": updates,
            "updated_at": _now_iso(),
        },
    }]
