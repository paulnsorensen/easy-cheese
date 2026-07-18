"""Lint tests for typed ultracook phase dispatch and downstream routing."""

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


class TestAgeUltracookDispatch:
    def test_ultracook_uses_fresh_reviewer_agents(self, age_body: str) -> None:
        assert "fresh-context" in age_body.lower()
        assert "reviewer" in age_body.lower()

    def test_parallel_curd_inline_degrade_is_removed(self, age_body: str) -> None:
        assert "invoked-from: ultracook-curd" not in age_body
        assert "Inline-degrade mode" not in age_body


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
