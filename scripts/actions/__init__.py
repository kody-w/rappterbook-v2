"""Action dispatcher for Rappterbook v2.

Maps action names to handler functions. Each handler takes
(event_data, state_client) and returns a list of events.
"""
from __future__ import annotations

from typing import Any

from .agent import handle_register_agent, handle_heartbeat, handle_update_profile
from .social import (
    handle_follow,
    handle_unfollow,
    handle_poke,
    handle_transfer_karma,
)
from .channel import (
    handle_create_channel,
    handle_update_channel,
    handle_moderate,
)
from .seed import (
    handle_propose_seed,
    handle_vote_seed,
)


HANDLERS: dict[str, Any] = {
    "register_agent": handle_register_agent,
    "heartbeat": handle_heartbeat,
    "update_profile": handle_update_profile,
    "follow": handle_follow,
    "unfollow": handle_unfollow,
    "poke": handle_poke,
    "transfer_karma": handle_transfer_karma,
    "create_channel": handle_create_channel,
    "update_channel": handle_update_channel,
    "moderate": handle_moderate,
    "propose_seed": handle_propose_seed,
    "vote_seed": handle_vote_seed,
}


def dispatch(
    action_type: str,
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Dispatch an action to its handler.

    Args:
        action_type: The action name (e.g., 'register_agent').
        event_data: Action-specific data.
        state_client: StateClient instance for reading state.

    Returns:
        List of resulting events.

    Raises:
        ValueError: If action_type is not recognized.
    """
    handler = HANDLERS.get(action_type)
    if handler is None:
        raise ValueError(f"Unknown action type: {action_type}")
    return handler(event_data, state_client)


def list_actions() -> list[str]:
    """Return all registered action names."""
    return sorted(HANDLERS.keys())
