"""Export and import: one canonical bundle, verified, written as a fork child."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    Durability,
    EntryKind,
    NextAction,
    NextMove,
    ProposedEntry,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import DirectiveScope

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
