"""Frame runner: executes a single simulation frame.

Reads state, selects agents, runs them through the harness,
and returns a list of events. Does NOT write state directly --
the orchestrator handles that.
"""
from __future__ import annotations

import time
from typing import Any

from .agent_harness import run_agent, select_active_agents
from .state_client import StateClient


def build_frame_context(
    state_client: StateClient,
    frame: int,
) -> dict[str, Any]:
    """Build the context that agents see during a frame.

    Args:
        state_client: State client instance.
        frame: Current frame number.

    Returns:
        Context dict with recent_posts, trending, active_seed, frame.
    """
    recent_posts = state_client.read_view("recent_posts")
    trending = state_client.read_view("trending")
    seeds = state_client.read_view("seeds")

    active_seed = None
    if isinstance(seeds, dict):
        for seed_id, seed in seeds.get("seeds", {}).items():
            if seed.get("status") == "active":
                active_seed = seed
                active_seed["id"] = seed_id
                break

    return {
        "frame": frame,
        "recent_posts": recent_posts.get("posts", []) if isinstance(recent_posts, dict) else [],
        "trending": trending.get("trending", []) if isinstance(trending, dict) else [],
        "active_seed": active_seed,
    }


def run_frame(
    state_client: StateClient,
    frame: int | None = None,
    max_agents: int = 10,
) -> dict[str, Any]:
    """Run a single simulation frame.

    Args:
        state_client: State client for reading/writing state.
        frame: Frame number override. If None, auto-increments.
        max_agents: Maximum agents to run this frame.

    Returns:
        Dict with 'frame', 'events', 'agents_run', 'duration_ms'.
    """
    start_time = time.time()

    # Determine frame number
    if frame is None:
        frame = state_client.get_latest_frame() + 1

    # Read agents
    agents_view = state_client.read_view("agents")
    agents = agents_view.get("agents", {}) if isinstance(agents_view, dict) else {}

    # Select active agents for this frame
    active = select_active_agents(agents, frame, max_per_frame=max_agents)

    # Build shared context
    context = build_frame_context(state_client, frame)

    # Run each agent
    all_events: list[dict[str, Any]] = []
    agents_run: list[str] = []

    for agent in active:
        agent_id = agent.get("id", "unknown")
        try:
            actions = run_agent(agent, context)
            for action in actions:
                event = {
                    "type": f"{action.get('type', 'unknown')}.requested",
                    "agent_id": agent_id,
                    "frame": frame,
                    "timestamp_ms": int(time.time() * 1000),
                    "data": action.get("data", {}),
                }
                all_events.append(event)
            agents_run.append(agent_id)
        except Exception:
            # Individual agent failure is non-fatal
            agents_run.append(agent_id)
            continue

    duration_ms = int((time.time() - start_time) * 1000)

    return {
        "frame": frame,
        "events": all_events,
        "agents_run": agents_run,
        "duration_ms": duration_ms,
    }
