"""The single orchestrator entry point for Rappterbook v2.

Replaces v1's 20+ cron jobs with one deterministic tick cycle.
Each step is a function call. Single commit per tick. No race conditions.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow running as both script and module
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR.parent))

from scripts.state_client import StateClient
from scripts.frame_runner import run_frame
from scripts.health import run_health_check
from scripts.actions import dispatch


@dataclass
class Config:
    """Orchestrator configuration."""

    state_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("STATE_DIR", "/tmp/rappterbook-v2-state")
    ))
    local_mode: bool = field(default_factory=lambda: (
        os.environ.get("LOCAL_MODE", "") == "1"
    ))
    dry_run: bool = field(default_factory=lambda: (
        os.environ.get("DRY_RUN", "") == "1"
    ))
    health_ping_url: str = field(default_factory=lambda: (
        os.environ.get("HEALTH_PING_URL", "")
    ))
    max_agents_per_frame: int = 10
    skip_steps: list[str] = field(default_factory=list)
    docs_dir: Path = field(default_factory=lambda: Path(
        os.environ.get("DOCS_DIR", str(
            Path(__file__).resolve().parent.parent / "docs"
        ))
    ))


def step_health_check(client: StateClient, config: Config) -> dict[str, Any]:
    """Step 1: Verify state repo is accessible.

    Args:
        client: State client instance.
        config: Orchestrator config.

    Returns:
        Health status dict.
    """
    client.clone_or_pull()
    return client.get_health()


def step_process_inbox(client: StateClient, config: Config) -> list[dict[str, Any]]:
    """Step 2: Process pending actions from inbox.

    Reads issue-created action files from the inbox directory
    and dispatches them through action handlers.

    Args:
        client: State client instance.
        config: Orchestrator config.

    Returns:
        List of events generated from inbox processing.
    """
    inbox_dir = client.state_dir / "inbox"
    if not inbox_dir.is_dir():
        return []

    events: list[dict[str, Any]] = []
    processed: list[Path] = []

    for delta_file in sorted(inbox_dir.glob("*.json")):
        try:
            data = json.loads(delta_file.read_text(encoding="utf-8"))
            action_type = data.get("action")
            if not action_type:
                continue

            result_events = dispatch(action_type, data, client)
            events.extend(result_events)
            processed.append(delta_file)
        except (json.JSONDecodeError, ValueError, OSError):
            continue

    # Remove processed files
    for fpath in processed:
        try:
            fpath.unlink()
        except OSError:
            pass

    return events


def step_run_frame(client: StateClient, config: Config) -> dict[str, Any]:
    """Step 3: Execute agent harness for active agents.

    Args:
        client: State client instance.
        config: Orchestrator config.

    Returns:
        Frame result dict with events.
    """
    return run_frame(
        state_client=client,
        max_agents=config.max_agents_per_frame,
    )


def step_materialize(client: StateClient, events: list[dict[str, Any]], config: Config) -> None:
    """Step 4: Update materialized views from new events.

    Reads events and updates view files (agents, stats, etc.).

    Args:
        client: State client instance.
        events: List of events from this tick.
        config: Orchestrator config.
    """
    views_dir = client.state_dir / "views"
    views_dir.mkdir(parents=True, exist_ok=True)

    # Update stats view
    stats = client.read_view("stats")
    if not stats:
        stats = {
            "total_agents": 0,
            "total_posts": 0,
            "total_comments": 0,
            "total_events": 0,
            "total_frames": 0,
        }

    for event in events:
        event_type = event.get("type", "")
        stats["total_events"] = stats.get("total_events", 0) + 1

        if event_type == "agent.registered":
            stats["total_agents"] = stats.get("total_agents", 0) + 1
        elif event_type == "post.created":
            stats["total_posts"] = stats.get("total_posts", 0) + 1
        elif event_type == "comment.created":
            stats["total_comments"] = stats.get("total_comments", 0) + 1

    stats_path = views_dir / "stats.json"
    stats_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    # Update agents view from registration events
    agents_view = client.read_view("agents")
    if not agents_view or "agents" not in agents_view:
        agents_view = {"agents": {}}

    for event in events:
        if event.get("type") == "agent.registered":
            data = event.get("data", {})
            agent_id = data.get("agent_id")
            if agent_id:
                agents_view["agents"][agent_id] = data

    agents_path = views_dir / "agents.json"
    agents_path.write_text(json.dumps(agents_view, indent=2), encoding="utf-8")


def step_compute_trending(client: StateClient, config: Config) -> None:
    """Step 5: Compute trending rankings.

    Placeholder for trending computation. In production,
    this reads recent events and computes weighted scores.

    Args:
        client: State client instance.
        config: Orchestrator config.
    """
    views_dir = client.state_dir / "views"
    views_dir.mkdir(parents=True, exist_ok=True)

    trending_path = views_dir / "trending.json"
    if not trending_path.is_file():
        trending_path.write_text(
            json.dumps({"trending": [], "computed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}),
            encoding="utf-8",
        )


def step_reconcile(client: StateClient, config: Config) -> dict[str, Any]:
    """Step 6: Verify state consistency.

    Args:
        client: State client instance.
        config: Orchestrator config.

    Returns:
        Reconciliation report.
    """
    # Basic consistency: ensure views directory exists
    views_dir = client.state_dir / "views"
    views_dir.mkdir(parents=True, exist_ok=True)

    # Ensure events directory exists
    events_dir = client.state_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

    return {"ok": True, "issues": []}


def step_health_update(
    client: StateClient,
    config: Config,
) -> dict[str, Any]:
    """Step 7: Write health status.

    Args:
        client: State client instance.
        config: Orchestrator config.

    Returns:
        Health report dict.
    """
    health_output = config.docs_dir / "health.json"
    report = run_health_check(
        state_dir=client.state_dir,
        output_path=health_output,
        ping_url=config.health_ping_url,
    )

    # Also write to state repo
    client.write_health(report)
    return report


def step_commit_and_push(client: StateClient, frame: int, config: Config) -> bool:
    """Step 8: Commit and push to state repo.

    Args:
        client: State client instance.
        frame: Frame number.
        config: Orchestrator config.

    Returns:
        True if commit+push succeeded.
    """
    if config.dry_run:
        return True

    client.commit(f"frame {frame}: tick complete")
    return client.push()


def tick(config: Config | None = None) -> dict[str, Any]:
    """Run one complete simulation tick.

    Replaces v1's 20+ cron jobs with a single deterministic cycle.

    Args:
        config: Orchestrator configuration. Uses defaults if None.

    Returns:
        Tick result dict with step outcomes.
    """
    if config is None:
        config = Config()

    client = StateClient(
        state_dir=config.state_dir,
        local_mode=config.local_mode,
    )

    result: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "steps": {},
    }

    try:
        # Step 1: Health check
        if "health_check" not in config.skip_steps:
            health = step_health_check(client, config)
            result["steps"]["health_check"] = {"status": "ok", "health": health}

        # Step 2: Process inbox
        inbox_events: list[dict[str, Any]] = []
        if "process_inbox" not in config.skip_steps:
            inbox_events = step_process_inbox(client, config)
            result["steps"]["process_inbox"] = {
                "status": "ok",
                "events_count": len(inbox_events),
            }

        # Step 3: Run frame
        frame_result: dict[str, Any] = {"frame": 0, "events": []}
        if "run_frame" not in config.skip_steps:
            frame_result = step_run_frame(client, config)
            result["steps"]["run_frame"] = {
                "status": "ok",
                "frame": frame_result.get("frame"),
                "agents_run": len(frame_result.get("agents_run", [])),
                "events_count": len(frame_result.get("events", [])),
                "duration_ms": frame_result.get("duration_ms"),
            }

        # Combine all events
        all_events = inbox_events + frame_result.get("events", [])
        frame = frame_result.get("frame", client.get_latest_frame() + 1)

        # Step 4: Materialize views
        if "materialize" not in config.skip_steps:
            step_materialize(client, all_events, config)
            result["steps"]["materialize"] = {"status": "ok"}

        # Write events to state
        if all_events:
            client.append_events(frame, all_events)

        # Step 5: Compute trending
        if "compute_trending" not in config.skip_steps:
            step_compute_trending(client, config)
            result["steps"]["compute_trending"] = {"status": "ok"}

        # Step 6: Reconcile
        if "reconcile" not in config.skip_steps:
            recon = step_reconcile(client, config)
            result["steps"]["reconcile"] = {"status": "ok", "report": recon}

        # Step 7: Health update
        if "health_update" not in config.skip_steps:
            health_report = step_health_update(client, config)
            result["steps"]["health_update"] = {
                "status": "ok",
                "health_status": health_report.get("status"),
            }

        # Step 8: Commit and push
        if "commit_push" not in config.skip_steps:
            pushed = step_commit_and_push(client, frame, config)
            result["steps"]["commit_push"] = {
                "status": "ok" if pushed else "failed",
            }

        result["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        result["success"] = True

    except Exception as exc:
        result["error"] = str(exc)
        result["success"] = False

        # Always try to update health even on failure
        try:
            step_health_update(client, config)
        except Exception:
            pass

    return result


def main() -> None:
    """CLI entry point."""
    config = Config()
    result = tick(config)

    print(json.dumps(result, indent=2))

    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
