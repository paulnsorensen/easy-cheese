"""Lint tests for downstream SKILL.md edits required by the ultracook retirement.

After folding /cheese-factory into /ultracook:
- /age must document the inline-degrade mode for sub-agent invocation.
- /cheese must route decomposable specs to /ultracook (parallel mode).

These tests assert those clauses are present so silent removal surfaces in CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS = REPO_ROOT / "skills"


@pytest.fixture(scope="module")
def age_body() -> str:
    return (SKILLS / "age" / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def cheese_body() -> str:
    return (SKILLS / "cheese" / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def readme_body() -> str:
    return (REPO_ROOT / "README.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def agents_body() -> str:
    return (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")


class TestAgeInlineDegrade:
    def test_inline_degrade_section_exists(self, age_body: str) -> None:
        # Header style follows existing /age conventions (### sub-section).
        assert "Inline-degrade mode" in age_body

    def test_marker_phrase_documented(self, age_body: str) -> None:
        # The detection marker must be named so ultracook curd workers
        # know what to pass.
        assert "invoked-from: ultracook-curd" in age_body

    def test_nesting_limit_rationale_present(self, age_body: str) -> None:
        # The "why" must travel with the contract — level-2 nesting is the
        # specific harness limit being honoured.
        lowered = age_body.lower()
        assert "nesting" in lowered, "must name the nesting-depth limit"

    def test_output_identity_guaranteed(self, age_body: str) -> None:
        # Output between fan-out and inline-degrade must be identical or
        # downstream chaining breaks.
        assert "identical" in age_body.lower() or "same" in age_body.lower()


class TestCheeseRoutesToUltracook:
    def test_intent_shapes_table_lists_ultracook(self, cheese_body: str) -> None:
        # Must appear in the routing table.
        assert "/ultracook" in cheese_body

    def test_handoff_offers_ultracook(self, cheese_body: str) -> None:
        # Default option set must route decomposable specs to /ultracook.
        assert "/ultracook" in cheese_body
        assert "decomposable spec" in cheese_body

    def test_trigger_phrases_present(self, cheese_body: str) -> None:
        lowered = cheese_body.lower()
        # At least one ultracook-parallel phrase must be present.
        assert (
            "parallel curd" in lowered
            or "2+" in lowered
            or "many curds" in lowered
            or "parallelize" in lowered
            or "decompos" in lowered
        )


class TestSkillTableUpdates:
    def test_readme_lists_ultracook(self, readme_body: str) -> None:
        assert "skills/ultracook/SKILL.md" in readme_body
        assert "/ultracook" in readme_body

    def test_agents_lists_ultracook(self, agents_body: str) -> None:
        assert "/ultracook" in agents_body
