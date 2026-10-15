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
from easy_cheese_schemas.contracts import DirectiveScope
from easy_cheese_schemas import (
    Durability,
    EntryKind,
    EntryState,
    NextAction,
    NextMove,
    WheypointProjection,
    WheypointRecord,
    ProtectedEntry,
    WheypointStatus,
)

from easy_cheese.shared.wheypoint import projection, records

from conftest import Promotion

SRC = Path(__file__).resolve().parents[3] / "src/easy_cheese/shared/wheypoint"


def test_a_built_projection_derives_everything_from_the_record(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    built, _ = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )

    assert built.work_id == record.work_id
    assert built.revision_id == record.revision_id
    assert built.schema_version == record.schema_version
    assert built.record_digest == records.record_digest(record)
    assert built.next_action == record.next_action
    assert built.gating_entry_ids == []
    assert built.status is WheypointStatus.OK


def test_the_rendered_preamble_carries_the_whole_contract(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    built, markdown = projection.build_projection(
        record, durability=Durability.REPO_SNAPSHOT
    )
    lines = markdown.splitlines()

    assert lines[:4] == [
        "status: ok",
        "next: cook",
        "artifact: .cheese/cook/wheypoint-record-store-projection.md",
        "Implement the canonical record runtime.",
    ]
    assert lines[-5:] == [
        "work_id: work-0001",
        "revision_id: rev-0001",
        f"record_digest: {built.record_digest}",
        "durability: repo-snapshot",
        f"schema_version: {record.schema_version}",
    ]


@pytest.mark.parametrize("gating", [False, True])
def test_render_and_parse_round_trip_exactly(
    make_record: Callable[..., WheypointRecord], gating: bool
) -> None:
    record = make_record(gating=gating)
    built, markdown = projection.build_projection(
        record, durability=Durability.PUBLISHED
    )
    assert projection.render(built, record) == markdown
    assert projection.parse(markdown) == built


@pytest.mark.parametrize("durability", list(Durability))
def test_every_durability_level_round_trips(
    make_record: Callable[..., WheypointRecord], durability: Durability
) -> None:
    _, markdown = projection.build_projection(make_record(), durability=durability)
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


def test_a_v5_projection_carries_no_digest_line_and_closes_with_identifiers(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    lines = markdown.splitlines()
    assert "projection_digest" not in markdown
    assert lines[:4] == [
        "status: ok",
        "next: cook",
        "artifact: .cheese/cook/wheypoint-record-store-projection.md",
        "Implement the canonical record runtime.",
    ]
    headings = [line for line in lines if line.startswith("## ")]
    assert headings[-1] == "## Identifiers"
    assert lines[lines.index("## Identifiers") + 1 :] == [
        "",
        "work_id: work-0001",
        "revision_id: rev-0001",
        f"record_digest: {built.record_digest}",
        "durability: canonical-local",
        f"schema_version: {built.schema_version}",
    ]


def test_a_projection_edited_by_hand_still_parses_and_quotes_its_record(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    edited = markdown.replace(
        "Implement the canonical record runtime.", "Ship it, whatever"
    )
    assert edited != markdown
    # No projection digest guards the body; the record digest is the identity.
    assert projection.parse(edited).record_digest == built.record_digest


def test_a_schema_4_layout_with_pins_above_the_title_still_parses(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    head, _, rest = markdown.partition("\n\n# Wheypoint handoff\n")
    body = rest[: rest.index("\n## Identifiers\n")]
    pins = "\n".join(
        [
            f"work_id: {built.work_id}",
            f"revision_id: {built.revision_id}",
            f"record_digest: {built.record_digest}",
            "projection_digest: sha256:" + "0" * 64,
            f"durability: {built.durability.value}",
            f"schema_version: {built.schema_version}",
        ]
    )
    legacy = f"{head}\n\n{pins}\n\n# Wheypoint handoff\n{body}\n"
    assert "## Identifiers" not in legacy
    assert projection.parse(legacy) == built


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
    ("git", "check-ignore", "--stdin", "-z"),
    ("git", "merge-base", "--is-ancestor", None, "HEAD"),
    ("git", "rev-list", "--count", None),
    ("git", "rev-parse", "--show-toplevel"),
    ("git", "worktree", "list", "--porcelain"),
}
MUTATING_GIT = ("commit", "push", "add", "checkout", "reset", "rm", "tag", "merge")


def _argv_tuple(node: ast.List | ast.Tuple) -> tuple[str | None, ...]:
    return tuple(
        element.value
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
        else None
        for element in node.elts
    )


def _run_git_argvs(tree: ast.AST) -> list[tuple[str | None, ...]]:
    """Every argv passed as the first positional argument to a `run_git` or
    `run_git_ok` call, prefixed with the `"git"` literal those wrappers
    supply themselves."""
    argvs: list[tuple[str | None, ...]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.id
            if isinstance(func, ast.Name)
            else (func.attr if isinstance(func, ast.Attribute) else None)
        )
        if name is None or name.lstrip("_") not in ("run_git", "run_git_ok"):
            continue
        if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple)):
            continue
        argvs.append(("git", *_argv_tuple(node.args[0])))
    return argvs


def test_the_runtime_never_reaches_for_a_git_mutation() -> None:
    for path in sorted(SRC.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for verb in MUTATING_GIT:
            assert f'"git", "{verb}"' not in text, f"{path.name} mutates git: {verb}"
            assert f"'git', '{verb}'" not in text, f"{path.name} mutates git: {verb}"
        assert "git commit" not in text, path.name
        assert "git push" not in text, path.name
        tree = ast.parse(text)
        for argv in _run_git_argvs(tree):
            assert argv[1] not in MUTATING_GIT, f"{path.name} mutates git: {argv[1]}"


def test_every_git_invocation_in_the_runtime_is_on_the_read_only_allowlist() -> None:
    """A new module cannot quietly add a git call: the argv has to be named
    here, whether it is a literal list/tuple or the first argument to
    `run_git`/`run_git_ok`, and the only ones named are inspections."""
    found: set[tuple[str | None, ...]] = set()
    for path in sorted(SRC.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple)):
                continue
            argv = _argv_tuple(node)
            if argv and argv[0] == "git":
                found.add(argv)
        found.update(_run_git_argvs(tree))

    assert found == READ_ONLY_GIT


def test_ac15_projection_body_renders_the_record_as_markdown_and_lints_clean(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese_schemas import ArtifactLink, EntryKind, EntryState, ProtectedEntry

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
        working_context=["src/easy_cheese/shared/wheypoint/projection.py"],
        artifact_links=[ArtifactLink(path=".cheese/cook/x.md", covers_entry_ids=[])],
        directives=[directive],
        questions=[open_question],
    )
    built, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )

    headings = [line for line in markdown.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Gates",
        "## Open entries",
        "## Decisions",
        "## Directives",
        "## Notes",
        "## Context",
        "## Artifacts",
        "## Links",
        "## Identifiers",
    ]
    assert "```json" not in markdown
    assert "- q-000000000002 (question) \u2014 Bump or migrate?" in markdown
    assert "  > is it all in STE100?" in markdown
    assert "Body of the record.\nSecond line." in markdown
    assert "- src/easy_cheese/shared/wheypoint/projection.py" in markdown
    assert "- .cheese/cook/x.md" in markdown
    for decision in record.decisions:
        assert f"- {decision.entry_id} (decision) \u2014 {decision.summary}" in markdown
    assert projection.parse(markdown) == built


def _ref(work_id: str, suffix: str = "") -> str:
    return f"wheypoint:paulnsorensen-easy-cheese/{work_id}{suffix}"


def _edged_record(make_record: Callable[..., WheypointRecord]) -> WheypointRecord:
    from easy_cheese_schemas.contracts import EdgeKind, WorkEdge

    return make_record(
        edges=(
            WorkEdge(
                to=_ref("parent", "@rev-0009"),
                kind=EdgeKind.FORKED_FROM,
                revision_id="rev-0001",
            ),
            WorkEdge(
                to=_ref("sibling"),
                kind=EdgeKind.SUPERSEDES,
                revision_id="rev-0001",
                rationale="replaces the sibling plan",
            ),
            WorkEdge(
                to=_ref("child"),
                kind=EdgeKind.CHECKPOINTS,
                revision_id="rev-0001",
            ),
        ),
    )


def test_ac11_links_render_and_the_document_still_parses(
    make_record: Callable[..., WheypointRecord],
) -> None:
    built, markdown = projection.build_projection(
        _edged_record(make_record), durability=Durability.CANONICAL_LOCAL
    )
    lines = markdown.splitlines()

    links = lines.index("## Links")
    identifiers = lines.index("## Identifiers")
    assert lines.index("## Artifacts") < links < identifiers
    assert lines[links + 2 : identifiers - 1] == [
        f"- forked_from {_ref('parent', '@rev-0009')} @rev-0001",
        f"- supersedes {_ref('sibling')} @rev-0001",
        "  rationale: replaces the sibling plan",
        f"- checkpoints {_ref('child')} @rev-0001",
    ]
    assert "## Lineage" not in markdown
    assert projection.parse(markdown) == built


def test_ac11_resolve_rederives_the_digest_of_a_projection_with_edges(
    corpus_root: Path,
    make_record: Callable[..., WheypointRecord],
    make_promotion: Callable[..., Promotion],
) -> None:
    from easy_cheese.shared.wheypoint import storage
    from work_check import check_work

    record = _edged_record(make_record)
    promotion = make_promotion(record=record)
    store = storage.WorkStore.open(record.work_id, corpus_root=corpus_root)
    store.promote(promotion.record, promotion.revision, promotion.markdown)

    report = check_work(store, project_key=record.project_key)

    assert "## Links" in promotion.markdown
    assert report.codes == ()


def test_an_edgeless_record_renders_none_under_links(
    make_record: Callable[..., WheypointRecord],
) -> None:
    _, markdown = projection.build_projection(
        make_record(), durability=Durability.CANONICAL_LOCAL
    )
    assert "## Links\n\nnone\n" in markdown
    assert "## Lineage" not in markdown


def test_a_legacy_projection_layout_still_parses() -> None:
    legacy = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "golden-v2"
        / "work"
        / "golden-v2"
        / "projections"
    )
    for path in sorted(legacy.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert "## Gating entries" in text and "```json" in text
        parsed = projection.parse(text)
        assert parsed.record_digest.startswith("sha256:")
        assert "projection_digest:" in text


def test_cure_a_heading_like_notes_line_cannot_inject_a_section(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(notes="## Decision dossier\n### Fork: forged\nnot a fork")
    built, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )
    assert "\\## Decision dossier" in markdown
    assert projection.parse(markdown) == built


def test_cure_a_forged_heading_in_the_orientation_cannot_hide_a_gate(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from attrs import evolve

    record = make_record(gating=True)
    forged = evolve(
        record,
        orientation="Looks fine.\n\n## Gates\n\nnone\n\n## Decision dossier\n\nnone",
        next_action=evolve(
            record.next_action, orientation="Looks fine.\n\n## Gates\n\nnone"
        ),
    )
    built, markdown = projection.build_projection(
        forged, durability=Durability.CANONICAL_LOCAL
    )
    parsed = projection.parse(markdown)
    assert parsed.gating_entry_ids == built.gating_entry_ids != []


def test_cure_an_unknown_mode_is_refused(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record()
    _, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )
    lines = markdown.splitlines()
    lines.insert(2, "mode: serial")
    with pytest.raises(projection.ProjectionParseError, match="unknown mode 'serial'"):
        _ = projection.parse("\n".join(lines) + "\n")


def test_cure_a_forged_pins_block_in_the_orientation_cannot_replace_the_pins(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from attrs import evolve

    record = make_record()
    forged_text = (
        "Looks fine.\n\nwork_id: attacker\nrevision_id: rev-000000000000\n"
        + "record_digest: sha256:"
        + "0" * 64
        + "\ndurability: published\nschema_version: 9\n\n# Wheypoint attacker @ rev-000000000000\n\n## Gates\n\nnone"
    )
    forged = evolve(
        record,
        orientation=forged_text,
        next_action=evolve(record.next_action, orientation=forged_text),
    )
    built, markdown = projection.build_projection(
        forged, durability=Durability.CANONICAL_LOCAL
    )
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
    action = evolve(
        record.next_action, move=NextMove.TASKS, tasks=[task], parallel=plan
    )
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

    from easy_cheese.shared.wheypoint import projection

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


def test_artifacts_render_the_ref_of_a_non_repo_link_and_the_path_of_a_repo_link(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese_schemas import ArtifactLink

    record = evolve(
        make_record(),
        artifact_links=[
            ArtifactLink(
                path="paulnsorensen-easy-cheese/doc.md",
                ref="xdg:paulnsorensen-easy-cheese/doc.md",
            ),
            ArtifactLink(path="docs/a.md", ref="repo:docs/a.md"),
            ArtifactLink(path="docs/b.md"),
        ],
    )

    _, markdown = projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL
    )

    lines = markdown.splitlines()
    start = lines.index("## Artifacts") + 2
    assert lines[start : start + 3] == [
        "- xdg:paulnsorensen-easy-cheese/doc.md",
        "- docs/a.md",
        "- docs/b.md",
    ]


def _notes_section(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    start = lines.index("## Notes") + 1
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("## "))
    return [line for line in lines[start:end] if line]


def _render(record: WheypointRecord, *, checkout: Path | None = None) -> str:
    return projection.build_projection(
        record, durability=Durability.CANONICAL_LOCAL, checkout=checkout
    )[1]


def test_drift_marker_names_both_revisions_when_decisions_are_newer(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        notes="Body.", notes_revision_number=3, decisions_revision_number=5
    )

    section = _notes_section(_render(record))

    assert len(section) == 2
    assert section[0] == (
        "> notes may be stale: decisions changed at revision 5, "
        "notes written at revision 3"
    )
    assert section[1] == "Body."


def test_drift_marker_shows_when_decisions_are_stamped_and_notes_are_not(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(notes="Body.", decisions_revision_number=2)

    section = _notes_section(_render(record))

    assert section[0].startswith(
        "> notes may be stale: decisions changed at revision 2"
    )
    assert "unstamped" in section[0]


@pytest.mark.parametrize(
    ("notes_at", "decisions_at"), [(4, 4), (5, 3), (2, None), (None, None)]
)
def test_drift_marker_is_absent_unless_decisions_are_newer(
    make_record: Callable[..., WheypointRecord],
    notes_at: int | None,
    decisions_at: int | None,
) -> None:
    record = make_record(
        notes="Body.",
        notes_revision_number=notes_at,
        decisions_revision_number=decisions_at,
    )

    assert _notes_section(_render(record)) == ["Body."]


def test_unstamped_record_keeps_the_canonical_bytes_it_had(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(notes="Body.")

    unstructured = records.unstructure(record)

    assert "notes_revision_number" not in unstructured
    assert "decisions_revision_number" not in unstructured
    assert "stale" not in _render(record)
    stamped = make_record(notes="Body.", notes_revision_number=1)
    assert records.record_digest(stamped) != records.record_digest(record)


def _decision(entry_id: str, **fields: object) -> ProtectedEntry:
    base: dict[str, object] = {
        "entry_id": entry_id,
        "kind": EntryKind.DECISION,
        "summary": f"Decision {entry_id}",
        "state": EntryState.ACTIVE,
        "blocks_continuation": False,
    }
    return ProtectedEntry(**{**base, **fields})  # pyright: ignore[reportArgumentType]


def test_superseded_section_lists_the_pair_and_hides_the_entry_from_its_kind(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        decisions=[
            _decision(
                "d-old",
                state=EntryState.SUPERSEDED,
                rationale="Replaced.",
                superseded_by="d-new",
            ),
            _decision("d-new"),
        ]
    )

    markdown = _render(record)
    lines = markdown.splitlines()

    assert "- d-old -> d-new" in lines
    assert lines.index("## Superseded") < lines.index("## Identifiers")
    decisions = lines[lines.index("## Decisions") : lines.index("## Directives")]
    assert any("d-new" in line for line in decisions)
    assert not any("d-old" in line for line in decisions)
    assert projection.parse(markdown).work_id == record.work_id


def test_superseded_section_is_absent_without_superseded_entries(
    make_record: Callable[..., WheypointRecord],
) -> None:
    assert "## Superseded" not in _render(make_record(decisions=[_decision("d-one")]))


def _question(entry_id: str, **fields: object) -> ProtectedEntry:
    base: dict[str, object] = {
        "entry_id": entry_id,
        "kind": EntryKind.QUESTION,
        "summary": f"Question {entry_id}?",
        "state": EntryState.ACTIVE,
        "blocks_continuation": False,
    }
    return ProtectedEntry(**{**base, **fields})  # pyright: ignore[reportArgumentType]


def _open_section(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    start = lines.index("## Open entries") + 1
    end = next(i for i in range(start, len(lines)) if lines[i].startswith("## "))
    return [line for line in lines[start:end] if line]


def test_owner_group_puts_each_owner_under_a_subheading_and_unowned_under_unassigned(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        questions=[
            _question("q-loose"),
            _question("q-bo", owner="Bo", when="before launch"),
            _question("q-ana", owner="Ana"),
            _question("q-bo2", owner="bo"),
        ]
    )

    markdown = _render(record)
    section = _open_section(markdown)

    assert section == [
        "### Ana",
        "- q-ana (question) — Question q-ana?",
        "### Bo",
        "- q-bo (question) — Question q-bo? (when: before launch)",
        "- q-bo2 (question) — Question q-bo2?",
        "### unassigned",
        "- q-loose (question) — Question q-loose?",
    ]
    assert projection.parse(markdown).work_id == record.work_id


def test_owner_group_keeps_the_flat_list_when_no_question_has_an_owner(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        questions=[_question("q-one"), _question("q-two", when="soon")]
    )

    assert _open_section(_render(record)) == [
        "- q-one (question) — Question q-one?",
        "- q-two (question) — Question q-two? (when: soon)",
    ]


def _directive(entry_id: str, **fields: object) -> ProtectedEntry:
    base: dict[str, object] = {
        "entry_id": entry_id,
        "kind": EntryKind.DIRECTIVE,
        "summary": f"Directive {entry_id}",
        "state": EntryState.ACTIVE,
        "blocks_continuation": False,
        "quote": f"words of {entry_id}",
    }
    return ProtectedEntry(**{**base, **fields})  # pyright: ignore[reportArgumentType]


def test_operator_preferences_render_apart_from_work_directives(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        directives=[
            _directive("p-work"),
            _directive("p-style", scope=DirectiveScope.OPERATOR),
        ]
    )

    markdown = _render(record)
    lines = markdown.splitlines()
    directives = lines[
        lines.index("## Directives") : lines.index("## Operator preferences")
    ]
    operator = lines[lines.index("## Operator preferences") : lines.index("## Notes")]

    assert any("p-work" in line for line in directives)
    assert not any("p-style" in line for line in directives)
    assert any("p-style" in line for line in operator)
    assert "  > words of p-style" in operator
    assert operator == [
        "## Operator preferences",
        "",
        "- p-style (directive) — Directive p-style",
        "  > words of p-style",
        "",
    ]
    assert directives[-1] == ""
    assert projection.parse(markdown).work_id == record.work_id


def test_operator_preferences_section_is_absent_without_operator_directives(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(directives=[_directive("p-work")])

    assert "## Operator preferences" not in _render(record)
    assert "scope" not in records.unstructure(record)["directives"][0]  # pyright: ignore[reportIndexIssue]


def _git(root: Path, *args: str) -> None:
    import subprocess

    _ = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def test_local_reference_section_lists_xdg_absolute_and_ignored_paths(
    make_record: Callable[..., WheypointRecord],
    tmp_path: Path,
) -> None:
    from easy_cheese_schemas import ArtifactLink

    repo = tmp_path / "repo"
    (repo / ".cheese").mkdir(parents=True)
    _ = (repo / ".cheese" / "plan.md").write_text("plan\n", encoding="utf-8")
    _ = (repo / ".gitignore").write_text(".cheese/\n", encoding="utf-8")
    _ = (repo / "tracked.py").write_text("x\n", encoding="utf-8")
    _git(repo, "init", "-q")
    elsewhere = tmp_path / "other-worktree" / "notes.md"
    record = make_record(
        working_context=["see .cheese/plan.md:4 and tracked.py:2"],
        artifact_links=[
            ArtifactLink(path="xdg-doc", ref="xdg:proj/doc.md"),
            ArtifactLink(path=str(elsewhere)),
            ArtifactLink(path="tracked.py"),
            ArtifactLink(path=".cheese/cook/x.md"),
        ],
    )

    lines = _render(record, checkout=repo).splitlines()
    section = lines[lines.index("## Local references") + 2 :]
    listed = section[: section.index("")] if "" in section else section

    assert listed == [
        "- xdg:proj/doc.md",
        f"- {elsewhere}",
        "- .cheese/cook/x.md",
        "- .cheese/plan.md:4",
    ]


def test_a_relative_reference_that_leaves_the_checkout_is_local_and_keeps_ignored_refs(
    make_record: Callable[..., WheypointRecord],
    tmp_path: Path,
) -> None:
    from easy_cheese_schemas import ArtifactLink

    repo = tmp_path / "repo"
    (repo / ".cheese").mkdir(parents=True)
    _ = (repo / ".gitignore").write_text(".cheese/\n", encoding="utf-8")
    _ = (repo / "tracked.py").write_text("x\n", encoding="utf-8")
    (repo / "link").symlink_to(tmp_path)
    _git(repo, "init", "-q")
    record = make_record(
        artifact_links=[
            ArtifactLink(path="../out.md"),
            ArtifactLink(path="link/out.md"),
            ArtifactLink(path="tracked.py"),
            ArtifactLink(path=".cheese/cook/x.md"),
        ],
    )

    lines = _render(record, checkout=repo).splitlines()
    section = lines[lines.index("## Local references") + 2 :]
    listed = section[: section.index("")] if "" in section else section

    assert listed == ["- ../out.md", "- link/out.md", "- .cheese/cook/x.md"]


def test_a_failed_check_ignore_fails_closed_and_is_visible(
    make_record: Callable[..., WheypointRecord],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    from easy_cheese_schemas import ArtifactLink

    repo = tmp_path / "repo"
    repo.mkdir()
    _ = (repo / "tracked.py").write_text("x\n", encoding="utf-8")
    _git(repo, "init", "-q")

    def broken(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess([], 128, "", "fatal: boom")

    monkeypatch.setattr(projection.subprocess, "run", broken)
    record = make_record(artifact_links=[ArtifactLink(path="tracked.py")])

    with pytest.raises(projection.CheckIgnoreError, match="exited 128"):
        _ = projection._ignored(["tracked.py"], repo)  # pyright: ignore[reportPrivateUsage]
    assert "- tracked.py" in _render(record, checkout=repo)

    def timed_out(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("git", 5)

    monkeypatch.setattr(projection.subprocess, "run", timed_out)
    with pytest.raises(projection.CheckIgnoreError):
        _ = projection._ignored(["tracked.py"], repo)  # pyright: ignore[reportPrivateUsage]


def test_local_reference_outside_a_checkout_keeps_xdg_and_absolute_only(
    make_record: Callable[..., WheypointRecord],
) -> None:
    from easy_cheese_schemas import ArtifactLink

    record = make_record(
        artifact_links=[
            ArtifactLink(path="xdg-doc", ref="xdg:proj/doc.md"),
            ArtifactLink(path="/tmp/elsewhere/notes.md"),
            ArtifactLink(path=".cheese/cook/x.md"),
        ],
    )

    markdown = _render(record)

    assert "- xdg:proj/doc.md\n- /tmp/elsewhere/notes.md\n" in markdown
    assert markdown.count("- .cheese/cook/x.md") == 1


def test_local_reference_section_is_absent_without_local_refs(
    make_record: Callable[..., WheypointRecord],
) -> None:
    assert "## Local references" not in _render(make_record())


def test_a_free_text_slash_command_is_not_a_local_reference(
    make_record: Callable[..., WheypointRecord],
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    record = make_record(
        working_context=["run /cook then call /api/v1/users or see /etc/hosts"]
    )

    markdown = _render(record, checkout=repo)

    assert "- /cook" not in markdown
    assert "- /api/v1/users" not in markdown
    assert "- /etc/hosts" in markdown


def test_local_references_do_not_depend_on_the_working_directory(
    make_record: Callable[..., WheypointRecord],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    (repo / ".cheese").mkdir(parents=True)
    _ = (repo / ".cheese" / "plan.md").write_text("plan\n", encoding="utf-8")
    _ = (repo / ".gitignore").write_text(".cheese/\n", encoding="utf-8")
    _git(repo, "init", "-q")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    record = make_record(working_context=["see .cheese/plan.md:4"])

    assert "- .cheese/plan.md:4" in _render(record, checkout=repo)
    assert "## Local references" not in _render(record)


def test_a_gated_question_keeps_its_owner_and_when_and_parses_back_to_its_id(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        questions=[
            _question(
                "q-gate",
                blocks_continuation=True,
                owner="Ana",
                when="before launch",
            ),
            _question("q-plain-gate", blocks_continuation=True),
        ]
    )

    markdown = _render(record)
    lines = markdown.splitlines()
    gates = lines[lines.index("## Gates") + 2 : lines.index("## Open entries") - 1]

    assert gates == [
        "- q-gate — Question q-gate? (owner: Ana) (when: before launch)",
        "- q-plain-gate — Question q-plain-gate?",
    ]
    assert projection.parse(markdown).gating_entry_ids == ["q-gate", "q-plain-gate"]


def test_an_owner_literally_named_unassigned_stays_apart_from_unowned_questions(
    make_record: Callable[..., WheypointRecord],
) -> None:
    record = make_record(
        questions=[_question("q-loose"), _question("q-named", owner="Unassigned")]
    )

    assert _open_section(_render(record)) == [
        "### Unassigned",
        "- q-named (question) — Question q-named?",
        "### unassigned",
        "- q-loose (question) — Question q-loose?",
    ]
