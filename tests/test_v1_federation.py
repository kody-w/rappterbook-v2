"""Tests for scripts/v1_federation.py."""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from scripts.v1_federation import (
    _cache_path,
    _fetch_v1_file,
    _is_cache_fresh,
    clear_cache,
    get_v1_agents,
    get_v1_posts,
    get_v1_stats,
    get_v1_summary,
    get_v1_trending,
    CACHE_TTL,
)


@pytest.fixture
def v1_cache(tmp_path: Path) -> Path:
    """Set up a temporary v1 cache directory."""
    cache = tmp_path / "v1cache"
    cache.mkdir()
    return cache


class TestCacheFreshness:
    """Test cache TTL checks."""

    def test_missing_file_not_fresh(self, tmp_path: Path) -> None:
        """Missing file is not fresh."""
        assert _is_cache_fresh(tmp_path / "nope.json") is False

    def test_new_file_is_fresh(self, tmp_path: Path) -> None:
        """Just-created file is fresh."""
        f = tmp_path / "test.json"
        f.write_text("{}")
        assert _is_cache_fresh(f) is True


class TestFetchV1File:
    """Test fetching v1 state files."""

    @patch("scripts.v1_federation.CACHE_DIR")
    @patch("scripts.v1_federation.urllib.request.urlopen")
    def test_fetches_from_network(
        self, mock_urlopen: MagicMock, mock_cache: MagicMock, tmp_path: Path
    ) -> None:
        """Fetches from network when cache is empty."""
        with patch("scripts.v1_federation.CACHE_DIR", tmp_path):
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({"agents": {}}).encode()
            mock_resp.__enter__ = MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = _fetch_v1_file("agents.json")
            assert result is not None
            assert "agents" in result

    @patch("scripts.v1_federation.CACHE_DIR")
    def test_uses_cache_when_fresh(self, mock_cache: MagicMock, tmp_path: Path) -> None:
        """Uses cached file when fresh."""
        with patch("scripts.v1_federation.CACHE_DIR", tmp_path):
            cache_file = tmp_path / "agents.json"
            cache_file.write_text(json.dumps({"agents": {"cached": True}}))
            result = _fetch_v1_file("agents.json")
            assert result is not None
            assert result.get("agents", {}).get("cached") is True

    @patch("scripts.v1_federation.CACHE_DIR")
    @patch("scripts.v1_federation.urllib.request.urlopen")
    def test_network_failure_returns_none(
        self, mock_urlopen: MagicMock, mock_cache: MagicMock, tmp_path: Path
    ) -> None:
        """Returns None on network failure with no cache."""
        import urllib.error
        with patch("scripts.v1_federation.CACHE_DIR", tmp_path):
            mock_urlopen.side_effect = urllib.error.URLError("timeout")
            result = _fetch_v1_file("agents.json")
            assert result is None


class TestGetV1Agents:
    """Test v1 agent fetching."""

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_returns_list(self, mock_fetch: MagicMock) -> None:
        """Returns a list of agent dicts."""
        mock_fetch.return_value = {
            "agents": {
                "agent-1": {"name": "Alice", "bio": "Test", "status": "active"},
            }
        }
        agents = get_v1_agents()
        assert len(agents) == 1
        assert agents[0]["name"] == "Alice"

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_handles_failure(self, mock_fetch: MagicMock) -> None:
        """Returns empty list on failure."""
        mock_fetch.return_value = None
        assert get_v1_agents() == []

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_agent_fields(self, mock_fetch: MagicMock) -> None:
        """Agent dicts have expected fields."""
        mock_fetch.return_value = {
            "agents": {
                "a1": {"name": "X", "bio": "Y", "status": "active", "framework": "gpt"},
            }
        }
        agents = get_v1_agents()
        a = agents[0]
        assert "id" in a
        assert "name" in a
        assert "bio" in a
        assert "status" in a


class TestGetV1Stats:
    """Test v1 stats fetching."""

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_returns_stats(self, mock_fetch: MagicMock) -> None:
        """Returns stats dict."""
        mock_fetch.return_value = {
            "total_agents": 100,
            "total_posts": 5000,
            "total_comments": 20000,
            "total_channels": 15,
            "total_votes": 10000,
        }
        stats = get_v1_stats()
        assert stats["total_agents"] == 100
        assert stats["total_posts"] == 5000

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_handles_failure(self, mock_fetch: MagicMock) -> None:
        """Returns empty dict on failure."""
        mock_fetch.return_value = None
        assert get_v1_stats() == {}


class TestGetV1Posts:
    """Test v1 post fetching."""

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_returns_posts(self, mock_fetch: MagicMock) -> None:
        """Returns list of posts."""
        mock_fetch.return_value = {
            "posts": [
                {"title": "Post 1", "channel": "general", "number": 1},
                {"title": "Post 2", "channel": "tech", "number": 2},
            ]
        }
        posts = get_v1_posts()
        assert len(posts) == 2

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_respects_limit(self, mock_fetch: MagicMock) -> None:
        """Limit is respected."""
        mock_fetch.return_value = {
            "posts": [{"title": f"Post {i}"} for i in range(100)]
        }
        posts = get_v1_posts(limit=5)
        assert len(posts) == 5

    @patch("scripts.v1_federation._fetch_v1_file")
    def test_handles_failure(self, mock_fetch: MagicMock) -> None:
        """Returns empty list on failure."""
        mock_fetch.return_value = None
        assert get_v1_posts() == []


class TestGetV1Summary:
    """Test v1 summary generation."""

    @patch("scripts.v1_federation.get_v1_agents")
    @patch("scripts.v1_federation.get_v1_stats")
    @patch("scripts.v1_federation.get_v1_posts")
    @patch("scripts.v1_federation.get_v1_trending")
    def test_summary_structure(
        self,
        mock_trending: MagicMock,
        mock_posts: MagicMock,
        mock_stats: MagicMock,
        mock_agents: MagicMock,
    ) -> None:
        """Summary has all expected fields."""
        mock_agents.return_value = []
        mock_stats.return_value = {}
        mock_posts.return_value = []
        mock_trending.return_value = []

        summary = get_v1_summary()
        assert "agents" in summary
        assert "stats" in summary
        assert "recent_posts" in summary
        assert "source" in summary
        assert summary["source"] == "rappterbook-v1"


class TestClearCache:
    """Test cache clearing."""

    @patch("scripts.v1_federation.CACHE_DIR")
    def test_clears_cache(self, mock_dir: MagicMock, tmp_path: Path) -> None:
        """Clears all cached files."""
        with patch("scripts.v1_federation.CACHE_DIR", tmp_path):
            (tmp_path / "agents.json").write_text("{}")
            (tmp_path / "stats.json").write_text("{}")
            clear_cache()
            assert len(list(tmp_path.glob("*.json"))) == 0
