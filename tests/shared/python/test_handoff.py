"""Tests for shared/scripts/handoff.py — preamble parse/render + flag rules."""

from __future__ import annotations

from types import ModuleType

import pytest


class TestParseHandoffSlug:
    def test_parses_ok_block(self, handoff: ModuleType) -> None:
        text = (
            "status: ok\n"
            "next: press\n"
            "artifact: .cheese/cook/demo.md\n"
            "Cooked the retry path; tests green.\n"
        )
        slug = handoff.parse_handoff_slug(text)
        assert slug.status == "ok"
        assert slug.halt_reason is None
        assert slug.next_skill == "press"
        assert slug.artifact == ".cheese/cook/demo.md"
        assert slug.orientation.startswith("Cooked the retry path")

    def test_parses_halt_block(self, handoff: ModuleType) -> None:
        text = (
            "status: halt: tests still failing after 3 attempts\n"
            "next: done\n"
            "artifact: .cheese/press/demo.md\n"
            "Three press attempts could not stabilise the retry test.\n"
        )
        slug = handoff.parse_handoff_slug(text)
        assert slug.status == "halt"
        assert slug.halt_reason == "tests still failing after 3 attempts"
        assert slug.is_halt() is True
        assert slug.next_skill == "done"

    def test_tolerates_leading_slash_on_next(self, handoff: ModuleType) -> None:
        text = (
            "status: ok\n"
            "next: /age\n"
            "artifact: \n"
            "Review the diff.\n"
        )
        slug = handoff.parse_handoff_slug(text)
        assert slug.next_skill == "age"
        assert slug.artifact is None

    def test_rejects_missing_lines(self, handoff: ModuleType) -> None:
        with pytest.raises(handoff.HandoffParseError, match="needs status"):
            handoff.parse_handoff_slug("status: ok\nnext: age\n")

    def test_rejects_unknown_status(self, handoff: ModuleType) -> None:
        text = (
            "status: maybe\n"
            "next: age\n"
            "artifact: \n"
            "Orientation.\n"
        )
        with pytest.raises(handoff.HandoffParseError, match="status must be"):
            handoff.parse_handoff_slug(text)

    def test_rejects_halt_without_reason(self, handoff: ModuleType) -> None:
        text = (
            "status: halt:\n"
            "next: done\n"
            "artifact: \n"
            "Orientation.\n"
        )
        with pytest.raises(handoff.HandoffParseError, match="halt status requires"):
            handoff.parse_handoff_slug(text)


class TestRenderHandoffSlug:
    def test_round_trip_ok(self, handoff: ModuleType) -> None:
        original = handoff.HandoffSlug(
            status="ok",
            halt_reason=None,
            next_skill="press",
            artifact=".cheese/cook/demo.md",
            orientation="Cooked the retry path.",
        )
        rendered = handoff.render_handoff_slug(original)
        reparsed = handoff.parse_handoff_slug(rendered + "\n")
        assert reparsed == original

    def test_round_trip_halt(self, handoff: ModuleType) -> None:
        original = handoff.HandoffSlug(
            status="halt",
            halt_reason="dep version conflict",
            next_skill="done",
            artifact=None,
            orientation="Stopped — version-doctor required.",
        )
        rendered = handoff.render_handoff_slug(original)
        assert "status: halt: dep version conflict" in rendered
        reparsed = handoff.parse_handoff_slug(rendered + "\n")
        assert reparsed == original

    def test_halt_without_reason_raises(self, handoff: ModuleType) -> None:
        bad = handoff.HandoffSlug(
            status="halt",
            halt_reason=None,
            next_skill="done",
            artifact=None,
            orientation="x",
        )
        with pytest.raises(ValueError, match="halt_reason"):
            handoff.render_handoff_slug(bad)


class TestParseSkillDispatch:
    def test_strips_slash_and_splits(self, handoff: ModuleType) -> None:
        skill, args = handoff.parse_skill_dispatch("/age demo-slug --hard")
        assert skill == "age"
        assert args == ["demo-slug", "--hard"]

    def test_bare_skill(self, handoff: ModuleType) -> None:
        skill, args = handoff.parse_skill_dispatch("/cure")
        assert skill == "cure"
        assert args == []

    def test_rejects_non_dispatch(self, handoff: ModuleType) -> None:
        with pytest.raises(ValueError, match="not a skill dispatch"):
            handoff.parse_skill_dispatch("age demo-slug")


class TestPropagateFlags:
    def test_hard_always_propagates(self, handoff: ModuleType) -> None:
        assert handoff.propagate_flags(["--hard"], in_auto_chain=False) == ["--hard"]
        assert handoff.propagate_flags(["--hard"], in_auto_chain=True) == ["--hard"]

    def test_auto_only_in_chain(self, handoff: ModuleType) -> None:
        assert handoff.propagate_flags(["--auto"], in_auto_chain=False) == []
        assert handoff.propagate_flags(["--auto"], in_auto_chain=True) == ["--auto"]

    def test_unrelated_flags_dropped(self, handoff: ModuleType) -> None:
        # Only --hard / --auto are recognised; anything else does not propagate.
        result = handoff.propagate_flags(
            ["--hard", "--verbose", "--stake=medium+"], in_auto_chain=True
        )
        assert result == ["--hard"]

    def test_flag_with_value_propagates(self, handoff: ModuleType) -> None:
        # --hard=true should still propagate based on the bare name.
        result = handoff.propagate_flags(["--hard=true"], in_auto_chain=False)
        assert result == ["--hard=true"]
