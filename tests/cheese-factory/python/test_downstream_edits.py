"""Lint tests for downstream SKILL.md edits required by the cheese-factory spec.

The spec mandates small contract amendments to two existing skills:
- /age must document the inline-degrade mode for sub-agent invocation.
- /cheese must list /cheese-factory as a routing target.

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
        # The detection marker must be named so cheese-factory curd workers
        # know what to pass.
        assert "invoked-from: cheese-factory-curd" in age_body or (
            "invoked-from:" in age_body and "cheese-factory" in age_body
        )

    def test_nesting_limit_rationale_present(self, age_body: str) -> None:
        # The "why" must travel with the contract — level-2 nesting is the
        # specific harness limit being honoured.
        lowered = age_body.lower()
        assert "nesting" in lowered, "must name the nesting-depth limit"

    def test_output_identity_guaranteed(self, age_body: str) -> None:
        # Output between fan-out and inline-degrade must be identical or
        # downstream chaining breaks.
        assert "identical" in age_body.lower() or "same" in age_body.lower()


class TestCheeseRoutesToCheeseFactory:
    def test_intent_shapes_table_lists_cheese_factory(self, cheese_body: str) -> None:
        # Must appear in the routing table.
        assert "cheese-factory" in cheese_body

    def test_handoff_offers_cheese_factory(self, cheese_body: str) -> None:
        # Default option set must include cheese-factory dispatch.
        assert "/cheese-factory" in cheese_body

    def test_trigger_phrases_present(self, cheese_body: str) -> None:
        lowered = cheese_body.lower()
        # At least one of the spec-named user phrases must be present.
        assert (
            "5+" in lowered
            or "many curds" in lowered
            or "parallelize" in lowered
            or "send through the factory" in lowered
        )


class TestSkillTableUpdates:
    def test_readme_lists_cheese_factory(self, readme_body: str) -> None:
        assert "skills/cheese-factory/SKILL.md" in readme_body
        assert "/cheese-factory" in readme_body

    def test_agents_lists_cheese_factory(self, agents_body: str) -> None:
        assert "/cheese-factory" in agents_body
