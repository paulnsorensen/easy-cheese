"""Move one record between people as a single canonical JSON bundle.

`export_bundle` freezes the current record into a bundle. `import_bundle`
verifies a bundle and writes it as the genesis of a fork child.

The bundle is one canonical JSON object (`canonical.canonical_bytes`):

* `record` and `projection`: the exported record, and its rendered projection;
* `record_digest`: the digest of the *exported* record;
* `projection_digest`: the digest of the projection text;
* `origin`: the source project, work id, revision id, and the digest of the
  unfiltered source record;
* `included`: which filtered kinds the author chose to keep;
* `bundle_digest`: the digest of the canonical bundle without this field.

Export drops operator-scope directives and local references unless asked. A
filtered record no longer matches the source digest, so `record_digest` covers
the record as exported and `origin` carries the source revision and digest
separately. A digest proves integrity, not authorship: whoever holds a bundle
can recompute every digest in it.

Import never trusts the bundle. It bounds the size, structures the record
against the schema, checks every digest, and writes nothing on any mismatch.
The child carries the record's orientation, next action, notes, working
context, artifact links, and active entries, plus one `forked_from` edge to
`wheypoint:<origin-project>/<work_id>@<revision_id>`. The origin project need
not exist on this machine: the edge is external lineage.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import attrs
from easy_cheese_schemas import (
    LOWER_IDENTIFIER_RE,
    ArtifactLink,
    Durability,
    EntryKind,
    EntryState,
    ProposedEntry,
    ProtectedEntry,
    RepositoryProvenance,
    SessionProvenance,
    WheypointDelta,
    WheypointRecord,
)
from easy_cheese_schemas.contracts import DirectiveScope, EdgeKind, WorkEdge

from . import canonical, commit, projection, records, storage

__all__ = [
    "BUNDLE_VERSION",
    "MAX_BUNDLE_BYTES",
    "TransferError",
    "export_bundle",
    "import_bundle",
    "parse_bundle",
]

BUNDLE_VERSION = 1
MAX_BUNDLE_BYTES = 4 * 1024 * 1024
_BUNDLE_KEYS = frozenset(
    {
        "bundle_version",
        "origin",
        "included",
        "record",
        "record_digest",
        "projection",
        "projection_digest",
        "bundle_digest",
    }
)
_ORIGIN_KEYS = frozenset({"project_key", "work_id", "revision_id", "revision_number", "record_digest"})
_INCLUDED_KEYS = frozenset({"operator", "local"})


class TransferError(ValueError):
    """The bundle cannot be made or taken. The message starts with a `code:` prefix."""


def _link_text(link: ArtifactLink) -> str:
    ref = link.ref
    return link.path if ref is None or ref.startswith("repo:") else ref


def _filtered(
    record: WheypointRecord, *, include_operator: bool, include_local: bool
) -> WheypointRecord:
    out = record
    if not include_operator:
        out = attrs.evolve(
            out,
            directives=[e for e in out.directives if e.scope is not DirectiveScope.OPERATOR],
        )
    if not include_local:
        local = projection.local_references(out)
        out = attrs.evolve(
            out,
            artifact_links=[a for a in out.artifact_links if _link_text(a) not in local],
            edges=tuple(e for e in out.edges if e.to not in local),
            working_context=[
                item for item in out.working_context if not any(t in item for t in local)
            ],
        )
    return out


def export_bundle(
    record: WheypointRecord, *, include_operator: bool = False, include_local: bool = False
) -> dict[str, object]:
    """The bundle for `record`, with its record, projection, and bundle digests."""
    exported = _filtered(
        record, include_operator=include_operator, include_local=include_local
    )
    _, markdown = projection.build_projection(
        exported, durability=Durability.CANONICAL_LOCAL
    )
    body: dict[str, object] = {
        "bundle_version": BUNDLE_VERSION,
        "origin": {
            "project_key": record.project_key,
            "work_id": record.work_id,
            "revision_id": record.revision_id,
            "revision_number": record.revision_number,
            "record_digest": records.record_digest(record),
        },
        "included": {"operator": include_operator, "local": include_local},
        "record": records.unstructure(exported),
        "record_digest": records.record_digest(exported),
        "projection": markdown,
        "projection_digest": canonical.digest_text(markdown),
    }
    return {**body, "bundle_digest": canonical.digest_value(body)}


def _invalid(detail: str) -> TransferError:
    return TransferError(f"bundle-invalid: {detail}")


def _mismatch(what: str) -> TransferError:
    return TransferError(f"bundle-digest-mismatch: the {what} does not match its digest")


def _object(value: object, what: str, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _invalid(f"{what} must be a JSON object")
    found = cast("dict[str, object]", value)
    if frozenset(found) != keys:
        raise _invalid(f"{what} must hold exactly {', '.join(sorted(keys))}")
    return found


def _text(bundle: dict[str, object], key: str) -> str:
    value = bundle[key]
    if not isinstance(value, str):
        raise _invalid(f"{key} must be a string")
    return value


def parse_bundle(raw: bytes) -> tuple[WheypointRecord, dict[str, object]]:
    """The verified record and origin of a bundle; raises before anything is written."""
    if len(raw) > MAX_BUNDLE_BYTES:
        raise _invalid(f"the bundle is larger than {MAX_BUNDLE_BYTES} bytes")
    try:
        loaded = cast(object, json.loads(raw))
    except ValueError as exc:
        raise _invalid(f"the bundle is not JSON: {exc}") from exc
    bundle = _object(loaded, "the bundle", _BUNDLE_KEYS)
    if bundle["bundle_version"] != BUNDLE_VERSION:
        raise _invalid(f"bundle_version must be {BUNDLE_VERSION}")
    origin = _object(bundle["origin"], "origin", _ORIGIN_KEYS)
    _ = _object(bundle["included"], "included", _INCLUDED_KEYS)
    body = {key: value for key, value in bundle.items() if key != "bundle_digest"}
    try:
        bundle_ok = canonical.digest_value(body) == bundle["bundle_digest"]
    except canonical.CanonicalJsonError as exc:
        raise _invalid(str(exc)) from exc
    if not bundle_ok:
        raise _mismatch("bundle")
    try:
        record = records.structure(bundle["record"], WheypointRecord, forbid_unknown=True)
    except records.RecordError as exc:
        raise _invalid(str(exc)) from exc
    markdown = _text(bundle, "projection")
    if records.record_digest(record) != bundle["record_digest"]:
        raise _mismatch("record")
    if canonical.digest_text(markdown) != bundle["projection_digest"]:
        raise _mismatch("projection")
    try:
        parsed = projection.parse(markdown)
    except projection.ProjectionParseError as exc:
        raise _invalid(f"the projection cannot be read: {exc}") from exc
    if (
        parsed.record_digest != bundle["record_digest"]
        or parsed.work_id != record.work_id
        or parsed.revision_id != record.revision_id
    ):
        raise _mismatch("projection identifiers")
    if (
        origin["work_id"] != record.work_id
        or origin["revision_id"] != record.revision_id
        or origin["project_key"] != record.project_key
    ):
        raise _invalid("origin does not name the bundle record")
    return record, origin


def _proposed(entry: ProtectedEntry) -> ProposedEntry:
    return ProposedEntry(
        kind=entry.kind,
        summary=entry.summary,
        blocks_continuation=entry.blocks_continuation,
        rationale=entry.rationale,
        quote=entry.quote,
        owner=entry.owner,
        when=entry.when,
        scope=entry.scope,
    )


def _active(record: WheypointRecord, kind: EntryKind) -> list[ProposedEntry]:
    return [
        _proposed(e)
        for e in records.entries(record)
        if e.kind is kind and e.state is EntryState.ACTIVE
    ]


def import_bundle(
    raw: bytes,
    *,
    slug: str | None,
    corpus_root: Path,
    session_provenance: SessionProvenance,
    repository: RepositoryProvenance | None = None,
    durability: Durability = Durability.CANONICAL_LOCAL,
    finalize: Callable[[commit.PendingRevision], None] | None = None,
) -> tuple[commit.CommitResult, list[str]]:
    """Verify `raw` and write its record as a fork-child genesis named `slug`.

    `slug` defaults to the bundle record's work id. A name that is not a lower
    identifier, or that already holds a record, is refused. An artifact link
    that is local on this machine cannot be digested here, so it is skipped and
    returned beside the result.
    """
    record, origin = parse_bundle(raw)
    name = record.work_id if slug is None else slug
    if LOWER_IDENTIFIER_RE.fullmatch(name) is None:
        raise TransferError(f"invalid-slug: {name!r} is not a lower-case identifier")
    try:
        target = storage.WorkStore.open(name, corpus_root=corpus_root)
    except storage.StorageError as exc:
        raise TransferError(f"invalid-slug: {exc}") from exc
    if target.record_path.exists() or any(target.revisions_dir.glob("*.json")):
        raise TransferError(f"import-exists: work {name!r} already has a record or history")
    source = f"wheypoint:{origin['project_key']}/{origin['work_id']}@{origin['revision_id']}"
    local = projection.local_references(record)
    kept = [a for a in record.artifact_links if _link_text(a) not in local]
    skipped = [a for a in record.artifact_links if _link_text(a) in local]
    delta = WheypointDelta(
        work_id=name,
        expected_revision_id=commit.GENESIS_PARENT,
        orientation=record.orientation,
        working_context=list(record.working_context),
        notes=record.notes,
        next_action=record.next_action,
        add_decisions=_active(record, EntryKind.DECISION) or None,
        add_questions=_active(record, EntryKind.QUESTION) or None,
        add_directives=_active(record, EntryKind.DIRECTIVE) or None,
        add_artifact_links=[ArtifactLink(path=a.path, ref=a.ref) for a in kept] or None,
        session_provenance=session_provenance,
    )
    result = commit.commit(
        delta,
        store=target,
        repository=repository,
        durability=durability,
        fork_edge=WorkEdge(to=source, kind=EdgeKind.FORKED_FROM),
        finalize=finalize,
    )
    return result, [_link_text(a) for a in skipped]
