"""Contract tests for the `/cure` skill after the r014 skill-review cure.

The review, edge, and hub notes recorded four defects that live in this area:
the documented handoff command deleted the report body, it could not emit the
terminal transition, the typed curd path was the only documented input path,
and the post-PR write-back ran after `/plate` had already committed.

The prose assertions below are the regression evidence for those fixes: each
one fails if the clause is removed again. The two writer probes prove that the
documented commands really behave the way the prose now claims.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared.write_handoff_artifact import write_artifact

REPO_ROOT = Path(__file__).resolve().parents[2]
CURE = REPO_ROOT / "skills" / "cure"

CURD_RESULT_SCHEMA = "https://schemas.easy-cheese.dev/curd-result"


def _read(name: str) -> str:
    return (CURE / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def skill() -> str:
    return _read("SKILL.md")


def _writer_blocks(skill: str) -> list[str]:
    blocks = cast(list[str], re.findall(r"```text\n(.*?)```", skill, re.DOTALL))
    return [block for block in blocks if "write-handoff-artifact" in block]


# --- handoff writer command -------------------------------------------------


class TestHandoffWriterCommand:
    def test_every_writer_command_passes_a_body_file(self, skill: str) -> None:
        blocks = _writer_blocks(skill)
        assert blocks, "cure must document the write-handoff-artifact command"
        for block in blocks:
            assert "--body-file" in block, (
                "a writer command without --body-file replaces the cure report "
                f"with the bare preamble:\n{block}"
            )

    def test_review_command_carries_the_curd_result_schema(self, skill: str) -> None:
        review = [b for b in _writer_blocks(skill) if "--next age" in b]
        assert len(review) == 1
        assert CURD_RESULT_SCHEMA in review[0]
        assert "--baseline" in review[0]
        assert "--durable-flags" in review[0]

    def test_terminal_command_omits_the_payload_schema(self, skill: str) -> None:
        terminal = [b for b in _writer_blocks(skill) if "--next done" in b]
        assert len(terminal) == 1, "cure must document a separate terminal command"
        assert "--payload-schema" not in terminal[0], (
            "a terminal transition rejects a payload schema"
        )

    def test_next_is_not_described_as_storage_routing(self, skill: str) -> None:
        assert "`phase=cure` and `next=age` control storage routing only." not in skill
        assert "`phase=cure` controls storage routing." in skill

    def test_artifact_names_the_consumed_report(self, skill: str) -> None:
        assert "artifact: <path-if-any>" not in skill
        assert "`artifact:` names the source report that this run consumed." in skill


class TestDocumentedWriterBehaviour:
    """Run the documented commands: the body must survive both transitions."""

    def test_review_transition_preserves_the_body(self, tmp_path: Path) -> None:
        body = "# Cure report\n\n### Applied\n\n- 1 — fixed\n"
        written = write_artifact(
            slug="demo",
            status="ok",
            next_skill="age",
            artifact=".cheese/age/demo.md",
            orientation="cure applied 1 finding",
            body=body,
            root=tmp_path,
            phase="cure",
            payload_schema_uri=CURD_RESULT_SCHEMA,
            durable_flags="none",
            baseline="none",
        )
        text = written.read_text(encoding="utf-8")
        assert "### Applied" in text
        assert "baseline: none" in text
        assert "durable_flags: none" in text
        assert text.index("next: age") < text.index("### Applied")

    def test_terminal_transition_without_a_payload_schema(self, tmp_path: Path) -> None:
        written = write_artifact(
            slug="demo",
            status="ok",
            next_skill="done",
            artifact=".cheese/age/demo.md",
            orientation="cure applied 1 finding",
            body="# Cure report\n\n### Applied\n\n- 1 — fixed\n",
            root=tmp_path,
            phase="cure",
            baseline="none",
        )
        text = written.read_text(encoding="utf-8")
        assert "next: done" in text
        assert "### Applied" in text


# --- input paths ------------------------------------------------------------


class TestInputPaths:
    def test_report_path_does_not_require_a_typed_plan(self, skill: str) -> None:
        assert "Take the report path in every other case." in skill
        assert (
            "Take the typed path only when the handoff also supplies a `CurdPlan`."
            in skill
        )

    def test_planner_result_is_no_longer_required(self, skill: str) -> None:
        assert "PlannerResult" not in skill, (
            "no producer transports PlannerResult to cure"
        )

    def test_source_report_is_consumed_and_validated(self, skill: str) -> None:
        assert "`handoff_context.source_report`" in skill
        assert "halt: unreadable source report" in skill

    def test_selection_guide_lists_the_range_verb(self) -> None:
        assert "1-3" in _read("references/selection.md")


# --- downstream dispatch ----------------------------------------------------


class TestDownstreamDispatch:
    def test_age_dispatch_carries_the_slug(self, skill: str) -> None:
        dispatches = cast(list[str], re.findall(r"/age [^\n`]*--scope", skill))
        for match in dispatches:
            assert "<slug>" in match, f"cure must send the slug to age: {match!r}"

    def test_write_back_runs_before_plate(self, skill: str) -> None:
        assert "Run § Post-PR write-back before every `/plate` dispatch." in skill
        assert "After publication, run § Post-PR learnings write-back." not in skill

    def test_write_back_reference_states_the_plate_order(self) -> None:
        writeback = _read("references/post-pr-writeback.md")
        assert "Run this write-back before Cure dispatches `/plate`." in writeback
        assert "[TBD]" not in writeback, "the deferred move section is superseded"

    def test_hard_gate_stops_only_on_failed_and_non_tty(self, skill: str) -> None:
        assert "Stop publication on a `FAILED` gate result." in skill
        assert "fail-open policy" in skill


# --- reviewer resolution ----------------------------------------------------


class TestReviewerResolution:
    def test_reviewer_resolves_through_the_shared_resolver(self, skill: str) -> None:
        assert "agent-resolution.md" in skill
        assert "Halt when fresh-context isolation is unavailable." in skill

    def test_no_pinned_model_for_the_taste_test(self, skill: str) -> None:
        assert "pinned Opus model" not in skill
