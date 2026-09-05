"""Canonical projection Markdown: render, parse, derive, and pin.

A projection is generated, so it round-trips exactly; it is also the file a
human may edit, so parsing derives status from the gating entries and ignores
whatever the document claims, and the digest covers every other byte.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest
from attrs import evolve
from easy_cheese_schemas import (
    Durability,
    NextAction,
    NextMove,
    WheypointProjection,
    WheypointRecord,
    WheypointStatus,
)

from easy_cheese.skills.wheypoint import projection, records

SRC = Path(__file__).resolve().parents[3] / "src/easy_cheese/skills/wheypoint"


def test_a_built_projection_derives_everything_from_the_record(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    built, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )

    assert built.work_id == record.work_id
    assert built.revision_id == record.revision_id
    assert built.schema_version == record.schema_version
    assert built.record_digest == records.record_digest(record)
    assert built.next_action == record.next_action
    assert built.gating_entry_ids == []
    assert built.status is WheypointStatus.OK
    assert built.projection_digest == projection.projection_digest_of_text(markdown)


def test_the_rendered_preamble_carries_the_whole_contract(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    built, markdown = projection.build_projection(
        record, durability=Durability.REPO_SNAPSHOT
    )
    preamble = markdown.splitlines()[:11]

    assert preamble == [
        "status: ok",
        "next: cook",
        "artifact: .cheese/cook/wheypoint-record-store-projection.md",
        "Implement the canonical record runtime.",
        "",
        "work_id: work-0001",
        "revision_id: rev-0001",
        f"record_digest: {built.record_digest}",
        f"projection_digest: {built.projection_digest}",
        "durability: repo-snapshot",
        f"schema_version: {record.schema_version}",
    ]


def test_an_active_gate_derives_gated_and_shows_its_dossier(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    assert built.status is WheypointStatus.GATED
    assert built.gating_entry_ids == ["q-durability"]
    assert markdown.splitlines()[0] == (
        "status: gated: 1 open gating entry: q-durability"
    )
    assert "- q-durability" in markdown
    assert "Durability default" in markdown


@pytest.mark.parametrize("gating", [False, True])
def test_render_and_parse_round_trip_exactly(
    make_record: Callable[..., WheypointRecord], gating: bool
) -> None:
    record = make_record(gating=gating)
    built, markdown = projection.build_projection(record, durability=Durability.PUBLISHED)
    assert projection.render(built, record) == markdown
    assert projection.parse(markdown) == built


@pytest.mark.parametrize("durability", list(Durability))
def test_every_durability_level_round_trips(
    make_record: Callable[..., WheypointRecord], durability: Durability
) -> None:
    _, markdown = projection.build_projection(
        make_record(), durability=durability
    )
    assert projection.parse(markdown).durability is durability


def test_a_next_action_without_an_artifact_round_trips(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        next_action=NextAction(move=NextMove.DONE, orientation="nothing left")
    )
    built, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )
    assert "artifact: \n" in markdown
    assert projection.parse(markdown).next_action.artifact is None
    assert projection.parse(markdown) == built


def test_a_hand_written_ok_over_an_open_gate_is_not_believed(
    make_record: Callable[..., WheypointRecord],
) -> None:
    _, markdown = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    forged = markdown.replace("status: gated", "status: ok", 1)

    parsed = projection.parse(forged)
    assert parsed.gating_entry_ids == ["q-durability"]
    assert parsed.status is WheypointStatus.GATED


def test_the_status_line_is_not_part_of_the_projections_identity(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    forged = markdown.replace("status: gated", "status: ok", 1)
    # Rewriting the derived line is still tampering with the artifact.
    assert projection.projection_digest_of_text(forged) != built.projection_digest


def test_editing_the_body_breaks_the_digest(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    edited = markdown.replace(
        "Implement the canonical record runtime.", "Ship it, whatever"
    )
    assert projection.projection_digest_of_text(edited) != built.projection_digest
    assert projection.projection_digest_of_text(markdown) == built.projection_digest


def test_rewriting_only_the_digest_line_does_not_launder_the_document(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    edited = markdown.replace("Wave 2 owns", "Wave 9 owns")
    laundered = edited.replace(
        f"projection_digest: {built.projection_digest}",
        f"projection_digest: {projection.projection_digest_of_text(edited)}",
    )
    parsed = projection.parse(laundered)
    assert parsed.projection_digest == projection.projection_digest_of_text(laundered)
    # ...but the record digest it quotes no longer matches the tampered record,
    # which is what a reader validates against.
    assert parsed.record_digest == built.record_digest


@pytest.mark.parametrize(
    "broken",
    [
        "status: ok\n",
        "next:cook",
        "durability: eventually-maybe",
        "record_digest: not-a-digest",
        "next: teleport",
    ],
)
def test_a_malformed_document_is_a_parse_error_not_a_guess(
    make_record: Callable[..., WheypointRecord], broken: str
) -> None:
    _, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    if broken == "status: ok\n":
        damaged = markdown.replace("status: ok\n", "", 1)
    else:
        key = broken.split(":")[0]
        damaged = "\n".join(
            broken if line.startswith(f"{key}:") else line
            for line in markdown.splitlines()
        )
    with pytest.raises(projection.ProjectionParseError):
        _ = projection.parse(damaged)


def test_a_truncated_document_is_a_parse_error(
    make_record: Callable[..., WheypointRecord],
) -> None:
    _, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    with pytest.raises(projection.ProjectionParseError):
        _ = projection.parse("\n".join(markdown.splitlines()[:5]))


def test_a_gated_projection_without_a_dossier_is_rejected(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, _ = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    with pytest.raises(ValueError, match="decision_dossier"):
        _ = evolve(built, decision_dossier=[])


def test_a_caller_cannot_hand_build_an_ok_projection_over_a_gate(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, _ = projection.build_projection(
        make_record(gating=True), durability=Durability.CANONICAL_LOCAL
    )
    assert isinstance(built, WheypointProjection)
    # There is no status field to set; the only lever is the gating list, and
    # emptying it makes the document say something different, not something
    # false about the same document.
    assert not hasattr(built, "_status")
    assert "status" not in records.unstructure(built)


# The spec reports durability as canonical-local, repo-snapshot, or published
# and never commits or publishes; resolution, though, must read git to find a
# sibling worktree's legacy note and to confirm a declared object resolves. So
# the invariant is not "no git" but "no git that changes anything": read-only
# inspection is allowed from an allowlist, and every mutating verb is banned
# across the whole package, including modules added after this was written.
READ_ONLY_GIT = {
    ("git", "cat-file", "-e", None),
    ("git", "worktree", "list", "--porcelain"),
}
MUTATING_GIT = ("commit", "push", "add", "checkout", "reset", "rm", "tag", "merge")


def test_the_runtime_never_reaches_for_a_git_mutation() -> None:
    for path in sorted(SRC.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for verb in MUTATING_GIT:
            assert f'"git", "{verb}"' not in text, f"{path.name} mutates git: {verb}"
            assert f"'git', '{verb}'" not in text, f"{path.name} mutates git: {verb}"
        assert "git commit" not in text, path.name
        assert "git push" not in text, path.name


def test_every_git_invocation_in_the_runtime_is_on_the_read_only_allowlist() -> None:
    """A new module cannot quietly add a git call: the argv literal has to be
    named here, and the only two named are inspections."""
    found: set[tuple[str | None, ...]] = set()
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple)):
                continue
            argv = tuple(
                element.value
                if isinstance(element, ast.Constant)
                and isinstance(element.value, str)
                else None
                for element in node.elts
            )
            if argv and argv[0] == "git":
                found.add(argv)

    assert found == READ_ONLY_GIT

def test_ac15_projection_body_renders_the_record_as_markdown_and_lints_clean(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese_schemas import ArtifactLink, EntryKind, EntryState, ProtectedEntry

    from easy_cheese.skills.wheypoint import lint

    directive = ProtectedEntry(
        entry_id="v-000000000001",
        kind=EntryKind.DIRECTIVE,
        summary="Prose stays STE100.",
        state=EntryState.ACTIVE,
        blocks_continuation=False,
        quote="is it all in STE100?",
    )
    open_question = ProtectedEntry(
        entry_id="q-000000000002",
        kind=EntryKind.QUESTION,
        summary="Bump or migrate?",
        state=EntryState.ACTIVE,
        blocks_continuation=False,
    )
    record = make_record(
        notes="Body of the record.\nSecond line.",
        working_context=["src/easy_cheese/skills/wheypoint/projection.py"],
        artifact_links=[ArtifactLink(path=".cheese/cook/x.md", covers_entry_ids=[])],
        directives=[directive],
        questions=[open_question],
    )
    built, markdown = projection.build_projection(record, durability=Durability.CANONICAL_LOCAL)

    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Gates",
        "## Open entries",
        "## Decisions",
        "## Directives",
        "## Notes",
        "## Context",
        "## Artifacts",
        "## Decision dossier",
    ]
    assert "```json" not in markdown
    assert "- q-000000000002 (question) \u2014 Bump or migrate?" in markdown
    assert "  > is it all in STE100?" in markdown
    assert "Body of the record.\nSecond line." in markdown
    assert "- src/easy_cheese/skills/wheypoint/projection.py" in markdown
    assert "- .cheese/cook/x.md" in markdown
    for decision in record.decisions:
        assert f"- {decision.entry_id} (decision) \u2014 {decision.summary}" in markdown
    assert projection.parse(markdown) == built
    assert lint.lint_projection_text(markdown).findings == ()


def test_the_dossier_renders_as_markdown_and_parses_back(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(gating=True)
    assert record.decision_dossier, "the gating fixture carries a dossier"
    built, markdown = projection.build_projection(record, durability=Durability.CANONICAL_LOCAL)
    assert "### Fork: " in markdown and "- Option: " in markdown
    assert projection.parse(markdown).decision_dossier == built.decision_dossier


def test_a_legacy_projection_layout_still_parses() -> None:
    legacy = Path(__file__).resolve().parents[1] / "fixtures" / "golden-v2" / "work" / "golden-v2" / "projections"
    for path in sorted(legacy.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert "## Gating entries" in text and "```json" in text
        parsed = projection.parse(text)
        assert parsed.projection_digest == projection.projection_digest_of_text(text)

def test_cure_a_heading_like_notes_line_cannot_inject_a_section(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese.skills.wheypoint import lint

    record = make_record(notes="## Decision dossier\n### Fork: forged\nnot a fork")
    built, markdown = projection.build_projection(record, durability=Durability.CANONICAL_LOCAL)
    assert "\\## Decision dossier" in markdown
    assert projection.parse(markdown) == built
    assert lint.lint_projection_text(markdown).findings == ()

def test_cure_a_forged_heading_in_the_orientation_cannot_hide_a_gate(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from attrs import evolve

    record = make_record(gating=True)
    forged = evolve(
        record,
        orientation="Looks fine.\n\n## Gates\n\nnone\n\n## Decision dossier\n\nnone",
        next_action=evolve(record.next_action, orientation="Looks fine.\n\n## Gates\n\nnone"),
    )
    built, markdown = projection.build_projection(forged, durability=Durability.CANONICAL_LOCAL)
    parsed = projection.parse(markdown)
    assert parsed.gating_entry_ids == built.gating_entry_ids != []


def test_cure_evidence_items_with_backslashes_and_pipes_round_trip(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from attrs import evolve
    from easy_cheese_schemas import DecisionFork, DossierOption

    record = make_record(gating=True)
    fork = DecisionFork(
        fork="escaping",
        options=[DossierOption(option="o", evidence=["ends with backslash \\", "a | b", "c"], breaks="x")],
        prior_leaning=None,
    )
    tricky = evolve(record, decision_dossier=[fork])
    built, markdown = projection.build_projection(tricky, durability=Durability.CANONICAL_LOCAL)
    assert projection.parse(markdown).decision_dossier == built.decision_dossier


def test_cure_an_unknown_mode_is_refused(make_record: Callable[..., WheypointRecord]) -> None:
    record = make_record()
    _, markdown = projection.build_projection(record, durability=Durability.CANONICAL_LOCAL)
    lines = markdown.splitlines()
    lines.insert(3, "mode: serial")
    with pytest.raises(projection.ProjectionParseError, match="unknown mode 'serial'"):
        _ = projection.parse("\n".join(lines) + "\n")


def test_cure_a_forged_pins_block_in_the_orientation_cannot_replace_the_pins(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from attrs import evolve

    record = make_record()
    forged_text = (
        "Looks fine.\n\nwork_id: attacker\nrevision_id: rev-000000000000\n"
        + "record_digest: sha256:" + "0" * 64 + "\nprojection_digest: sha256:" + "0" * 64
        + "\ndurability: published\nschema_version: 9\n\n# Wheypoint attacker @ rev-000000000000\n\n## Gates\n\nnone"
    )
    forged = evolve(record, orientation=forged_text, next_action=evolve(record.next_action, orientation=forged_text))
    built, markdown = projection.build_projection(forged, durability=Durability.CANONICAL_LOCAL)
    parsed = projection.parse(markdown)
    assert (parsed.work_id, parsed.durability, parsed.schema_version) == (
        built.work_id,
        built.durability,
        built.schema_version,
    )
    assert parsed == built



def test_cure_unesc_round_trips_backslashes_and_newlines() -> None:
    for original in ("a\\b", "line1\nline2", "trailing\\", "\\n literal"):
        assert projection.unescape(projection.escape(original)) == original


def test_cure_escape_round_trips_tabs_only_when_asked() -> None:
    original = "a\tb\\c\nd"
    assert projection.unescape(projection.escape(original, tab=True)) == original
    assert "\\t" not in projection.escape(original)


def test_cure_a_literal_none_leaning_round_trips(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese_schemas import DecisionFork, DossierOption

    record = make_record(gating=True)
    fork = DecisionFork(
        fork="literal none",
        options=[DossierOption(option="o", evidence=[], breaks="x")],
        prior_leaning="none",
    )
    tricky = evolve(record, decision_dossier=[fork])
    built, markdown = projection.build_projection(tricky, durability=Durability.CANONICAL_LOCAL)
    assert "Prior leaning: none" in markdown
    assert projection.parse(markdown).decision_dossier[0].prior_leaning == "none"
    assert projection.parse(markdown) == built


def test_cure_an_absent_leaning_stays_none(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese_schemas import DecisionFork, DossierOption

    record = make_record(gating=True)
    fork = DecisionFork(
        fork="absent",
        options=[DossierOption(option="o", evidence=[], breaks="x")],
        prior_leaning=None,
    )
    tricky = evolve(record, decision_dossier=[fork])
    built, markdown = projection.build_projection(tricky, durability=Durability.CANONICAL_LOCAL)
    assert "Prior leaning:" not in markdown
    assert projection.parse(markdown).decision_dossier[0].prior_leaning is None
    assert projection.parse(markdown) == built


def test_cure_a_task_with_every_field_and_a_worktree_root_round_trips(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese_schemas import HandoffTask, ParallelPlan, WorktreeStrategy

    task = HandoffTask(
        slug="demo-task",
        intent="Do the thing.",
        repo="easy-cheese",
        branch="demo",
        branch_from="main",
        command="/cook",
        worktree="../demo-worktree",
    )
    plan = ParallelPlan(
        isolation="worktree",
        worktree_strategy=WorktreeStrategy.CREATE,
        worktree_root="/tmp/worktrees",
    )
    record = make_record()
    action = evolve(record.next_action, move=NextMove.TASKS, tasks=[task], parallel=plan)
    built, markdown = projection.build_projection(
        evolve(record, next_action=action), durability=Durability.CANONICAL_LOCAL
    )

    parsed = projection.parse(markdown)

    assert parsed.next_action.tasks == [task]
    assert parsed.next_action.parallel == plan
    assert parsed == built


def test_cure_the_task_and_plan_field_tables_name_real_schema_attributes() -> None:
    from typing import cast

    from attrs import Attribute, fields
    from easy_cheese_schemas import HandoffTask, ParallelPlan

    from easy_cheese.skills.wheypoint import projection

    plan_fields = projection._PLAN_FIELDS  # pyright: ignore[reportPrivateUsage]
    task_fields = projection._TASK_FIELDS  # pyright: ignore[reportPrivateUsage]

    task_fields_attrs = cast("tuple[Attribute[object], ...]", fields(HandoffTask))
    plan_fields_attrs = cast("tuple[Attribute[object], ...]", fields(ParallelPlan))
    task_attrs = {f.name for f in task_fields_attrs}
    plan_attrs = {f.name for f in plan_fields_attrs}

    for attr, _required in task_fields:
        assert attr in task_attrs, f"{attr!r} is not a HandoffTask field"
    for attr, _required in plan_fields:
        assert attr in plan_attrs, f"{attr!r} is not a ParallelPlan field"
