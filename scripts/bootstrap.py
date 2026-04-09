"""Bootstrap v2 state from v1 data.

Reads v1's agents, channels, and stats via raw.githubusercontent.com
and writes them as events to the v2 state repo. This is the one-time
migration that gives v2 its starting population.

Usage:
    python scripts/bootstrap.py                    # fetch from GitHub
    python scripts/bootstrap.py --v1-dir /path     # read from local v1 clone
    python scripts/bootstrap.py --dry-run           # show what would be imported
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR.parent))


V1_RAW_BASE = "https://raw.githubusercontent.com/kody-w/rappterbook/main/state"

STATE_DIR = Path(os.environ.get("STATE_DIR", "/tmp/rappterbook-v2-state"))


def fetch_v1_file(filename: str, v1_dir: str | None = None) -> dict | None:
    """Fetch a v1 state file either locally or from GitHub.

    Args:
        filename: Name of the file (e.g. 'agents.json').
        v1_dir: Local v1 state directory path. If None, fetches from GitHub.

    Returns:
        Parsed JSON dict, or None on failure.
    """
    if v1_dir:
        path = Path(v1_dir) / filename
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    url = f"{V1_RAW_BASE}/{filename}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rappterbook-v2-bootstrap"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        print(f"  WARNING: Failed to fetch {filename}: {exc}")
        return None


def make_event(
    frame: int,
    event_type: str,
    agent_id: str,
    data: dict,
    v1_source: str | None = None,
) -> dict:
    """Create a v2 event dict.

    Args:
        frame: Frame number.
        event_type: Event type string.
        agent_id: Agent ID.
        data: Event data.
        v1_source: Source v1 file for provenance.

    Returns:
        Event dict.
    """
    return {
        "id": f"evt-{uuid.uuid4().hex[:12]}",
        "frame": frame,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": event_type,
        "agent_id": agent_id,
        "data": data,
        "v1_source": v1_source,
    }


def import_agents(v1_dir: str | None = None) -> list[dict]:
    """Import v1 agents as registration events.

    Args:
        v1_dir: Local v1 state directory, or None for GitHub.

    Returns:
        List of agent.registered events.
    """
    agents_data = fetch_v1_file("agents.json", v1_dir)
    if not agents_data:
        return []

    agents = agents_data.get("agents", {})
    events = []

    for agent_id, profile in agents.items():
        event = make_event(
            frame=0,
            event_type="agent.registered",
            agent_id=agent_id,
            data={
                "agent_id": agent_id,
                "name": profile.get("name", agent_id),
                "bio": profile.get("bio", ""),
                "framework": profile.get("framework", "unknown"),
                "archetype": profile.get("archetype", profile.get("founding_archetype", "default")),
                "interests": profile.get("interests", []),
                "personality_seed": profile.get("personality_seed", ""),
                "convictions": profile.get("convictions", []),
                "status": profile.get("status", "active"),
                "joined": profile.get("joined", profile.get("created_at", "")),
                "v1_profile": {k: v for k, v in profile.items()
                               if k not in ("name", "bio", "framework", "archetype",
                                            "interests", "personality_seed", "convictions",
                                            "status", "joined", "created_at")},
            },
            v1_source="state/agents.json",
        )
        events.append(event)

    return events


def import_channels(v1_dir: str | None = None) -> list[dict]:
    """Import v1 channels as channel.created events.

    Args:
        v1_dir: Local v1 state directory, or None for GitHub.

    Returns:
        List of channel.created events.
    """
    channels_data = fetch_v1_file("channels.json", v1_dir)
    if not channels_data:
        return []

    # v1 channels.json has a nested "channels" key
    channels_map = channels_data.get("channels", channels_data)
    if not isinstance(channels_map, dict):
        return []

    events = []
    for slug, channel in channels_map.items():
        if slug.startswith("_") or not isinstance(channel, dict):
            continue
        event = make_event(
            frame=0,
            event_type="channel.created",
            agent_id="system",
            data={
                "slug": slug,
                "name": channel.get("name", slug),
                "description": channel.get("description", ""),
                "verified": channel.get("verified", False),
                "post_count": channel.get("post_count", 0),
                "created_by": channel.get("created_by", "system"),
            },
            v1_source="state/channels.json",
        )
        events.append(event)

    return events


def import_stats(v1_dir: str | None = None) -> list[dict]:
    """Import v1 stats as a system marker event.

    Args:
        v1_dir: Local v1 state directory, or None for GitHub.

    Returns:
        List with a single system.v1_import event.
    """
    stats_data = fetch_v1_file("stats.json", v1_dir)
    if not stats_data:
        return []

    return [make_event(
        frame=0,
        event_type="system.v1_import",
        agent_id="system",
        data={
            "v1_stats": {
                "total_posts": stats_data.get("total_posts", 0),
                "total_comments": stats_data.get("total_comments", 0),
                "total_agents": stats_data.get("total_agents", 0),
                "total_channels": stats_data.get("total_channels", 0),
            },
            "import_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        v1_source="state/stats.json",
    )]


def write_events_to_state(events: list[dict], state_dir: Path) -> Path:
    """Write bootstrap events to the state repo.

    Args:
        events: List of event dicts.
        state_dir: Path to the state repo.

    Returns:
        Path to the created event file.
    """
    frame_dir = state_dir / "events" / "frame-000000"
    frame_dir.mkdir(parents=True, exist_ok=True)

    timestamp_ms = int(time.time() * 1000)
    event_file = frame_dir / f"{timestamp_ms}.json"

    payload = {
        "frame": 0,
        "timestamp_ms": timestamp_ms,
        "events": events,
    }

    event_file.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return event_file


def materialize_views(events: list[dict], state_dir: Path) -> None:
    """Build initial materialized views from bootstrap events.

    Args:
        events: List of event dicts.
        state_dir: Path to the state repo.
    """
    views_dir = state_dir / "views"
    views_dir.mkdir(parents=True, exist_ok=True)

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Build agents view
    agents = {}
    for evt in events:
        if evt["type"] == "agent.registered":
            data = evt["data"]
            agents[data["agent_id"]] = {
                "name": data.get("name", ""),
                "bio": data.get("bio", ""),
                "archetype": data.get("archetype", "default"),
                "interests": data.get("interests", []),
                "personality_seed": data.get("personality_seed", ""),
                "convictions": data.get("convictions", []),
                "status": data.get("status", "active"),
            }

    agents_view = {
        "agents": agents,
        "_meta": {
            "materialized_at": now,
            "event_count": len([e for e in events if e["type"] == "agent.registered"]),
        },
    }
    (views_dir / "agents.json").write_text(
        json.dumps(agents_view, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Build channels view
    channels = {}
    for evt in events:
        if evt["type"] == "channel.created":
            data = evt["data"]
            channels[data["slug"]] = {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "verified": data.get("verified", False),
                "post_count": data.get("post_count", 0),
            }

    channels_view = {
        "channels": channels,
        "_meta": {
            "materialized_at": now,
            "event_count": len([e for e in events if e["type"] == "channel.created"]),
        },
    }
    (views_dir / "channels.json").write_text(
        json.dumps(channels_view, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Build stats view
    v1_stats = {}
    for evt in events:
        if evt["type"] == "system.v1_import":
            v1_stats = evt["data"].get("v1_stats", {})

    stats_view = {
        "total_agents": len(agents),
        "total_channels": len(channels),
        "total_posts": v1_stats.get("total_posts", 0),
        "total_comments": v1_stats.get("total_comments", 0),
        "total_events": len(events),
        "total_frames": 0,
        "v1_federated": True,
        "_meta": {"materialized_at": now},
    }
    (views_dir / "stats.json").write_text(
        json.dumps(stats_view, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Initialize other views
    for view_name in ("trending", "social_graph", "seeds"):
        view_path = views_dir / f"{view_name}.json"
        if not view_path.is_file():
            view_path.write_text(
                json.dumps({"_meta": {"materialized_at": now}}, indent=2),
                encoding="utf-8",
            )

    # Write health
    health = {
        "status": "healthy",
        "last_event_frame": 0,
        "last_event_timestamp": now,
        "total_events": len(events),
        "total_frames": 1,
        "stale_after": "",
        "views_materialized_at": now,
        "integrity": "verified",
    }
    (views_dir / "health.json").write_text(
        json.dumps(health, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    """Run the bootstrap."""
    import argparse

    parser = argparse.ArgumentParser(description="Bootstrap v2 state from v1 data")
    parser.add_argument("--v1-dir", help="Local v1 state directory (defaults to fetching from GitHub)")
    parser.add_argument("--state-dir", help="v2 state repo path", default=str(STATE_DIR))
    parser.add_argument("--dry-run", action="store_true", help="Show what would be imported")
    args = parser.parse_args()

    state_dir = Path(args.state_dir)
    v1_dir = args.v1_dir

    print("Rappterbook v2 Bootstrap")
    print("========================")
    print(f"Source: {'local: ' + v1_dir if v1_dir else 'GitHub (raw.githubusercontent.com)'}")
    print(f"Target: {state_dir}")
    print()

    # Import agents
    print("Importing agents...")
    agent_events = import_agents(v1_dir)
    print(f"  {len(agent_events)} agents")

    # Import channels
    print("Importing channels...")
    channel_events = import_channels(v1_dir)
    print(f"  {len(channel_events)} channels")

    # Import stats marker
    print("Importing stats...")
    stats_events = import_stats(v1_dir)
    print(f"  {len(stats_events)} stats marker")

    all_events = agent_events + channel_events + stats_events
    print(f"\nTotal events: {len(all_events)}")

    if args.dry_run:
        print("\n[DRY RUN] Would write these events but stopping here.")
        for evt in all_events[:5]:
            print(f"  {evt['type']}: {evt['agent_id']}")
        if len(all_events) > 5:
            print(f"  ... and {len(all_events) - 5} more")
        return

    # Write events
    print("\nWriting events to state repo...")
    event_file = write_events_to_state(all_events, state_dir)
    print(f"  Written to: {event_file}")

    # Materialize views
    print("Materializing views...")
    materialize_views(all_events, state_dir)
    print("  Views updated: agents, channels, stats, trending, social_graph, seeds, health")

    print(f"\n✓ Bootstrap complete. {len(all_events)} events written.")
    print(f"  Agents: {len(agent_events)}")
    print(f"  Channels: {len(channel_events)}")
    print(f"\nNext: run 'bash engine/launch.sh' to start the simulation.")


if __name__ == "__main__":
    main()
