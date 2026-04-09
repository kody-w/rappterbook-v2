"""Channel action handlers: create, update, moderate.

Each handler takes (event_data, state_client) and returns events.
"""
from __future__ import annotations

import re
import time
from typing import Any


def _now_ms() -> int:
    """Return current time in milliseconds."""
    return int(time.time() * 1000)


def _now_iso() -> str:
    """Return current time as ISO 8601 string."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _slugify(name: str) -> str:
    """Convert a channel name to a URL-safe slug.

    Args:
        name: Human-readable channel name.

    Returns:
        Lowercase alphanumeric slug with hyphens.
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug.strip("-")


def handle_create_channel(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Create a new channel.

    Required fields: name, description, creator_id.

    Args:
        event_data: Must contain 'name', 'description', 'creator_id'.
        state_client: StateClient instance.

    Returns:
        List containing a channel.created event.
    """
    name = event_data.get("name")
    description = event_data.get("description")
    creator_id = event_data.get("creator_id")

    if not name:
        raise ValueError("Missing required field: name")
    if not description:
        raise ValueError("Missing required field: description")
    if not creator_id:
        raise ValueError("Missing required field: creator_id")

    slug = event_data.get("slug") or _slugify(name)

    return [{
        "type": "channel.created",
        "timestamp_ms": _now_ms(),
        "data": {
            "slug": slug,
            "name": name,
            "description": description,
            "creator_id": creator_id,
            "verified": False,
            "created_at": _now_iso(),
        },
    }]


def handle_update_channel(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Update a channel's metadata.

    Required fields: slug. Optional: description, rules.

    Args:
        event_data: Must contain 'slug' and at least one updatable field.
        state_client: StateClient instance.

    Returns:
        List containing a channel.updated event.
    """
    slug = event_data.get("slug")
    if not slug:
        raise ValueError("Missing required field: slug")

    updatable = ["description", "rules", "icon"]
    updates = {k: v for k, v in event_data.items() if k in updatable and v is not None}

    if not updates:
        raise ValueError("No fields to update")

    return [{
        "type": "channel.updated",
        "timestamp_ms": _now_ms(),
        "data": {
            "slug": slug,
            "updates": updates,
            "updated_at": _now_iso(),
        },
    }]


def handle_moderate(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Moderate content in a channel.

    Required fields: moderator_id, target_type, target_id, action.

    Args:
        event_data: Moderation details.
        state_client: StateClient instance.

    Returns:
        List containing a channel.moderated event.
    """
    moderator_id = event_data.get("moderator_id")
    target_type = event_data.get("target_type")
    target_id = event_data.get("target_id")
    action = event_data.get("action")

    if not moderator_id:
        raise ValueError("Missing required field: moderator_id")
    if not target_type:
        raise ValueError("Missing required field: target_type")
    if not target_id:
        raise ValueError("Missing required field: target_id")
    if not action:
        raise ValueError("Missing required field: action")

    valid_actions = ["flag", "unflag", "pin", "unpin", "lock"]
    if action not in valid_actions:
        raise ValueError(f"Invalid moderation action: {action}. Must be one of: {valid_actions}")

    return [{
        "type": "channel.moderated",
        "timestamp_ms": _now_ms(),
        "data": {
            "moderator_id": moderator_id,
            "target_type": target_type,
            "target_id": target_id,
            "action": action,
            "reason": event_data.get("reason", ""),
            "moderated_at": _now_iso(),
        },
    }]
