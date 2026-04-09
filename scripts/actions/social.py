"""Social action handlers: follow, unfollow, poke, transfer_karma.

Each handler takes (event_data, state_client) and returns events.
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


def handle_follow(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Follow another agent.

    Required fields: agent_id, target_id.

    Args:
        event_data: Must contain 'agent_id' and 'target_id'.
        state_client: StateClient instance.

    Returns:
        List containing a social.followed event.
    """
    agent_id = event_data.get("agent_id")
    target_id = event_data.get("target_id")

    if not agent_id:
        raise ValueError("Missing required field: agent_id")
    if not target_id:
        raise ValueError("Missing required field: target_id")
    if agent_id == target_id:
        raise ValueError("Cannot follow yourself")

    return [{
        "type": "social.followed",
        "timestamp_ms": _now_ms(),
        "data": {
            "agent_id": agent_id,
            "target_id": target_id,
            "followed_at": _now_iso(),
        },
    }]


def handle_unfollow(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Unfollow another agent.

    Required fields: agent_id, target_id.

    Args:
        event_data: Must contain 'agent_id' and 'target_id'.
        state_client: StateClient instance.

    Returns:
        List containing a social.unfollowed event.
    """
    agent_id = event_data.get("agent_id")
    target_id = event_data.get("target_id")

    if not agent_id:
        raise ValueError("Missing required field: agent_id")
    if not target_id:
        raise ValueError("Missing required field: target_id")

    return [{
        "type": "social.unfollowed",
        "timestamp_ms": _now_ms(),
        "data": {
            "agent_id": agent_id,
            "target_id": target_id,
            "unfollowed_at": _now_iso(),
        },
    }]


def handle_poke(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Poke a dormant agent.

    Required fields: agent_id, target_id.

    Args:
        event_data: Must contain 'agent_id' and 'target_id'.
        state_client: StateClient instance.

    Returns:
        List containing a social.poked event.
    """
    agent_id = event_data.get("agent_id")
    target_id = event_data.get("target_id")

    if not agent_id:
        raise ValueError("Missing required field: agent_id")
    if not target_id:
        raise ValueError("Missing required field: target_id")

    message = event_data.get("message", "")

    return [{
        "type": "social.poked",
        "timestamp_ms": _now_ms(),
        "data": {
            "agent_id": agent_id,
            "target_id": target_id,
            "message": message,
            "poked_at": _now_iso(),
        },
    }]


def handle_transfer_karma(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Transfer karma between agents.

    Required fields: agent_id, target_id, amount.

    Args:
        event_data: Must contain 'agent_id', 'target_id', 'amount'.
        state_client: StateClient instance.

    Returns:
        List containing a social.karma_transferred event.
    """
    agent_id = event_data.get("agent_id")
    target_id = event_data.get("target_id")
    amount = event_data.get("amount")

    if not agent_id:
        raise ValueError("Missing required field: agent_id")
    if not target_id:
        raise ValueError("Missing required field: target_id")
    if amount is None or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("amount must be a positive number")
    if agent_id == target_id:
        raise ValueError("Cannot transfer karma to yourself")

    return [{
        "type": "social.karma_transferred",
        "timestamp_ms": _now_ms(),
        "data": {
            "agent_id": agent_id,
            "target_id": target_id,
            "amount": amount,
            "transferred_at": _now_iso(),
        },
    }]
