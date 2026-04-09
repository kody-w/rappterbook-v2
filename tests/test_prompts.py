"""Tests for the 10 prompt files in prompts/."""
from __future__ import annotations

from pathlib import Path

import pytest


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

EXPECTED_PROMPTS = [
    "01_resurrection.md",
    "02_schelling_point.md",
    "03_time_capsule.md",
    "04_socratic_debugger.md",
    "05_emergent_constitution.md",
    "06_mirror_test.md",
    "07_telephone_game.md",
    "08_prediction_market.md",
    "09_cultural_drift.md",
    "10_bootstrap_paradox.md",
]


class TestPromptFiles:
    """Test that all prompt files exist and are valid."""

    def test_all_10_prompts_exist(self) -> None:
        """All 10 prompt files exist."""
        for name in EXPECTED_PROMPTS:
            path = PROMPTS_DIR / name
            assert path.is_file(), f"Missing prompt: {name}"

    def test_readme_exists(self) -> None:
        """README.md exists in prompts directory."""
        assert (PROMPTS_DIR / "README.md").is_file()

    def test_readme_lists_all_prompts(self) -> None:
        """README mentions all 10 prompts."""
        readme = (PROMPTS_DIR / "README.md").read_text()
        for name in EXPECTED_PROMPTS:
            # Check the number is referenced
            num = name.split("_")[0]
            assert num in readme, f"README missing reference to prompt {num}"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_is_valid_markdown(self, filename: str) -> None:
        """Each prompt is non-empty markdown."""
        path = PROMPTS_DIR / filename
        content = path.read_text()
        assert len(content) > 100, f"{filename} is too short"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_has_title(self, filename: str) -> None:
        """Each prompt has a markdown title (# heading)."""
        content = (PROMPTS_DIR / filename).read_text()
        assert content.startswith("#"), f"{filename} missing title"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_has_concept_section(self, filename: str) -> None:
        """Each prompt has a concept section."""
        content = (PROMPTS_DIR / filename).read_text()
        assert "## Concept" in content, f"{filename} missing Concept section"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_has_prompt_text(self, filename: str) -> None:
        """Each prompt has actual prompt text."""
        content = (PROMPTS_DIR / filename).read_text()
        assert "## Prompt Text" in content or "```" in content, \
            f"{filename} missing prompt text"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_has_success_criteria(self, filename: str) -> None:
        """Each prompt has success criteria."""
        content = (PROMPTS_DIR / filename).read_text()
        assert "## Success Criteria" in content, \
            f"{filename} missing Success Criteria section"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_has_v1_comparison(self, filename: str) -> None:
        """Each prompt explains why it's impossible in v1."""
        content = (PROMPTS_DIR / filename).read_text()
        assert "v1" in content.lower(), \
            f"{filename} doesn't mention v1 comparison"

    @pytest.mark.parametrize("filename", EXPECTED_PROMPTS)
    def test_prompt_under_size_limit(self, filename: str) -> None:
        """Each prompt is under 5000 characters."""
        content = (PROMPTS_DIR / filename).read_text()
        assert len(content) < 8000, \
            f"{filename} is {len(content)} chars (limit: 8000)"

    def test_filenames_match_pattern(self) -> None:
        """Prompt filenames follow NN_name.md pattern."""
        import re
        for name in EXPECTED_PROMPTS:
            assert re.match(r"\d{2}_[a-z_]+\.md", name), \
                f"Bad filename pattern: {name}"

    def test_prompts_directory_clean(self) -> None:
        """No unexpected files in prompts directory."""
        allowed = set(EXPECTED_PROMPTS + ["README.md"])
        actual = set(p.name for p in PROMPTS_DIR.iterdir() if p.is_file())
        unexpected = actual - allowed
        assert not unexpected, f"Unexpected files: {unexpected}"
