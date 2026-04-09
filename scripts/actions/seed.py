"""Seed action handlers: propose, vote.

Each handler takes (event_data, state_client) and returns events.
Seeds are proposals for simulation-wide activities.
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


def handle_propose_seed(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Propose a new seed for the simulation.

    Required fields: proposer_id, title, description.

    Args:
        event_data: Must contain 'proposer_id', 'title', 'description'.
        state_client: StateClient instance.

    Returns:
        List containing a seed.proposed event.
    """
    proposer_id = event_data.get("proposer_id")
    title = event_data.get("title")
    description = event_data.get("description")

    if not proposer_id:
        raise ValueError("Missing required field: proposer_id")
    if not title:
        raise ValueError("Missing required field: title")
    if not description:
        raise ValueError("Missing required field: description")

    seed_type = event_data.get("type", "discussion")
    valid_types = ["discussion", "artifact", "experiment", "governance"]
    if seed_type not in valid_types:
        raise ValueError(f"Invalid seed type: {seed_type}. Must be one of: {valid_types}")

    return [{
        "type": "seed.proposed",
        "timestamp_ms": _now_ms(),
        "data": {
            "proposer_id": proposer_id,
            "title": title,
            "description": description,
            "seed_type": seed_type,
            "status": "proposed",
            "votes_for": 0,
            "votes_against": 0,
            "proposed_at": _now_iso(),
        },
    }]


def handle_vote_seed(
    event_data: dict[str, Any],
    state_client: Any,
) -> list[dict[str, Any]]:
    """Vote on a seed proposal.

    Required fields: voter_id, seed_id, vote.

    Args:
        event_data: Must contain 'voter_id', 'seed_id', 'vote' (for/against).
        state_client: StateClient instance.

    Returns:
        List containing a seed.voted event.
    """
    voter_id = event_data.get("voter_id")
    seed_id = event_data.get("seed_id")
    vote = event_data.get("vote")

    if not voter_id:
        raise ValueError("Missing required field: voter_id")
    if not seed_id:
        raise ValueError("Missing required field: seed_id")
    if vote not in ("for", "against"):
        raise ValueError("vote must be 'for' or 'against'")

    return [{
        "type": "seed.voted",
        "timestamp_ms": _now_ms(),
        "data": {
            "voter_id": voter_id,
            "seed_id": seed_id,
            "vote": vote,
            "voted_at": _now_iso(),
        },
    }]
