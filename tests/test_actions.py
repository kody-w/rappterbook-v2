"""Tests for scripts/actions/ handlers."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.actions import dispatch, list_actions, HANDLERS
from scripts.actions.agent import (
    handle_heartbeat,
    handle_register_agent,
    handle_update_profile,
)
from scripts.actions.social import (
    handle_follow,
    handle_poke,
    handle_transfer_karma,
    handle_unfollow,
)
from scripts.actions.channel import (
    handle_create_channel,
    handle_moderate,
    handle_update_channel,
)
from scripts.actions.seed import handle_propose_seed, handle_vote_seed


@pytest.fixture
def mock_client() -> MagicMock:
    """Mock state client for handler testing."""
    return MagicMock()


class TestDispatcher:
    """Test action dispatch system."""

    def test_all_handlers_registered(self) -> None:
        """All expected action types are in HANDLERS."""
        expected = [
            "register_agent", "heartbeat", "update_profile",
            "follow", "unfollow", "poke", "transfer_karma",
            "create_channel", "update_channel", "moderate",
            "propose_seed", "vote_seed",
        ]
        for action in expected:
            assert action in HANDLERS, f"Missing handler: {action}"

    def test_dispatch_valid_action(self, mock_client: MagicMock) -> None:
        """Dispatching a valid action returns events."""
        events = dispatch("register_agent", {
            "name": "Test", "framework": "gpt", "bio": "Hi"
        }, mock_client)
        assert len(events) > 0

    def test_dispatch_invalid_action(self, mock_client: MagicMock) -> None:
        """Dispatching an unknown action raises ValueError."""
        with pytest.raises(ValueError, match="Unknown action"):
            dispatch("nonexistent_action", {}, mock_client)

    def test_list_actions(self) -> None:
        """List actions returns sorted list."""
        actions = list_actions()
        assert isinstance(actions, list)
        assert actions == sorted(actions)
        assert len(actions) == len(HANDLERS)


class TestRegisterAgent:
    """Test agent registration."""

    def test_register_success(self, mock_client: MagicMock) -> None:
        """Successful registration returns agent.registered event."""
        events = handle_register_agent(
            {"name": "Alice", "framework": "gpt-4", "bio": "A test agent"},
            mock_client,
        )
        assert len(events) == 1
        assert events[0]["type"] == "agent.registered"
        assert events[0]["data"]["name"] == "Alice"

    def test_register_missing_name(self, mock_client: MagicMock) -> None:
        """Missing name raises ValueError."""
        with pytest.raises(ValueError, match="name"):
            handle_register_agent(
                {"framework": "gpt", "bio": "test"}, mock_client
            )

    def test_register_missing_framework(self, mock_client: MagicMock) -> None:
        """Missing framework raises ValueError."""
        with pytest.raises(ValueError, match="framework"):
            handle_register_agent(
                {"name": "A", "bio": "test"}, mock_client
            )

    def test_register_missing_bio(self, mock_client: MagicMock) -> None:
        """Missing bio raises ValueError."""
        with pytest.raises(ValueError, match="bio"):
            handle_register_agent(
                {"name": "A", "framework": "gpt"}, mock_client
            )

    def test_register_generates_id(self, mock_client: MagicMock) -> None:
        """Registration generates an agent ID from name."""
        events = handle_register_agent(
            {"name": "Test Agent", "framework": "gpt", "bio": "hi"},
            mock_client,
        )
        assert events[0]["data"]["agent_id"] == "test-agent"


class TestHeartbeat:
    """Test heartbeat action."""

    def test_heartbeat_success(self, mock_client: MagicMock) -> None:
        """Heartbeat returns agent.heartbeat event."""
        events = handle_heartbeat({"agent_id": "agent-1"}, mock_client)
        assert len(events) == 1
        assert events[0]["type"] == "agent.heartbeat"

    def test_heartbeat_missing_id(self, mock_client: MagicMock) -> None:
        """Missing agent_id raises ValueError."""
        with pytest.raises(ValueError, match="agent_id"):
            handle_heartbeat({}, mock_client)


class TestUpdateProfile:
    """Test profile update."""

    def test_update_bio(self, mock_client: MagicMock) -> None:
        """Updating bio returns profile_updated event."""
        events = handle_update_profile(
            {"agent_id": "a1", "bio": "New bio"}, mock_client
        )
        assert events[0]["type"] == "agent.profile_updated"
        assert events[0]["data"]["updates"]["bio"] == "New bio"

    def test_update_no_fields(self, mock_client: MagicMock) -> None:
        """No updatable fields raises ValueError."""
        with pytest.raises(ValueError, match="No fields"):
            handle_update_profile({"agent_id": "a1"}, mock_client)

    def test_update_missing_agent_id(self, mock_client: MagicMock) -> None:
        """Missing agent_id raises ValueError."""
        with pytest.raises(ValueError, match="agent_id"):
            handle_update_profile({"bio": "test"}, mock_client)


class TestFollow:
    """Test follow action."""

    def test_follow_success(self, mock_client: MagicMock) -> None:
        """Following returns social.followed event."""
        events = handle_follow(
            {"agent_id": "a1", "target_id": "a2"}, mock_client
        )
        assert events[0]["type"] == "social.followed"

    def test_follow_self(self, mock_client: MagicMock) -> None:
        """Following yourself raises ValueError."""
        with pytest.raises(ValueError, match="yourself"):
            handle_follow({"agent_id": "a1", "target_id": "a1"}, mock_client)

    def test_follow_missing_target(self, mock_client: MagicMock) -> None:
        """Missing target raises ValueError."""
        with pytest.raises(ValueError, match="target_id"):
            handle_follow({"agent_id": "a1"}, mock_client)


class TestUnfollow:
    """Test unfollow action."""

    def test_unfollow_success(self, mock_client: MagicMock) -> None:
        """Unfollowing returns social.unfollowed event."""
        events = handle_unfollow(
            {"agent_id": "a1", "target_id": "a2"}, mock_client
        )
        assert events[0]["type"] == "social.unfollowed"


class TestPoke:
    """Test poke action."""

    def test_poke_success(self, mock_client: MagicMock) -> None:
        """Poking returns social.poked event."""
        events = handle_poke(
            {"agent_id": "a1", "target_id": "a2"}, mock_client
        )
        assert events[0]["type"] == "social.poked"

    def test_poke_with_message(self, mock_client: MagicMock) -> None:
        """Poke can include a message."""
        events = handle_poke(
            {"agent_id": "a1", "target_id": "a2", "message": "Wake up!"},
            mock_client,
        )
        assert events[0]["data"]["message"] == "Wake up!"


class TestTransferKarma:
    """Test karma transfer."""

    def test_transfer_success(self, mock_client: MagicMock) -> None:
        """Transfer returns karma_transferred event."""
        events = handle_transfer_karma(
            {"agent_id": "a1", "target_id": "a2", "amount": 10},
            mock_client,
        )
        assert events[0]["type"] == "social.karma_transferred"
        assert events[0]["data"]["amount"] == 10

    def test_transfer_negative(self, mock_client: MagicMock) -> None:
        """Negative amount raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            handle_transfer_karma(
                {"agent_id": "a1", "target_id": "a2", "amount": -5},
                mock_client,
            )

    def test_transfer_self(self, mock_client: MagicMock) -> None:
        """Transferring to self raises ValueError."""
        with pytest.raises(ValueError, match="yourself"):
            handle_transfer_karma(
                {"agent_id": "a1", "target_id": "a1", "amount": 10},
                mock_client,
            )

    def test_transfer_zero(self, mock_client: MagicMock) -> None:
        """Zero amount raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            handle_transfer_karma(
                {"agent_id": "a1", "target_id": "a2", "amount": 0},
                mock_client,
            )


class TestCreateChannel:
    """Test channel creation."""

    def test_create_success(self, mock_client: MagicMock) -> None:
        """Creating a channel returns channel.created event."""
        events = handle_create_channel(
            {"name": "Philosophy", "description": "Deep thoughts", "creator_id": "a1"},
            mock_client,
        )
        assert events[0]["type"] == "channel.created"
        assert events[0]["data"]["slug"] == "philosophy"

    def test_create_custom_slug(self, mock_client: MagicMock) -> None:
        """Custom slug is used when provided."""
        events = handle_create_channel(
            {
                "name": "My Channel",
                "description": "Test",
                "creator_id": "a1",
                "slug": "custom-slug",
            },
            mock_client,
        )
        assert events[0]["data"]["slug"] == "custom-slug"

    def test_create_missing_name(self, mock_client: MagicMock) -> None:
        """Missing name raises ValueError."""
        with pytest.raises(ValueError, match="name"):
            handle_create_channel(
                {"description": "test", "creator_id": "a1"}, mock_client
            )


class TestModerate:
    """Test moderation action."""

    def test_moderate_flag(self, mock_client: MagicMock) -> None:
        """Flagging content returns channel.moderated event."""
        events = handle_moderate(
            {
                "moderator_id": "mod-1",
                "target_type": "post",
                "target_id": "42",
                "action": "flag",
            },
            mock_client,
        )
        assert events[0]["type"] == "channel.moderated"
        assert events[0]["data"]["action"] == "flag"

    def test_moderate_invalid_action(self, mock_client: MagicMock) -> None:
        """Invalid moderation action raises ValueError."""
        with pytest.raises(ValueError, match="Invalid moderation"):
            handle_moderate(
                {
                    "moderator_id": "mod-1",
                    "target_type": "post",
                    "target_id": "42",
                    "action": "delete",
                },
                mock_client,
            )


class TestProposeSeed:
    """Test seed proposal."""

    def test_propose_success(self, mock_client: MagicMock) -> None:
        """Proposing a seed returns seed.proposed event."""
        events = handle_propose_seed(
            {
                "proposer_id": "a1",
                "title": "Build a Library",
                "description": "Create a community library system",
            },
            mock_client,
        )
        assert events[0]["type"] == "seed.proposed"
        assert events[0]["data"]["status"] == "proposed"

    def test_propose_with_type(self, mock_client: MagicMock) -> None:
        """Seed type is included."""
        events = handle_propose_seed(
            {
                "proposer_id": "a1",
                "title": "Experiment",
                "description": "A test",
                "type": "experiment",
            },
            mock_client,
        )
        assert events[0]["data"]["seed_type"] == "experiment"

    def test_propose_invalid_type(self, mock_client: MagicMock) -> None:
        """Invalid seed type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid seed type"):
            handle_propose_seed(
                {
                    "proposer_id": "a1",
                    "title": "T",
                    "description": "D",
                    "type": "invalid",
                },
                mock_client,
            )


class TestVoteSeed:
    """Test seed voting."""

    def test_vote_for(self, mock_client: MagicMock) -> None:
        """Voting for a seed returns seed.voted event."""
        events = handle_vote_seed(
            {"voter_id": "a1", "seed_id": "s1", "vote": "for"},
            mock_client,
        )
        assert events[0]["type"] == "seed.voted"
        assert events[0]["data"]["vote"] == "for"

    def test_vote_against(self, mock_client: MagicMock) -> None:
        """Voting against returns correct vote."""
        events = handle_vote_seed(
            {"voter_id": "a1", "seed_id": "s1", "vote": "against"},
            mock_client,
        )
        assert events[0]["data"]["vote"] == "against"

    def test_vote_invalid(self, mock_client: MagicMock) -> None:
        """Invalid vote raises ValueError."""
        with pytest.raises(ValueError, match="for.*against"):
            handle_vote_seed(
                {"voter_id": "a1", "seed_id": "s1", "vote": "maybe"},
                mock_client,
            )
