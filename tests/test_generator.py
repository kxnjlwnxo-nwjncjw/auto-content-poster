"""Tests for src/content_generator/generator.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch
import pytest

from src.content_generator.generator import generate_post, generate_all_platforms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_TEXT = "Stay hydrated and move daily! Small habits build big results. 💪 #Fitness #Health"


def _mock_anthropic(text: str = FAKE_TEXT):
    """Return a mock anthropic client whose messages.create returns `text`."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=text)]
    )
    return mock_client


# ---------------------------------------------------------------------------
# generate_post
# ---------------------------------------------------------------------------

class TestGeneratePost:
    def test_returns_required_keys(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            result = generate_post("fitness", "twitter")
        assert {"niche", "platform", "topic", "text", "hashtags", "needs_image", "needs_video"} <= result.keys()

    def test_correct_niche_and_platform_echoed(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            result = generate_post("crypto", "telegram")
        assert result["niche"] == "crypto"
        assert result["platform"] == "telegram"

    def test_text_is_stripped(self):
        padded = "   some post text   "
        with patch("src.content_generator.generator.client", _mock_anthropic(padded)):
            result = generate_post("tech", "twitter")
        assert result["text"] == "some post text"

    def test_twitter_needs_image_false(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            result = generate_post("fitness", "twitter")
        assert result["needs_image"] is False
        assert result["needs_video"] is False

    def test_instagram_needs_image_true(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            result = generate_post("food", "instagram")
        assert result["needs_image"] is True

    def test_unknown_niche_raises(self):
        with pytest.raises(ValueError, match="Unknown niche"):
            generate_post("astrology", "twitter")

    def test_hashtags_is_list(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            result = generate_post("motivation", "facebook")
        assert isinstance(result["hashtags"], list)
        assert len(result["hashtags"]) > 0

    def test_topic_comes_from_niche_profile(self):
        from src.niches.niche_config import NICHE_PROFILES
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            result = generate_post("fitness", "twitter")
        assert result["topic"] in NICHE_PROFILES["fitness"]["topics"]


# ---------------------------------------------------------------------------
# generate_all_platforms
# ---------------------------------------------------------------------------

class TestGenerateAllPlatforms:
    def test_returns_one_post_per_platform(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            results = generate_all_platforms("fitness", ["twitter", "telegram"])
        assert len(results) == 2
        platforms = {r["platform"] for r in results}
        assert platforms == {"twitter", "telegram"}

    def test_bad_platform_skipped_not_raised(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            results = generate_all_platforms("fitness", ["twitter", "nonexistent"])
        # nonexistent raises KeyError in PLATFORM_CONSTRAINTS → caught → skipped
        assert len(results) == 1
        assert results[0]["platform"] == "twitter"

    def test_empty_platform_list_returns_empty(self):
        with patch("src.content_generator.generator.client", _mock_anthropic()):
            results = generate_all_platforms("tech", [])
        assert results == []
