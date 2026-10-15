"""Export and import: one canonical bundle, verified, written as a fork child."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    Durability,
    EntryKind,
    HandoffTask,
    NextAction,
    NextMove,
    ParallelPlan,
    ProposedEntry,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import DirectiveScope, EdgeKind, WorkEdge, WorktreeStrategy

from conftest import payload_at, run_cli
from easy_cheese.shared.wheypoint import canonical, commit, projection, records, storage
from easy_cheese.shared.wheypoint import resolve as resolve_mod
from easy_cheese.shared.wheypoint import transfer

CAPTURED = SessionProvenance(captured_at="2026-09-01T00:00:00Z")
PUBLIC = "https://example.com/spec"


def _local(corpus_root: Path) -> str:
    """An `xdg:` reference: it needs this machine's corpus home."""
    path = corpus_root.parent / "alice-notes" / "private.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text("private\n")
    return "xdg:alice-notes/private.md"


def _author(corpus_root: Path, work_id: str = "alpha") -> WheypointRecord:
    local = _local(corpus_root)
    store = storage.WorkStore.open(work_id, corpus_root=corpus_root)
    result = commit.commit(
        WheypointDelta(
            work_id=work_id,
            expected_revision_id=commit.GENESIS_PARENT,
            orientation="Alpha work.\nShip the bundle.",
            working_context=["src/easy_cheese/shared/wheypoint/transfer.py"],
            notes="Remember the digest rule.",
            next_action=NextAction(move=NextMove.COOK, orientation="Build it."),
            session_provenance=CAPTURED,
            add_decisions=[
                ProposedEntry(kind=EntryKind.DECISION, summary="Use JSON.", rationale="digests")
            ],
            add_questions=[ProposedEntry(kind=EntryKind.QUESTION, summary="Who reviews?")],
            add_directives=[
                ProposedEntry(kind=EntryKind.DIRECTIVE, summary="Ship small.", quote="ship small"),
                ProposedEntry(
                    kind=EntryKind.DIRECTIVE,
                    summary="Be terse.",
                    quote="be terse",
                    scope=DirectiveScope.OPERATOR,
                ),
            ],
            add_artifact_links=[
                ArtifactLink(path="public-spec", ref=PUBLIC),
                ArtifactLink(path="private-doc", ref=local),
            ],
        ),
        store=store,
    )
    return result.record


def _export(tmp_path: Path, *flags: str, ref: str = "alpha") -> tuple[Path, dict[str, object]]:
    out = tmp_path / "bundle.json"
    status, payload = run_cli(["export", ref, "--out", str(out), *flags])
    assert status == 0
    return out, payload


def _bundle(path: Path) -> dict[str, object]:
    return cast("dict[str, object]", json.loads(path.read_bytes()))


def _import(bundle: Path, *flags: str) -> tuple[int, dict[str, object]]:
    return run_cli(["import", str(bundle), "--no-note", *flags])


def _section(markdown: str, heading: str) -> list[str]:
    lines = markdown.splitlines()
    start = lines.index(heading) + 1
    end = start
    while end < len(lines) and not lines[end].startswith("## "):
        end += 1
    return [line for line in lines[start:end] if line.strip()]


def _other_machine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "other-cheese"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    monkeypatch.setenv("EASY_CHEESE_PROJECT", "bob-project")
    return home / "bob-project"


def test_export_writes_one_canonical_bundle_with_digests(
    corpus_root: Path, tmp_path: Path
) -> None:
    record = _author(corpus_root)
    out, payload = _export(tmp_path)
    raw = out.read_bytes()
    bundle = _bundle(out)
    body = {k: v for k, v in bundle.items() if k != "bundle_digest"}
    assert raw == canonical.canonical_bytes(bundle) + b"\n"
    assert bundle["bundle_digest"] == canonical.digest_value(body)
    assert bundle["projection_digest"] == canonical.digest_text(cast(str, bundle["projection"]))
    assert payload["bundle_digest"] == bundle["bundle_digest"]
    assert cast(dict[str, object], bundle["origin"])["revision_id"] == record.revision_id


def test_export_omits_operator_directives_and_local_references_by_default(
    corpus_root: Path, tmp_path: Path
) -> None:
    record = _author(corpus_root)
    bundle = _bundle(_export(tmp_path)[0])
    exported = records.structure(bundle["record"], WheypointRecord)
    assert [d.summary for d in exported.directives] == ["Ship small."]
    assert [link.ref for link in exported.artifact_links] == [PUBLIC]
    assert "Be terse." not in cast(str, bundle["projection"])
    assert _local(corpus_root) not in cast(str, bundle["projection"])
    # The filtered record has its own digest; the origin keeps the source one.
    assert bundle["record_digest"] == records.record_digest(exported)
    assert cast(dict[str, object], bundle["origin"])["record_digest"] == records.record_digest(record)
    assert bundle["record_digest"] != records.record_digest(record)


def test_export_include_flags_keep_operator_and_local(
    corpus_root: Path, tmp_path: Path
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path, "--include-operator", "--include-local")[0])
    exported = records.structure(bundle["record"], WheypointRecord)
    assert {d.summary for d in exported.directives} == {"Ship small.", "Be terse."}
    assert {link.ref for link in exported.artifact_links} == {PUBLIC, _local(corpus_root)}
    assert bundle["included"] == {"operator": True, "local": True}


@pytest.mark.usefixtures("corpus_root")
def test_export_command_refuses_an_unknown_ref(tmp_path: Path) -> None:
    status, payload = run_cli(["export", "missing", "--out", str(tmp_path / "b.json")])
    assert status == 1
    assert payload_at(payload, "error", "code") == "export-unresolved"
    assert not (tmp_path / "b.json").exists()


def test_export_command_prints_the_bundle_without_out(corpus_root: Path) -> None:
    _ = _author(corpus_root)
    status, payload = run_cli(["export", "alpha"])
    assert status == 0
    assert payload_at(payload, "bundle", "bundle_digest") == payload["bundle_digest"]


def test_import_genesis_carries_the_record_and_one_forked_from_edge(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _author(corpus_root)
    out, _ = _export(tmp_path)
    other = _other_machine(tmp_path, monkeypatch)
    status, payload = _import(out, "--as", "beta")
    assert status == 0
    imported = storage.WorkStore.open("beta", corpus_root=other).read_record()
    assert imported is not None
    assert payload["revision_number"] == 1
    assert imported.orientation == source.orientation
    assert imported.notes == source.notes
    assert imported.next_action == source.next_action
    assert imported.working_context == source.working_context
    assert [link.ref for link in imported.artifact_links] == [PUBLIC]
    assert [(e.kind, e.summary) for e in records.entries(imported)] == [
        (EntryKind.DECISION, "Use JSON."),
        (EntryKind.QUESTION, "Who reviews?"),
        (EntryKind.DIRECTIVE, "Ship small."),
    ]
    assert [(e.kind.value, e.to) for e in imported.edges] == [
        ("forked_from", f"wheypoint:{source.project_key}/alpha@{source.revision_id}")
    ]


def test_import_skips_an_included_local_link_and_reports_it(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    out, _ = _export(tmp_path, "--include-local")
    other = _other_machine(tmp_path, monkeypatch)
    status, payload = _import(out, "--as", "beta")
    assert status == 0
    imported = storage.WorkStore.open("beta", corpus_root=other).read_record()
    assert imported is not None
    assert [link.ref for link in imported.artifact_links] == [PUBLIC]
    warnings = cast("list[str]", payload_at(payload, "warnings"))
    assert any(w.startswith("skipped-local-link:") for w in warnings)


def test_import_digest_mismatch_refuses_and_writes_nothing(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    out, _ = _export(tmp_path)
    bundle = _bundle(out)
    tampered = {**bundle, "projection": cast(str, bundle["projection"]).replace("Build it.", "Skip it.")}
    bad_bundle = tmp_path / "bad.json"
    _ = bad_bundle.write_bytes(canonical.canonical_bytes(tampered))
    other = _other_machine(tmp_path, monkeypatch)
    status, payload = _import(bad_bundle, "--as", "beta")
    assert status == 1
    assert payload_at(payload, "error", "code") == "bundle-digest-mismatch"
    assert not (other / "work").exists()


@pytest.mark.parametrize("field", ["record_digest", "projection_digest"])
def test_import_each_inner_digest_is_checked_even_when_the_bundle_digest_is_redone(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path)[0])
    forged = {k: v for k, v in bundle.items() if k != "bundle_digest"}
    forged[field] = "sha256:" + "0" * 64
    forged["bundle_digest"] = canonical.digest_value(forged)
    path = tmp_path / "forged.json"
    _ = path.write_bytes(canonical.canonical_bytes(forged))
    other = _other_machine(tmp_path, monkeypatch)
    status, payload = _import(path)
    assert status == 1
    assert payload_at(payload, "error", "code") == "bundle-digest-mismatch"
    assert not (other / "work").exists()


def test_import_refuses_oversized_malformed_and_unsafe_slug_input(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    out, _ = _export(tmp_path)
    _ = _other_machine(tmp_path, monkeypatch)
    huge = tmp_path / "huge.json"
    _ = huge.write_bytes(b" " * (transfer.MAX_BUNDLE_BYTES + 1))
    junk = tmp_path / "junk.json"
    _ = junk.write_text("[1, 2]")
    for path in (huge, junk):
        status, payload = _import(path)
        assert status == 1
        assert payload_at(payload, "error", "code") == "bundle-invalid"
    status, payload = _import(out, "--as", "../escape")
    assert status == 1
    assert payload_at(payload, "error", "code") == "invalid-slug"


def test_import_refuses_to_overwrite_an_existing_record(
    corpus_root: Path, tmp_path: Path
) -> None:
    _ = _author(corpus_root)
    out, _ = _export(tmp_path)
    status, payload = _import(out)
    assert status == 1
    assert payload_at(payload, "error", "code") == "import-exists"


def test_import_and_resolve_an_imported_record_is_authoritative_with_the_same_projection(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    out, _ = _export(tmp_path)
    bundle_projection = cast(str, _bundle(out)["projection"])
    other = _other_machine(tmp_path, monkeypatch)
    status, _payload = _import(out, "--as", "beta")
    assert status == 0
    # The origin project is absent from this machine: external lineage, no gate.
    assert not (other.parent / "paulnsorensen-easy-cheese").exists()
    resolution = resolve_mod.resolve("beta", corpus_root=other, project_key="bob-project")
    assert resolution.outcome is resolve_mod.ResolutionOutcome.AUTHORITATIVE
    assert resolution.record is not None
    _, markdown = projection.build_projection(
        resolution.record, durability=Durability.CANONICAL_LOCAL
    )
    assert resolution.projection is not None
    assert resolution.projection.next_action.orientation == "Build it."
    # Entry ids are derived per record, so they are masked; summaries must match.
    def masked(markdown: str, heading: str) -> list[str]:
        return [re.sub(r"\b[a-z]-[0-9a-f]{12}\b", "<id>", row) for row in _section(markdown, heading)]

    for heading in ("## Open entries", "## Decisions", "## Directives", "## Notes"):
        assert masked(markdown, heading) == masked(bundle_projection, heading)
    assert "Who reviews?" in "\n".join(masked(markdown, "## Open entries"))


def _repo(tmp_path: Path) -> Path:
    """A real Git checkout that ignores `*.log`, apart from the working directory."""
    root = tmp_path / "author-repo"
    (root / "src").mkdir(parents=True)
    _ = (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    _ = (root / "scratch.log").write_text("noise\n", encoding="utf-8")
    _ = (root / ".gitignore").write_text("*.log\n", encoding="utf-8")
    for args in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "x"],
    ):
        _ = subprocess.run(["git", "-C", str(root), *args], check=True)
    return root


def _author_in(
    corpus_root: Path, repo: Path, *, notes: str, links: list[ArtifactLink], context: list[str]
) -> WheypointRecord:
    return commit.commit(
        WheypointDelta(
            work_id="alpha",
            expected_revision_id=commit.GENESIS_PARENT,
            orientation="Alpha work.",
            working_context=context,
            notes=notes,
            next_action=NextAction(move=NextMove.COOK, orientation="Build it."),
            session_provenance=CAPTURED,
            add_decisions=[
                ProposedEntry(kind=EntryKind.DECISION, summary="Use JSON.", rationale="digests")
            ],
            add_artifact_links=links,
            add_edges=[WorkEdge(to="repo:scratch.log", kind=EdgeKind.CHECKPOINTS)],
        ),
        store=storage.WorkStore.open("alpha", corpus_root=corpus_root),
        artifact_root=repo,
    ).record


def test_export_filters_by_the_given_checkout_not_the_working_directory(
    corpus_root: Path, tmp_path: Path
) -> None:
    repo = _repo(tmp_path)
    outside = tmp_path / "elsewhere.txt"
    _ = outside.write_text("x\n", encoding="utf-8")
    _ = _author_in(
        corpus_root,
        repo,
        notes=f"Read scratch.log and {outside} and src/app.py.",
        links=[
            ArtifactLink(path="src/app.py"),
            ArtifactLink(path="scratch.log"),
        ],
        context=["src/app.py", "scratch.log", "src/myscratch.log.py"],
    )
    out, _payload = _export(tmp_path, "--workspace-root", str(repo))
    bundle = _bundle(out)
    exported = records.structure(bundle["record"], WheypointRecord)
    text = json.dumps(bundle)
    assert [link.path for link in exported.artifact_links] == ["src/app.py"]
    assert not [e for e in exported.edges if e.kind.value != "forked_from"]
    # A token is compared whole: a longer word that merely contains a local one stays.
    assert exported.working_context == ["src/app.py", "src/myscratch.log.py"]
    assert exported.notes == (
        f"Read {transfer.LOCAL_MARKER} and {transfer.LOCAL_MARKER} and src/app.py."
    )
    assert str(outside) not in text
    assert "scratch.log" not in cast(str, bundle["projection"]).replace("myscratch.log", "")


def test_export_include_local_keeps_free_text_references(
    corpus_root: Path, tmp_path: Path
) -> None:
    repo = _repo(tmp_path)
    _ = _author_in(
        corpus_root, repo, notes="Read scratch.log now.", links=[], context=["src/app.py"]
    )
    bundle = _bundle(_export(tmp_path, "--workspace-root", str(repo), "--include-local")[0])
    assert cast(dict[str, object], bundle["record"])["notes"] == "Read scratch.log now."


def test_export_without_a_checkout_refuses_a_repository_link(
    corpus_root: Path, tmp_path: Path
) -> None:
    repo = _repo(tmp_path)
    record = _author_in(
        corpus_root, repo, notes="n", links=[ArtifactLink(path="src/app.py")], context=["src/app.py"]
    )
    with pytest.raises(transfer.TransferError, match="export-checkout-required"):
        _ = transfer.export_bundle(record, checkout=None)


def test_import_skips_links_this_machine_cannot_digest(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    other_work = storage.WorkStore.open("gamma", corpus_root=corpus_root)
    _ = commit.commit(
        WheypointDelta(
            work_id="gamma",
            expected_revision_id=commit.GENESIS_PARENT,
            orientation="Gamma.",
            working_context=[],
            notes="g",
            next_action=NextAction(move=NextMove.HOLD, orientation="Wait."),
            session_provenance=CAPTURED,
        ),
        store=other_work,
        artifact_root=repo,
    )
    _ = _author_in(
        corpus_root,
        repo,
        notes="n",
        links=[
            ArtifactLink(path="src/app.py"),
            ArtifactLink(path="gamma", ref="wheypoint:paulnsorensen-easy-cheese/gamma"),
            ArtifactLink(path="spec", ref=PUBLIC),
        ],
        context=["src/app.py"],
    )
    out, _payload = _export(tmp_path, "--workspace-root", str(repo))
    other = _other_machine(tmp_path, monkeypatch)
    empty = tmp_path / "importer-repo"
    empty.mkdir()
    status, payload = _import(out, "--as", "beta", "--workspace-root", str(empty))
    assert status == 0
    imported = storage.WorkStore.open("beta", corpus_root=other).read_record()
    assert imported is not None
    assert [link.ref for link in imported.artifact_links] == [PUBLIC]
    warnings = cast("list[str]", payload_at(payload, "warnings"))
    assert sorted(w.split(":")[0] for w in warnings) == ["skipped-unresolvable-link"] * 2


def _forge(bundle: dict[str, object], **changes: object) -> dict[str, object]:
    forged = {k: v for k, v in bundle.items() if k != "bundle_digest"}
    forged.update(changes)
    forged["bundle_digest"] = canonical.digest_value(forged)
    return forged


def _import_forged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forged: dict[str, object]
) -> dict[str, object]:
    path = tmp_path / "forged.json"
    _ = path.write_bytes(canonical.canonical_bytes(forged))
    other = _other_machine(tmp_path, monkeypatch)
    status, payload = _import(path)
    assert status == 1
    assert not (other / "work").exists()
    return payload


def test_import_refuses_an_origin_that_names_another_record(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path)[0])
    origin = {**cast(dict[str, object], bundle["origin"]), "work_id": "other"}
    payload = _import_forged(tmp_path, monkeypatch, _forge(bundle, origin=origin))
    assert payload_at(payload, "error", "code") == "bundle-digest-mismatch"


def test_import_refuses_projection_identifiers_that_name_another_record(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path)[0])
    markdown = cast(str, bundle["projection"]).replace(
        cast(str, bundle["record_digest"]), "sha256:" + "1" * 64
    )
    forged = _forge(bundle, projection=markdown, projection_digest=canonical.digest_text(markdown))
    payload = _import_forged(tmp_path, monkeypatch, forged)
    assert payload_at(payload, "error", "code") == "bundle-digest-mismatch"
    assert "projection identifiers" in cast(str, payload_at(payload, "error", "message"))


@pytest.mark.parametrize(
    "change",
    [
        {"bundle_version": True},
        {"included": {"operator": 1, "local": False}},
    ],
)
def test_import_refuses_loosely_typed_fields(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: dict[str, object]
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path)[0])
    payload = _import_forged(tmp_path, monkeypatch, _forge(bundle, **change))
    assert payload_at(payload, "error", "code") == "bundle-invalid"


@pytest.mark.parametrize(
    "origin_change",
    [{"revision_number": True}, {"revision_number": 9}, {"record_digest": "nope"}],
)
def test_import_refuses_a_malformed_origin(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin_change: dict[str, object]
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path)[0])
    origin = {**cast(dict[str, object], bundle["origin"]), **origin_change}
    payload = _import_forged(tmp_path, monkeypatch, _forge(bundle, origin=origin))
    assert payload_at(payload, "error", "code") == "bundle-invalid"


def test_import_refuses_an_included_flag_the_record_contradicts(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path, "--include-operator")[0])
    payload = _import_forged(
        tmp_path, monkeypatch, _forge(bundle, included={"operator": False, "local": False})
    )
    assert payload_at(payload, "error", "code") == "bundle-invalid"


def test_import_refuses_a_deeply_nested_bundle_as_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deep = tmp_path / "deep.json"
    _ = deep.write_bytes(b"[" * 200_000)
    _ = _other_machine(tmp_path, monkeypatch)
    status, payload = _import(deep)
    assert status == 1
    assert payload_at(payload, "error", "code") == "bundle-invalid"


def test_refused_import_creates_no_note_directory(
    corpus_root: Path, tmp_path: Path
) -> None:
    _ = _author(corpus_root)
    out, _payload = _export(tmp_path)
    notes = tmp_path / "notes-dir"
    status, payload = run_cli(["import", str(out), "--as", "../escape", "--note-dir", str(notes)])
    assert (status, payload_at(payload, "error", "code")) == (1, "invalid-slug")
    status, payload = run_cli(["import", str(out), "--note-dir", str(notes)])
    assert (status, payload_at(payload, "error", "code")) == (1, "import-exists")
    assert not notes.exists()


def test_import_writes_the_mirror_without_no_note(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    out, _payload = _export(tmp_path)
    _ = _other_machine(tmp_path, monkeypatch)
    notes = tmp_path / "notes-dir"
    status, payload = run_cli(["import", str(out), "--as", "beta", "--note-dir", str(notes)])
    assert status == 0
    mirror = notes / "beta.md"
    assert payload_at(payload, "note_path") == str(mirror)
    assert "Build it." in mirror.read_text(encoding="utf-8")


def test_import_reproduces_the_drift_marker_of_the_source_projection(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _author(corpus_root)
    _ = commit.commit(
        WheypointDelta(
            work_id="alpha",
            expected_revision_id=source.revision_id,
            session_provenance=CAPTURED,
            add_decisions=[ProposedEntry(kind=EntryKind.DECISION, summary="Change course.")],
        ),
        store=storage.WorkStore.open("alpha", corpus_root=corpus_root),
    )
    out, _payload = _export(tmp_path)
    bundle_projection = cast(str, _bundle(out)["projection"])
    marker = [m for m in _section(bundle_projection, "## Notes") if m.startswith("> notes may be stale")]
    assert len(marker) == 1
    other = _other_machine(tmp_path, monkeypatch)
    status, _imported = _import(out, "--as", "beta")
    assert status == 0
    resolution = resolve_mod.resolve("beta", corpus_root=other, project_key="bob-project")
    assert resolution.record is not None
    _, markdown = projection.build_projection(
        resolution.record, durability=Durability.CANONICAL_LOCAL
    )
    imported = [m for m in _section(markdown, "## Notes") if m.startswith("> notes may be stale")]
    assert imported == ["> notes may be stale: decisions changed at revision 1, notes written at unstamped"]
    record = resolution.record
    assert (record.notes_revision_number, record.decisions_revision_number) == (None, 1)
    assert record.revision_number == 1


def _author_tasks(corpus_root: Path) -> WheypointRecord:
    return commit.commit(
        WheypointDelta(
            work_id="alpha",
            expected_revision_id=commit.GENESIS_PARENT,
            orientation="Alpha work.",
            working_context=[],
            notes="n",
            next_action=NextAction(
                move=NextMove.TASKS,
                orientation="Fan out.",
                tasks=[
                    HandoffTask(
                        slug="one",
                        intent="Do it in /home/alice/secret-plan",
                        repo="/home/alice/repo",
                        branch="b",
                        branch_from="main",
                        command="/cook --spec /home/alice/spec.md",
                        worktree="/home/alice/wt",
                    )
                ],
                parallel=ParallelPlan(
                    isolation="worktree",
                    worktree_strategy=WorktreeStrategy.CREATE,
                    worktree_root="/home/alice/wts",
                ),
            ),
            session_provenance=CAPTURED,
        ),
        store=storage.WorkStore.open("alpha", corpus_root=corpus_root),
    ).record


def test_default_export_omits_tasks_and_parallel(corpus_root: Path, tmp_path: Path) -> None:
    _ = _author_tasks(corpus_root)
    bundle = _bundle(_export(tmp_path)[0])
    exported = records.structure(bundle["record"], WheypointRecord)
    assert exported.next_action.tasks is None
    assert exported.next_action.parallel is None
    assert exported.next_action.move is NextMove.HOLD
    assert "/home/alice" not in json.dumps(bundle)
    assert bundle["included"] == {"operator": False, "local": False}


def test_include_local_export_keeps_tasks_and_parallel(
    corpus_root: Path, tmp_path: Path
) -> None:
    _ = _author_tasks(corpus_root)
    bundle = _bundle(_export(tmp_path, "--include-local")[0])
    exported = records.structure(bundle["record"], WheypointRecord)
    assert exported.next_action.move is NextMove.TASKS
    assert [t.slug for t in exported.next_action.tasks or []] == ["one"]
    assert exported.next_action.parallel is not None


def test_import_refuses_tasks_when_the_bundle_says_local_was_dropped(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author_tasks(corpus_root)
    bundle = _bundle(_export(tmp_path, "--include-local")[0])
    forged = _forge(bundle, included={"operator": False, "local": False})
    payload = _import_forged(tmp_path, monkeypatch, forged)
    assert payload_at(payload, "error", "code") == "bundle-invalid"


def test_export_fails_closed_when_check_ignore_fails(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    _ = _author_in(
        corpus_root,
        repo,
        notes="Read scratch.log now.",
        links=[ArtifactLink(path="src/app.py"), ArtifactLink(path="scratch.log")],
        context=["src/app.py", "scratch.log"],
    )

    def broken(_candidates: list[str], _checkout: Path) -> set[str]:
        raise projection.CheckIgnoreError("git unavailable")

    monkeypatch.setattr(projection, "_ignored", broken)
    bundle = _bundle(_export(tmp_path, "--workspace-root", str(repo))[0])
    exported = records.structure(bundle["record"], WheypointRecord)
    assert exported.artifact_links == []
    assert exported.working_context == []
    assert not [e for e in exported.edges if e.kind.value != "forked_from"]
    assert "scratch.log" not in json.dumps(bundle)


def test_export_scrubs_an_absolute_path_that_does_not_exist(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _repo(tmp_path)
    _ = _author_in(
        corpus_root,
        repo,
        notes="See /home/alice/private/notes.md today.",
        links=[],
        context=["/home/alice/private/ctx.md"],
    )
    out, _payload = _export(tmp_path, "--workspace-root", str(repo))
    bundle = _bundle(out)
    assert "/home/alice" not in json.dumps(bundle)
    assert cast(dict[str, object], bundle["record"])["notes"] == (
        f"See {transfer.LOCAL_MARKER} today."
    )
    _ = _other_machine(tmp_path, monkeypatch)
    status, _imported = _import(out, "--as", "beta")
    assert status == 0


def test_import_refuses_a_credential_and_writes_nothing(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = commit.commit(
        WheypointDelta(
            work_id="alpha",
            expected_revision_id=commit.GENESIS_PARENT,
            orientation="Alpha work.",
            working_context=[],
            notes="deploy with password: hunter2hunter2hunter2",
            next_action=NextAction(move=NextMove.HOLD, orientation="Wait."),
            session_provenance=CAPTURED,
        ),
        store=storage.WorkStore.open("alpha", corpus_root=corpus_root),
    )
    out, _payload = _export(tmp_path)
    other = _other_machine(tmp_path, monkeypatch)
    status, payload = _import(out, "--as", "beta")
    assert status == 1
    assert payload_at(payload, "error", "code") == "secret-pattern"
    assert not (other / "work").exists()


def test_import_refuses_a_forged_origin_record_digest_as_a_digest_mismatch(
    corpus_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = _author(corpus_root)
    bundle = _bundle(_export(tmp_path, "--include-operator", "--include-local")[0])
    origin = {**cast(dict[str, object], bundle["origin"]), "record_digest": "sha256:" + "2" * 64}
    payload = _import_forged(tmp_path, monkeypatch, _forge(bundle, origin=origin))
    assert payload_at(payload, "error", "code") == "bundle-digest-mismatch"
