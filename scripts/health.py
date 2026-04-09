"""Health monitoring for Rappterbook v2.

Checks state repo freshness, event log integrity, and reports status.
Supports external health ping (e.g., Healthchecks.io).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


# Status thresholds (in seconds)
HEALTHY_THRESHOLD = 2 * 3600       # < 2 hours
STALE_THRESHOLD = 6 * 3600         # 2-6 hours
DEGRADED_THRESHOLD = 24 * 3600     # 6-24 hours
# > 24 hours = dead


def compute_status(last_event_age_seconds: float | None) -> str:
    """Compute health status from event age.

    Args:
        last_event_age_seconds: Seconds since last event, or None if unknown.

    Returns:
        Status string: 'healthy', 'stale', 'degraded', 'dead', or 'unknown'.
    """
    if last_event_age_seconds is None:
        return "unknown"
    if last_event_age_seconds < HEALTHY_THRESHOLD:
        return "healthy"
    if last_event_age_seconds < STALE_THRESHOLD:
        return "stale"
    if last_event_age_seconds < DEGRADED_THRESHOLD:
        return "degraded"
    return "dead"


def count_events(state_dir: Path) -> int:
    """Count total events across all frames.

    Args:
        state_dir: Path to state directory.

    Returns:
        Total event count.
    """
    events_dir = state_dir / "events"
    if not events_dir.is_dir():
        return 0

    total = 0
    for frame_dir in events_dir.iterdir():
        if frame_dir.is_dir() and frame_dir.name.startswith("frame-"):
            for event_file in frame_dir.glob("*.json"):
                try:
                    data = json.loads(event_file.read_text(encoding="utf-8"))
                    total += len(data.get("events", []))
                except (json.JSONDecodeError, OSError):
                    continue
    return total


def count_frames(state_dir: Path) -> int:
    """Count total frames in the events directory.

    Args:
        state_dir: Path to state directory.

    Returns:
        Number of frame directories.
    """
    events_dir = state_dir / "events"
    if not events_dir.is_dir():
        return 0

    return sum(
        1 for d in events_dir.iterdir()
        if d.is_dir() and d.name.startswith("frame-")
    )


def get_last_event_time(state_dir: Path) -> float | None:
    """Find the timestamp of the most recent event.

    Args:
        state_dir: Path to state directory.

    Returns:
        Unix timestamp of last event, or None if no events.
    """
    events_dir = state_dir / "events"
    if not events_dir.is_dir():
        return None

    latest: float | None = None
    # Check only the highest frame directory
    frame_dirs = sorted(
        (d for d in events_dir.iterdir()
         if d.is_dir() and d.name.startswith("frame-")),
        key=lambda d: d.name,
        reverse=True,
    )

    for frame_dir in frame_dirs[:3]:  # Check last 3 frames max
        for event_file in frame_dir.glob("*.json"):
            try:
                data = json.loads(event_file.read_text(encoding="utf-8"))
                ts = data.get("timestamp_ms", 0) / 1000.0
                if latest is None or ts > latest:
                    latest = ts
            except (json.JSONDecodeError, OSError):
                continue
        if latest is not None:
            break

    return latest


def check_integrity(state_dir: Path) -> dict[str, Any]:
    """Check event log integrity.

    Args:
        state_dir: Path to state directory.

    Returns:
        Dict with 'ok' bool and list of 'issues'.
    """
    issues: list[str] = []
    events_dir = state_dir / "events"

    if not events_dir.is_dir():
        return {"ok": True, "issues": ["No events directory (fresh install)"]}

    for frame_dir in sorted(events_dir.iterdir()):
        if not frame_dir.is_dir() or not frame_dir.name.startswith("frame-"):
            continue

        for event_file in frame_dir.glob("*.json"):
            try:
                data = json.loads(event_file.read_text(encoding="utf-8"))
                if "events" not in data:
                    issues.append(f"{event_file.name}: missing 'events' key")
                if "frame" not in data:
                    issues.append(f"{event_file.name}: missing 'frame' key")
            except json.JSONDecodeError as exc:
                issues.append(f"{event_file.name}: invalid JSON: {exc}")
            except OSError as exc:
                issues.append(f"{event_file.name}: read error: {exc}")

    return {"ok": len(issues) == 0, "issues": issues}


def build_health_report(state_dir: Path) -> dict[str, Any]:
    """Build a complete health report.

    Args:
        state_dir: Path to state directory.

    Returns:
        Health report dict.
    """
    last_event_time = get_last_event_time(state_dir)
    now = time.time()

    age = None
    if last_event_time is not None:
        age = now - last_event_time

    status = compute_status(age)
    integrity = check_integrity(state_dir)

    return {
        "status": status,
        "last_event_time": last_event_time,
        "last_event_age_seconds": age,
        "total_events": count_events(state_dir),
        "total_frames": count_frames(state_dir),
        "integrity": integrity,
        "checked_at": now,
        "checked_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
    }


def write_health_json(report: dict[str, Any], output_path: Path) -> None:
    """Write health report to a JSON file.

    Args:
        report: Health report dict.
        output_path: Path to write the JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def ping_external(url: str, status: str) -> bool:
    """Ping an external health monitoring service.

    Args:
        url: Health check URL (e.g., Healthchecks.io ping URL).
        status: Current health status string.

    Returns:
        True if ping succeeded.
    """
    if not url:
        return False

    # Append /fail for non-healthy statuses
    ping_url = url
    if status not in ("healthy",):
        ping_url = url.rstrip("/") + "/fail"

    try:
        req = urllib.request.Request(ping_url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError):
        return False


def run_health_check(
    state_dir: Path,
    output_path: Path | None = None,
    ping_url: str = "",
) -> dict[str, Any]:
    """Run a complete health check.

    Args:
        state_dir: Path to state directory.
        output_path: If set, write health.json here.
        ping_url: If set, ping this URL with health status.

    Returns:
        Health report dict.
    """
    report = build_health_report(state_dir)

    if output_path:
        write_health_json(report, output_path)

    if ping_url:
        report["external_ping"] = ping_external(ping_url, report["status"])

    return report
