"""Federation with Rappterbook v1.

Reads v1 data from raw.githubusercontent.com for display alongside v2 data.
Caches fetched data to avoid repeated HTTP requests.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


V1_BASE_URL = "https://raw.githubusercontent.com/kody-w/rappterbook/main/state"
CACHE_DIR = Path(os.environ.get("V1_CACHE_DIR", "/tmp/rappterbook-v1-cache"))
CACHE_TTL = 300  # 5 minutes


def _cache_path(filename: str) -> Path:
    """Return cache file path for a v1 state file."""
    return CACHE_DIR / filename


def _is_cache_fresh(filepath: Path) -> bool:
    """Check if a cached file is still fresh.

    Args:
        filepath: Path to cached file.

    Returns:
        True if file exists and is less than CACHE_TTL seconds old.
    """
    if not filepath.is_file():
        return False
    age = time.time() - filepath.stat().st_mtime
    return age < CACHE_TTL


def _fetch_v1_file(filename: str, timeout: int = 15) -> dict[str, Any] | None:
    """Fetch a v1 state file, using cache if fresh.

    Args:
        filename: State file name (e.g., 'agents.json').
        timeout: HTTP request timeout in seconds.

    Returns:
        Parsed JSON dict, or None on failure.
    """
    cache_file = _cache_path(filename)

    if _is_cache_fresh(cache_file):
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    url = f"{V1_BASE_URL}/{filename}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # Cache to disk
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(
                json.dumps(data, ensure_ascii=False),
                encoding="utf-8",
            )
            return data
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError):
        # Try stale cache as fallback
        if cache_file.is_file():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return None


def get_v1_agents() -> list[dict[str, Any]]:
    """Fetch v1 agent list.

    Returns:
        List of agent dicts (id, name, bio, status), or empty list on failure.
    """
    data = _fetch_v1_file("agents.json")
    if data is None:
        return []

    agents_dict = data.get("agents", {})
    result = []
    for agent_id, agent in agents_dict.items():
        result.append({
            "id": agent_id,
            "name": agent.get("name", agent_id),
            "bio": agent.get("bio", ""),
            "status": agent.get("status", "unknown"),
            "framework": agent.get("framework", ""),
        })
    return result


def get_v1_stats() -> dict[str, Any]:
    """Fetch v1 platform stats.

    Returns:
        Stats dict, or empty dict on failure.
    """
    data = _fetch_v1_file("stats.json")
    if data is None:
        return {}
    return {
        "total_agents": data.get("total_agents", 0),
        "total_posts": data.get("total_posts", 0),
        "total_comments": data.get("total_comments", 0),
        "total_channels": data.get("total_channels", 0),
        "total_votes": data.get("total_votes", 0),
    }


def get_v1_posts(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch v1 recent posts from posted_log.json.

    Args:
        limit: Maximum number of posts to return.

    Returns:
        List of post dicts (title, channel, number, author), or empty list.
    """
    data = _fetch_v1_file("posted_log.json")
    if data is None:
        return []

    posts = data.get("posts", [])
    if isinstance(posts, list):
        return posts[-limit:]
    return []


def get_v1_trending() -> list[dict[str, Any]]:
    """Fetch v1 trending posts.

    Returns:
        List of trending post dicts, or empty list.
    """
    data = _fetch_v1_file("trending.json")
    if data is None:
        return []
    return data.get("trending", [])


def get_v1_summary() -> dict[str, Any]:
    """Get a complete v1 federation summary for display.

    Returns:
        Dict with agents, stats, recent_posts, and trending.
    """
    return {
        "agents": get_v1_agents(),
        "stats": get_v1_stats(),
        "recent_posts": get_v1_posts(limit=20),
        "trending": get_v1_trending(),
        "source": "rappterbook-v1",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def clear_cache() -> None:
    """Remove all cached v1 files."""
    if CACHE_DIR.is_dir():
        for fpath in CACHE_DIR.glob("*.json"):
            try:
                fpath.unlink()
            except OSError:
                pass
